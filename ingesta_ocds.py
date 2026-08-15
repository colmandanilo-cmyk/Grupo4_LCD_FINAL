"""
ingesta_ocds.py — Fuente 1: descarga masiva OCDS/SEACE y normalización.

Aporta la demanda histórica del Estado: qué compró, por cuánto, qué entidad
y bajo qué categoría CUBSO. Es la base del ranking de oportunidad.

Evidencia de la rúbrica:
  1. Extracción y normalización de respuestas JSON → registros tabulares.
  2. Almacenamiento en formato optimizado (Parquet, compresión snappy).
  3. Automatización y registro de actividades (CLI + logging por corrida).
  4. Manejo de restricciones: descarga en streaming con reintentos, timeout
     y User-Agent identificado; procesamiento línea a línea para no cargar
     el archivo completo en memoria.

CAMBIO EN LA TRAZABILIDAD (revisión T1)
---------------------------------------
El log registra solo eventos del proceso (inicio y fin de etapa, estado,
reintentos, errores, archivos escritos). Todo conteo o métrica se escribe en
reports/, separado de la trazabilidad.

Uso:
    python ingesta_ocds.py                 # descarga los años de config.py
    python ingesta_ocds.py --anios 2025    # sobreescribe el periodo
    python ingesta_ocds.py --demo          # datos sintéticos (sin red)
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

import config
from utils import Cronometro, Reporte, bytes_legibles, crear_logger

log = crear_logger("ingesta_ocds")

CHUNK_DESCARGA = 1024 * 512  # 512 KB por bloque de streaming
FLUSH_CADA = 50_000          # registros acumulados antes de volcar a un lote
N_PROCESOS_DEMO = 6_000      # procesos sintéticos por año en modo demo


# ---------------------------------------------------------------------------
# 1. Descarga masiva (streaming, idempotente, con reintentos)
# ---------------------------------------------------------------------------
def descargar_anio(anio: int, reporte: Reporte, refrescar: bool = False) -> Path:
    """Descarga el .jsonl.gz de un año, con reintentos y backoff exponencial.

    La descarga es en streaming: el archivo se escribe por bloques sin
    cargarlo completo en memoria (superan los 100 MB). Si el archivo ya
    existe en data/raw/ se reutiliza, lo que hace la ingesta idempotente.

    Excepción: el AÑO EN CURSO cambia día a día (se publican procesos nuevos).
    Con refrescar=True, ese año se vuelve a descargar aunque ya exista, para
    que una corrida diaria efectivamente actualice los datos. Los años
    cerrados (anteriores al actual) nunca se re-descargan: ya no cambian.
    """
    destino = config.RAW_DIR / f"ocds_{anio}.jsonl.gz"
    anio_actual = datetime.now().year
    es_anio_en_curso = anio == anio_actual
    debe_refrescar = refrescar and es_anio_en_curso

    if destino.exists() and destino.stat().st_size > 0 and not debe_refrescar:
        log.info("Archivo ya presente | anio=%s | se reutiliza (idempotencia)", anio)
        reporte.metrica(f"descarga_{anio}", "reutilizado")
        return destino

    if debe_refrescar and destino.exists():
        log.info("Refresco del año en curso | anio=%s | se vuelve a descargar", anio)

    url = config.OCDS_DOWNLOAD_URL.format(anio=anio)
    for intento in range(1, config.MAX_REINTENTOS + 1):
        try:
            log.info("Descarga solicitada | anio=%s | intento=%d/%d",
                     anio, intento, config.MAX_REINTENTOS)
            with requests.get(
                url, stream=True, timeout=config.HTTP_TIMEOUT,
                headers={"User-Agent": config.HTTP_HEADERS["User-Agent"]},
            ) as r:
                r.raise_for_status()
                total = 0
                with open(destino, "wb") as f:
                    for bloque in r.iter_content(chunk_size=CHUNK_DESCARGA):
                        f.write(bloque)
                        total += len(bloque)
                log.info("Descarga finalizada | anio=%s | estado=EXITO", anio)
                reporte.metrica(f"descarga_{anio}_bytes", total)
                reporte.metrica(f"descarga_{anio}_tamanio", bytes_legibles(total))
                return destino
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as exc:
            destino.unlink(missing_ok=True)  # no dejar archivos parciales
            if intento == config.MAX_REINTENTOS:
                break
            espera = config.BACKOFF_BASE ** intento + random.uniform(0, 1)
            log.warning("Fallo de descarga | anio=%s | tipo=%s | backoff=%.1fs",
                        anio, type(exc).__name__, espera)
            time.sleep(espera)

    log.error("Descarga agotó reintentos | anio=%s | estado=ERROR", anio)
    raise RuntimeError(f"No se pudo descargar el año {anio} tras "
                       f"{config.MAX_REINTENTOS} intentos.")


# ---------------------------------------------------------------------------
# 2. Extracción y normalización del JSON OCDS
# ---------------------------------------------------------------------------
def extraer_registro(release: dict) -> list[dict]:
    """Convierte un release compilado OCDS en filas tabulares normalizadas.

    Cada proceso puede tener varias adjudicaciones (awards) y cada award
    varios ítems con clasificación CUBSO; se emite una fila por ítem
    adjudicado, que es el grano necesario para agregar demanda por categoría.
    """
    filas = []
    ocid = release.get("ocid")
    fecha = release.get("date")
    buyer = (release.get("buyer") or {}).get("name")
    tender = release.get("tender") or {}
    metodo = tender.get("procurementMethodDetails")
    categoria_tender = tender.get("mainProcurementCategory")

    for award in release.get("awards") or []:
        valor = award.get("value") or {}
        proveedores = award.get("suppliers") or []
        prov = proveedores[0] if proveedores else {}
        for item in award.get("items") or [{}]:
            clasif = item.get("classification") or {}
            filas.append({
                "ocid": ocid,
                "fecha": fecha,
                "entidad": buyer,
                "metodo_contratacion": metodo,
                "tipo_objeto": categoria_tender,
                "cubso_id": clasif.get("id"),
                "cubso_descripcion": clasif.get("description"),
                "descripcion_item": item.get("description"),
                "monto_adjudicado": valor.get("amount"),
                "moneda": valor.get("currency"),
                "estado_award": award.get("status"),
                "proveedor_id": prov.get("id"),
                "proveedor_nombre": prov.get("name"),
                "n_proveedores_award": len(proveedores),
            })
    return filas


def normalizar_anio(ruta_gz: Path, anio: int, reporte: Reporte) -> pd.DataFrame:
    """Lee el .jsonl.gz línea a línea y devuelve un DataFrame normalizado.

    El procesamiento por línea mantiene el uso de memoria acotado sin
    importar el tamaño del archivo. Las líneas malformadas se contabilizan y
    se descartan sin detener la corrida.
    """
    registros, lotes = [], []
    lineas, errores = 0, 0

    with gzip.open(ruta_gz, "rt", encoding="utf-8") as f:
        for linea in f:
            lineas += 1
            try:
                release = json.loads(linea)
            except json.JSONDecodeError:
                errores += 1
                continue
            registros.extend(extraer_registro(release))
            if len(registros) >= FLUSH_CADA:
                lotes.append(pd.DataFrame(registros))
                registros = []

    if registros:
        lotes.append(pd.DataFrame(registros))

    df = pd.concat(lotes, ignore_index=True) if lotes else pd.DataFrame()

    if errores:
        log.warning("Lineas malformadas descartadas | anio=%s", anio)
    log.info("Normalizacion finalizada | anio=%s | estado=EXITO", anio)

    reporte.seccion(f"normalizacion_{anio}", {
        "lineas_leidas": lineas,
        "lineas_malformadas": errores,
        "filas_item_award": int(len(df)),
    })

    if df.empty:
        return df

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True)
    df["anio"] = df["fecha"].dt.year.astype("Int16")
    df["monto_adjudicado"] = pd.to_numeric(df["monto_adjudicado"], errors="coerce")
    df["cubso_id"] = df["cubso_id"].astype("string").str.strip()
    df["proveedor_id"] = df["proveedor_id"].astype("string").str.strip()
    df["cubso_descripcion"] = (
        df["cubso_descripcion"].astype("string").str.strip().str.upper()
    )
    for col in ("entidad", "metodo_contratacion", "tipo_objeto", "moneda",
                "estado_award"):
        df[col] = df[col].astype("category")
    return df


# ---------------------------------------------------------------------------
# 3. Persistencia optimizada + agregado de demanda
# ---------------------------------------------------------------------------
def persistir(df: pd.DataFrame, reporte: Reporte) -> None:
    """Guarda el detalle normalizado y el agregado de demanda en Parquet."""
    df.to_parquet(config.PARQUET_OCDS, engine="pyarrow",
                  compression="snappy", index=False)
    log.info("Archivo escrito | %s", config.PARQUET_OCDS.name)
    reporte.metrica("filas_detalle", int(len(df)))
    reporte.metrica("tamanio_detalle",
                    bytes_legibles(config.PARQUET_OCDS.stat().st_size))

    validos = df.dropna(subset=["cubso_descripcion", "monto_adjudicado"])
    demanda = (
        validos.groupby("cubso_descripcion", as_index=False, observed=True)
        .agg(demanda_soles=("monto_adjudicado", "sum"),
             n_procesos=("ocid", "nunique"))
        .sort_values("demanda_soles", ascending=False)
    )
    demanda.to_parquet(config.PARQUET_DEMANDA, engine="pyarrow",
                       compression="snappy", index=False)
    log.info("Archivo escrito | %s", config.PARQUET_DEMANDA.name)
    reporte.metrica("categorias_cubso", int(len(demanda)))


# ---------------------------------------------------------------------------
# Modo demo (sin red)
# ---------------------------------------------------------------------------
# Categorías ancla del modo demo. Son reales (existen en el CUBSO) y las tres
# primeras son de alimentación, que es el rubro del caso que se narra en la
# sustentación. El resto del catálogo se genera sintéticamente alrededor.
CATEGORIAS_DEMO = [
    # (id, descripción, familia, proveedores en el pool, peso de demanda)
    ("501015", "SERVICIO DE ALIMENTACION Y NUTRICION HOSPITALARIA", "ALIMENTOS", 40, 6.0),
    ("501020", "SERVICIO DE ALIMENTACION PARA EVENTOS VARIOS", "ALIMENTOS", 25, 2.0),
    ("501025", "SERVICIO DE PREPARACION Y REPARTO DE ALMUERZOS", "ALIMENTOS", 6, 1.2),
    ("501030", "SUMINISTRO DE VIVERES SECOS Y ABARROTES", "ALIMENTOS", 12, 1.6),
    ("501035", "SUMINISTRO DE FRUTAS Y VERDURAS FRESCAS", "ALIMENTOS", 9, 0.9),
    ("921215", "SERVICIO DE SEGURIDAD Y VIGILANCIA", "SERVICIOS", 30, 4.0),
    ("921220", "SERVICIO DE LIMPIEZA DE LOCALES", "SERVICIOS", 22, 2.4),
    ("432115", "EQUIPOS DE COMPUTO PERSONAL", "BIENES", 8, 3.0),
    ("531015", "UNIFORMES Y PRENDAS DE VESTIR INSTITUCIONALES", "BIENES", 14, 1.1),
    ("511015", "MEDICAMENTOS DE USO HUMANO", "BIENES", 35, 12.0),
    ("151015", "COMBUSTIBLE DIESEL B5", "BIENES", 11, 9.0),
    ("721015", "EJECUCION DE OBRA DE INFRAESTRUCTURA VIAL", "OBRAS", 18, 20.0),
]

# Objetos genéricos con los que se fabrica la cola larga: categorías chicas,
# que son la mayoría del catálogo real y las que el índice tiene que ordenar.
OBJETOS_COLA = [
    "SERVICIO DE MANTENIMIENTO DE", "SUMINISTRO DE", "ALQUILER DE",
    "SERVICIO DE CAPACITACION EN", "ADQUISICION DE", "SERVICIO DE IMPRESION DE",
]
COMPLEMENTOS_COLA = [
    "EQUIPOS DE OFICINA", "MOBILIARIO ESCOLAR", "MATERIAL DE LIMPIEZA",
    "REPUESTOS AUTOMOTRICES", "UTILES DE ESCRITORIO", "EQUIPOS DE AIRE ACONDICIONADO",
    "SEÑALIZACION VIAL", "MATERIAL DE LABORATORIO", "SOFTWARE OFIMATICO",
    "SERVICIOS DE MENSAJERIA", "TEXTILES HOSPITALARIOS", "HERRAMIENTAS MANUALES",
    "EQUIPOS DE PROTECCION PERSONAL", "MATERIAL BIBLIOGRAFICO", "GRUPOS ELECTROGENOS",
]

# Estacionalidad: el gasto público peruano no es plano. Se concentra en el
# último trimestre por el cierre presupuestal y cae en enero-febrero.
PESO_MES = [0.4, 0.5, 0.8, 1.0, 1.0, 1.1, 1.0, 1.0, 1.1, 1.4, 1.8, 2.2]


def _catalogo_demo(rng: random.Random) -> list[tuple]:
    """Arma el catálogo del modo demo: anclas reales + cola larga sintética."""
    catalogo = list(CATEGORIAS_DEMO)
    for i in range(78):
        objeto = rng.choice(OBJETOS_COLA)
        complemento = rng.choice(COMPLEMENTOS_COLA)
        catalogo.append((
            f"9{i:05d}",
            f"{objeto} {complemento} - LOTE {i:02d}",
            rng.choice(["BIENES", "SERVICIOS"]),
            rng.randint(1, 12),          # pool de proveedores chico
            rng.lognormvariate(-1.2, 0.9),  # peso de demanda: cola larga
        ))
    return catalogo


def generar_demo(anio: int) -> Path:
    """Fabrica un .jsonl.gz con la estructura real de OCDS y una distribución
    de demanda comparable a la real.

    POR QUÉ NO ES UNIFORME
    ----------------------
    La versión anterior repartía 300 procesos entre cinco categorías con montos
    sacados de una uniforme. El resultado era un catálogo donde todas las
    categorías demandaban más o menos lo mismo, y sobre eso ni el binning ni el
    escalado tienen nada que mostrar: cualquier normalización devuelve el mismo
    orden que la columna cruda.

    La demanda pública real tiene cola muy larga (obras, medicamentos y
    combustible concentran órdenes de magnitud más monto que el resto) y
    estacionalidad marcada por el cierre presupuestal de diciembre. El
    generador reproduce las dos cosas con una lognormal por categoría y un peso
    mensual, de modo que el modo demo sirva para demostrar la transformación y
    no solo para probar que el código corre.
    """
    destino = config.RAW_DIR / f"ocds_demo_{anio}.jsonl.gz"
    rng = random.Random(4364 + anio)
    catalogo = _catalogo_demo(rng)
    entidades = ["MINSA", "GOBIERNO REGIONAL DE LIMA",
                 "MUNICIPALIDAD DE SAN ISIDRO", "ESSALUD", "MINEDU",
                 "GOBIERNO REGIONAL DE CUSCO", "PROGRAMA QALI WARMA"]
    metodos = ["Adjudicación Simplificada", "Licitación Pública",
               "Contratación Directa", "Subasta Inversa Electrónica"]

    pesos = [c[4] for c in catalogo]
    meses = list(range(1, 13))

    with gzip.open(destino, "wt", encoding="utf-8") as f:
        for i in range(N_PROCESOS_DEMO):
            cid, cdesc, familia, pool, peso = rng.choices(catalogo, weights=pesos)[0]
            # Monto lognormal escalado por el peso de la categoría: cola larga
            monto = round(rng.lognormvariate(10.2, 1.15) * peso, 2)
            mes = rng.choices(meses, weights=PESO_MES)[0]
            release = {
                "ocid": f"ocds-dgv273-DEMO-{anio}-{i:05d}",
                "date": f"{anio}-{mes:02d}-{rng.randint(1, 28):02d}T00:00:00Z",
                "buyer": {"name": rng.choice(entidades)},
                "tender": {"procurementMethodDetails": rng.choice(metodos),
                           "mainProcurementCategory":
                               "works" if familia == "OBRAS" else
                               "goods" if familia == "BIENES" else "services"},
                "awards": [{
                    "status": "active",
                    "value": {"amount": monto, "currency": "PEN"},
                    "suppliers": [{
                        "id": f"PE-RUC-20{cid}{rng.randint(1, pool):03d}",
                        "name": f"PROVEEDOR DEMO {cid}-{rng.randint(1, pool):03d}",
                    }],
                    "items": [{"classification": {"id": cid, "description": cdesc},
                               "description": f"Ítem demo {i}"}],
                }],
            }
            f.write(json.dumps(release, ensure_ascii=False) + "\n")
    log.info("Archivo demo generado | anio=%s | procesos=%d | categorias=%d",
             anio, N_PROCESOS_DEMO, len(catalogo))
    return destino


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta masiva OCDS/SEACE")
    parser.add_argument("--anios", nargs="*", type=int, default=config.OCDS_ANIOS,
                        help="Años a ingestar (por defecto los de config.py)")
    parser.add_argument("--demo", action="store_true",
                        help="Usa datos sintéticos locales en lugar de descargar")
    parser.add_argument("--refrescar", action="store_true",
                        help="Vuelve a descargar el año en curso aunque ya exista "
                             "(para corridas diarias que deben actualizar datos)")
    args = parser.parse_args()

    log.info("INICIO ingesta OCDS | anios=%s | demo=%s | refrescar=%s",
             args.anios, args.demo, args.refrescar)
    reporte = Reporte("ingesta_ocds")
    reporte.metrica("anios", args.anios)
    reporte.metrica("modo_demo", args.demo)

    frames = []
    with Cronometro(log, "ingesta OCDS completa"):
        for anio in args.anios:
            ruta = (generar_demo(anio) if args.demo
                    else descargar_anio(anio, reporte, refrescar=args.refrescar))
            with Cronometro(log, f"normalizacion {anio}"):
                df = normalizar_anio(ruta, anio, reporte)
            if not df.empty:
                frames.append(df)

        if not frames:
            log.error("Sin registros obtenidos | estado=ERROR")
            reporte.guardar()
            return
        persistir(pd.concat(frames, ignore_index=True), reporte)

    ruta_rep = reporte.guardar()
    log.info("Reporte de metricas escrito | %s", ruta_rep.name)
    log.info("FIN ingesta OCDS | estado=EXITO")


if __name__ == "__main__":
    main()

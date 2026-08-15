"""
ficha_proveedores.py — Fuente 2: habilitación real del proveedor por RUC.

QUÉ CAMBIA Y POR QUÉ IMPORTA
----------------------------
La definición original del proyecto era que la densidad de oferta combinara
dos planos: proveedores ADJUDICADOS (quién ganó, de OCDS) y proveedores
HABILITADOS (quién puede competir, del registro oficial). El contraste entre
ambos —"habilitados vs. adjudicados"— es la justificación de fondo para usar
dos fuentes.

En la primera implementación el capítulo de habilitados quedó como un proxy
por coincidencia de texto sobre un buscador que además devolvía HTTP 403.
Este módulo lo reemplaza por el dato verificado: la Ficha Única del Proveedor
consultada por RUC contra el endpoint

    GET https://eap.oece.gob.pe/perfilprov-bus/1.0/ficha/{RUC}

que responde 200 y entrega, en el bloque `proveedorT01`:

    esHabilitado      -> bool: si el proveedor está habilitado para contratar
    lscIdTipRegVig    -> str : capítulos RNP VIGENTES, como IDs separados por
                              espacio (p. ej. "4 1 2")
    lscIdTipReg       -> str : capítulos inscritos históricos
    esAptoContratar   -> bool
    cmcTexto          -> str : capacidad máxima de contratación (ejecutores)
    espProvT01s       -> list: especialidades (consultores de obras)

Con esto la habilitación deja de ser un proxy textual y pasa a ser el estado
real del proveedor en el RNP. La limitación declarada del proyecto se puede
suavizar en consecuencia.

MAPEO DE CAPÍTULOS  (PENDIENTE DE CONFIRMACIÓN — ver CAPITULOS_RNP)
------------------------------------------------------------------
El RNP administra cuatro capítulos donde un proveedor puede inscribirse:
bienes, servicios, consultor de obras y ejecutor de obras. El endpoint los
entrega como IDs numéricos. Para el proveedor de prueba (RUC 10714515590),
`lscIdTipRegVig` = "4 1 2" coincide con las tres etiquetas visibles en su
ficha web: BIENES, SERVICIOS y CONSULTOR DE OBRAS. Falta un solo dato para
fijar el mapeo con certeza: la respuesta del endpoint `grupos` de la ficha,
que lista los capítulos con su nombre. Hasta confirmarlo, el mapeo de abajo
es la hipótesis más probable y está aislado para cambiarse en un único lugar.

COSTO Y DISEÑO
--------------
El detalle OCDS tiene del orden de 30 000 RUC adjudicatarios únicos. A una
petición por RUC con pausa de cortesía, descargar todo de una vez tomaría
horas. Por eso la consulta es un CACHÉ INCREMENTAL REANUDABLE: cada ficha se
guarda al obtenerse y las corridas siguientes solo piden los RUC que faltan.
Esto reparte el costo entre varias corridas y hace la ingesta idempotente.

Uso:
    python ficha_proveedores.py --limite 500     # primeras 500 fichas faltantes
    python ficha_proveedores.py --limite 0       # todas las faltantes
    python ficha_proveedores.py --rucs 10714515590 20100...  # RUC puntuales
    python ficha_proveedores.py --demo           # fichas sintéticas (sin red)
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

import config
from utils import Cronometro, Reporte, crear_logger

log = crear_logger("ficha_proveedores")

# Caché de fichas: un único JSON {ruc: ficha_normalizada} para que sea fácil
# de versionar y de reanudar.
#
# El modo demo escribe en un archivo APARTE. Compartir el caché entre demo y
# producción parece cómodo hasta que las fichas sintéticas se mezclan con las
# reales: como el demo siempre "responde", esas filas quedan marcadas como
# habilitadas y contaminan el conteo de habilitados por capítulo sin dejar
# rastro evidente. Separarlos hace imposible el accidente.
CACHE = config.CHECKPOINT_DIR / "fichas_proveedores_cache.json"
CACHE_DEMO = config.CHECKPOINT_DIR / "fichas_proveedores_cache_demo.json"
ENDPOINT_FICHA = "https://eap.oece.gob.pe/perfilprov-bus/1.0/ficha/{ruc}"

RUC_VALIDO = re.compile(r"\d{11}")


def normalizar_ruc(identificador: str) -> str | None:
    """Extrae los 11 dígitos del RUC de un identificador OCDS.

    POR QUÉ HACE FALTA
    ------------------
    El OCDS identifica al proveedor con el esquema de organización delante:
    `PE-RUC-20501020023`. El endpoint de la ficha espera solo el número.

    Consultado con el prefijo, el servicio NO devuelve un error: responde
    HTTP 200 con `resultado.codigo = "00"` y un `proveedorT01` vacío. Es el
    peor modo de fallo posible, porque el pipeline lo interpreta como una
    consulta exitosa de un proveedor sin habilitación y guarda esa ficha vacía
    en el caché. El síntoma recién aparece al final: miles de fichas
    descargadas y casi ninguna habilitada.

    Devuelve None si no encuentra un RUC de 11 dígitos, para descartar el
    identificador en vez de consultar una URL que no puede funcionar.
    """
    if not identificador:
        return None
    encontrado = RUC_VALIDO.search(str(identificador))
    return encontrado.group(0) if encontrado else None


def ficha_utilizable(ficha: dict) -> bool:
    """Indica si una ficha trae contenido real del registro.

    Una respuesta con código 00 pero sin razón social ni capítulos no es un
    proveedor sin habilitación: es una consulta que no llegó a buscar nada.
    Distinguirlas evita que el caché acumule respuestas vacías que después se
    cuentan como negativas.
    """
    if not isinstance(ficha, dict):
        return False
    return bool(ficha.get("razon_social")) or bool(ficha.get("ids_capitulos_raw"))

# Fallos consecutivos tras los cuales se corta la corrida. Un RUC que no
# existe falla aislado, entre vecinos que sí responden; cinco seguidos ya no
# son casualidad, es el servidor que dejó de atender. Cortar ahí ahorra una
# hora de backoff inútil y deja el caché listo para retomar.
FALLOS_SEGUIDOS_PARA_CORTAR = 5

# -------------------------------------------------------------------------
# Mapeo de capítulos RNP.  << AJUSTAR AQUÍ cuando se confirme con `grupos` >>
# Hipótesis actual, coherente con el caso de prueba "4 1 2" = B/S/Consultor:
CAPITULOS_RNP = {
    "1": "BIENES",
    "2": "SERVICIOS",
    "3": "EJECUTOR_DE_OBRAS",
    "4": "CONSULTOR_DE_OBRAS",
}
# Nota: si `grupos` revela otro orden, basta reescribir este dict; el resto
# del módulo y del pipeline no cambia.
# -------------------------------------------------------------------------

# Puente CUBSO -> capítulo RNP. El tipo de objeto contractual de una categoría
# CUBSO (bien/servicio/obra/consultoría) determina en qué capítulo debe estar
# habilitado un proveedor para competir en ella.
TIPO_OCDS_A_CAPITULO = {
    "goods": "BIENES",
    "services": "SERVICIOS",
    "works": "EJECUTOR_DE_OBRAS",
    "consultingServices": "CONSULTOR_DE_OBRAS",
}


# ---------------------------------------------------------------------------
# 1. Parseo de la ficha  (única función a tocar si cambia el JSON del endpoint)
# ---------------------------------------------------------------------------
def parsear_ficha(payload: dict, ruc: str) -> dict:
    """Extrae de la respuesta del endpoint los campos de habilitación.

    Aislada a propósito: si el endpoint cambia de forma, este es el único
    lugar a modificar. Todo acceso es defensivo porque el publicador declara
    campos que pueden venir nulos.
    """
    prov = payload.get("proveedorT01") or {}
    resultado = payload.get("resultadoT01") or {}

    # Capítulos vigentes: "4 1 2" -> ["CONSULTOR_DE_OBRAS","BIENES","SERVICIOS"]
    ids_vigentes = str(prov.get("lscIdTipRegVig") or "").split()
    capitulos = sorted({CAPITULOS_RNP.get(i, f"DESCONOCIDO_{i}")
                        for i in ids_vigentes if i})

    return {
        "proveedor_id": ruc,
        "ruc": prov.get("numRuc") or ruc,
        "razon_social": prov.get("nomRzsProv"),
        "es_habilitado": bool(prov.get("esHabilitado")),
        "es_apto_contratar": bool(prov.get("esAptoContratar")),
        "capitulos_vigentes": capitulos,
        "ids_capitulos_raw": prov.get("lscIdTipRegVig"),
        "capacidad_max_contratacion": prov.get("cmcTexto"),
        "n_especialidades": len(prov.get("espProvT01s") or []),
        "tipo_personeria": prov.get("tipoPersoneria"),
        "codigo_respuesta": resultado.get("codigo"),
        "consultado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# 2. Caché incremental reanudable
# ---------------------------------------------------------------------------
def ruta_cache(demo: bool) -> Path:
    """Devuelve el archivo de caché que corresponde al modo de ejecución."""
    return CACHE_DEMO if demo else CACHE


def cargar_cache(demo: bool = False) -> dict:
    """Carga el caché de fichas ya consultadas (RUC -> ficha).

    De paso hace una limpieza que no se puede posponer: descarta las entradas
    cuya clave no sea un RUC de 11 dígitos. Son residuo de la versión que
    consultaba el endpoint con el prefijo `PE-RUC-` del OCDS, y mantenerlas
    haría que esos proveedores nunca se volvieran a consultar, porque el caché
    los da por resueltos.

    La depuración mira la CLAVE y no el contenido a propósito. Una ficha vacía
    con clave válida es información legítima: significa que ese RUC se
    consultó bien y no está inscrito en el RNP. Borrarla obligaría a
    reconsultarlo en cada corrida, para siempre.
    """
    ruta = ruta_cache(demo)
    if not ruta.exists():
        return {}

    with open(ruta, encoding="utf-8") as f:
        crudo = json.load(f)

    cache = {k: v for k, v in crudo.items() if RUC_VALIDO.fullmatch(str(k))}
    descartadas = len(crudo) - len(cache)
    vacias = sum(1 for v in cache.values() if not ficha_utilizable(v))

    log.info("Cache de fichas cargado | validas=%d | sin_registro=%d | "
             "descartadas=%d | modo=%s",
             len(cache), vacias, descartadas, "demo" if demo else "real")
    if descartadas:
        log.warning("Entradas con clave invalida depuradas | esos RUC se "
                    "volveran a consultar | cantidad=%d", descartadas)
    return cache


def guardar_cache(cache: dict, demo: bool = False) -> None:
    """Persiste el caché completo (se llama tras cada bloque de fichas)."""
    with open(ruta_cache(demo), "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def rucs_objetivo(explicitos: list[str] | None) -> list[str]:
    """Determina qué RUC consultar: los indicados, o los adjudicatarios OCDS.

    Si no se pasan RUC explícitos, se toman los proveedores que aparecen como
    adjudicatarios en el detalle OCDS: son exactamente los que hay que
    contrastar contra su habilitación.
    """
    if explicitos:
        normalizados = [normalizar_ruc(r) for r in explicitos]
        return [r for r in normalizados if r]

    if not config.PARQUET_OCDS.exists():
        raise FileNotFoundError(
            "No existe ocds_procesos.parquet y no se pasaron --rucs. "
            "Ejecute ingesta_ocds.py o indique RUC con --rucs."
        )
    detalle = pd.read_parquet(config.PARQUET_OCDS, columns=["proveedor_id"])

    # Extracción vectorizada de los 11 dígitos: el OCDS entrega el proveedor
    # como PE-RUC-20501020023 y el endpoint espera solo el número.
    rucs = (detalle["proveedor_id"].dropna().astype("string")
            .str.extract(r"(\d{11})", expand=False).dropna())
    descartados = len(detalle["proveedor_id"].dropna()) - len(rucs)
    if descartados:
        log.warning("Identificadores sin RUC de 11 digitos | descartados=%d",
                    descartados)
    return rucs.unique().tolist()


# ---------------------------------------------------------------------------
# 3. Descarga de una ficha con reintentos
# ---------------------------------------------------------------------------
def descargar_ficha(sesion: requests.Session, ruc: str) -> dict | None:
    """Descarga y parsea una ficha con backoff exponencial + jitter.

    Devuelve la ficha normalizada, o None si se agotaron los reintentos (el
    RUC quedará pendiente para otra corrida, sin romper el caché).

    El código HTTP se registra en el log porque no todos los fallos significan
    lo mismo: un 429 pide bajar el ritmo y reintentar, un 403 indica bloqueo
    (reintentar solo lo empeora) y un 5xx es un problema del servidor que
    suele resolverse solo. Sin el código, las tres situaciones se ven iguales
    en el log y no hay forma de decidir si conviene esperar o parar.
    """
    url = ENDPOINT_FICHA.format(ruc=ruc)
    for intento in range(1, config.MAX_REINTENTOS + 1):
        codigo = None
        try:
            r = sesion.get(url, headers=config.HTTP_HEADERS,
                           timeout=config.HTTP_TIMEOUT)
            codigo = r.status_code
            if codigo == 429 or codigo >= 500:
                raise requests.HTTPError(f"HTTP {codigo}")
            r.raise_for_status()
            return parsear_ficha(r.json(), ruc)
        except (requests.HTTPError, requests.ConnectionError,
                requests.Timeout, ValueError) as exc:
            if intento == config.MAX_REINTENTOS:
                log.error("Ficha agotó reintentos | tipo=%s | http=%s",
                          type(exc).__name__, codigo)
                break
            espera = config.BACKOFF_BASE ** intento + random.uniform(0, 1)
            log.warning("Fallo de ficha | tipo=%s | http=%s | backoff=%.1fs | "
                        "intento=%d/%d", type(exc).__name__, codigo, espera,
                        intento, config.MAX_REINTENTOS)
            time.sleep(espera)
    return None


def generar_ficha_demo(ruc: str) -> dict:
    """Fabrica una ficha con la estructura real del endpoint (sin red)."""
    rng = random.Random(hash(ruc) & 0xFFFF)
    combos = [["1"], ["2"], ["1", "2"], ["4", "1", "2"], ["3"], ["3", "4"]]
    ids = rng.choice(combos)
    payload = {
        "resultadoT01": {"codigo": "00", "mensaje": "Procesamiento completado."},
        "proveedorT01": {
            "numRuc": ruc,
            "nomRzsProv": f"PROVEEDOR DEMO {ruc[-4:]}",
            "esHabilitado": rng.random() > 0.15,
            "esAptoContratar": rng.random() > 0.1,
            "lscIdTipReg": " ".join(ids),
            "lscIdTipRegVig": " ".join(ids),
            "cmcTexto": None,
            "espProvT01s": [],
            "tipoPersoneria": rng.choice([1, 2]),
        },
    }
    return parsear_ficha(payload, ruc)


# ---------------------------------------------------------------------------
# 4. Orquestación
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Habilitación real de proveedores por RUC (Ficha Única OECE)"
    )
    parser.add_argument("--limite", type=int, default=500,
                        help="Máximo de fichas faltantes a consultar (0 = todas)")
    parser.add_argument("--rucs", nargs="*",
                        help="RUC puntuales a consultar (ignora el detalle OCDS)")
    parser.add_argument("--demo", action="store_true",
                        help="Genera fichas sintéticas (sin red)")
    args = parser.parse_args()

    log.info("INICIO ficha proveedores | limite=%d | demo=%s",
             args.limite, args.demo)
    reporte = Reporte("ficha_proveedores")
    reporte.metrica("modo_demo", args.demo)

    cache = cargar_cache(args.demo)
    objetivos = rucs_objetivo(args.rucs)
    pendientes = [r for r in objetivos if r not in cache]

    # El conteo se hace ANTES de aplicar el límite. Calcularlo después hacía
    # que "en_cache" incluyera a los pendientes que esta corrida no iba a
    # tocar, y el log daba a entender un avance que no existía.
    en_cache = len(objetivos) - len(pendientes)
    faltantes = pendientes[:args.limite] if (args.limite and args.limite > 0) \
        else pendientes

    reporte.metrica("rucs_objetivo", len(objetivos))
    reporte.metrica("rucs_en_cache", en_cache)
    reporte.metrica("rucs_pendientes_totales", len(pendientes))
    reporte.metrica("rucs_a_consultar_esta_corrida", len(faltantes))
    reporte.metrica("cobertura_pct", round(100 * en_cache / max(len(objetivos), 1), 2))
    log.info("Plan de consulta | objetivo=%d | en_cache=%d | cobertura=%.1f%% | "
             "pendientes=%d | a_consultar=%d",
             len(objetivos), en_cache, 100 * en_cache / max(len(objetivos), 1),
             len(pendientes), len(faltantes))

    sesion = requests.Session()
    nuevas, fallidas = 0, 0
    fallos_seguidos = 0
    with Cronometro(log, "consulta incremental de fichas"):
        for i, ruc in enumerate(faltantes, 1):
            ficha = (generar_ficha_demo(ruc) if args.demo
                     else descargar_ficha(sesion, ruc))
            if ficha is None:
                fallidas += 1
                fallos_seguidos += 1
                # CORTACIRCUITOS. Cuando el servidor deja de responder, el
                # fallo no es del RUC sino de la conexión: seguir iterando
                # gasta un minuto de backoff por cada uno y no consigue nada.
                # Se corta la corrida de forma limpia, con el caché ya
                # guardado, para retomar más tarde desde donde quedó.
                if fallos_seguidos >= FALLOS_SEGUIDOS_PARA_CORTAR:
                    log.error("Corte por fallos consecutivos | seguidos=%d | "
                              "probable bloqueo o limite de tasa | estado=PARCIAL",
                              fallos_seguidos)
                    break
                continue
            fallos_seguidos = 0
            cache[ruc] = ficha
            nuevas += 1
            if nuevas % 50 == 0:
                guardar_cache(cache, args.demo)          # persistencia periódica
                log.info("Progreso | fichas nuevas en esta corrida=%d", nuevas)
            if not args.demo:
                time.sleep(config.PAUSA_ENTRE_CONSULTAS)
        guardar_cache(cache, args.demo)

    reporte.metrica("fichas_nuevas", nuevas)
    reporte.metrica("fichas_fallidas", fallidas)
    reporte.metrica("corte_por_fallos_seguidos",
                    fallos_seguidos >= FALLOS_SEGUIDOS_PARA_CORTAR)

    if not cache:
        log.error("Sin fichas obtenidas | estado=ERROR")
        reporte.guardar()
        return

    with Cronometro(log, "consolidación del padrón de habilitación"):
        df = pd.DataFrame(cache.values())
        # capitulos_vigentes es lista -> se explota para poder cruzar por capítulo
        df.to_parquet(config.PARQUET_PADRON, engine="pyarrow",
                      compression="snappy", index=False)
        log.info("Archivo escrito | %s", config.PARQUET_PADRON.name)

    reporte.metrica("fichas_nuevas", nuevas)
    reporte.metrica("fichas_fallidas", fallidas)
    reporte.metrica("padron_total", int(len(df)))
    reporte.metrica("habilitados", int(df["es_habilitado"].sum()))
    reporte.metrica("no_habilitados", int((~df["es_habilitado"]).sum()))
    # Distribución por capítulo (dato, va al reporte)
    expl = df.explode("capitulos_vigentes")
    reporte.seccion("por_capitulo",
                    expl["capitulos_vigentes"].value_counts(dropna=True).to_dict())
    if (expl["capitulos_vigentes"].astype(str).str.startswith("DESCONOCIDO")).any():
        log.warning("Hay IDs de capítulo sin mapear | confirmar CAPITULOS_RNP con `grupos`")

    ruta = reporte.guardar()
    log.info("Reporte de metricas escrito | %s", ruta.name)
    log.info("FIN ficha proveedores | estado=EXITO")


if __name__ == "__main__":
    main()

"""
monitor_convocatorias.py — Fuente 3: Monitor de Llamados Vigentes.

QUÉ APORTA Y POR QUÉ ES NECESARIO
---------------------------------
Las Fuentes 1 y 2 son históricas: dicen dónde CONVIENE competir. Ninguna de
las dos dice dónde se PUEDE competir hoy. Una categoría puede concentrar
millones de soles de demanda histórica y no tener una sola convocatoria
abierta esta semana; y a la inversa, una categoría mediana puede estar
convocando ahora mismo.

Este módulo cierra esa brecha: consume la API de releases del OECE, se queda
con los procesos cuyo periodo de recepción de ofertas sigue abierto y los
publica por categoría CUBSO, de modo que el ranking de oportunidad del radar
se pueda aterrizar en llamados concretos y accionables.

FUENTE
------
Endpoint REST público y paginado del Portal de Contrataciones Abiertas:

    GET /api/v1/releasesAfter?format=json&order=desc

Devuelve un release package OCDS ordenado por fecha de publicación
descendente. La paginación es por cursor: la respuesta trae `links.next`
con la URL de la página siguiente (parámetro `searchAfter`), en lugar de un
número de página. Está documentado en
https://contratacionesabiertas.oece.gob.pe/api y es el mismo endpoint que
utiliza el colector oficial de la Open Contracting Partnership
(kingfisher-collect, spider `peru_oece_api_releases`).

De cada release vigente se extraen tres tablas:

  1. convocatorias_vigentes.parquet  — la convocatoria (entidad, objeto,
     método, monto referencial, cronograma, categoría CUBSO).
  2. documentos_convocatoria.parquet — bases administrativas, pliego
     absolutorio y demás documentos publicados. Es la materia prima de la
     pantalla de formalidades.
  3. cronograma_convocatoria.parquet — hitos del procedimiento (registro de
     participantes, consultas, presentación de ofertas, buena pro).

MANEJO DE RESTRICCIONES
-----------------------
  * cabeceras con User-Agent y Referer declarados (config.HTTP_HEADERS),
  * timeout por petición y pausa de cortesía entre páginas,
  * backoff exponencial con jitter ante HTTP 429 / 5xx / timeout,
  * checkpoint del cursor: la recorrida se interrumpe y reanuda sin repetir.

TRAZABILIDAD
------------
El log registra únicamente eventos (página descargada, código HTTP,
reintento, error, archivo escrito). Los conteos y las métricas van a
reports/, nunca al log.

Uso:
    python monitor_convocatorias.py                 # páginas definidas en config.py
    python monitor_convocatorias.py --paginas 40    # recorrido más profundo
    python monitor_convocatorias.py --demo          # sin red, datos sintéticos
    python monitor_convocatorias.py --reiniciar     # ignora el cursor guardado
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

import config
from utils import Cronometro, Reporte, crear_logger, registrar_corrida

log = crear_logger("monitor_convocatorias")

CHECKPOINT = config.CHECKPOINT_DIR / "convocatorias_checkpoint.json"

# Etapas del procedimiento en las que todavía se puede participar. Un release
# en 'complete', 'unsuccessful' o 'cancelled' ya no admite ofertas.
ESTADOS_VIGENTES = {"active", "planned", "planning"}


# ---------------------------------------------------------------------------
# 1. Utilidades de parseo
# ---------------------------------------------------------------------------
def _fecha(valor: str | None):
    """Convierte una fecha ISO de OCDS a Timestamp UTC, o NaT si no es válida."""
    if not valor:
        return pd.NaT
    return pd.to_datetime(valor, errors="coerce", utc=True)


def extraer_convocatoria(release: dict) -> dict | None:
    """Aplana un release OCDS a una fila de convocatoria.

    Devuelve None si el release no corresponde a un procedimiento de
    selección utilizable (sin tender o sin identificador).

    Todos los accesos usan .get() porque el esquema real presenta campos
    faltantes documentados por el propio publicador.
    """
    ocid = release.get("ocid")
    tender = release.get("tender") or {}
    if not ocid or not tender:
        return None

    periodo = tender.get("tenderPeriod") or {}
    consultas = tender.get("enquiryPeriod") or {}
    valor = tender.get("value") or {}
    comprador = release.get("buyer") or {}

    # Categoría CUBSO: se toma la del primer ítem clasificado. Es la llave de
    # unión con el ranking de oportunidad construido sobre la demanda
    # histórica, que también se agrega por descripción CUBSO.
    cubso_id, cubso_desc, n_items = None, None, 0
    for item in tender.get("items") or []:
        n_items += 1
        clasif = item.get("classification") or {}
        if cubso_id is None and clasif.get("id"):
            cubso_id = clasif.get("id")
            cubso_desc = clasif.get("description")

    return {
        "ocid": ocid,
        "id_release": release.get("id"),
        "convocatoria": tender.get("id"),
        "titulo": tender.get("title"),
        "descripcion": tender.get("description"),
        "entidad": comprador.get("name"),
        "metodo_contratacion": tender.get("procurementMethodDetails"),
        "tipo_objeto": tender.get("mainProcurementCategory"),
        "estado_tender": tender.get("status"),
        "monto_referencial": (valor.get("amount")),
        "moneda": valor.get("currency"),
        # El publicador marca con esta bandera los procedimientos cuya
        # información está reservada por ley. En esos casos value.amount llega
        # como 0 de forma deliberada: no es un hueco de datos ni un contrato
        # sin valor, y la Data App debe declararlo en lugar de imprimir S/ 0.
        "info_reservada": bool(tender.get("hasTenderInformationProtectedByLaw")),
        # release.date es el instante en que el pipeline OCDS escribió el
        # registro, no la fecha de convocatoria: agrupa miles de procesos en
        # domingos y fecha en el año en curso procedimientos de años previos.
        # La fecha administrativa real es tender.datePublished.
        "fecha_publicacion": _fecha(tender.get("datePublished"))
        if tender.get("datePublished")
        else _fecha(release.get("date")),
        "fecha_release": _fecha(release.get("date")),
        "fecha_inicio_ofertas": _fecha(periodo.get("startDate")),
        "fecha_cierre_ofertas": _fecha(periodo.get("endDate")),
        # El publicador entrega tenderPeriod con startDate == endDate en la
        # práctica totalidad de los procesos, de modo que el plazo de ofertas
        # no es reconstruible. enquiryPeriod sí trae rangos reales y delimita
        # la etapa en que todavía se puede registrar participación y consultar.
        "fecha_consultas_inicio": _fecha(consultas.get("startDate")),
        "fecha_consultas_fin": _fecha(consultas.get("endDate")),
        "cubso_id": cubso_id,
        "cubso_descripcion": cubso_desc,
        "n_items": n_items,
        "n_documentos": len(tender.get("documents") or []),
        "url_ficha": f"{config.RELEASE_DETALLE_ENDPOINT}/{ocid}",
    }


def extraer_documentos(release: dict) -> list[dict]:
    """Extrae los documentos publicados del procedimiento.

    Son la base de la pantalla de formalidades: las bases administrativas
    (biddingDocuments) contienen los requisitos de calificación exigibles,
    y el pliego absolutorio los modifica. Se conserva el tipo OCDS
    (documentType) porque es lo que permite distinguirlos.
    """
    ocid = release.get("ocid")
    tender = release.get("tender") or {}
    filas = []
    for doc in tender.get("documents") or []:
        filas.append({
            "ocid": ocid,
            "documento_id": doc.get("id"),
            "tipo_documento": doc.get("documentType"),
            "titulo": doc.get("title"),
            "formato": doc.get("format"),
            "url": doc.get("url"),
            "fecha_publicacion": _fecha(doc.get("datePublished")),
        })
    return filas


def extraer_cronograma(release: dict) -> list[dict]:
    """Extrae los hitos del procedimiento (milestones de OCDS).

    El cronograma es información crítica para el proveedor: la mayoría de
    las descalificaciones no son técnicas sino de plazo. Registrarlo permite
    que la Data App avise cuántos días quedan para cada etapa.
    """
    ocid = release.get("ocid")
    tender = release.get("tender") or {}
    filas = []
    for hito in tender.get("milestones") or []:
        filas.append({
            "ocid": ocid,
            "hito_id": hito.get("id"),
            "hito": hito.get("title"),
            "tipo_hito": hito.get("type"),
            "estado": hito.get("status"),
            "fecha_programada": _fecha(hito.get("dueDate")),
            "fecha_real": _fecha(hito.get("dateMet")),
        })
    return filas


# ---------------------------------------------------------------------------
# 2. Compilación de releases parciales por OCID
# ---------------------------------------------------------------------------
def _ultimo_valido(serie: pd.Series):
    """Devuelve el valor no vacío más reciente de una serie ya ordenada.

    La API del OECE publica releases OCDS incrementales: un release reciente
    puede omitir campos que sí estaban en un release anterior del mismo OCID.
    Para la vista operativa necesitamos una foto compilada del proceso, no
    simplemente la primera fila que aparezca en la paginación.

    Esta función implementa una compilación tabular conservadora para los
    campos que usa el dashboard: toma el valor no vacío más reciente. No
    intenta reemplazar el algoritmo completo del estándar OCDS para todos los
    objetos del esquema; se limita a los campos planos extraídos arriba.
    """
    validos = serie[serie.notna()]
    if validos.empty:
        return pd.NaT if pd.api.types.is_datetime64_any_dtype(serie.dtype) else None

    if pd.api.types.is_string_dtype(validos.dtype) or validos.dtype == object:
        mask = validos.astype("string").str.strip().ne("")
        validos = validos[mask.fillna(False)]
        if validos.empty:
            return None
    return validos.iloc[-1]


def compilar_convocatorias(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Combina releases parciales del mismo OCID en una fila utilizable.

    Los releases se ordenan cronológicamente y cada campo toma el último valor
    no vacío publicado. Así, si el release más reciente solo informa una
    modificación y omite ``tender.status`` o ``tenderPeriod``, se conservan los
    valores publicados previamente para el mismo proceso.

    Retorna también métricas de diagnóstico para poder demostrar cuántos
    campos fueron recuperados gracias a la compilación.
    """
    if df.empty:
        return df.copy(), {
            "ocids_unicos": 0,
            "releases_compilados": 0,
            "estado_recuperado": 0,
            "cierre_recuperado": 0,
        }

    trabajo = df.copy()
    for _col_fecha in ("fecha_publicacion", "fecha_release"):
        if _col_fecha in trabajo.columns:
            trabajo[_col_fecha] = pd.to_datetime(
                trabajo[_col_fecha], errors="coerce", utc=True
            )
    _orden = "fecha_release" if "fecha_release" in trabajo.columns else "fecha_publicacion"
    trabajo = trabajo.sort_values(
        ["ocid", _orden], ascending=[True, True], na_position="first"
    )

    # Ruta rápida: el archivo anual del Registro OCP publica un compiled
    # release por proceso, así que no hay OCID repetidos y no hay nada que
    # compilar. Recorrer 100.000 grupos en Python para copiar el único valor de
    # cada uno cuesta minutos y produce exactamente la misma tabla.
    if not trabajo["ocid"].duplicated().any():
        rapido = trabajo.copy()
        rapido["n_releases_compilados"] = 1
        for _col_conteo in ("n_items", "n_documentos"):
            if _col_conteo in rapido.columns:
                rapido[_col_conteo] = (
                    pd.to_numeric(rapido[_col_conteo], errors="coerce")
                    .fillna(0).astype(int)
                )
        metricas_rapidas = {
            "ocids_unicos": int(rapido["ocid"].nunique()),
            "releases_compilados": int(len(rapido)),
            "estado_recuperado": 0,
            "cierre_recuperado": 0,
            "releases_promedio_por_ocid": 1.0,
            "ruta": "sin_ocid_duplicado",
        }
        return rapido.reset_index(drop=True), metricas_rapidas

    # Foto del release más reciente, antes de compilar. Sirve para medir qué
    # información recuperamos de releases anteriores.
    ultimos = trabajo.groupby("ocid", sort=False, as_index=False).tail(1).set_index("ocid")

    campos_ultimo_valido = [
        "id_release", "convocatoria", "titulo", "descripcion", "entidad",
        "metodo_contratacion", "tipo_objeto", "estado_tender",
        "monto_referencial", "moneda", "info_reservada", "fecha_publicacion",
        "fecha_inicio_ofertas", "fecha_cierre_ofertas",
        "fecha_consultas_inicio", "fecha_consultas_fin",
        "cubso_id", "cubso_descripcion", "url_ficha",
    ]

    filas = []
    for ocid, grupo in trabajo.groupby("ocid", sort=False):
        fila = {"ocid": ocid}
        if "fecha_release" in grupo.columns:
            fila["fecha_release"] = grupo["fecha_release"].max()
        for campo in campos_ultimo_valido:
            fila[campo] = _ultimo_valido(grupo[campo]) if campo in grupo.columns else None
        # En releases parciales, items/documentos pueden no repetirse. Para la
        # ficha nos interesa saber si alguna versión los publicó.
        fila["n_items"] = int(pd.to_numeric(grupo.get("n_items"), errors="coerce").fillna(0).max())
        fila["n_documentos"] = int(pd.to_numeric(grupo.get("n_documentos"), errors="coerce").fillna(0).max())
        fila["n_releases_compilados"] = int(len(grupo))
        filas.append(fila)

    compilado = pd.DataFrame(filas)
    compilado = compilado.set_index("ocid", drop=False)

    # Diagnóstico de campos que el release más reciente omitía y que fueron
    # recuperados de una versión anterior del mismo proceso.
    estado_recuperado = int(
        (
            ultimos["estado_tender"].isna()
            & compilado.loc[ultimos.index, "estado_tender"].notna()
        ).sum()
    )
    cierre_recuperado = int(
        (
            ultimos["fecha_cierre_ofertas"].isna()
            & compilado.loc[ultimos.index, "fecha_cierre_ofertas"].notna()
        ).sum()
    )

    compilado = compilado.reset_index(drop=True)
    metricas = {
        "ocids_unicos": int(compilado["ocid"].nunique()),
        "releases_compilados": int(len(trabajo)),
        "estado_recuperado": estado_recuperado,
        "cierre_recuperado": cierre_recuperado,
        "releases_promedio_por_ocid": round(len(trabajo) / max(len(compilado), 1), 2),
    }
    return compilado, metricas


# ---------------------------------------------------------------------------
# 3. Cliente HTTP con reintentos y cursor reanudable
# ---------------------------------------------------------------------------
def cargar_cursor() -> str | None:
    """Recupera la URL de continuación guardada por una corrida anterior."""
    if CHECKPOINT.exists():
        with open(CHECKPOINT, encoding="utf-8") as f:
            estado = json.load(f)
        log.info("Checkpoint de cursor encontrado | reanudando recorrido")
        return estado.get("proxima_url")
    return None


def guardar_cursor(url: str | None) -> None:
    """Persiste el cursor tras cada página (a prueba de cortes)."""
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump({"proxima_url": url,
                   "actualizado_en": datetime.now(timezone.utc).isoformat()},
                  f, ensure_ascii=False)


def limpiar_cursor() -> None:
    """Elimina el checkpoint después de una corrida completada.

    El checkpoint existe para REANUDAR una corrida interrumpida. Si se conserva
    después de una corrida exitosa, la siguiente ejecución arranca en páginas
    antiguas y deja de comportarse como un monitor de actualidad.
    """
    CHECKPOINT.unlink(missing_ok=True)


def descargar_pagina(sesion: requests.Session, url: str) -> tuple[list[dict], str | None]:
    """Descarga una página de releases con backoff exponencial + jitter.

    Devuelve (releases, url_siguiente). Ante agotamiento de reintentos
    devuelve ([], None) para que el recorrido termine de forma ordenada
    conservando lo ya obtenido.
    """
    for intento in range(1, config.MAX_REINTENTOS + 1):
        try:
            r = sesion.get(url, headers=config.HTTP_HEADERS,
                           timeout=config.HTTP_TIMEOUT)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            cuerpo = r.json()
            log.info("Pagina descargada | http=%s | intento=%d", r.status_code, intento)
            releases = cuerpo.get("releases") or []
            siguiente = (cuerpo.get("links") or {}).get("next")
            return releases, siguiente
        except (requests.HTTPError, requests.ConnectionError,
                requests.Timeout, ValueError) as exc:
            if intento == config.MAX_REINTENTOS:
                log.error("Pagina agotó reintentos | tipo=%s", type(exc).__name__)
                break
            espera = config.BACKOFF_BASE ** intento + random.uniform(0, 1)
            log.warning("Fallo de descarga | tipo=%s | backoff=%.1fs | intento=%d/%d",
                        type(exc).__name__, espera, intento, config.MAX_REINTENTOS)
            time.sleep(espera)
    return [], None


# ---------------------------------------------------------------------------
# 4. Modo demo (sin red)
# ---------------------------------------------------------------------------
def generar_releases_demo(pagina: int) -> list[dict]:
    """Fabrica releases con la estructura real de OCDS, sin conexión.

    Permite demostrar el monitor en clase aunque la red del aula bloquee el
    portal. Los datos son deterministas (semilla fija) y las fechas se
    calculan relativas a hoy para que siempre existan llamados vigentes.
    """
    rng = random.Random(4364 + pagina)
    hoy = datetime.now(timezone.utc)
    categorias = [
        ("501015", "SERVICIO DE ALIMENTACION Y NUTRICION HOSPITALARIA"),
        ("501020", "SERVICIO DE ALIMENTACION PARA EVENTOS VARIOS"),
        ("501025", "SERVICIO DE PREPARACION DE ALMUERZO"),
        ("921215", "SERVICIO DE SEGURIDAD Y VIGILANCIA"),
        ("432115", "EQUIPOS DE COMPUTO PERSONAL"),
    ]
    entidades = ["ESSALUD", "MINSA", "GOBIERNO REGIONAL DE LIMA",
                 "MUNICIPALIDAD DE SAN ISIDRO", "MINEDU"]
    metodos = ["Adjudicación Simplificada", "Licitación Pública",
               "Concurso Público", "Subasta Inversa Electrónica"]

    releases = []
    for i in range(10):
        cid, cdesc = rng.choice(categorias)
        dias_para_cierre = rng.randint(-5, 25)  # algunos ya vencidos
        cierre = hoy + timedelta(days=dias_para_cierre)
        inicio = cierre - timedelta(days=rng.randint(8, 20))
        n = (pagina - 1) * 10 + i + 1
        releases.append({
            "ocid": f"ocds-dgv273-seacev3-DEMO-{n:05d}",
            "id": f"DEMO-{n:05d}-1",
            "date": (hoy - timedelta(days=rng.randint(0, 10))).isoformat(),
            "buyer": {"name": rng.choice(entidades)},
            "tender": {
                "id": f"AS-SM-{n}-2026",
                "title": f"Contratación del {cdesc.lower()}",
                "description": f"Servicio requerido por la entidad — demo {n}",
                "status": "active",
                "procurementMethodDetails": rng.choice(metodos),
                "mainProcurementCategory": "services",
                "value": {"amount": round(rng.uniform(80_000, 4_500_000), 2),
                          "currency": "PEN"},
                "tenderPeriod": {"startDate": inicio.isoformat(),
                                 "endDate": cierre.isoformat()},
                "items": [{"classification": {"id": cid, "description": cdesc},
                           "description": f"Ítem demo {n}"}],
                "documents": [
                    {"id": f"{n}-1", "documentType": "biddingDocuments",
                     "title": "Bases Administrativas", "format": "pdf",
                     "url": "https://contratacionesabiertas.oece.gob.pe/demo/bases.pdf",
                     "datePublished": inicio.isoformat()},
                    {"id": f"{n}-2", "documentType": "clarifications",
                     "title": "Pliego absolutorio de consultas y observaciones",
                     "format": "pdf",
                     "url": "https://contratacionesabiertas.oece.gob.pe/demo/pliego.pdf",
                     "datePublished": inicio.isoformat()},
                ],
                "milestones": [
                    {"id": f"{n}-m1", "title": "Registro de participantes",
                     "type": "preProcurement", "status": "scheduled",
                     "dueDate": (inicio + timedelta(days=2)).isoformat()},
                    {"id": f"{n}-m2", "title": "Formulación de consultas y observaciones",
                     "type": "preProcurement", "status": "scheduled",
                     "dueDate": (inicio + timedelta(days=5)).isoformat()},
                    {"id": f"{n}-m3", "title": "Presentación de ofertas",
                     "type": "preProcurement", "status": "scheduled",
                     "dueDate": cierre.isoformat()},
                    {"id": f"{n}-m4", "title": "Otorgamiento de la buena pro",
                     "type": "preProcurement", "status": "scheduled",
                     "dueDate": (cierre + timedelta(days=4)).isoformat()},
                ],
            },
        })
    return releases


# ---------------------------------------------------------------------------
# 5. Lectura del snapshot anual compilado (fuente preferida)
# ---------------------------------------------------------------------------
def recorrer_compilado_local(anio: int) -> tuple[list, list, list, dict]:
    """Lee el archivo anual OCDS ya descargado por ``ingesta_ocds.py``.

    El Registro de Datos de Open Contracting publica cada proceso del archivo
    anual como un *compiled release*. Para el monitor operativo esta fuente es
    preferible a ``releasesAfter`` porque ya contiene la foto acumulada del
    proceso y, por tanto, no depende de reconstruir campos omitidos en releases
    incrementales.

    Se procesa línea por línea para no cargar el JSON completo en memoria.
    """
    ruta = config.RAW_DIR / f"ocds_{anio}.jsonl.gz"
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe {ruta}. Descargue primero el snapshot con: "
            f"python ingesta_ocds.py --anios 2024 2025 {anio} --refrescar"
        )

    convocatorias, documentos, cronograma = [], [], []
    stats = {
        "fuente": "snapshot_anual_compilado",
        "archivo": ruta.name,
        "lineas_leidas": 0,
        "lineas_malformadas": 0,
        "sin_tender": 0,
        "releases_leidos": 0,
    }

    with gzip.open(ruta, "rt", encoding="utf-8") as f:
        for linea in f:
            stats["lineas_leidas"] += 1
            try:
                release = json.loads(linea)
            except json.JSONDecodeError:
                stats["lineas_malformadas"] += 1
                continue

            stats["releases_leidos"] += 1
            fila = extraer_convocatoria(release)
            if fila is None:
                stats["sin_tender"] += 1
                continue

            convocatorias.append(fila)
            documentos.extend(extraer_documentos(release))
            cronograma.extend(extraer_cronograma(release))

    log.info(
        "Snapshot anual procesado | anio=%s | archivo=%s | estado=EXITO",
        anio, ruta.name,
    )
    return convocatorias, documentos, cronograma, stats


# ---------------------------------------------------------------------------
# 5. Recorrido y filtrado de vigencia
# ---------------------------------------------------------------------------
def recorrer(paginas: int, demo: bool, reiniciar: bool) -> tuple[list, list, list, dict]:
    """Recorre N páginas de la API y acumula convocatorias, documentos e hitos."""
    url = None if (demo or reiniciar) else cargar_cursor()
    if url is None:
        url = f"{config.RELEASES_ENDPOINT}?format=json&order=desc"

    sesion = requests.Session()
    convocatorias, documentos, cronograma = [], [], []
    stats = {"paginas_ok": 0, "paginas_fallidas": 0, "releases_leidos": 0,
             "sin_tender": 0}

    for pagina in range(1, paginas + 1):
        if demo:
            releases, siguiente = generar_releases_demo(pagina), "demo"
        else:
            releases, siguiente = descargar_pagina(sesion, url)

        if not releases:
            stats["paginas_fallidas"] += 1
            log.warning("Pagina sin resultados | nro=%d | se detiene el recorrido",
                        pagina)
            break

        stats["paginas_ok"] += 1
        stats["releases_leidos"] += len(releases)

        for release in releases:
            fila = extraer_convocatoria(release)
            if fila is None:
                stats["sin_tender"] += 1
                continue
            convocatorias.append(fila)
            documentos.extend(extraer_documentos(release))
            cronograma.extend(extraer_cronograma(release))

        if not demo:
            guardar_cursor(siguiente)
            if not siguiente:
                log.info("Fin del recorrido | no hay pagina siguiente")
                break
            url = siguiente
            time.sleep(config.PAUSA_ENTRE_CONSULTAS)  # cortesía con el servidor

    return convocatorias, documentos, cronograma, stats


def marcar_vigencia(df: pd.DataFrame, dias_alerta: int) -> pd.DataFrame:
    """Clasifica cada convocatoria según hasta cuándo admite participación.

    LIMITACIÓN MEDIDA DE LA FUENTE
    ------------------------------
    El publicador entrega ``tenderPeriod`` con ``startDate`` igual a
    ``endDate``: sobre el archivo anual 2026, 99.663 de 99.673 procesos con
    ambas fechas las tienen idénticas. Con ese campo el plazo de ofertas no es
    reconstruible y toda convocatoria nacería cerrada, lo que no describe la
    realidad sino la publicación.

    ``enquiryPeriod`` sí trae rangos reales (por ejemplo, del 04/08 al 13/08) y
    delimita la etapa de registro de participantes y consultas. Se usa como
    límite efectivo cuando el periodo de ofertas viene colapsado, y la columna
    ``origen_limite`` deja registrado de dónde salió cada valor para que la
    lectura no se confunda con un plazo de presentación de ofertas.

    Valores de ``vigencia``:
      VIGENTE     — el límite efectivo aún no vence.
      POR CERRAR  — vence dentro de los próximos ``dias_alerta`` días.
      CERRADA     — el límite efectivo ya venció, o el estado del tender ya no
                    admite participación.
      SIN FECHA   — no hay ninguna fecha utilizable; se declara en vez de
                    asumir vigencia.
    """
    ahora = pd.Timestamp.now(tz="UTC")
    df = df.copy()

    for col in ("fecha_inicio_ofertas", "fecha_cierre_ofertas",
                "fecha_consultas_inicio", "fecha_consultas_fin"):
        if col not in df.columns:
            df[col] = pd.NaT
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    # El periodo de ofertas solo es utilizable si el cierre es posterior al
    # inicio. Si coinciden, el dato existe pero no describe un plazo.
    ofertas_util = (
        df["fecha_cierre_ofertas"].notna()
        & df["fecha_inicio_ofertas"].notna()
        & (df["fecha_cierre_ofertas"] > df["fecha_inicio_ofertas"])
    )
    df["periodo_ofertas_colapsado"] = (
        df["fecha_cierre_ofertas"].notna()
        & df["fecha_inicio_ofertas"].notna()
        & (df["fecha_cierre_ofertas"] == df["fecha_inicio_ofertas"])
    )

    limite = df["fecha_cierre_ofertas"].where(ofertas_util)
    origen = pd.Series("sin fecha utilizable", index=df.index, dtype="object")
    origen[ofertas_util] = "cierre de ofertas"

    usar_consultas = limite.isna() & df["fecha_consultas_fin"].notna()
    limite = limite.where(~usar_consultas, df["fecha_consultas_fin"])
    origen[usar_consultas] = "fin de consultas"

    df["fecha_limite_participacion"] = limite
    df["origen_limite"] = origen

    df["dias_para_cierre"] = (
        (limite - ahora).dt.total_seconds() / 86400
    ).round(1)
    df["dias_para_fin_consultas"] = (
        (df["fecha_consultas_fin"] - ahora).dt.total_seconds() / 86400
    ).round(1)

    estado_ok = df["estado_tender"].isin(ESTADOS_VIGENTES) | df["estado_tender"].isna()
    sin_fecha = limite.isna()
    abierta = (df["dias_para_cierre"] >= 0) & estado_ok

    df["vigencia"] = "CERRADA"
    df.loc[abierta, "vigencia"] = "VIGENTE"
    df.loc[abierta & (df["dias_para_cierre"] <= dias_alerta), "vigencia"] = "POR CERRAR"
    df.loc[sin_fecha, "vigencia"] = "SIN FECHA"
    return df


# ---------------------------------------------------------------------------
# 6. Orquestación
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor de convocatorias vigentes del OECE / OCDS"
    )
    parser.add_argument(
        "--fuente", choices=["local", "api"], default="local",
        help=(
            "local = usa el snapshot anual compilado descargado por ingesta_ocds.py "
            "(recomendado); api = usa releasesAfter como respaldo"
        ),
    )
    parser.add_argument(
        "--anio", type=int, default=datetime.now().year,
        help="Año del snapshot OCDS local; por defecto, el año actual",
    )
    parser.add_argument("--paginas", type=int,
                        default=config.RELEASES_PAGINAS_DEFECTO,
                        help="Páginas de la API a recorrer cuando --fuente api")
    parser.add_argument("--dias-alerta", type=int, default=config.DIAS_ALERTA_CIERRE,
                        help="Días para marcar una convocatoria como POR CERRAR")
    parser.add_argument("--demo", action="store_true",
                        help="Genera releases sintéticos (sin red)")
    parser.add_argument("--reiniciar", action="store_true",
                        help="Ignora el cursor cuando se usa --fuente api")
    args = parser.parse_args()

    fuente = "demo" if args.demo else args.fuente
    log.info(
        "INICIO monitor | fuente=%s | anio=%s | paginas=%d | dias_alerta=%d",
        fuente, args.anio, args.paginas, args.dias_alerta,
    )
    reporte = Reporte("monitor_convocatorias")
    reporte.metrica("fuente_monitor", fuente)
    reporte.metrica("anio_monitor", args.anio)
    reporte.metrica("paginas_solicitadas", args.paginas)
    reporte.metrica("modo_demo", args.demo)

    if args.demo:
        with Cronometro(log, "generación demo"):
            convocatorias, documentos, cronograma, stats = recorrer(
                min(args.paginas, 3), True, True
            )
        requiere_compilacion = True
    elif args.fuente == "local":
        with Cronometro(log, "lectura del snapshot anual compilado"):
            convocatorias, documentos, cronograma, stats = recorrer_compilado_local(
                args.anio
            )
        # El archivo anual del Registro OCP ya representa cada proceso como
        # compiled release. Aun así usamos la función de compilación para
        # resolver cualquier OCID repetido sin perder valores no nulos.
        requiere_compilacion = True
    else:
        with Cronometro(log, "recorrido de la API de releases"):
            convocatorias, documentos, cronograma, stats = recorrer(
                args.paginas, False, args.reiniciar
            )
        requiere_compilacion = True

    if not convocatorias:
        log.error("Sin convocatorias obtenidas | fuente=%s", fuente)
        reporte.seccion("recorrido", stats)
        reporte.guardar()
        return

    with Cronometro(log, "normalización y clasificación de vigencia"):
        bruto = pd.DataFrame(convocatorias)
        if requiere_compilacion:
            df, metricas_compilacion = compilar_convocatorias(bruto)
        else:
            df, metricas_compilacion = bruto, {}

        df["monto_referencial"] = pd.to_numeric(
            df["monto_referencial"], errors="coerce"
        )
        df["cubso_descripcion"] = (
            df["cubso_descripcion"].astype("string").str.strip().str.upper()
        )
        for col in ("entidad", "metodo_contratacion", "tipo_objeto",
                    "estado_tender", "moneda"):
            df[col] = df[col].astype("category")
        df = marcar_vigencia(df, args.dias_alerta)

    with Cronometro(log, "escritura de salidas Parquet"):
        df.to_parquet(
            config.PARQUET_CONVOCATORIAS, engine="pyarrow",
            compression="snappy", index=False,
        )
        log.info("Archivo escrito | %s", config.PARQUET_CONVOCATORIAS.name)

        if documentos:
            docs = pd.DataFrame(documentos).drop_duplicates(
                subset=["ocid", "documento_id"], keep="last"
            )
            docs.to_parquet(
                config.PARQUET_DOCUMENTOS, engine="pyarrow",
                compression="snappy", index=False,
            )
            log.info("Archivo escrito | %s", config.PARQUET_DOCUMENTOS.name)

        if cronograma:
            cron = pd.DataFrame(cronograma).drop_duplicates(
                subset=["ocid", "hito_id"], keep="last"
            )
            cron.to_parquet(
                config.PARQUET_CRONOGRAMA, engine="pyarrow",
                compression="snappy", index=False,
            )
            log.info("Archivo escrito | %s", config.PARQUET_CRONOGRAMA.name)

    reporte.seccion("recorrido", stats)
    reporte.seccion("compilacion_releases", metricas_compilacion)
    reporte.metrica("convocatorias_totales", int(len(df)))

    if df["fecha_publicacion"].notna().any():
        fecha_max = df["fecha_publicacion"].max()
        reporte.metrica("fecha_publicacion_max_fuente", fecha_max.isoformat())
        desfase_dias = max(
            0,
            int((pd.Timestamp.now(tz="UTC") - fecha_max).total_seconds() // 86400),
        )
        reporte.metrica("desfase_dias_fuente", desfase_dias)

    if df["fecha_cierre_ofertas"].notna().any():
        reporte.metrica(
            "fecha_cierre_max_fuente",
            df["fecha_cierre_ofertas"].max().isoformat(),
        )

    reporte.seccion("por_vigencia", df["vigencia"].value_counts().to_dict())
    reporte.seccion("por_origen_limite", df["origen_limite"].value_counts().to_dict())
    reporte.metrica(
        "periodo_ofertas_colapsado",
        int(df["periodo_ofertas_colapsado"].sum()),
    )
    if "info_reservada" in df.columns:
        _monto = pd.to_numeric(df["monto_referencial"], errors="coerce")
        reporte.seccion("monto_referencial", {
            "con_monto_publicado": int(_monto.gt(0).sum()),
            "reservado_por_ley": int((_monto.fillna(0).le(0) & df["info_reservada"]).sum()),
            "sin_monto_publicado": int((_monto.fillna(0).le(0) & ~df["info_reservada"]).sum()),
        })
    if df["fecha_consultas_fin"].notna().any():
        reporte.metrica(
            "fecha_consultas_fin_max",
            df["fecha_consultas_fin"].max().isoformat(),
        )
    reporte.metrica("documentos_extraidos", len(documentos))
    reporte.metrica("hitos_extraidos", len(cronograma))

    vigentes = df[df["vigencia"].isin(["VIGENTE", "POR CERRAR"])]
    reporte.metrica("convocatorias_vigentes", int(len(vigentes)))
    reporte.metrica(
        "categorias_cubso_con_llamado",
        int(vigentes["cubso_descripcion"].nunique()),
    )

    if not vigentes.empty:
        reporte.guardar_tabla(
            vigentes.nlargest(min(50, len(vigentes)), "monto_referencial")[
                ["ocid", "entidad", "titulo", "metodo_contratacion",
                 "monto_referencial", "fecha_cierre_ofertas",
                 "dias_para_cierre", "cubso_descripcion", "vigencia"]
            ],
            "vigentes_top",
        )

    ruta = reporte.guardar()
    log.info("Reporte de metricas escrito | %s", ruta.name)

    # El cursor solo tiene sentido para el respaldo por API. El modo local
    # siempre vuelve a leer el snapshot anual más reciente descargado.
    if fuente == "api":
        limpiar_cursor()
        log.info("Checkpoint limpiado | proxima corrida API inicia desde lo mas reciente")

    registrar_corrida("monitor_convocatorias")
    log.info("FIN monitor | estado=EXITO")


if __name__ == "__main__":
    main()

"""
config.py — Configuración centralizada del proyecto Radar de Oportunidades.

Proyecto : Radar de Oportunidades en Compras Públicas
Curso    : Lenguaje de Ciencia de Datos II (4364) — CIBERTEC
Versión  : 3 — incorpora el Monitor de Convocatorias Vigentes (Fuente 3)
           y el Catálogo de Formalidades (Fuente 4).

Todas las rutas, URLs y parámetros de reintento viven aquí para que ningún
módulo tenga valores "quemados" en el código.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"                 # datos crudos descargados
PROCESSED_DIR = DATA_DIR / "processed"     # datos normalizados (Parquet)
CHECKPOINT_DIR = DATA_DIR / "checkpoints"  # checkpoints de descargas reanudables
LOG_DIR = BASE_DIR / "logs"                # trazabilidad de ejecución (SIN datos)
REPORT_DIR = BASE_DIR / "reports"          # métricas y resultados (SÍ datos)
NORMATIVA_DIR = BASE_DIR / "normativa"     # catálogo de formalidades

for _d in (RAW_DIR, PROCESSED_DIR, CHECKPOINT_DIR, LOG_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Fuente 1 — OCDS / SEACE (descarga masiva anual)  ·  LA DEMANDA HISTÓRICA
# ---------------------------------------------------------------------------
# El OECE publica los procesos de contratación del SEACE en estándar OCDS.
# La descarga masiva por año está disponible como .jsonl.gz (una línea JSON
# por proceso) a través del Data Registry de la Open Contracting Partnership,
# que replica mensualmente https://contratacionesabiertas.oece.gob.pe/descargas
OCDS_PUBLICATION_ID = 135  # Perú — OECE en data.open-contracting.org
OCDS_DOWNLOAD_URL = (
    "https://data.open-contracting.org/es/publication/"
    f"{OCDS_PUBLICATION_ID}/download?name={{anio}}.jsonl.gz"
)
OCDS_ANIOS = [2024, 2025, 2026]

# ---------------------------------------------------------------------------
# Fuente 2 — Ficha Única del Proveedor (OECE)  ·  LA HABILITACIÓN REAL
# ---------------------------------------------------------------------------
# Endpoint REST público que respalda la Ficha Única del Proveedor (FUP). Se
# consulta por RUC y entrega el estado real del proveedor en el RNP:
# esHabilitado, esAptoContratar y los capítulos vigentes (lscIdTipRegVig).
#
# Reemplaza el proxy por coincidencia textual del buscador anterior: la
# habilitación deja de estimarse y pasa a leerse del registro oficial.
FICHA_PROVEEDOR_ENDPOINT = "https://eap.oece.gob.pe/perfilprov-bus/1.0/ficha/{ruc}"

# Capítulos del RNP donde un proveedor puede estar habilitado. El endpoint los
# entrega como IDs; el mapeo ID->nombre vive en ficha_proveedores.py
# (CAPITULOS_RNP) y se confirma con el endpoint auxiliar `grupos` de la ficha.
CAPITULOS_RNP_NOMBRES = ["BIENES", "SERVICIOS",
                         "CONSULTOR_DE_OBRAS", "EJECUTOR_DE_OBRAS"]

# ---------------------------------------------------------------------------
# Fuente 3 — Snapshot OCDS compilado / API OECE  ·  LOS LLAMADOS VIGENTES
# ---------------------------------------------------------------------------
# El monitor usa por defecto el snapshot anual OCDS ya descargado en data/raw.
# El Registro OCP representa cada proceso como un compiled release, por lo que
# esta es la fuente preferida para recuperar tender.status y tenderPeriod completos.
# El endpoint REST de releases se conserva como respaldo técnico.
#
# Documentado en https://contratacionesabiertas.oece.gob.pe/api y utilizado
# por el colector oficial de la Open Contracting Partnership
# (kingfisher-collect, spider `peru_oece_api_releases`), lo que da respaldo
# institucional a la elección del endpoint.
#
# Aporta la dimensión que ninguna de las dos fuentes anteriores tiene: qué
# está convocado HOY. La demanda histórica dice dónde conviene competir; el
# monitor dice dónde se puede competir esta semana.
RELEASES_ENDPOINT = "https://contratacionesabiertas.oece.gob.pe/api/v1/releasesAfter"
RELEASE_DETALLE_ENDPOINT = "https://contratacionesabiertas.oece.gob.pe/api/v1/release"
# Páginas a recorrer por corrida del monitor. El valor original (15) devolvía
# unas 150 convocatorias que cubrían solo 5 categorías CUBSO de las 30 705 del
# catálogo, así que el cruce del radar histórico contra los llamados abiertos
# era imposible por aritmética, no por criterio.
#
# No es un límite de la fuente: es cuánto se decide recorrer. Con la pausa de
# cortesía entre páginas, 200 páginas tardan unos 20 minutos. Conviene correr el
# monitor con este valor una vez antes de presentar y medir cuántas categorías
# distintas aparecen, que es el número que decide si el cruce es viable.
RELEASES_PAGINAS_DEFECTO = 200

# Una convocatoria se considera VIGENTE si su tenderPeriod.endDate todavía no
# venció. Este margen permite además listar las que cierran en los próximos N
# días como "por cerrar" (alerta temprana para el proveedor).
DIAS_ALERTA_CIERRE = 7

# Cabeceras: nos identificamos y declaramos el origen de la consulta
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://contratacionesabiertas.oece.gob.pe/",
}

# ---------------------------------------------------------------------------
# Fuente 4 — Catálogo de formalidades  ·  QUÉ SE NECESITA PARA POSTULAR
# ---------------------------------------------------------------------------
# Archivo curado por el equipo a partir de la Ley N.º 32069 (Ley General de
# Contrataciones Públicas) y su Reglamento (D.S. 009-2025-EF). No se descarga:
# es un dataset de referencia versionado con el proyecto, con la base legal
# citada en cada requisito para que sea auditable.
CATALOGO_FORMALIDADES = NORMATIVA_DIR / "formalidades_catalogo.json"

# ---------------------------------------------------------------------------
# Etiqueta de competencia (reemplaza a la clasificación de mercado 2x2)
# ---------------------------------------------------------------------------
# La etiqueta anterior cruzaba demanda alta con espacio de mercado, y resultaba
# ilegible junto al índice: el índice multiplica por accesibilidad y premia
# ticket bajo, mientras que la demanda alta viene con ticket alto. Las dos
# señales apuntaban en direcciones opuestas y el top del ranking aparecía
# etiquetado como "Nicho menor", que en pantalla se lee como un error.
#
# La etiqueta ahora describe una sola cosa, la que el padrón permite medir por
# categoría: cuántos de los que ganaron siguen habilitados para volver a ganar.
# Es unidimensional, nunca contradice al índice, y pone el resultado de la
# ficha del RNP a la vista en cada fila.
BANDAS_COMPETENCIA = [-1, 0, 2, 5, float("inf")]
BANDAS_COMPETENCIA_ETIQUETAS = [
    "Sin adjudicatario vigente",
    "Poca competencia (1-2)",
    "Competencia media (3-5)",
    "Disputado (>5)",
]

# ---------------------------------------------------------------------------
# Parámetros de transformación (Tema 4)  ·  BINNING Y ESCALADO
# ---------------------------------------------------------------------------
# La UIT es la unidad con la que la propia normativa peruana mide el tamaño de
# una contratación, así que las bandas de ticket se anclan en ella en lugar de
# usar cuartiles arbitrarios. Valor 2026 fijado por D.S. 301-2025-EF.
# ACTUALIZAR CADA ENERO: el MEF publica el nuevo valor en diciembre.
UIT_SOLES = 5_500
UIT_ANIO = 2026

# Cortes en múltiplos de UIT. El primero (8 UIT) NO es una elección del equipo:
# es el umbral legal por debajo del cual la contratación se tramita como
# contratación menor, con requisitos y plazos reducidos. Es exactamente la
# frontera que le importa a una MYPE que recién empieza. Los cortes de 50 y
# 200 UIT sí son del equipo, para separar el tramo intermedio del grande.
BANDAS_TICKET_UIT = [0, 8, 50, 200, float("inf")]
BANDAS_TICKET_ETIQUETAS = [
    "Contratación menor (≤8 UIT)",
    "Accesible (8-50 UIT)",
    "Intermedio (50-200 UIT)",
    "Grande (>200 UIT)",
]

# Pesos del potencial de mercado. Suman 1 y están a la vista: la señal es
# descriptiva y su fórmula tiene que poder discutirse, no esconderse.
#
# La accesibilidad NO figura acá porque no es un sumando: multiplica el
# potencial. Un mercado grande al que el proveedor no puede entrar no vale
# "un poco menos", vale cero. Ver la justificación en transformacion.escalar().
PESOS_INDICE = {
    "demanda": 0.55,   # cuánto compra el Estado en esa categoría
    "espacio": 0.45,   # cuánto margen queda frente a la competencia
}

# Factor de accesibilidad por banda de ticket. Multiplica el potencial de
# mercado para dar el índice final.
#
# Los valores son una decisión del equipo, no una medición, y están puestos
# acá para que se discutan en vez de quedar escondidos en el código. El
# criterio: la contratación menor es plenamente accesible para una MYPE; a
# partir de 200 UIT (S/ 1.1 millones) hacen falta capacidad financiera y
# experiencia acreditada que la mayoría no tiene, así que el potencial queda
# reducido a una décima parte, no anulado (una MYPE puede subcontratar o
# consorciarse, pero no es su mercado natural).
FACTOR_ACCESIBILIDAD = {
    "Contratación menor (≤8 UIT)": 1.00,
    "Accesible (8-50 UIT)": 0.75,
    "Intermedio (50-200 UIT)": 0.35,
    "Grande (>200 UIT)": 0.10,
}
# Categorías sin ticket calculable: se les asigna el valor de la banda
# intermedia para no premiarlas ni castigarlas por falta de dato.
FACTOR_ACCESIBILIDAD_DESCONOCIDO = 0.35

# ---------------------------------------------------------------------------
# Piso de mercado: qué categorías entran al ranking
# ---------------------------------------------------------------------------
# Sin un piso, el índice premia mercados vacíos por diminutos: una categoría
# donde el Estado gastó S/ 44 000 en dos años no tiene competencia porque no
# vale la pena competir ahí, no porque haya una oportunidad desatendida.
#
# El criterio principal es la RECURRENCIA y no el monto. Una categoría con un
# solo proceso en dos años es una compra que pasó una vez: el proveedor no
# puede inscribirse en el RNP, esperar el trámite y presentarse a algo que ya
# ocurrió. La mediana de procesos por categoría es exactamente 1, así que este
# filtro separa mercados de compras aisladas.
#
# El piso monetario es secundario y suave: descarta lo residual sin recortar
# nada defendible. Va en UIT acumuladas del período, no en soles, para que
# sobreviva al cambio de UIT de cada enero.
MINIMO_PROCESOS_MERCADO = 5
MINIMO_DEMANDA_UIT_MERCADO = 100

# Tercer criterio del piso: cuántos ganadores históricos respaldan la señal.
#
# `espacio_mercado` se construye sobre `competencia_vigente`, que cuenta
# adjudicatarios que siguen habilitados en el RNP. Ese conteo depende de dos
# cruces imperfectos y medidos: la ficha del RNP cubre el 80,7% de los
# adjudicatarios, y solo el 77% de los `proveedor_id` del OCDS trae RUC de once
# dígitos (consorcios y personas naturales quedan fuera del cruce).
#
# En una categoría con dos ganadores, un `competencia_vigente` igual a cero es
# indistinguible de no tener la ficha de ninguno de los dos. El índice lo
# premiaría como mercado desierto sin poder demostrarlo. Con tres o más
# ganadores, la probabilidad de que el cero sea artefacto de cobertura cae lo
# suficiente como para tratarlo como señal.
#
# No filtra categorías chicas: filtra categorías donde la señal no es
# verificable con los datos que tenemos.
MINIMO_GANADORES_SENAL = 3


# Las categorías que no llegan al piso NO se borran del maestro: se marcan con
# `apto_para_ranking = False`. El índice se calcula igual y la Data App filtra
# por la bandera en su vista por defecto, con opción de desactivarla. Así la
# decisión de alcance es visible y reversible en lugar de quedar escondida en
# una fila que desapareció.

# ---------------------------------------------------------------------------
# Política de reintentos y cortesía con los servidores
# ---------------------------------------------------------------------------
HTTP_TIMEOUT = 30            # segundos por petición
MAX_REINTENTOS = 5           # reintentos ante 429 / 5xx / timeout
BACKOFF_BASE = 2.0           # espera = BACKOFF_BASE ** intento + jitter
PAUSA_ENTRE_CONSULTAS = 1.5  # segundos entre páginas (rate limiting propio)

# ---------------------------------------------------------------------------
# Archivos de salida
# ---------------------------------------------------------------------------
PARQUET_OCDS = PROCESSED_DIR / "ocds_procesos.parquet"
PARQUET_DEMANDA = PROCESSED_DIR / "demanda_por_categoria.parquet"
PARQUET_DENSIDAD = PROCESSED_DIR / "densidad_proveedores.parquet"
PARQUET_PADRON = PROCESSED_DIR / "proveedores_padron.parquet"
PARQUET_DICCIONARIO_CUBSO = PROCESSED_DIR / "diccionario_cubso.parquet"
PARQUET_CONVOCATORIAS = PROCESSED_DIR / "convocatorias_vigentes.parquet"
PARQUET_DOCUMENTOS = PROCESSED_DIR / "documentos_convocatoria.parquet"
PARQUET_CRONOGRAMA = PROCESSED_DIR / "cronograma_convocatoria.parquet"
PARQUET_ESTACIONALIDAD = PROCESSED_DIR / "estacionalidad_categoria.parquet"
PARQUET_MAESTRO = PROCESSED_DIR / "maestro_oportunidades.parquet"

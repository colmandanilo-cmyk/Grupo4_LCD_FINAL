"""
utils.py — Trazabilidad de ejecución y reporte de métricas.

SEPARACIÓN DE RESPONSABILIDADES (corrección solicitada en la revisión T1)
------------------------------------------------------------------------
La revisión observó, con razón, que el log estaba grabando datos y resultados
(una vista previa del dataset maestro escrita con `to_string()`). Un log de
proceso debe registrar QUÉ PASÓ, no QUÉ DATOS SALIERON.

Este módulo separa físicamente ambas cosas:

  logs/   → TRAZABILIDAD. Solo eventos del proceso: inicio y fin de etapa,
            duración, éxito o error, código HTTP, reintentos, archivos
            escritos. Nunca contenido de los datos.

  reports/→ RESULTADOS. Métricas de calidad, conteos, coberturas y vistas
            previas, en formato JSON/CSV consultable. Es el lugar correcto
            para los datos: versionable, legible por máquina y separado del
            registro de operación.

La separación no queda librada a la disciplina del programador: el logger
instala un filtro (`FiltroTrazabilidad`) que rechaza cualquier intento de
escribir un objeto de datos o un texto multilínea. Si un módulo intenta
volcar una tabla al log, el filtro lo bloquea y deja constancia del intento.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import config

# Longitud máxima de un mensaje de trazabilidad. Un evento de proceso se
# describe en una línea; si necesita más, es un dato y no un evento.
MAX_LARGO_MENSAJE = 300

# Tipos que nunca deben llegar al log (se detectan por nombre para no
# importar pandas/numpy aquí y mantener utils.py sin dependencias pesadas).
TIPOS_DE_DATOS = {"DataFrame", "Series", "ndarray", "Index", "ExtensionArray"}


class FiltroTrazabilidad(logging.Filter):
    """Impide que el log reciba datos o resultados.

    Aplica tres reglas, en orden:

    1. Objetos de datos: si algún argumento del mensaje es un DataFrame,
       Series o ndarray, el registro se reemplaza por una advertencia. Esto
       bloquea el patrón `log.info("%s", df)` y también `df.head().to_string()`
       cuando se pasa el objeto directamente.
    2. Texto multilínea: una tabla renderizada siempre contiene saltos de
       línea. Un evento de proceso, nunca. Los mensajes multilínea se
       colapsan y se marcan como bloqueados.
    3. Longitud: todo mensaje se trunca a MAX_LARGO_MENSAJE caracteres.

    El bloqueo se registra como WARNING, de modo que la auditoría del log
    muestre que el control existe y actuó, en vez de perder el evento.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for argumento in (record.args or ()):
            if type(argumento).__name__ in TIPOS_DE_DATOS:
                record.msg = (
                    "[BLOQUEADO] Se intentó escribir un objeto de datos (%s) "
                    "en el log. Los resultados van a reports/, no a logs/."
                    % type(argumento).__name__
                )
                record.args = ()
                record.levelno = logging.WARNING
                record.levelname = "WARNING"
                return True

        mensaje = record.getMessage()

        if "\n" in mensaje or "\r" in mensaje:
            record.msg = (
                "[BLOQUEADO] Se intentó escribir contenido multilínea en el "
                "log (probable volcado de tabla). Los resultados van a reports/."
            )
            record.args = ()
            record.levelno = logging.WARNING
            record.levelname = "WARNING"
            return True

        if len(mensaje) > MAX_LARGO_MENSAJE:
            record.msg = mensaje[:MAX_LARGO_MENSAJE] + " […truncado]"
            record.args = ()

        return True


def crear_logger(nombre: str) -> logging.Logger:
    """Devuelve un logger que escribe a consola y a un archivo por corrida.

    El archivo lleva marca de tiempo (logs/<modulo>_<AAAAMMDD_HHMMSS>.log),
    de modo que cada ejecución sea auditable por separado. El filtro de
    trazabilidad se instala en los dos manejadores.
    """
    logger = logging.getLogger(nombre)
    if logger.handlers:  # evita duplicar manejadores al reimportar
        return logger

    logger.setLevel(logging.INFO)
    formato = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    filtro = FiltroTrazabilidad()

    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = logging.FileHandler(
        config.LOG_DIR / f"{nombre}_{marca}.log", encoding="utf-8"
    )
    archivo.setFormatter(formato)
    archivo.addFilter(filtro)

    consola = logging.StreamHandler()
    consola.setFormatter(formato)
    consola.addFilter(filtro)

    logger.addHandler(archivo)
    logger.addHandler(consola)
    logger.propagate = False
    return logger


class Cronometro:
    """Context manager que cronometra una etapa y registra su desenlace.

    Registra el inicio, y al cerrar informa si la etapa terminó con ÉXITO o
    con ERROR junto con su duración. Ante una excepción deja constancia del
    tipo de error (no del dato que lo provocó) y la vuelve a levantar.

        with Cronometro(log, "descarga OCDS 2025"):
            ...
    """

    def __init__(self, logger: logging.Logger, etapa: str):
        self.log = logger
        self.etapa = etapa
        self.inicio = 0.0

    def __enter__(self) -> "Cronometro":
        self.inicio = time.perf_counter()
        self.log.info("INICIO etapa | %s", self.etapa)
        return self

    def __exit__(self, exc_tipo, exc_valor, tb) -> bool:
        duracion = time.perf_counter() - self.inicio
        if exc_tipo is None:
            self.log.info("FIN etapa | %s | estado=EXITO | duracion=%.2fs",
                          self.etapa, duracion)
        else:
            self.log.error("FIN etapa | %s | estado=ERROR | tipo=%s | duracion=%.2fs",
                           self.etapa, exc_tipo.__name__, duracion)
        return False  # no suprime la excepción


class Reporte:
    """Acumula métricas de una corrida y las escribe en reports/.

    Es la contraparte del log: acá van los números y los resultados que antes
    contaminaban la trazabilidad. La salida es un JSON por corrida, con marca
    de tiempo, más un CSV opcional para las tablas de calidad.

        rep = Reporte("diagnostico")
        rep.metrica("filas_ocds", 228012)
        rep.seccion("calidad_ocds", {"nulos_cubso": 33656})
        rep.guardar()
    """

    def __init__(self, nombre: str):
        self.nombre = nombre
        self.marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.contenido: dict = {
            "modulo": nombre,
            "generado_en": datetime.now().isoformat(timespec="seconds"),
            "metricas": {},
            "secciones": {},
        }

    def metrica(self, clave: str, valor) -> None:
        """Registra una métrica escalar de la corrida."""
        self.contenido["metricas"][clave] = valor

    def seccion(self, clave: str, valor) -> None:
        """Registra un bloque estructurado (dict o lista de dicts)."""
        self.contenido["secciones"][clave] = valor

    def guardar(self) -> Path:
        """Escribe el reporte JSON y devuelve la ruta."""
        destino = config.REPORT_DIR / f"{self.nombre}_{self.marca}.json"
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(self.contenido, f, ensure_ascii=False, indent=2, default=str)
        return destino

    def guardar_tabla(self, df, sufijo: str) -> Path:
        """Escribe una tabla de resultados como CSV dentro de reports/."""
        destino = config.REPORT_DIR / f"{self.nombre}_{sufijo}_{self.marca}.csv"
        df.to_csv(destino, index=False, encoding="utf-8-sig")
        return destino


def registrar_corrida(nombre: str) -> None:
    """Graba la fecha de fin exitoso de un módulo en el metadato versionado.

    Los logs y reportes registran cada corrida en local, pero su contenido no
    viaja con el repositorio: en Streamlit Cloud las carpetas llegan vacías y
    la Data App no puede fechar las corridas desde ahí. Este JSON acompaña a
    los parquet (mismo directorio, mismo commit), de modo que la fecha de
    corrida viaje con el dato que esa corrida produjo.

    Se llama al final exitoso de cada módulo. Si el archivo no existe o está
    corrupto se reconstruye: perder el metadato de módulos anteriores es
    preferible a abortar una corrida que ya terminó bien.
    """
    ruta = config.RUTA_METADATA_CORRIDAS
    datos: dict = {}
    if ruta.exists():
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            if not isinstance(datos, dict):
                datos = {}
        except (json.JSONDecodeError, OSError):
            datos = {}
    datos[nombre] = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8")


def bytes_legibles(n: int | float) -> str:
    """Convierte una cantidad de bytes a una unidad legible."""
    tamanio = float(n)
    for unidad in ("B", "KB", "MB", "GB"):
        if tamanio < 1024 or unidad == "GB":
            return f"{tamanio:.1f} {unidad}"
        tamanio /= 1024
    return f"{tamanio:.1f} GB"


def optimizar_memoria(df, umbral_categoria: float = 0.5) -> tuple:
    """Baja los tipos de un DataFrame al mínimo que representa sus valores.

    QUÉ HACE Y POR QUÉ
    ------------------
    pandas infiere tipos por seguridad, no por eficiencia: un conteo de
    proveedores que nunca pasa de 40 llega como int64 (8 bytes por fila) y una
    descripción CUBSO que se repite miles de veces llega como object, es decir
    un puntero a un string de Python por cada fila. En un dataset de 30 000
    categorías el desperdicio es tolerable; en el detalle OCDS, que ronda las
    230 000 filas por año, ya no.

    Tres reglas, en orden:

      1. Enteros y flotantes: `pd.to_numeric(downcast=...)` elige el tipo más
         chico que representa el rango real de la columna. Nunca amplía.
      2. Texto repetitivo: object o string cuya proporción de valores únicos
         está por debajo de `umbral_categoria` pasa a `category`, que guarda
         cada valor una sola vez y deja códigos enteros en su lugar.
      3. Todo lo demás se deja como está. Un downcast de un float con muchos
         decimales significativos puede perder precisión, así que solo se
         aplica a columnas donde el propio pandas confirma que el valor cabe.

    No modifica el DataFrame recibido: devuelve una copia optimizada más un
    diccionario con el antes y el después, para que el ahorro sea un número
    reportable y no una afirmación.

    Devuelve:
        (df_optimizado, metricas)
    """
    import pandas as pd  # local: mantiene utils.py liviano al importarse

    antes_bytes = int(df.memory_usage(deep=True).sum())
    salida = df.copy()
    cambios = {}

    for col in salida.columns:
        tipo_original = str(salida[col].dtype)
        serie = salida[col]

        if pd.api.types.is_integer_dtype(serie):
            # Int64 con nulos no admite downcast directo; se respeta.
            if not isinstance(serie.dtype, pd.api.extensions.ExtensionDtype):
                salida[col] = pd.to_numeric(serie, downcast="integer")
        elif pd.api.types.is_float_dtype(serie):
            salida[col] = pd.to_numeric(serie, downcast="float")
        elif pd.api.types.is_bool_dtype(serie) or \
                isinstance(serie.dtype, pd.CategoricalDtype):
            continue
        elif pd.api.types.is_object_dtype(serie) or \
                pd.api.types.is_string_dtype(serie):
            no_nulos = serie.dropna()
            if no_nulos.empty:
                continue
            # Las columnas con listas o dicts no son categorizables.
            if isinstance(no_nulos.iloc[0], (list, dict, set)):
                continue
            proporcion_unicos = no_nulos.nunique() / len(no_nulos)
            if proporcion_unicos < umbral_categoria:
                salida[col] = serie.astype("category")

        tipo_nuevo = str(salida[col].dtype)
        if tipo_nuevo != tipo_original:
            cambios[str(col)] = f"{tipo_original} -> {tipo_nuevo}"

    despues_bytes = int(salida.memory_usage(deep=True).sum())
    metricas = {
        "memoria_antes": bytes_legibles(antes_bytes),
        "memoria_despues": bytes_legibles(despues_bytes),
        "ahorro_pct": round(100 * (1 - despues_bytes / max(antes_bytes, 1)), 1),
        "columnas_modificadas": cambios,
    }
    return salida, metricas


def limpiar_antiguos(dias_retencion: int = 30) -> dict:
    """Borra logs y reportes con más de `dias_retencion` días de antigüedad.

    Evita que las corridas automáticas diarias acumulen archivos sin límite.
    Los datos (Parquet) NO se tocan: solo la trazabilidad y las métricas
    envejecen. Devuelve un conteo de lo borrado para registrarlo.
    """
    import time as _time

    limite = _time.time() - dias_retencion * 86400
    borrados = {"logs": 0, "reports": 0}
    for carpeta, clave in ((config.LOG_DIR, "logs"),
                           (config.REPORT_DIR, "reports")):
        for archivo in carpeta.glob("*"):
            if archivo.name == ".gitkeep":
                continue
            if archivo.is_file() and archivo.stat().st_mtime < limite:
                archivo.unlink()
                borrados[clave] += 1
    return borrados

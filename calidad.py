"""
calidad.py — Métricas de calidad de datos.

DE DÓNDE SALE ESTE MÓDULO
-------------------------
El Tema 3 define seis métricas para medir el estado de un dataset ANTES de
limpiarlo o transformarlo: completitud, unicidad, validez, consistencia,
exactitud y actualidad. Este módulo las implementa sobre los datasets del
proyecto en lugar del CSV de ventas de clase.

QUÉ LO DIFERENCIA DE validacion.py
----------------------------------
Los dos miran los mismos datos pero contestan preguntas distintas y en momentos
distintos del pipeline.

  calidad.py    MIDE. Devuelve porcentajes y conteos: cuánto le falta a este
                dataset, cuán vigente está. Nunca rechaza una fila. Su salida
                es un diagnóstico que se compara entre corridas para ver si la
                fuente se degradó.

  validacion.py DECIDE. Aplica esquemas Pandera y reglas de negocio, y corta el
                pipeline si el porcentaje de rechazo supera la tolerancia.

Se mide primero y se valida después: si la completitud de `monto_adjudicado`
cae del 98 % al 40 % de un mes a otro, eso se ve en la métrica aunque cada fila
individual siga pasando el esquema.

SIN ITERACIÓN POR FILAS
-----------------------
Todas las métricas se calculan con operaciones sobre columnas completas
(`notna()`, `duplicated()`, `between()`, `isin()`, comparaciones booleanas).
No hay un solo recorrido fila por fila: sobre el detalle OCDS, que tiene
cientos de miles de filas, la diferencia entre una máscara booleana y un bucle
de Python es de dos órdenes de magnitud.

Uso:
    python calidad.py
"""

from __future__ import annotations

import pandas as pd

import config
from utils import Cronometro, Reporte, crear_logger

log = crear_logger("calidad")

# Dominios permitidos: cualquier valor fuera de estas listas indica que la
# fuente cambió de catálogo o que hubo un error de carga.
MONEDAS_VALIDAS = ["PEN", "USD", "EUR"]
ESTADOS_AWARD_VALIDOS = ["active", "cancelled", "unsuccessful", "pending"]
TIPOS_OBJETO_VALIDOS = ["goods", "services", "works"]

# Cotas de plausibilidad para la métrica de exactitud. No son límites legales:
# son detectores de error de unidad (montos cargados en céntimos, comas
# corridas). Un contrato público por debajo de un sol o por encima de cinco mil
# millones es un dato mal cargado, no un contrato.
MONTO_MINIMO_PLAUSIBLE = 1
MONTO_MAXIMO_PLAUSIBLE = 5_000_000_000

# Umbral de actualidad: si el dato más reciente tiene más de estos días, la
# fuente dejó de actualizarse y el tablero está mostrando historia vieja.
DIAS_PARA_CONSIDERAR_VIGENTE = 120


# ---------------------------------------------------------------------------
# Métrica 1 — Completitud
# ---------------------------------------------------------------------------
def completitud(df: pd.DataFrame) -> dict:
    """Porcentaje de valores no nulos, por columna y global.

    `notna()` devuelve una matriz booleana del tamaño del DataFrame y `mean()`
    la promedia por columna en una sola pasada de NumPy.
    """
    por_columna = (df.notna().mean() * 100).round(2)
    return {
        "global_pct": round(float(df.notna().to_numpy().mean() * 100), 2),
        "por_columna_pct": por_columna.to_dict(),
        "columnas_incompletas": por_columna[por_columna < 100].sort_values().to_dict(),
        "columnas_vacias": por_columna[por_columna == 0].index.tolist(),
    }


# ---------------------------------------------------------------------------
# Métrica 2 — Unicidad
# ---------------------------------------------------------------------------
def unicidad(df: pd.DataFrame, clave: str | list[str]) -> dict:
    """Proporción de registros no duplicados según la clave de negocio.

    Se mide contra la clave, no contra la fila completa: dos filas idénticas en
    todas sus columnas son un problema evidente, pero dos filas con el mismo
    identificador y datos distintos son un problema peor y solo se ve así.
    """
    claves = [clave] if isinstance(clave, str) else clave
    presentes = [c for c in claves if c in df.columns]
    if not presentes:
        return {"aplicable": False, "motivo": f"clave ausente: {claves}"}

    duplicados = int(df.duplicated(subset=presentes).sum())
    total = len(df)
    return {
        "aplicable": True,
        "clave": presentes,
        "registros": total,
        "duplicados": duplicados,
        "unicidad_pct": round(100 * (total - duplicados) / max(total, 1), 2),
    }


# ---------------------------------------------------------------------------
# Métrica 3 — Validez
# ---------------------------------------------------------------------------
def validez(df: pd.DataFrame) -> dict:
    """Proporción de valores que pertenecen a los dominios permitidos.

    Cada comprobación es una máscara booleana sobre la columna completa. Se
    excluyen los nulos del denominador: un valor ausente es un problema de
    completitud, no de validez, y mezclarlos hace que las dos métricas se
    contaminen.
    """
    resultados = {}

    def dominio(columna: str, permitidos: list) -> None:
        if columna not in df.columns:
            return
        serie = df[columna].dropna()
        if serie.empty:
            return
        fuera = ~serie.astype("string").isin(permitidos)
        resultados[columna] = {
            "evaluados": int(serie.size),
            "fuera_de_dominio": int(fuera.sum()),
            "validez_pct": round(100 * (1 - fuera.mean()), 2),
            "valores_no_esperados": serie[fuera].astype("string")
                                    .value_counts().head(5).to_dict(),
        }

    dominio("moneda", MONEDAS_VALIDAS)
    dominio("estado_award", ESTADOS_AWARD_VALIDOS)
    dominio("tipo_objeto", TIPOS_OBJETO_VALIDOS)

    # El RUC peruano tiene 11 dígitos. En OCDS llega prefijado como
    # "PE-RUC-20123456789", así que se valida el sufijo.
    if "proveedor_id" in df.columns:
        rucs = df["proveedor_id"].dropna().astype("string")
        sufijo = rucs.str.extract(r"(\d{8,})$", expand=False)
        bien_formado = sufijo.str.len().eq(11).fillna(False)
        resultados["proveedor_id"] = {
            "evaluados": int(rucs.size),
            "fuera_de_dominio": int((~bien_formado).sum()),
            "validez_pct": round(100 * bien_formado.mean(), 2),
            "regla": "sufijo numérico de 11 dígitos (RUC)",
        }

    return resultados


# ---------------------------------------------------------------------------
# Métrica 4 — Consistencia
# ---------------------------------------------------------------------------
def consistencia(df: pd.DataFrame) -> dict:
    """Coherencia lógica entre columnas del mismo registro.

    Son las incoherencias que ninguna comprobación columna por columna puede
    ver: cada regla cruza al menos dos campos.
    """
    resultados = {}

    # Un proceso con monto adjudicado tiene que tener categoría CUBSO: es lo
    # que permite agregarlo. Si falta, el monto se pierde en la agregación.
    if {"monto_adjudicado", "cubso_descripcion"} <= set(df.columns):
        huerfanos = (df["monto_adjudicado"].notna()
                     & df["cubso_descripcion"].isna())
        resultados["monto_sin_categoria"] = {
            "registros": int(huerfanos.sum()),
            "pct": round(100 * huerfanos.mean(), 2),
            "impacto": "el monto no entra en ninguna categoría del radar",
        }

    # Una adjudicación activa declara proveedor. Si no lo trae, la capa de
    # adjudicados queda incompleta para esa categoría.
    if {"estado_award", "proveedor_id"} <= set(df.columns):
        activos = df["estado_award"].astype("string") == "active"
        sin_proveedor = activos & df["proveedor_id"].isna()
        resultados["adjudicacion_activa_sin_proveedor"] = {
            "registros": int(sin_proveedor.sum()),
            "pct_sobre_activos": round(
                100 * sin_proveedor.sum() / max(int(activos.sum()), 1), 2),
        }

    # El año derivado tiene que coincidir con la fecha de la que se derivó.
    if {"fecha", "anio"} <= set(df.columns):
        con_fecha = df["fecha"].notna() & df["anio"].notna()
        desalineados = con_fecha & (df["fecha"].dt.year != df["anio"])
        resultados["anio_no_coincide_con_fecha"] = {
            "registros": int(desalineados.sum()),
            "pct": round(100 * desalineados.mean(), 2),
        }

    # En el agregado: no puede haber demanda sin procesos que la expliquen.
    if {"demanda_soles", "n_procesos"} <= set(df.columns):
        imposible = (df["demanda_soles"] > 0) & (df["n_procesos"].fillna(0) <= 0)
        resultados["demanda_sin_procesos"] = {
            "registros": int(imposible.sum()),
            "pct": round(100 * imposible.mean(), 2),
        }

    return resultados


# ---------------------------------------------------------------------------
# Métrica 5 — Exactitud
# ---------------------------------------------------------------------------
def exactitud(df: pd.DataFrame, columnas_numericas: list[str] | None = None) -> dict:
    """Plausibilidad de los valores numéricos.

    Dos lecturas complementarias. La cota fija detecta errores de unidad, que
    son binarios: un monto de S/ 0.03 o de S/ 90 000 millones está mal cargado.
    El IQR detecta valores extremos relativos a la propia distribución, que en
    compras públicas casi nunca son errores (los megaproyectos existen) pero sí
    conviene tener contados antes de escalar.
    """
    resultados = {}

    if columnas_numericas is None:
        columnas_numericas = [c for c in ("monto_adjudicado", "demanda_soles",
                                          "ticket_promedio")
                              if c in df.columns]

    for columna in columnas_numericas:
        if columna not in df.columns:
            continue
        serie = pd.to_numeric(df[columna], errors="coerce").dropna()
        if serie.empty:
            continue

        implausibles = ~serie.between(MONTO_MINIMO_PLAUSIBLE,
                                      MONTO_MAXIMO_PLAUSIBLE)
        q1, q3 = serie.quantile([0.25, 0.75])
        iqr = q3 - q1
        atipicos = ~serie.between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)

        resultados[columna] = {
            "evaluados": int(serie.size),
            "fuera_de_cota": int(implausibles.sum()),
            "exactitud_pct": round(100 * (1 - implausibles.mean()), 2),
            "atipicos_iqr": int(atipicos.sum()),
            "atipicos_iqr_pct": round(100 * atipicos.mean(), 2),
            "limite_superior_iqr": round(float(q3 + 1.5 * iqr), 2),
        }

    return resultados


# ---------------------------------------------------------------------------
# Métrica 6 — Actualidad
# ---------------------------------------------------------------------------
def actualidad(df: pd.DataFrame, columna_fecha: str = "fecha") -> dict:
    """Antigüedad del dato más reciente.

    Es la métrica que más importa en este proyecto y la que ningún esquema
    detecta: un pipeline puede correr sin un solo error y estar publicando
    datos de hace un año porque la fuente dejó de replicarse. El OCDS del OECE
    se replica mensualmente, así que un desfase de pocas semanas es normal y
    uno de varios meses no lo es.
    """
    if columna_fecha not in df.columns:
        return {"aplicable": False, "motivo": f"sin columna {columna_fecha}"}

    fechas = pd.to_datetime(df[columna_fecha], errors="coerce", utc=True).dropna()
    if fechas.empty:
        return {"aplicable": False, "motivo": "sin fechas válidas"}

    ahora = pd.Timestamp.now(tz="UTC")
    mas_reciente = fechas.max()
    dias = int((ahora - mas_reciente).days)

    return {
        "aplicable": True,
        "fecha_mas_antigua": str(fechas.min().date()),
        "fecha_mas_reciente": str(mas_reciente.date()),
        "dias_de_desfase": dias,
        "vigente": bool(dias <= DIAS_PARA_CONSIDERAR_VIGENTE),
        "umbral_dias": DIAS_PARA_CONSIDERAR_VIGENTE,
    }


# ---------------------------------------------------------------------------
# Perfil consolidado
# ---------------------------------------------------------------------------
def perfil_completo(df: pd.DataFrame, nombre: str,
                    clave: str | list[str] = "cubso_descripcion") -> dict:
    """Aplica las seis métricas y calcula un puntaje agregado.

    El puntaje promedia las métricas expresables en porcentaje. No pretende ser
    un indicador científico: sirve para comparar la misma fuente entre corridas
    y detectar degradación. Su valor está en la serie, no en el número aislado.
    """
    perfil = {
        "dataset": nombre,
        "filas": int(len(df)),
        "columnas": int(df.shape[1]),
        "completitud": completitud(df),
        "unicidad": unicidad(df, clave),
        "validez": validez(df),
        "consistencia": consistencia(df),
        "exactitud": exactitud(df),
        "actualidad": actualidad(df),
    }

    componentes = [perfil["completitud"]["global_pct"]]
    if perfil["unicidad"].get("aplicable"):
        componentes.append(perfil["unicidad"]["unicidad_pct"])
    componentes += [v["validez_pct"] for v in perfil["validez"].values()]
    componentes += [v["exactitud_pct"] for v in perfil["exactitud"].values()]

    perfil["puntaje_calidad"] = round(sum(componentes) / len(componentes), 2)
    perfil["metricas_promediadas"] = len(componentes)
    return perfil


def registrar_en_log(perfil: dict) -> None:
    """Deja constancia de la medición en el log de trazabilidad.

    Una línea por métrica, porque el filtro de utils.py bloquea el texto
    multilínea: al log van eventos, y el detalle completo va al reporte JSON.
    Lo que se registra acá es el HECHO de que la métrica se calculó y su
    resultado resumido, que es exactamente lo que un auditor busca en un log.
    """
    nombre = perfil["dataset"]
    log.info("CALIDAD | dataset=%s | filas=%d | puntaje=%.2f",
             nombre, perfil["filas"], perfil["puntaje_calidad"])
    log.info("CALIDAD | dataset=%s | metrica=completitud | global=%.2f%% | "
             "columnas_incompletas=%d", nombre,
             perfil["completitud"]["global_pct"],
             len(perfil["completitud"]["columnas_incompletas"]))

    uni = perfil["unicidad"]
    if uni.get("aplicable"):
        log.info("CALIDAD | dataset=%s | metrica=unicidad | unicidad=%.2f%% | "
                 "duplicados=%d", nombre, uni["unicidad_pct"], uni["duplicados"])

    for columna, datos in perfil["validez"].items():
        log.info("CALIDAD | dataset=%s | metrica=validez | columna=%s | "
                 "validez=%.2f%% | fuera_dominio=%d",
                 nombre, columna, datos["validez_pct"], datos["fuera_de_dominio"])

    for regla, datos in perfil["consistencia"].items():
        log.info("CALIDAD | dataset=%s | metrica=consistencia | regla=%s | "
                 "registros=%d", nombre, regla, datos["registros"])

    for columna, datos in perfil["exactitud"].items():
        log.info("CALIDAD | dataset=%s | metrica=exactitud | columna=%s | "
                 "exactitud=%.2f%% | atipicos_iqr=%d",
                 nombre, columna, datos["exactitud_pct"], datos["atipicos_iqr"])

    act = perfil["actualidad"]
    if act.get("aplicable"):
        log.info("CALIDAD | dataset=%s | metrica=actualidad | desfase_dias=%d | "
                 "vigente=%s", nombre, act["dias_de_desfase"], act["vigente"])


def resumen_tabular(perfiles: list[dict]) -> pd.DataFrame:
    """Arma la tabla comparativa de calidad entre datasets.

    Es la vista que va al CSV de reports/ y la que se muestra en el notebook.
    """
    filas = [{
        "dataset": p["dataset"],
        "filas": p["filas"],
        "columnas": p["columnas"],
        "completitud_pct": p["completitud"]["global_pct"],
        "unicidad_pct": p["unicidad"].get("unicidad_pct"),
        "duplicados": p["unicidad"].get("duplicados"),
        "reglas_consistencia_incumplidas": sum(
            1 for v in p["consistencia"].values() if v["registros"] > 0),
        "desfase_dias": p["actualidad"].get("dias_de_desfase"),
        "puntaje_calidad": p["puntaje_calidad"],
    } for p in perfiles]
    return pd.DataFrame(filas)


def main() -> None:
    log.info("INICIO medicion de calidad")
    reporte = Reporte("calidad")

    fuentes = [
        (config.PARQUET_OCDS, "ocds_procesos", ["ocid", "cubso_id", "proveedor_id"]),
        (config.PARQUET_DEMANDA, "demanda_por_categoria", "cubso_descripcion"),
        (config.PARQUET_DENSIDAD, "densidad_proveedores", "cubso_descripcion"),
        (config.PARQUET_CONVOCATORIAS, "convocatorias_vigentes", "ocid"),
        (config.PARQUET_MAESTRO, "maestro_oportunidades", "cubso_descripcion"),
    ]

    perfiles = []
    for ruta, nombre, clave in fuentes:
        if not ruta.exists():
            log.warning("Dataset ausente | %s | se omite", ruta.name)
            continue
        with Cronometro(log, f"calidad de {nombre}"):
            perfil = perfil_completo(pd.read_parquet(ruta), nombre, clave)
            registrar_en_log(perfil)
            reporte.seccion(f"calidad_{nombre}", perfil)
            perfiles.append(perfil)

    if perfiles:
        tabla = resumen_tabular(perfiles)
        ruta_csv = reporte.guardar_tabla(tabla, "resumen_calidad")
        log.info("Tabla comparativa escrita | %s", ruta_csv.name)
        reporte.metrica("puntaje_promedio",
                        round(float(tabla["puntaje_calidad"].mean()), 2))

    ruta = reporte.guardar()
    log.info("Reporte de metricas escrito | %s", ruta.name)
    log.info("FIN medicion de calidad | estado=EXITO")


if __name__ == "__main__":
    main()

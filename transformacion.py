"""
transformacion.py — Enriquecimiento interno, binning y escalado.

QUÉ HACE ESTE MÓDULO
--------------------
Toma el dataset maestro ya integrado (demanda × densidad × convocatorias) y le
aplica las transformaciones que convierten cifras crudas en una señal
ordenable. Tres bloques, en este orden:

  1. ENRIQUECIMIENTO INTERNO — variables derivadas del propio dataset, sin
     fuentes nuevas. Incluye la explotación de la columna `fecha` del OCDS,
     que hasta ahora se guardaba y no se usaba: de ahí salen el mes pico de
     cada categoría y su grado de estacionalidad.

  2. BINNING — corta variables continuas en bandas interpretables. El usuario
     del radar no filtra por "ticket ≤ 43 750"; filtra por "contratos que mi
     empresa puede asumir". Las bandas de ticket se anclan en la UIT porque es
     la unidad con la que la propia normativa mide el tamaño de un contrato.

  3. ESCALADO E ÍNDICE — lleva las tres señales a una escala común y las
     combina en un puntaje de 0 a 100.

POR QUÉ MIN-MAX SOBRE log1p Y NO Z-SCORE
----------------------------------------
La demanda del Estado por categoría CUBSO tiene cola muy larga: unas pocas
categorías (obras, medicamentos, combustible) concentran órdenes de magnitud
más monto que el resto. Eso descarta las dos opciones directas.

Min-Max crudo le da 1.0 a la categoría mayor y apelmaza el resto contra el
cero. En la corrida de referencia el 97 % de las categorías quedaba por debajo
de 0.05, o sea que el índice deja de discriminar justo en el tramo donde vive
una MYPE.

Z-Score aguanta mejor la cola (por eso la teoría lo recomienda ante outliers),
pero devuelve valores negativos y sin cota. Al combinar tres componentes
ponderados, un puntaje de −1.8 no se interpreta en un tablero, y el componente
con más varianza termina dominando el orden sin que se note.

Aplicar log1p ANTES del Min-Max resuelve las dos cosas: el logaritmo comprime
la cola, con lo cual la sensibilidad de Min-Max a los extremos deja de ser un
problema, y el resultado queda acotado en [0, 1], que es la escala en la que ya
vive el otro componente del índice (`espacio_mercado`). Los dos términos entran
al índice medidos en la misma unidad, que es lo que hace legible su ponderación.

El Z-Score no se descarta. Se calcula sobre la demanda como variable de
DIAGNÓSTICO (`demanda_z`) para marcar categorías atípicas en el tablero
("esta categoría está 2.4 desviaciones sobre la media"). Ahí su falta de cota
es una ventaja. Las tres distribuciones se comparan en el reporte de la corrida
para que la elección quede documentada con números y no con una afirmación.

Uso:
    python transformacion.py          # se ejecuta sobre el maestro existente
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config
from utils import Cronometro, Reporte, crear_logger, optimizar_memoria, registrar_corrida

log = crear_logger("transformacion")

# Un mes concentra la demanda de la categoría si supera este porcentaje del
# total anual. Con 12 meses, el reparto plano da 8.3 % por mes; 25 % es tres
# veces eso, umbral suficiente para hablar de temporada.
UMBRAL_MES_PICO = 0.25

# Meses con actividad que una categoría debe tener para que la marca de
# estacionalidad signifique algo. Con menos de seis meses activos, un pico del
# 25 % es compatible con un reparto plano (una categoría con cuatro meses de
# movimiento reparte 25 % por mes sin ninguna temporada), así que la marca
# saltaría por bajo volumen y no por concentración real.
MINIMO_MESES_ACTIVOS = 6


# ---------------------------------------------------------------------------
# 1. ENRIQUECIMIENTO INTERNO
# ---------------------------------------------------------------------------
def estacionalidad_por_categoria(ocds: pd.DataFrame) -> pd.DataFrame:
    """Deriva el perfil temporal de cada categoría a partir de `fecha`.

    La ingesta ya guardaba la fecha de cada proceso pero nadie la usaba: la
    agregación de demanda la descartaba al agrupar por categoría. Acá se
    recupera esa dimensión, que es la que responde CUÁNDO conviene prepararse,
    no solo dónde.

    Produce, por categoría CUBSO:
        mes_pico            mes con mayor monto adjudicado (1-12)
        concentracion_mes   proporción del monto anual que cae en ese mes
        es_estacional       flag: concentra >=25 % del año en su mes pico Y
                            tiene al menos MINIMO_MESES_ACTIVOS meses activos
        meses_activos       en cuántos meses distintos hubo adjudicaciones
    """
    base = ocds.dropna(subset=["cubso_descripcion", "monto_adjudicado", "fecha"])
    if base.empty:
        return pd.DataFrame(columns=["cubso_descripcion", "mes_pico",
                                     "concentracion_mes", "es_estacional",
                                     "meses_activos"])

    base = base.assign(mes=base["fecha"].dt.month)

    # Agregación por categoría y mes: la operación es vectorizada, un groupby
    # sobre toda la tabla, no un bucle por categoría.
    por_mes = (base.groupby(["cubso_descripcion", "mes"], observed=True)
               ["monto_adjudicado"].sum().reset_index())

    total = por_mes.groupby("cubso_descripcion", observed=True)[
        "monto_adjudicado"].transform("sum")
    por_mes["participacion"] = por_mes["monto_adjudicado"] / total.replace(0, np.nan)

    # idxmax sobre el grupo devuelve la fila del mes pico sin iterar.
    indice_pico = por_mes.groupby("cubso_descripcion", observed=True)[
        "monto_adjudicado"].idxmax()
    pico = por_mes.loc[indice_pico, ["cubso_descripcion", "mes", "participacion"]]
    pico = pico.rename(columns={"mes": "mes_pico",
                                "participacion": "concentracion_mes"})

    activos = (por_mes.groupby("cubso_descripcion", as_index=False, observed=True)
               .agg(meses_activos=("mes", "nunique")))

    perfil = pico.merge(activos, on="cubso_descripcion", how="left")
    perfil["es_estacional"] = (
        (perfil["concentracion_mes"] >= UMBRAL_MES_PICO)
        & (perfil["meses_activos"] >= MINIMO_MESES_ACTIVOS)
    )
    perfil["mes_pico"] = perfil["mes_pico"].astype("Int8")
    perfil["concentracion_mes"] = perfil["concentracion_mes"].round(4)
    return perfil


def enriquecer(maestro: pd.DataFrame, perfil_temporal: pd.DataFrame | None
               ) -> pd.DataFrame:
    """Agrega las variables derivadas al maestro.

    Todas salen de columnas que ya están en el dataset. No hay fuente nueva:
    eso es lo que distingue el enriquecimiento interno de una integración.
    """
    df = maestro.copy()

    # --- Variables derivadas de la propia fila -----------------------------
    # Ticket en UIT: la misma cifra que `ticket_promedio` pero en la unidad
    # que usa la normativa, así el usuario compara contra los umbrales legales
    # que ya conoce en lugar de traducir soles mentalmente.
    df["ticket_uit"] = (df["ticket_promedio"] / config.UIT_SOLES).round(2)

    # ESPACIO DE MERCADO — cuántos competidores quedan en carrera
    # ----------------------------------------------------------
    # Se construye sobre `competencia_vigente`: los adjudicatarios de la
    # categoría que siguen habilitados en el RNP. Es el cruce del OCDS con la
    # ficha, y contesta lo que ninguna de las dos fuentes contesta sola.
    #
    # Antes se usaba la saturación (adjudicados de la categoría sobre
    # habilitados del capítulo). Se descartó porque divide dos universos
    # distintos: el numerador se cuenta por categoría CUBSO y el denominador
    # por capítulo RNP, que agrupa miles de categorías. El cociente quedaba en
    # el orden de 0.0001 para todo el catálogo y no ordenaba nada. El conteo de
    # habilitados por capítulo se conserva como contexto del sector, que es
    # para lo que sirve: solo toma cuatro valores.
    #
    # El logaritmo va antes de invertir por el mismo motivo que del lado de la
    # demanda: la competencia tiene cola larga (mediana 1, máximo 1334) y sin
    # comprimirla la categoría más disputada aplastaría al resto contra el 1.
    competencia = df["competencia_vigente"].astype("float64")
    comp_log = np.log1p(competencia)
    rango = comp_log.max() - comp_log.min()
    df["espacio_mercado"] = (
        1 - (comp_log - comp_log.min()) / rango if rango else 1.0
    ).round(4)

    # Donde ningún adjudicatario tiene RUC de once dígitos no hay cruce posible
    # con la ficha (consorcios, personas naturales bajo otro formato). Esas
    # categorías caen al sucedáneo de concentración en lugar de recibir un cero
    # que se leería como mercado vacío, y queda registro de cuáles son.
    sin_cruce = df["espacio_mercado"].isna()
    if sin_cruce.any():
        conc = df.loc[sin_cruce, "concentracion"].astype("float64")
        df.loc[sin_cruce, "espacio_mercado"] = (
            1 / (1 + conc.fillna(conc.median()))
        ).round(4)
    df["origen_espacio"] = np.where(sin_cruce, "concentracion",
                                    "competencia_vigente")

    # --- Piso de mercado: qué entra al ranking -----------------------------
    # Se marca, no se borra. Ver la justificación en config.py.
    demanda_uit = df["demanda_soles"] / config.UIT_SOLES
    apto = (
        (df["n_procesos"] >= config.MINIMO_PROCESOS_MERCADO)
        & (demanda_uit >= config.MINIMO_DEMANDA_UIT_MERCADO)
    )

    # Tercer criterio: cuántos ganadores históricos respaldan la señal.
    #
    # `espacio_mercado` se construye sobre `competencia_vigente`, que cuenta
    # adjudicatarios que siguen habilitados. Ese conteo depende de dos cruces
    # imperfectos y medidos: la ficha del RNP cubre el 80,7% de los
    # adjudicatarios, y solo el 77% de los `proveedor_id` trae RUC de once
    # dígitos (consorcios y personas naturales quedan fuera).
    #
    # En una categoría con dos ganadores, un `competencia_vigente` igual a cero
    # es indistinguible de no tener la ficha de ninguno de los dos. El índice
    # lo premiaría como mercado desierto sin poder demostrarlo. Con tres o más
    # ganadores la probabilidad de que el cero sea artefacto de cobertura cae
    # lo suficiente como para tratarlo como señal.
    #
    # No filtra categorías chicas: filtra categorías donde la señal no es
    # verificable. El umbral se lee de config.py cuando está declarado.
    minimo_ganadores = getattr(config, "MINIMO_GANADORES_SENAL", 3)
    if "ganadores_historicos" in df.columns:
        respaldo = pd.to_numeric(df["ganadores_historicos"], errors="coerce").fillna(0)
        apto &= respaldo >= minimo_ganadores

    df["apto_para_ranking"] = apto

    # --- Variables derivadas del cruce temporal ----------------------------
    if perfil_temporal is not None and not perfil_temporal.empty:
        # El módulo lee y escribe el mismo maestro, de modo que una segunda
        # corrida encuentra las columnas del perfil ya presentes. Sin
        # descartarlas, el merge las duplicaría con sufijos _x/_y y el acceso
        # posterior fallaría. Se eliminan para que mande siempre el perfil
        # recién calculado sobre el OCDS vigente.
        columnas_perfil = [
            c for c in perfil_temporal.columns if c != "cubso_descripcion"
        ]
        previas = [c for c in columnas_perfil if c in df.columns]
        if previas:
            df = df.drop(columns=previas)
        df = df.merge(perfil_temporal, on="cubso_descripcion", how="left")
        df["es_estacional"] = df["es_estacional"].fillna(False)
    else:
        for col, valor in (("mes_pico", pd.NA), ("concentracion_mes", pd.NA),
                           ("meses_activos", pd.NA), ("es_estacional", False)):
            df[col] = valor

    return df


# ---------------------------------------------------------------------------
# 2. BINNING
# ---------------------------------------------------------------------------
def aplicar_binning(df: pd.DataFrame) -> pd.DataFrame:
    """Corta las variables continuas en bandas que el usuario pueda filtrar.

    Se usan las dos formas de discretización, cada una donde corresponde:

      pd.cut  → banda de ticket. Los cortes vienen de afuera del dato (la UIT
                y el umbral de 8 UIT de la contratación menor), así que son
                fijos y comparables entre corridas. Si el año que viene el
                catálogo cambia, la banda "Contratación menor" sigue
                significando lo mismo.

      pd.qcut → cuartil de demanda. Acá el corte SÍ debe depender del dato,
                porque la pregunta es relativa: en qué cuarto del catálogo cae
                esta categoría. Un corte fijo en soles envejecería con la
                inflación y con el crecimiento del presupuesto.
    """
    salida = df.copy()

    # --- Bandas de ticket (cortes normativos) ------------------------------
    salida["banda_ticket"] = pd.cut(
        salida["ticket_uit"],
        bins=config.BANDAS_TICKET_UIT,
        labels=config.BANDAS_TICKET_ETIQUETAS,
        include_lowest=True,
    )

    # --- Cuartil de demanda (cortes empíricos) -----------------------------
    # duplicates="drop" evita que qcut reviente cuando muchas categorías
    # comparten el mismo monto y los bordes de cuartil coinciden.
    try:
        salida["cuartil_demanda"] = pd.qcut(
            salida["demanda_soles"], q=4,
            labels=["Q1 (menor)", "Q2", "Q3", "Q4 (mayor)"],
            duplicates="drop",
        )
    except ValueError:
        log.warning("qcut sin cortes distintos | cuartil_demanda no calculado")
        salida["cuartil_demanda"] = pd.NA

    # --- Banda de competencia (conteo, no proporción) ----------------------
    # Se corta sobre `competencia_vigente`, el conteo crudo de competidores que
    # siguen habilitados, y no sobre `espacio_mercado`, que es su versión
    # logarítmica y normalizada.
    #
    # El motivo es que esta columna se lee en pantalla. "Poca competencia (1-2)"
    # dice algo verificable: el usuario puede pedir la lista de esas dos
    # empresas. Una banda cortada sobre la variable escalada daría "entre las
    # menos disputadas del catálogo", que es una posición relativa y no permite
    # saber contra cuántos se compite. Los cortes en 0, 2 y 5 no son
    # percentiles: son las cantidades a las que cambia la conversación
    # comercial. La variable escalada sigue existiendo y alimenta el índice; es
    # ahí donde su forma continua sirve.
    salida["banda_competencia"] = pd.cut(
        salida["competencia_vigente"].astype("float64"),
        bins=config.BANDAS_COMPETENCIA,
        labels=config.BANDAS_COMPETENCIA_ETIQUETAS,
    ).astype("object")

    # Donde no hubo cruce con la ficha (ningún adjudicatario con RUC de once
    # dígitos) no se inventa una banda: se declara que el dato falta. Poner
    # "Sin adjudicatario vigente" ahí sería el error más caro del tablero,
    # porque es justo la etiqueta que el radar recomienda mirar primero.
    salida["banda_competencia"] = (
        salida["banda_competencia"].fillna("Competencia no determinada")
    )

    return salida


# ---------------------------------------------------------------------------
# 3. ESCALADO E ÍNDICE DE OPORTUNIDAD
# ---------------------------------------------------------------------------
def _minmax(serie: pd.Series) -> pd.Series:
    """Min-Max manual: (x - min) / (max - min), con guarda para rango cero."""
    s = serie.astype("float64")
    minimo, maximo = s.min(), s.max()
    if pd.isna(minimo) or maximo == minimo:
        return pd.Series(0.5, index=s.index)  # sin variación: todo al centro
    return (s - minimo) / (maximo - minimo)


def _zscore(serie: pd.Series) -> pd.Series:
    """Z-Score manual: (x - μ) / σ, con guarda para desviación cero."""
    s = serie.astype("float64")
    sigma = s.std()
    if pd.isna(sigma) or sigma == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / sigma


def escalar(df: pd.DataFrame, reporte: Reporte) -> pd.DataFrame:
    """Escala las tres señales y construye el índice de oportunidad.

    Deja en el DataFrame las columnas intermedias (`demanda_escalada`,
    `accesibilidad`, `potencial_mercado`) además del índice final. Son las
    que permiten
    explicar en la sustentación por qué una categoría quedó donde quedó, en vez
    de mostrar un puntaje que hay que creer.
    """
    salida = df.copy()

    # --- Componente 1: demanda, con log previo -----------------------------
    salida["demanda_log"] = np.log1p(salida["demanda_soles"].clip(lower=0))
    salida["demanda_escalada"] = _minmax(salida["demanda_log"]).round(4)

    # Z-Score como DIAGNÓSTICO, no como componente del índice: se compara con
    # las otras dos alternativas de escalado en el reporte de la corrida.
    salida["demanda_z"] = _zscore(salida["demanda_log"]).round(3)

    # --- Componente 2: espacio de mercado ----------------------------------
    # `espacio_mercado` ya viene en [0,1] desde enriquecer(), invertido y con
    # logaritmo previo, así que entra directo. No hace falta un percentil
    # intermedio: la variable de base (competencia vigente por categoría) tiene
    # variación real, de 0 a 1334 competidores.
    salida["espacio_escalado"] = salida["espacio_mercado"].clip(0, 1).round(4)

    # --- Componente 3: accesibilidad del ticket ----------------------------
    # ACCESIBILIDAD COMO FACTOR, NO COMO SUMANDO
    # ------------------------------------------
    # La primera versión la trataba como un tercer término ponderado al 20 %,
    # comprimido además por logaritmo. El resultado, con datos reales, fue que
    # el top del ranking se llenó de obras de saneamiento y puentes con tickets
    # de entre 200 y 8 000 UIT: la demanda enorme compensaba de sobra el
    # castigo por tamaño.
    #
    # El error era conceptual. Para quien usa el radar, poder asumir el
    # contrato no es una virtud que se compensa con otras: es una condición
    # previa. Un mercado de mil millones al que una MYPE no puede entrar no es
    # una oportunidad grande, es una oportunidad nula. Por eso ahora multiplica
    # en lugar de sumar, y una categoría inaccesible no puede llegar arriba por
    # mucha demanda que tenga.
    #
    # El factor sale de las bandas de UIT y no de la distribución observada.
    # Un corte por percentiles diría "esta categoría es más accesible que el
    # 70 % de las demás", que no le sirve a nadie: lo que el proveedor necesita
    # saber es si el contrato entra en su capacidad, y esa referencia es
    # normativa, no estadística.
    salida["accesibilidad"] = (
        salida["banda_ticket"].astype("string")
        .map(config.FACTOR_ACCESIBILIDAD).astype("float64")
        .fillna(config.FACTOR_ACCESIBILIDAD_DESCONOCIDO)
    )

    # --- Índice compuesto ---------------------------------------------------
    # Demanda y espacio se combinan con pesos que suman 1 (potencial de
    # mercado); la accesibilidad multiplica ese potencial (cuánto de él está
    # efectivamente al alcance).
    pesos = config.PESOS_INDICE
    potencial = (
        pesos["demanda"] * salida["demanda_escalada"].fillna(0)
        + pesos["espacio"] * salida["espacio_escalado"].fillna(0)
    )
    salida["potencial_mercado"] = (100 * potencial).round(1)
    salida["indice_oportunidad"] = (
        100 * potencial * salida["accesibilidad"]
    ).round(1)

    # --- Evidencia de que el escalado hizo algo ----------------------------
    # Se comparan las tres alternativas sobre la MISMA variable y se mide
    # cuántas categorías cambian de posición al ordenar por índice en lugar de
    # por demanda cruda. Ese número es el argumento, no la teoría.
    reporte.seccion("comparacion_escalado", _comparar_escalados(salida))

    orden_demanda = salida["demanda_soles"].rank(ascending=False, method="first")
    orden_indice = salida["indice_oportunidad"].rank(ascending=False, method="first")
    top50_demanda = set(salida.loc[orden_demanda <= 50, "cubso_descripcion"])
    top50_indice = set(salida.loc[orden_indice <= 50, "cubso_descripcion"])
    reporte.seccion("efecto_del_indice", {
        "categorias": int(len(salida)),
        "desplazamiento_medio_de_posicion":
            float((orden_indice - orden_demanda).abs().mean().round(1)),
        "categorias_nuevas_en_top50": int(len(top50_indice - top50_demanda)),
        "coincidencia_top50": int(len(top50_indice & top50_demanda)),
    })

    return salida


def _comparar_escalados(df: pd.DataFrame) -> dict:
    """Compara Min-Max crudo, Min-Max sobre log y Z-Score sobre la demanda.

    Devuelve percentiles de cada alternativa. Lo que se busca mostrar es la
    proporción de categorías que quedan aplastadas contra el cero con Min-Max
    crudo, que es el motivo por el que el proyecto no lo usa.
    """
    demanda = df["demanda_soles"].astype("float64")
    mm_crudo = _minmax(demanda)
    mm_log = _minmax(np.log1p(demanda.clip(lower=0)))
    z = _zscore(np.log1p(demanda.clip(lower=0)))

    def resumen(s: pd.Series) -> dict:
        return {
            "min": round(float(s.min()), 4),
            "p50": round(float(s.quantile(0.50)), 4),
            "p90": round(float(s.quantile(0.90)), 4),
            "max": round(float(s.max()), 4),
        }

    return {
        "minmax_crudo": {**resumen(mm_crudo),
                         "pct_bajo_0.05": round(float((mm_crudo < 0.05).mean() * 100), 1)},
        "minmax_sobre_log": {**resumen(mm_log),
                             "pct_bajo_0.05": round(float((mm_log < 0.05).mean() * 100), 1)},
        "zscore_sobre_log": {**resumen(z),
                             "pct_negativo": round(float((z < 0).mean() * 100), 1)},
        "elegido": "minmax_sobre_log",
    }


# ---------------------------------------------------------------------------
# Orquestación del módulo
# ---------------------------------------------------------------------------
def transformar(maestro: pd.DataFrame, ocds: pd.DataFrame | None,
                reporte: Reporte) -> pd.DataFrame:
    """Encadena las tres etapas y optimiza la memoria del resultado.

    Es la función que llama `diagnostico.py`. Vive separada de `main()` para
    que el notebook de wrangling pueda ejecutar cada etapa por separado y
    mostrar la salida intermedia sin duplicar el código del pipeline.
    """
    perfil = estacionalidad_por_categoria(ocds) if ocds is not None else None
    if perfil is not None and not perfil.empty:
        perfil.to_parquet(config.PARQUET_ESTACIONALIDAD, engine="pyarrow",
                          compression="snappy", index=False)
        log.info("Archivo escrito | %s", config.PARQUET_ESTACIONALIDAD.name)
        reporte.metrica("categorias_con_perfil_temporal", int(len(perfil)))

    df = enriquecer(maestro, perfil)
    df = aplicar_binning(df)
    df = escalar(df, reporte)

    reporte.seccion("distribucion_banda_ticket",
                    df["banda_ticket"].value_counts(dropna=False)
                    .rename(index=str).to_dict())
    reporte.seccion("distribucion_banda_competencia",
                    df["banda_competencia"].value_counts(dropna=False)
                    .rename(index=str).to_dict())
    if df["es_estacional"].notna().any():
        reporte.metrica("categorias_estacionales",
                        int(df["es_estacional"].fillna(False).sum()))

    df, metricas_memoria = optimizar_memoria(df)
    reporte.seccion("optimizacion_memoria", metricas_memoria)
    log.info("Optimizacion de memoria aplicada | ahorro=%s%%",
             metricas_memoria["ahorro_pct"])

    return df.sort_values("indice_oportunidad", ascending=False)


def main() -> None:
    log.info("INICIO transformacion")
    reporte = Reporte("transformacion")

    if not config.PARQUET_MAESTRO.exists():
        log.error("Falta el dataset maestro | estado=ERROR")
        raise FileNotFoundError(
            "No existe maestro_oportunidades.parquet. Ejecute diagnostico.py."
        )

    with Cronometro(log, "carga de insumos"):
        maestro = pd.read_parquet(config.PARQUET_MAESTRO)
        ocds = (pd.read_parquet(config.PARQUET_OCDS,
                                columns=["cubso_descripcion", "monto_adjudicado",
                                         "fecha"])
                if config.PARQUET_OCDS.exists() else None)

    with Cronometro(log, "enriquecimiento, binning y escalado"):
        transformado = transformar(maestro, ocds, reporte)
        transformado.to_parquet(config.PARQUET_MAESTRO, engine="pyarrow",
                                compression="snappy", index=False)
        log.info("Archivo escrito | %s", config.PARQUET_MAESTRO.name)

    ruta_csv = reporte.guardar_tabla(
        transformado.nlargest(100, "indice_oportunidad")[
            [c for c in ["cubso_descripcion", "indice_oportunidad",
                         "demanda_escalada", "espacio_escalado",
                         "accesibilidad", "potencial_mercado", "banda_ticket",
                         "cuartil_demanda", "mes_pico", "es_estacional"]
             if c in transformado.columns]
        ],
        "top100_indice",
    )
    log.info("Tabla de resultados escrita | %s", ruta_csv.name)

    ruta = reporte.guardar()
    log.info("Reporte de metricas escrito | %s", ruta.name)
    registrar_corrida("transformacion")
    log.info("FIN transformacion | estado=EXITO")


if __name__ == "__main__":
    main()

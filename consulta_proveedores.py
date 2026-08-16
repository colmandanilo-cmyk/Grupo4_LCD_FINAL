"""
consulta_proveedores.py — Densidad de oferta: adjudicados + habilitados.

Este módulo construye la densidad de oferta cruzando las dos fuentes de oferta
del proyecto. Publica TRES planos, cada uno con su grano y su lectura:

  ADJUDICADOS (de OCDS)          — proveedores únicos que YA GANARON en cada
                                   categoría CUBSO. Grano: categoría. Exacto.
  COMPETENCIA VIGENTE (cruce)    — de esos ganadores, cuántos siguen
                                   habilitados hoy en el RNP. Grano: categoría.
                                   Es la única cifra que responde "cuántos
                                   competidores tengo enfrente" y ninguna de
                                   las dos fuentes la da por separado.
  HABILITADOS (de la ficha)      — proveedores vigentes por CAPÍTULO RNP.
                                   Grano: capítulo (cuatro valores). Es
                                   contexto del sector, no una variable por
                                   categoría.

POR QUÉ YA NO SE PUBLICA UN RATIO DE SATURACIÓN
-----------------------------------------------
La versión anterior resumía el contraste en un cociente:

    saturacion = adjudicados_categoria / habilitados_capitulo

Se descartó al medirlo. El numerador se cuenta por categoría CUBSO (más de
treinta mil) y el denominador por capítulo RNP (cuatro), así que el cociente
divide dos universos que no son comparables: da del orden de 0.0001 para todo
el catálogo, su máximo observado no llega a 0.18 y no ordena nada. Las dos
columnas que lo componían siguen publicadas, de modo que el ratio se puede
reconstruir y auditar; lo que no se hace es presentarlo como señal.

En su lugar el proyecto usa `competencia_vigente`, que compara grano con grano:
ganadores de la categoría contra su propio estado de habilitación.

INSUMOS
-------
  - ocds_procesos.parquet          (ingesta_ocds.py)      -> adjudicados
  - proveedores_padron.parquet     (ficha_proveedores.py) -> habilitación x RUC
  - diccionario_cubso.parquet      (diccionario_cubso.py) -> CUBSO -> capítulo

Si falta la ficha de habilitación, el módulo calcula solo la capa de
adjudicados y lo deja registrado, sin abortar: el pipeline sigue siendo
utilizable de forma incremental.

Uso:
    python consulta_proveedores.py
"""

from __future__ import annotations

import pandas as pd

import config
from utils import Cronometro, Reporte, crear_logger, registrar_corrida

log = crear_logger("consulta_proveedores")

PARQUET_DICCIONARIO = config.PROCESSED_DIR / "diccionario_cubso.parquet"

# Proporción de adjudicatarios con ficha descargada por debajo de la cual la
# competencia vigente deja de ser interpretable. Con cobertura parcial el efecto
# no es un sesgo cualquiera: un ganador sin ficha se cuenta como no habilitado,
# así que la competencia sale subestimada y los "mercados desiertos" salen
# inflados. Sería el peor error posible en este tablero, porque un mercado
# desierto es exactamente lo que el radar recomienda mirar primero.
#
# No hay un valor canónico: 0.60 es una elección del equipo, lo bastante alta
# como para que la cifra represente al mercado y lo bastante baja como para ser
# alcanzable con una descarga incremental. Lo importante no es el número sino
# que la corrida deje registrado de qué lado del umbral cayó.
COBERTURA_MINIMA_PADRON = 0.60


def calcular_adjudicados(reporte: Reporte) -> pd.DataFrame:
    """Cuenta RUC únicos adjudicados por categoría CUBSO (exacto, desde OCDS)."""
    if not config.PARQUET_OCDS.exists():
        raise FileNotFoundError(
            "No existe ocds_procesos.parquet. Ejecute ingesta_ocds.py."
        )
    detalle = pd.read_parquet(
        config.PARQUET_OCDS,
        columns=["cubso_descripcion", "proveedor_id", "ocid"],
    )
    validos = detalle.dropna(subset=["cubso_descripcion", "proveedor_id"])
    adjudicados = (
        validos.groupby("cubso_descripcion", as_index=False, observed=True)
        .agg(adjudicados=("proveedor_id", "nunique"),
             n_adjudicaciones=("ocid", "size"),
             n_procesos_con_adjudicacion=("ocid", "nunique"))
    )
    log.info("Adjudicados calculados | estado=EXITO")
    reporte.metrica("categorias_con_adjudicados", int(len(adjudicados)))
    reporte.metrica("proveedores_adjudicatarios_unicos",
                    int(validos["proveedor_id"].nunique()))
    return adjudicados


def calcular_habilitados_por_capitulo(reporte: Reporte):
    """Cuenta proveedores habilitados vigentes por capítulo RNP.

    Usa la ficha real (esHabilitado + capítulos vigentes). Devuelve None si la
    ficha aún no se descargó, para que el pipeline pueda avanzar sin ella.

    COBERTURA: por qué se mide en este módulo
    -----------------------------------------
    Acá se conoce el denominador de la descarga (cuántos adjudicatarios tienen
    RUC) y el numerador (cuántas fichas hay), así que es el lugar donde la
    cobertura se puede calcular una sola vez y quedar registrada para toda la
    corrida. De ella depende que `competencia_vigente` sea una medición o una
    consecuencia de hasta dónde llegó la descarga: cada ficha faltante convierte
    a un ganador habilitado en un ganador aparentemente dado de baja.

    Por eso la cobertura se reporta siempre, incluso cuando es completa. Que el
    número esté en el reporte de la corrida es lo que permite defender la cifra
    frente a quien pregunte sobre cuántas fichas se apoya.
    """
    if not config.PARQUET_PADRON.exists():
        log.warning("Sin ficha de habilitación | ejecute ficha_proveedores.py")
        return None

    padron = pd.read_parquet(config.PARQUET_PADRON)
    habilitados = padron[padron["es_habilitado"]].copy()

    # Cobertura del padrón sobre los adjudicatarios que hay que contrastar.
    adjudicatarios = 0
    if config.PARQUET_OCDS.exists():
        ids = pd.read_parquet(config.PARQUET_OCDS, columns=["proveedor_id"])
        adjudicatarios = int(ids["proveedor_id"].dropna().astype("string")
                             .str.extract(r"(\d{11})", expand=False)
                             .dropna().nunique())
    cobertura = len(padron) / max(adjudicatarios, 1)
    reporte.metrica("adjudicatarios_con_ruc", adjudicatarios)
    reporte.metrica("fichas_en_padron", int(len(padron)))
    reporte.metrica("cobertura_padron_pct", round(100 * cobertura, 2))
    log.info("Cobertura del padron | fichas=%d | adjudicatarios=%d | pct=%.2f",
             len(padron), adjudicatarios, 100 * cobertura)

    if cobertura < COBERTURA_MINIMA_PADRON:
        log.warning("Cobertura del padron por debajo del umbral | pct=%.2f | "
                    "umbral=%.0f | la competencia vigente queda subestimada y "
                    "los mercados desiertos inflados",
                    100 * cobertura, 100 * COBERTURA_MINIMA_PADRON)
    reporte.metrica("competencia_vigente_interpretable",
                    cobertura >= COBERTURA_MINIMA_PADRON)

    if habilitados.empty:
        log.warning("Padron sin proveedores habilitados | capa de habilitados "
                    "no utilizable | revise ficha_proveedores.py")
        return None

    expl = habilitados.explode("capitulos_vigentes")
    expl = expl[expl["capitulos_vigentes"].notna()]
    por_capitulo = (
        expl.groupby("capitulos_vigentes", as_index=False)
        .agg(habilitados_capitulo=("proveedor_id", "nunique"))
        .rename(columns={"capitulos_vigentes": "capitulo_rnp"})
    )
    log.info("Habilitados por capítulo calculados | estado=EXITO")
    reporte.metrica("proveedores_habilitados", int(len(habilitados)))
    reporte.seccion("habilitados_por_capitulo",
                    dict(zip(por_capitulo["capitulo_rnp"],
                             por_capitulo["habilitados_capitulo"].astype(int))))
    return por_capitulo


def calcular_competencia_vigente(reporte: Reporte):
    """Cuenta, por categoría, cuántos ganadores siguen habilitados hoy.

    QUÉ APORTA QUE OCDS NO PUEDE DAR
    --------------------------------
    El OCDS dice quién ganó entre 2024 y 2025. La ficha del RNP dice quién
    está habilitado hoy. Cruzarlos por RUC contesta una pregunta que ninguna
    de las dos fuentes contesta sola: de los que ganaron en esta categoría,
    cuántos siguen en condiciones de volver a competir.

    Produce tres columnas por categoría CUBSO:
        ganadores_historicos  RUC distintos que ganaron alguna vez
        competencia_vigente   de esos, los que siguen habilitados
        salieron_del_registro la diferencia

    Cuando `competencia_vigente` es 0 con ganadores históricos mayores que
    cero, la categoría quedó sin ningún adjudicatario en carrera. Es el
    hallazgo que motiva la descarga completa del padrón.

    Solo cubre las categorías cuyos adjudicatarios tienen RUC de once
    dígitos. Los consorcios y las personas naturales bajo otro formato no
    cruzan contra el padrón, y sus categorías quedan sin el dato en lugar de
    recibir un cero que se leería como mercado vacío.
    """
    if not config.PARQUET_PADRON.exists():
        log.warning("Sin ficha de habilitacion | competencia vigente no calculable")
        return None

    padron = pd.read_parquet(config.PARQUET_PADRON,
                             columns=["ruc", "es_habilitado", "es_apto_contratar"])
    detalle = pd.read_parquet(config.PARQUET_OCDS,
                              columns=["cubso_descripcion", "proveedor_id"])
    detalle = detalle.dropna(subset=["cubso_descripcion", "proveedor_id"])

    # El id de OCDS viene con prefijo de esquema (PE-RUC-...): se extrae el RUC.
    detalle["ruc"] = (detalle["proveedor_id"].astype("string")
                      .str.extract(r"(\d{11})", expand=False))
    conruc = detalle.dropna(subset=["ruc"]).merge(padron, on="ruc", how="left")

    conruc["vigente"] = conruc["es_habilitado"].fillna(False)
    conruc["apto"] = conruc["es_apto_contratar"].fillna(False)

    # Los tres conteos son el mismo `nunique` sobre subconjuntos distintos de
    # la misma tabla. La versión anterior lo hacía con un `lambda` dentro de
    # `agg`, que pandas ejecuta una vez por grupo: treinta mil llamadas a una
    # función de Python y, peor, cada una reindexando la tabla completa con
    # `conruc.loc[s.index]`. Filtrar primero y agrupar después deja las tres
    # cuentas en tres groupby vectorizados sobre una tabla más chica.
    def contar(mascara, nombre: str) -> pd.Series:
        base = conruc if mascara is None else conruc[mascara]
        return (base.groupby("cubso_descripcion", observed=True)["ruc"]
                .nunique().rename(nombre))

    por_categoria = (
        pd.concat([contar(None, "ganadores_historicos"),
                   contar(conruc["vigente"], "competencia_vigente"),
                   contar(conruc["apto"], "competencia_apta")], axis=1)
        .fillna(0).astype("int64")
        .reset_index()
    )
    por_categoria["salieron_del_registro"] = (
        por_categoria["ganadores_historicos"] - por_categoria["competencia_vigente"]
    )
    desiertas = int(((por_categoria["competencia_vigente"] == 0)
                     & (por_categoria["ganadores_historicos"] > 0)).sum())

    log.info("Competencia vigente calculada | estado=EXITO")
    reporte.metrica("categorias_con_competencia_vigente", int(len(por_categoria)))
    reporte.metrica("categorias_desiertas", desiertas)
    reporte.metrica("categorias_con_bajas_en_el_registro",
                    int((por_categoria["salieron_del_registro"] > 0).sum()))
    reporte.metrica("adjudicatarios_no_habilitados",
                    int((~padron["es_habilitado"]).sum()))
    reporte.metrica("adjudicatarios_no_aptos",
                    int((~padron["es_apto_contratar"]).sum()))
    return por_categoria


def construir_densidad(adjudicados, habilitados, reporte, vigencia=None):
    """Une adjudicados, competencia vigente y habilitados del capítulo.

    Tres planos, cada uno con su grano y su lectura:
      - adjudicados          por categoría, de OCDS: quién ganó.
      - competencia_vigente  por categoría, OCDS x ficha: quién sigue en carrera.
      - habilitados_capitulo por capítulo, de la ficha: cuán poblada está la
                             puerta de entrada al sector. Es contexto, no una
                             variable por categoría: el RNP habilita por
                             capítulo, así que solo toma cuatro valores.
    """
    densidad = adjudicados.copy()
    densidad["densidad_proveedores"] = densidad["adjudicados"]

    if vigencia is not None:
        densidad = densidad.merge(vigencia, on="cubso_descripcion", how="left")
        densidad["mercado_desierto"] = (
            (densidad["competencia_vigente"] == 0)
            & (densidad["ganadores_historicos"] > 0)
        )
    else:
        for col in ("ganadores_historicos", "competencia_vigente",
                    "competencia_apta", "salieron_del_registro"):
            densidad[col] = pd.NA
        densidad["mercado_desierto"] = False

    if habilitados is None or not PARQUET_DICCIONARIO.exists():
        if not PARQUET_DICCIONARIO.exists():
            log.warning("Sin diccionario CUBSO | ejecute diccionario_cubso.py")
        densidad["capitulo_rnp"] = pd.NA
        densidad["habilitados_capitulo"] = pd.NA
        reporte.metrica("capa_habilitados", "ausente")
        return densidad

    dic = pd.read_parquet(PARQUET_DICCIONARIO,
                          columns=["cubso_descripcion", "capitulo_rnp"])
    densidad = densidad.merge(dic, on="cubso_descripcion", how="left")
    densidad = densidad.merge(habilitados, on="capitulo_rnp", how="left")

    # No se calcula el cociente adjudicados / habilitados: ver la explicación en
    # el encabezado del módulo. Las dos columnas quedan publicadas y quien
    # quiera reconstruirlo puede hacerlo, con la asimetría de grano a la vista.
    reporte.metrica("capa_habilitados", "presente")
    reporte.metrica("categorias_con_capitulo",
                    int(densidad["capitulo_rnp"].notna().sum()))
    return densidad


def main() -> None:
    log.info("INICIO consulta proveedores | densidad de dos capas")
    reporte = Reporte("consulta_proveedores")

    with Cronometro(log, "cálculo de adjudicados (OCDS)"):
        adjudicados = calcular_adjudicados(reporte)

    with Cronometro(log, "cálculo de habilitados (ficha RNP)"):
        habilitados = calcular_habilitados_por_capitulo(reporte)

    with Cronometro(log, "cálculo de competencia vigente (OCDS x ficha)"):
        vigencia = calcular_competencia_vigente(reporte)

    with Cronometro(log, "integración de los tres planos de densidad"):
        densidad = construir_densidad(adjudicados, habilitados, reporte, vigencia)
        densidad.to_parquet(config.PARQUET_DENSIDAD, engine="pyarrow",
                            compression="snappy", index=False)
        log.info("Archivo escrito | %s", config.PARQUET_DENSIDAD.name)

    ruta = reporte.guardar()
    log.info("Reporte de metricas escrito | %s", ruta.name)
    registrar_corrida("consulta_proveedores")
    log.info("FIN consulta proveedores | estado=EXITO")


if __name__ == "__main__":
    main()

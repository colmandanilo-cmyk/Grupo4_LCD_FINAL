"""
validacion.py — Validación automatizada de esquemas y reglas de negocio.

QUÉ RESUELVE
------------
El proyecto ya tenía `perfil_calidad()` en diagnostico.py, pero eso MIDE, no
VALIDA: cuenta nulos y duplicados y los reporta. Nada impedía que un dataset
con la mitad de las categorías sin monto siguiera de largo hasta la Data App.
Este módulo pone el corte: define qué forma debe tener cada dataset del
pipeline y qué reglas del dominio de compras públicas debe cumplir, y falla de
manera explícita cuando no se cumplen.

DOS NIVELES, PORQUE FALLAN COSAS DISTINTAS
------------------------------------------
  ESQUEMA (Pandera). Tipos, nulabilidad, unicidad y rangos por columna. Detecta
  que la fuente cambió de forma: un campo que pasó de número a texto, un ID que
  dejó de ser único, un monto negativo. Es validación sintáctica.

  REGLAS DE NEGOCIO. Coherencia entre columnas, que ningún esquema por columna
  puede ver: no puede haber más proveedores adjudicados que adjudicaciones, el
  ticket promedio tiene que reconstruirse desde demanda y procesos, el índice no
  puede superar al potencial que lo origina. Es validación semántica.

POR QUÉ NO SE DETIENE EL PIPELINE POR DEFECTO
---------------------------------------------
La validación corre en modo `lazy`: acumula TODOS los fallos en lugar de
abortar en el primero. Los `failure_cases` se escriben a reports/, no al log,
por la misma separación que ya se corrigió en utils.py: un caso que falló es un
dato, no un evento de proceso. El pipeline solo se detiene si el porcentaje de
filas rechazadas supera `TOLERANCIA_RECHAZO`, porque una fuente pública con
0,3 % de registros mal formados es normal y abortar por eso sería frágil.

Uso:
    python validacion.py             # valida las salidas ya generadas
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

import config
from utils import Cronometro, Reporte, crear_logger

log = crear_logger("validacion")

# Proporción de filas rechazadas a partir de la cual la corrida se considera
# fallida. Por debajo se registra y se sigue; por encima algo cambió en la
# fuente y seguir sería publicar un tablero equivocado.
TOLERANCIA_RECHAZO = 0.10

# Cota superior de monto por proceso. No es un límite legal: es un detector de
# errores de unidad (montos cargados en céntimos o con la coma corrida). El
# contrato público peruano más grande está muy por debajo de esta cifra.
MONTO_MAXIMO_RAZONABLE = 5_000_000_000


# ---------------------------------------------------------------------------
# Esquemas por dataset
# ---------------------------------------------------------------------------
ESQUEMA_DEMANDA = DataFrameSchema(
    columns={
        "cubso_descripcion": Column(
            str,
            checks=[
                Check.str_length(min_value=3, error="descripción CUBSO demasiado corta"),
                Check(lambda s: ~s.duplicated(), name="categoria_unica",
                      error="la categoría CUBSO debe ser única en el agregado"),
            ],
            nullable=False,
        ),
        "demanda_soles": Column(
            float,
            checks=[
                Check.greater_than_or_equal_to(0, error="la demanda no puede ser negativa"),
                Check.less_than(MONTO_MAXIMO_RAZONABLE,
                                error="monto fuera de rango: revisar unidad"),
            ],
            nullable=False,
        ),
        "n_procesos": Column(
            int,
            checks=Check.greater_than(0, error="una categoría con demanda tiene al menos un proceso"),
            nullable=False,
        ),
    },
    strict=False,   # admite columnas extra: el dataset crece con el proyecto
    coerce=True,
    name="demanda_por_categoria",
)

ESQUEMA_DENSIDAD = DataFrameSchema(
    columns={
        "cubso_descripcion": Column(str, nullable=False),
        "adjudicados": Column(
            int,
            checks=Check.greater_than_or_equal_to(0),
            nullable=False,
        ),
        "competencia_vigente": Column(
            float,
            checks=Check.greater_than_or_equal_to(
                0, error="la competencia vigente es un conteo: no puede ser negativa"),
            nullable=True,   # ausente donde el adjudicatario no tiene RUC
        ),
    },
    strict=False,
    coerce=True,
    name="densidad_proveedores",
)

ESQUEMA_MAESTRO = DataFrameSchema(
    columns={
        "cubso_descripcion": Column(
            str,
            checks=Check(lambda s: ~s.duplicated(), name="categoria_unica"),
            nullable=False,
        ),
        "demanda_soles": Column(float, checks=Check.greater_than_or_equal_to(0),
                                nullable=False),
        "n_procesos": Column(int, checks=Check.greater_than(0), nullable=False),
        "ticket_promedio": Column(float, checks=Check.greater_than(0),
                                  nullable=True),
        "indice_oportunidad": Column(
            float,
            checks=Check.in_range(0, 100, error="el índice se publica en escala 0-100"),
            nullable=False,
        ),
        "espacio_mercado": Column(float, checks=Check.in_range(0, 1),
                                  nullable=True),
        "convocatorias_vigentes": Column(
            "Int64",
            checks=Check.greater_than_or_equal_to(0),
            nullable=True,
        ),
        "competencia_vigente": Column(
            float,
            checks=Check.greater_than_or_equal_to(0),
            nullable=True,
        ),
        # La etiqueta se valida contra la lista de config y no contra una lista
        # escrita acá: si mañana se agrega una banda, el esquema la acepta sin
        # que haya que acordarse de tocar dos archivos. El valor extra es el
        # único que no sale de config, porque no es una banda sino la ausencia
        # de dato.
        "banda_competencia": Column(
            str,
            checks=Check.isin(config.BANDAS_COMPETENCIA_ETIQUETAS
                              + ["Competencia no determinada"]),
            nullable=False,
        ),
    },
    strict=False,
    coerce=True,
    name="maestro_oportunidades",
)


# ---------------------------------------------------------------------------
# Reglas de negocio (coherencia entre columnas)
# ---------------------------------------------------------------------------
def reglas_de_negocio(maestro: pd.DataFrame) -> dict:
    """Comprueba coherencias que ningún esquema por columna puede ver.

    Devuelve un dict con el conteo de filas que violan cada regla. Se devuelve
    en lugar de registrarse para que el llamador lo escriba en reports/.
    """
    resultados = {}

    # Un proveedor adjudicado ganó al menos una adjudicación, así que no puede
    # haber más proveedores distintos que adjudicaciones.
    #
    # OJO con el denominador, que ya se equivocó dos veces. Primero comparaba
    # contra `n_procesos`, y marcaba 968 categorías como incoherentes: está
    # mal, porque un proceso dividido en lotes emite varias adjudicaciones y
    # puede repartirlas entre proveedores distintos. Después pasó a
    # `n_adjudicaciones`, que daba el mismo número porque esa columna contaba
    # `nunique(ocid)`, es decir procesos otra vez con otro nombre. La cota real
    # es la cantidad de filas de adjudicación por categoría, que es el grano
    # del detalle OCDS: una fila por ítem adjudicado.
    if {"densidad_proveedores", "n_adjudicaciones"} <= set(maestro.columns):
        violan = (maestro["densidad_proveedores"].fillna(0)
                  > maestro["n_adjudicaciones"].fillna(0)).sum()
        resultados["adjudicados_no_supera_adjudicaciones"] = int(violan)

    # La competencia vigente es un subconjunto de los ganadores históricos: son
    # los mismos RUC filtrados por habilitación. No puede haber más. Si esta
    # regla falla, el cruce contra la ficha duplicó filas, que es el modo típico
    # en que un merge mal planteado se manifiesta.
    if {"competencia_vigente", "ganadores_historicos"} <= set(maestro.columns):
        violan = (maestro["competencia_vigente"]
                  > maestro["ganadores_historicos"]).sum()
        resultados["competencia_no_supera_ganadores"] = int(violan)

    # Un mercado desierto es, por definición, una categoría que tuvo ganadores y
    # hoy no tiene ninguno habilitado. La bandera se calcula en un módulo
    # (consulta_proveedores.py) y se consume en otro (la Data App), así que
    # conviene comprobar que sigue significando eso y no quedó desincronizada.
    if {"mercado_desierto", "competencia_vigente",
            "ganadores_historicos"} <= set(maestro.columns):
        esperado = ((maestro["competencia_vigente"] == 0)
                    & (maestro["ganadores_historicos"] > 0))
        marcado = maestro["mercado_desierto"].astype("object").fillna(False).astype(bool)
        resultados["mercado_desierto_coherente"] = int((marcado != esperado).sum())

    # El ticket promedio es demanda / procesos: debe reconstruirse. Se admite
    # 1 % de tolerancia por redondeo de punto flotante.
    if {"ticket_promedio", "demanda_soles", "n_procesos"} <= set(maestro.columns):
        esperado = maestro["demanda_soles"] / maestro["n_procesos"]
        # El denominador va en valor absoluto: si `esperado` fuese negativo por
        # una demanda corrupta, dividir por él invierte el signo del desvío y
        # la regla dejaría pasar justamente la fila que debía atrapar.
        desvio = ((maestro["ticket_promedio"] - esperado).abs()
                  / esperado.abs().replace(0, pd.NA))
        resultados["ticket_promedio_coherente"] = int((desvio > 0.01).sum())

    # Una categoría marcada como accionable debe tener llamados vigentes.
    if {"accionable_hoy", "convocatorias_vigentes"} <= set(maestro.columns):
        incoherentes = (maestro["accionable_hoy"]
                        & (maestro["convocatorias_vigentes"].fillna(0) == 0)).sum()
        resultados["accionable_con_llamados"] = int(incoherentes)

    # El índice es el potencial de mercado multiplicado por un factor de
    # accesibilidad que nunca pasa de 1, así que no puede superar al potencial.
    if {"indice_oportunidad", "potencial_mercado"} <= set(maestro.columns):
        incoherentes = (maestro["indice_oportunidad"]
                        > maestro["potencial_mercado"] + 0.1).sum()
        resultados["indice_no_supera_al_potencial"] = int(incoherentes)

    # Y el potencial se compone de dos términos acotados en [0,1] con pesos que
    # suman 1: tampoco puede superar al mayor de los dos.
    componentes = ["demanda_escalada", "espacio_escalado"]
    if set(componentes) <= set(maestro.columns) and \
            "potencial_mercado" in maestro.columns:
        maximo = maestro[componentes].max(axis=1)
        incoherentes = ((maestro["potencial_mercado"] / 100) > maximo + 0.01).sum()
        resultados["potencial_no_supera_sus_componentes"] = int(incoherentes)

    return resultados


# ---------------------------------------------------------------------------
# Motor de validación
# ---------------------------------------------------------------------------
def registrar_reglas_en_log(esquema: DataFrameSchema) -> None:
    """Deja constancia en el log de QUÉ se va a comprobar, antes de comprobarlo.

    Un log que solo dice "validación OK" no sirve para auditar: no permite
    saber si pasó porque los datos estaban bien o porque el esquema no
    comprobaba nada. Registrar las reglas antes de aplicarlas hace que el log
    responda las dos preguntas.

    Una línea por columna, porque el filtro de utils.py rechaza texto
    multilínea: al log van eventos, uno por renglón.
    """
    nombre = esquema.name or "dataset"
    columnas = esquema.columns
    log.info("REGLAS | dataset=%s | columnas_con_esquema=%d",
             nombre, len(columnas))
    for columna, definicion in columnas.items():
        checks = [getattr(c, "name", None) or str(c)
                  for c in (definicion.checks or [])]
        log.info("REGLAS | dataset=%s | columna=%s | tipo=%s | nullable=%s | "
                 "checks=%s", nombre, columna, definicion.dtype,
                 definicion.nullable, ", ".join(checks) or "(solo tipo)")


def validar(df: pd.DataFrame, esquema: DataFrameSchema, reporte: Reporte,
            detener: bool = False) -> pd.DataFrame:
    """Valida un DataFrame contra su esquema y reporta los fallos.

    Corre en modo lazy para juntar todos los errores en una sola pasada. Los
    casos que fallaron van a un CSV en reports/; al log solo llega el conteo,
    que es el evento.

    Si `detener` es True y la proporción de filas afectadas supera la
    tolerancia, levanta la excepción en lugar de continuar.
    """
    nombre = esquema.name or "dataset"
    registrar_reglas_en_log(esquema)
    try:
        validado = esquema.validate(df, lazy=True)
        log.info("VALIDACION | dataset=%s | estado=OK | filas=%d | "
                 "reglas_fallidas=0", nombre, len(validado))
        reporte.seccion(f"validacion_{nombre}", {
            "estado": "OK", "filas": int(len(validado)), "fallos": 0,
        })
        return validado

    except pa.errors.SchemaErrors as error:
        casos = error.failure_cases
        filas_afectadas = casos["index"].dropna().nunique()
        proporcion = filas_afectadas / max(len(df), 1)

        log.warning("VALIDACION | dataset=%s | estado=CON_FALLOS | "
                    "reglas_fallidas=%d | filas_afectadas=%d | pct=%.2f",
                    nombre, len(casos), filas_afectadas, 100 * proporcion)

        # Una línea por regla incumplida: el log dice cuál falló y cuántas
        # veces. El valor concreto que falló es un dato y va al CSV.
        for (columna, regla), cantidad in (
            casos.groupby(["column", "check"], dropna=False).size().items()
        ):
            log.warning("VALIDACION | dataset=%s | columna=%s | regla=%s | "
                        "casos=%d", nombre, columna, str(regla)[:80], cantidad)

        ruta = reporte.guardar_tabla(
            casos[["schema_context", "column", "check", "failure_case", "index"]],
            f"fallos_{nombre}",
        )
        log.info("Casos fallidos escritos | %s", ruta.name)

        reporte.seccion(f"validacion_{nombre}", {
            "estado": "CON_FALLOS",
            "filas": int(len(df)),
            "reglas_fallidas": int(len(casos)),
            "filas_afectadas": int(filas_afectadas),
            "pct_afectado": round(100 * proporcion, 2),
            "reglas": casos["check"].value_counts().to_dict(),
            "archivo_detalle": ruta.name,
        })

        if detener and proporcion > TOLERANCIA_RECHAZO:
            log.error("Rechazo por encima de la tolerancia | dataset=%s | estado=ERROR",
                      nombre)
            raise

        # Se devuelven las filas que sí pasaron, para no perder la corrida.
        indices_malos = set(casos["index"].dropna().astype(int))
        return df.drop(index=[i for i in indices_malos if i in df.index])


def main() -> None:
    log.info("INICIO validacion")
    reporte = Reporte("validacion")

    pares = [
        (config.PARQUET_DEMANDA, ESQUEMA_DEMANDA),
        (config.PARQUET_DENSIDAD, ESQUEMA_DENSIDAD),
        (config.PARQUET_MAESTRO, ESQUEMA_MAESTRO),
    ]

    maestro = None
    for ruta, esquema in pares:
        if not ruta.exists():
            log.warning("Dataset ausente | %s | se omite", ruta.name)
            continue
        with Cronometro(log, f"validacion de {esquema.name}"):
            df = pd.read_parquet(ruta)
            validado = validar(df, esquema, reporte)
            if esquema is ESQUEMA_MAESTRO:
                maestro = validado

    if maestro is not None:
        with Cronometro(log, "reglas de negocio"):
            reglas = reglas_de_negocio(maestro)
            reporte.seccion("reglas_de_negocio", reglas)
            for regla, violaciones in reglas.items():
                nivel = log.warning if violaciones else log.info
                nivel("NEGOCIO | regla=%s | violaciones=%d | estado=%s",
                      regla, violaciones, "FALLA" if violaciones else "OK")

    ruta = reporte.guardar()
    log.info("Reporte de metricas escrito | %s", ruta.name)
    log.info("FIN validacion | estado=EXITO")


if __name__ == "__main__":
    main()

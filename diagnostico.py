"""
diagnostico.py — Integración, diagnóstico de calidad y dataset maestro.

Toma las salidas de las cuatro fuentes y produce el dataset que alimenta la
Data App, junto con un reporte de calidad auditable.

QUÉ CAMBIÓ RESPECTO DE LA VERSIÓN T1
------------------------------------
1. TRAZABILIDAD (observación de la revisión). La versión anterior escribía
   una vista previa del dataset maestro en el log con `to_string()`. Eso era
   grabar resultados en el registro de proceso. Ahora el log solo registra
   eventos y todas las métricas y tablas se escriben en reports/.

2. INDICADORES. La densidad de oferta cruza el OCDS con la ficha del RNP
   (consulta_proveedores.py) y de ese cruce sale la variable que ordena el
   radar. Junto con la demanda y el ticket, la oportunidad queda definida de
   forma no ambigua:

     - competencia_vigente   : de los que ganaron en la categoría, cuántos
                               siguen habilitados hoy. Es un conteo por
                               categoría, comparable entre categorías.
     - ticket_promedio       : accesibilidad para una MYPE.
     - convocatorias_vigentes: si la categoría está convocando HOY (Fuente 3).

   Dos indicadores anteriores quedaron atrás y conviene saber por qué, porque
   la pregunta va a aparecer en la sustentación:

     - `concentracion` (procesos por proveedor) era el sucedáneo de la época en
       que no se tenía la habilitación. Se conserva como respaldo para las
       categorías que no cruzan contra la ficha, no como indicador principal.
     - `saturacion` (adjudicados de la categoría / habilitados del capítulo) se
       descartó al medirla: divide una cuenta por categoría entre una cuenta
       por capítulo, dos granos que no se comparan. Ver el encabezado de
       consulta_proveedores.py.

Uso:
    python diagnostico.py
"""

from __future__ import annotations

import pandas as pd

import config
import calidad
import transformacion
import validacion
from utils import Cronometro, Reporte, crear_logger, registrar_corrida

log = crear_logger("diagnostico")

# NOTA — acá vivían tres umbrales de clasificación (CONCENTRACION_ALTA,
# PERCENTIL_COMPETENCIA_ALTA, PERCENTIL_DEMANDA_ALTA) que alimentaban una
# etiqueta de mercado de 2x2: demanda alta o baja cruzada con espacio o
# saturación. Se eliminaron junto con la etiqueta.
#
# El motivo fue de lectura, no de cálculo. La etiqueta exigía demanda por
# encima del percentil 75 del catálogo, mientras que el índice premia el ticket
# accesible, que viene con demanda más chica. Las dos señales apuntaban en
# direcciones opuestas y el top del ranking aparecía rotulado "Nicho menor", que
# en pantalla se lee como un error del tablero.
#
# La etiqueta que quedó (`banda_competencia`, en transformacion.py) describe una
# sola cosa y con cortes que no dependen de la distribución: cuántos
# competidores vigentes tiene la categoría.


# NOTA — `perfil_calidad()` vivía acá y medía nulos, duplicados y memoria.
# Se movió a calidad.py y se amplió a las seis métricas del Tema 3
# (completitud, unicidad, validez, consistencia, exactitud, actualidad).
# El motivo no es sólo de alcance: medir la calidad es una responsabilidad
# distinta de integrar, y tenerlas en el mismo módulo hacía que cada vez que
# se agregaba una fuente hubiera que tocar la función de integración.


def construir_maestro(demanda: pd.DataFrame, densidad: pd.DataFrame,
                      convocatorias: pd.DataFrame | None) -> pd.DataFrame:
    """Integra las fuentes y calcula los indicadores de oportunidad."""
    demanda = (demanda.dropna(subset=["cubso_descripcion"])
               .drop_duplicates(subset=["cubso_descripcion"]))
    densidad = densidad.drop_duplicates(subset=["cubso_descripcion"])

    # La densidad ahora puede traer las columnas de la capa de habilitados
    # (capitulo_rnp, habilitados_capitulo, saturacion) si la ficha se descargó.
    cols_densidad = [c for c in
                     ["cubso_descripcion", "densidad_proveedores",
                      "n_adjudicaciones", "n_procesos_con_adjudicacion", "adjudicados", "capitulo_rnp",
                      "habilitados_capitulo", "ganadores_historicos",
                      "competencia_vigente", "competencia_apta",
                      "salieron_del_registro", "mercado_desierto"]
                     if c in densidad.columns]
    maestro = demanda.merge(
        densidad[cols_densidad],
        on="cubso_descripcion", how="left", validate="one_to_one",
    )

    # --- Indicadores derivados ---------------------------------------------
    maestro["ticket_promedio"] = (
        maestro["demanda_soles"] / maestro["n_procesos"].replace(0, pd.NA)
    )
    # concentración: sucedáneo cuando no hay capa de habilitados
    maestro["concentracion"] = (
        maestro["n_procesos"] / maestro["densidad_proveedores"].replace(0, pd.NA)
    ).round(2)
    if "competencia_vigente" not in maestro.columns:
        maestro["competencia_vigente"] = pd.NA

    # --- Fuente 3: llamados abiertos por categoría --------------------------
    if convocatorias is not None and not convocatorias.empty:
        vigentes = convocatorias[
            convocatorias["vigencia"].isin(["VIGENTE", "POR CERRAR"])
        ]
        por_categoria = (
            vigentes.groupby("cubso_descripcion", as_index=False, observed=True)
            .agg(convocatorias_vigentes=("ocid", "nunique"),
                 monto_vigente=("monto_referencial", "sum"))
        )
        maestro = maestro.merge(por_categoria, on="cubso_descripcion", how="left")
    else:
        maestro["convocatorias_vigentes"] = pd.NA
        maestro["monto_vigente"] = pd.NA

    maestro["convocatorias_vigentes"] = (
        maestro["convocatorias_vigentes"].fillna(0).astype("Int64")
    )

    # La etiqueta de competencia (`banda_competencia`) se calcula en la etapa de
    # binning de transformacion.py y no acá. Es una discretización de una
    # variable continua, que es exactamente lo que hace esa etapa: tenerla en
    # dos lugares fue lo que produjo dos etiquetas rivales en el mismo dataset.
    maestro["accionable_hoy"] = maestro["convocatorias_vigentes"] > 0

    return maestro.sort_values("demanda_soles", ascending=False)


def main() -> None:
    log.info("INICIO diagnostico e integracion")
    reporte = Reporte("diagnostico")

    faltantes = [p.name for p in (config.PARQUET_DEMANDA, config.PARQUET_DENSIDAD)
                 if not p.exists()]
    if faltantes:
        log.error("Faltan insumos de la ingesta | estado=ERROR")
        raise FileNotFoundError(
            f"Faltan salidas de la ingesta: {', '.join(faltantes)}. "
            "Ejecute ingesta_ocds.py y consulta_proveedores.py (admiten --demo)."
        )

    with Cronometro(log, "carga de Parquet"):
        demanda = pd.read_parquet(config.PARQUET_DEMANDA)
        densidad = pd.read_parquet(config.PARQUET_DENSIDAD)
        ocds = (pd.read_parquet(config.PARQUET_OCDS)
                if config.PARQUET_OCDS.exists() else None)
        convocatorias = (pd.read_parquet(config.PARQUET_CONVOCATORIAS)
                         if config.PARQUET_CONVOCATORIAS.exists() else None)
        if convocatorias is None:
            log.warning("Sin convocatorias vigentes | ejecute monitor_convocatorias.py")

    # --- Métricas de calidad (Tema 3): al reporte Y al log -----------------
    # Las seis métricas se calculan sobre cada fuente ANTES de validar. Al log
    # va una línea por métrica (el evento auditable: qué se midió y qué dio);
    # al reporte JSON va el detalle completo por columna.
    with Cronometro(log, "metricas de calidad de datos"):
        fuentes = [(demanda, "demanda_por_categoria", "cubso_descripcion"),
                   (densidad, "densidad_proveedores", "cubso_descripcion")]
        if ocds is not None:
            fuentes.insert(0, (ocds, "ocds_procesos",
                               ["ocid", "cubso_id", "proveedor_id"]))
        if config.PARQUET_PADRON.exists():
            fuentes.append((pd.read_parquet(config.PARQUET_PADRON),
                            "proveedores_padron", "proveedor_id"))
        if convocatorias is not None:
            fuentes.append((convocatorias, "convocatorias_vigentes", "ocid"))

        perfiles = []
        for datos, nombre, clave in fuentes:
            perfil = calidad.perfil_completo(datos, nombre, clave)
            calidad.registrar_en_log(perfil)
            reporte.seccion(f"calidad_{nombre}", perfil)
            perfiles.append(perfil)

        ruta_calidad = reporte.guardar_tabla(
            calidad.resumen_tabular(perfiles), "resumen_calidad")
        log.info("Tabla comparativa de calidad escrita | %s", ruta_calidad.name)

    # --- Validación de INSUMOS: antes de integrar, no después --------------
    # Integrar datos que ya vienen mal solo propaga el error al maestro y lo
    # vuelve más difícil de rastrear. Se valida cada fuente en su propio
    # esquema y se sigue con las filas que pasaron.
    with Cronometro(log, "validacion de insumos"):
        demanda = validacion.validar(demanda, validacion.ESQUEMA_DEMANDA, reporte)
        densidad = validacion.validar(densidad, validacion.ESQUEMA_DENSIDAD, reporte)

    with Cronometro(log, "integracion y calculo de indicadores"):
        maestro = construir_maestro(demanda, densidad, convocatorias)

    # --- Transformación (Tema 4): enriquecer, binning, escalar -------------
    with Cronometro(log, "transformacion: enriquecimiento, binning y escalado"):
        maestro = transformacion.transformar(maestro, ocds, reporte)

    # --- Validación de SALIDA: el contrato de lo que consume la Data App ---
    with Cronometro(log, "validacion del maestro"):
        maestro = validacion.validar(maestro, validacion.ESQUEMA_MAESTRO,
                                     reporte, detener=True)
        reglas = validacion.reglas_de_negocio(maestro)
        reporte.seccion("reglas_de_negocio", reglas)
        for regla, violaciones in reglas.items():
            nivel = log.warning if violaciones else log.info
            nivel("NEGOCIO | regla=%s | violaciones=%d | estado=%s",
                  regla, violaciones, "FALLA" if violaciones else "OK")

    with Cronometro(log, "escritura del maestro"):
        maestro.to_parquet(config.PARQUET_MAESTRO, engine="pyarrow",
                           compression="snappy", index=False)
        log.info("Archivo escrito | %s", config.PARQUET_MAESTRO.name)

    # --- Métricas del maestro: al reporte -----------------------------------
    aptas = maestro["apto_para_ranking"].astype("object").fillna(False).astype(bool)
    desiertas = maestro["mercado_desierto"].astype("object").fillna(False).astype(bool)
    cobertura = maestro["densidad_proveedores"].notna().mean()
    reporte.metrica("categorias_maestro", int(len(maestro)))
    reporte.metrica("cobertura_densidad_pct", round(100 * cobertura, 2))
    reporte.metrica("categorias_accionables_hoy",
                    int(maestro["accionable_hoy"].sum()))
    reporte.seccion("piso_de_mercado", {
        "categorias_totales": int(len(maestro)),
        "aptas_para_ranking": int(aptas.sum()),
        "descartadas_por_piso": int((~aptas).sum()),
        "minimo_procesos": config.MINIMO_PROCESOS_MERCADO,
        "minimo_demanda_uit": config.MINIMO_DEMANDA_UIT_MERCADO,
    })
    reporte.seccion("mercados_desiertos", {
        "total": int(desiertas.sum()),
        "aptos_para_ranking": int((desiertas & aptas).sum()),
        "demanda_MM": round(float(maestro.loc[desiertas, "demanda_soles"].sum() / 1e6), 1),
    })
    reporte.seccion("concentracion", {
        "mediana": float(maestro["concentracion"].median()),
        "p90": float(maestro["concentracion"].quantile(0.9)),
        "maxima": float(maestro["concentracion"].max()),
    })
    if maestro["competencia_vigente"].notna().any():
        comp = maestro["competencia_vigente"].dropna()
        reporte.seccion("competencia_vigente", {
            "categorias_con_dato": int(comp.size),
            "mediana": float(comp.median()),
            "p90": float(comp.quantile(0.9)),
            "categorias_desiertas": int((comp == 0).sum()),
        })

    # La vista previa que antes iba al log ahora es un CSV consultable.
    #
    # El ranking se arma SOBRE LAS CATEGORÍAS APTAS, no sobre el maestro
    # completo. Sin este filtro el top se llena de compras únicas de treinta mil
    # soles cuyo adjudicatario salió del registro: cero competencia porque el
    # mercado no existe, no porque esté desatendido.
    ruta_csv = reporte.guardar_tabla(
        maestro[aptas].nlargest(100, "indice_oportunidad")[
            [c for c in
             ["cubso_descripcion", "indice_oportunidad", "demanda_soles",
              "n_procesos", "densidad_proveedores", "habilitados_capitulo",
              "competencia_vigente", "salieron_del_registro", "mercado_desierto",
              "apto_para_ranking", "espacio_mercado", "potencial_mercado",
              "accesibilidad", "ticket_promedio", "ticket_uit",
              "banda_ticket", "cuartil_demanda", "mes_pico", "es_estacional",
              "convocatorias_vigentes", "banda_competencia", "accionable_hoy"]
             if c in maestro.columns]
        ],
        "top100_indice_oportunidad",
    )
    log.info("Tabla de resultados escrita | %s", ruta_csv.name)

    # Panel aparte: mercados sin adjudicatario vigente. Se ordenan por demanda
    # y no por índice, porque acá la pregunta es cuánto vale el rubro que quedó
    # sin nadie en carrera. La banda de ticket va al lado para que se vea de un
    # vistazo cuáles están al alcance de una MYPE y cuáles son obra grande.
    if desiertas.any():
        ruta_des = reporte.guardar_tabla(
            maestro[desiertas].nlargest(200, "demanda_soles")[
                [c for c in
                 ["cubso_descripcion", "demanda_soles", "n_procesos",
                  "ganadores_historicos", "salieron_del_registro",
                  "ticket_uit", "banda_ticket", "apto_para_ranking",
                  "indice_oportunidad", "mes_pico", "convocatorias_vigentes"]
                 if c in maestro.columns]
            ],
            "mercados_desiertos",
        )
        log.info("Panel de mercados desiertos escrito | %s", ruta_des.name)

    ruta = reporte.guardar()
    log.info("Reporte de metricas escrito | %s", ruta.name)
    registrar_corrida("diagnostico")
    log.info("FIN diagnostico | estado=EXITO")


if __name__ == "__main__":
    main()

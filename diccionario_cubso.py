"""
diccionario_cubso.py — Fuente 5: puente CUBSO -> tipo de objeto -> capítulo RNP.

POR QUÉ EXISTE
--------------
La habilitación de un proveedor en el RNP está expresada por capítulo (bienes,
servicios, consultor de obras, ejecutor de obras), mientras que la demanda y
los adjudicados están a nivel de código CUBSO fino. Para cruzar habilitados
con adjudicados hace falta un puente que diga, para cada código CUBSO, a qué
capítulo pertenece.

El CUBSO es jerárquico (segmento -> familia -> clase -> ...) y está construido
sobre el estándar UNSPSC. El OECE publica el catálogo completo en Excel, con
el tipo de cada código. Ese archivo es la fuente ideal de este diccionario.

DOS MODOS DE CONSTRUCCIÓN
-------------------------
1. OFICIAL (preferido): si se coloca el Excel del CUBSO en
   normativa/cubso_oficial.xlsx, se lee de ahí el tipo de cada código.
   Descargable desde la sede del OECE (www.gob.pe/oece -> Publicaciones del
   SEACE -> Documentos de orientación -> "CUBSO").

2. DERIVADO (por defecto, sin dependencias externas): se infiere el tipo de
   cada categoría CUBSO a partir del propio detalle OCDS, que ya trae el
   `mainProcurementCategory` (goods / services / works / consultingServices)
   de cada proceso. Se asigna a cada CUBSO el tipo mayoritario observado.

El modo derivado permite que el pipeline corra de punta a punta sin descargas
adicionales; el modo oficial lo hace más preciso cuando el Excel está presente.

Uso:
    python diccionario_cubso.py            # deriva desde OCDS
    python diccionario_cubso.py --oficial  # usa normativa/cubso_oficial.xlsx
"""

from __future__ import annotations

import argparse

import pandas as pd

import config
from utils import Cronometro, Reporte, crear_logger

log = crear_logger("diccionario_cubso")

EXCEL_OFICIAL = config.NORMATIVA_DIR / "cubso_oficial.xlsx"
PARQUET_DICCIONARIO = config.PROCESSED_DIR / "diccionario_cubso.parquet"

TIPO_A_CAPITULO = {
    "goods": "BIENES",
    "services": "SERVICIOS",
    "works": "EJECUTOR_DE_OBRAS",
    "consultingServices": "CONSULTOR_DE_OBRAS",
}


def derivar_desde_ocds() -> pd.DataFrame:
    """Infiere el capítulo de cada CUBSO a partir del tipo observado en OCDS.

    A cada descripción CUBSO se le asigna el tipo de objeto (goods/services/
    works/consulting) que aparece con mayor frecuencia en los procesos donde
    fue clasificada. Es una aproximación razonable: en la práctica una
    categoría CUBSO pertenece de forma estable a un único capítulo.
    """
    if not config.PARQUET_OCDS.exists():
        raise FileNotFoundError(
            "No existe ocds_procesos.parquet. Ejecute ingesta_ocds.py "
            "(el modo --demo también sirve para probar el puente)."
        )
    cols = ["cubso_id", "cubso_descripcion", "tipo_objeto"]
    detalle = pd.read_parquet(config.PARQUET_OCDS, columns=cols)
    detalle = detalle.dropna(subset=["cubso_descripcion"])

    # tipo mayoritario por categoría
    conteo = (detalle.groupby(["cubso_descripcion", "tipo_objeto"],
                              observed=True).size()
              .reset_index(name="n"))
    idx = conteo.groupby("cubso_descripcion", observed=True)["n"].idxmax()
    mayor = conteo.loc[idx, ["cubso_descripcion", "tipo_objeto"]]

    # un código representativo por descripción (para conservar la jerarquía)
    codigo = (detalle.dropna(subset=["cubso_id"])
              .groupby("cubso_descripcion", observed=True)["cubso_id"]
              .first().reset_index())

    dic = mayor.merge(codigo, on="cubso_descripcion", how="left")
    dic["capitulo_rnp"] = dic["tipo_objeto"].map(TIPO_A_CAPITULO).fillna("SERVICIOS")
    dic["segmento"] = dic["cubso_id"].astype("string").str[:2]
    dic["origen"] = "derivado_ocds"
    log.info("Diccionario derivado desde OCDS | estado=EXITO")
    return dic[["cubso_id", "cubso_descripcion", "segmento",
                "tipo_objeto", "capitulo_rnp", "origen"]]


# Hojas del Excel oficial y su capítulo del RNP. El archivo trae una hoja por
# capítulo, así que la clasificación no se infiere de ninguna columna: viene
# dada por la estructura del propio catálogo.
#
# La columna "Tipo de ítem" del Excel confirma además el mapeo de IDs que la
# ficha del RNP entrega en `lscIdTipRegVig`, que hasta ahora era una hipótesis:
#   1-BIENES · 2-SERVICIOS · 3-OBRAS · 4-CONSULTORIAS OBRAS
HOJAS_OFICIALES = {
    "BIENES": "BIENES",
    "SERVICIOS": "SERVICIOS",
    "OBRAS": "EJECUTOR_DE_OBRAS",
    "CONSULTORIA DE OBRAS": "CONSULTOR_DE_OBRAS",
}

# Los datos empiezan en la fila 7: las seis primeras son título, capítulo,
# nivel, la nota legal y el encabezado partido en dos renglones.
FILAS_PREAMBULO = 6


def leer_oficial() -> pd.DataFrame:
    """Lee el diccionario desde el Excel oficial del CUBSO.

    ESTRUCTURA DEL ARCHIVO
    ----------------------
    El OECE publica el CUBSO como un XLSX con una hoja por capítulo (BIENES,
    SERVICIOS, OBRAS, CONSULTORIA DE OBRAS). Cada hoja arranca con seis filas
    de preámbulo (título, capítulo, nivel, nota legal y el encabezado partido
    en dos renglones) y a partir de la séptima trae cuatro columnas útiles:
    número correlativo, código de 16 dígitos, título del ítem y tipo.

    Esto es lo que el modo derivado no puede darnos: el `mainProcurementCategory`
    del OCDS distingue goods / services / works, pero no separa la ejecución de
    obra de la consultoría de obra. En el RNP son capítulos distintos, con
    requisitos distintos, y a un proveedor le importa la diferencia.
    """
    if not EXCEL_OFICIAL.exists():
        raise FileNotFoundError(
            f"No se encontró {EXCEL_OFICIAL}. Descargue el CUBSO del OECE "
            "(gob.pe/oece -> Publicaciones del SEACE -> Documentos de "
            "orientación, filtrando por CUBSO) o use el modo derivado."
        )

    partes = []
    for hoja, capitulo in HOJAS_OFICIALES.items():
        try:
            crudo = pd.read_excel(
                EXCEL_OFICIAL, sheet_name=hoja, skiprows=FILAS_PREAMBULO,
                usecols=[0, 1, 2, 3],
                names=["nro", "cubso_id", "cubso_descripcion", "tipo_item"],
                dtype=str,
            )
        except ValueError:
            log.warning("Hoja ausente en el Excel oficial | hoja=%s", hoja)
            continue

        crudo = crudo.dropna(subset=["cubso_id", "cubso_descripcion"])
        parte = pd.DataFrame({
            "cubso_id": crudo["cubso_id"].str.strip(),
            "cubso_descripcion": crudo["cubso_descripcion"].str.strip().str.upper(),
            "capitulo_rnp": capitulo,
        })
        log.info("Hoja leída | hoja=%s | filas=%d", hoja, len(parte))
        partes.append(parte)

    if not partes:
        raise ValueError("El Excel del CUBSO no contiene ninguna hoja esperada.")

    dic = pd.concat(partes, ignore_index=True)
    dic["segmento"] = dic["cubso_id"].str[:2]
    dic["tipo_objeto"] = dic["capitulo_rnp"]
    dic["origen"] = "excel_oficial"

    # Una misma descripción puede repetirse entre capítulos (por ejemplo un
    # título genérico que existe como bien y como servicio). Se conserva la
    # primera según el orden de HOJAS_OFICIALES, que va de lo más específico a
    # lo más general, y se deja registro de cuántas hubo.
    duplicadas = int(dic["cubso_descripcion"].duplicated().sum())
    if duplicadas:
        log.warning("Descripciones repetidas entre capitulos | cantidad=%d",
                    duplicadas)
    dic = dic.drop_duplicates(subset=["cubso_descripcion"], keep="first")

    log.info("Diccionario leído del Excel oficial | estado=EXITO")
    return dic[["cubso_id", "cubso_descripcion", "segmento",
                "tipo_objeto", "capitulo_rnp", "origen"]]


def combinar(oficial: pd.DataFrame, derivado: pd.DataFrame) -> pd.DataFrame:
    """Completa el catálogo oficial con lo derivado del OCDS.

    POR QUÉ HACEN FALTA LOS DOS
    ---------------------------
    El Excel oficial es preciso pero no exhaustivo respecto de lo que aparece
    en los datos: el CUBSO es dinámico y las descripciones del OCDS no siempre
    coinciden literalmente con el título del catálogo (abreviaturas, lotes,
    variantes de redacción). Quedarse solo con lo oficial dejaría sin capítulo
    a las categorías que no calzan exacto, y quedarse solo con lo derivado
    perdería la distinción entre ejecución y consultoría de obra.

    La combinación toma el capítulo oficial donde la descripción coincide y
    cae al derivado donde no. La columna `origen` deja ver cuál alimentó cada
    fila, que es lo que permite declarar la precisión del cruce sin estimarla.
    """
    faltantes = derivado[~derivado["cubso_descripcion"]
                         .isin(set(oficial["cubso_descripcion"]))]
    combinado = pd.concat([oficial, faltantes], ignore_index=True)
    log.info("Diccionario combinado | oficial=%d | derivado=%d | total=%d",
             len(oficial), len(faltantes), len(combinado))
    return combinado


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construye el diccionario CUBSO -> capítulo RNP"
    )
    parser.add_argument("--oficial", action="store_true",
                        help="Usa el Excel oficial del CUBSO y lo completa con "
                             "lo derivado de OCDS para las categorías que no "
                             "aparezcan en el catálogo")
    parser.add_argument("--solo-oficial", action="store_true",
                        help="Usa únicamente el Excel oficial, sin completar")
    args = parser.parse_args()

    log.info("INICIO diccionario CUBSO | oficial=%s | solo_oficial=%s",
             args.oficial, args.solo_oficial)
    reporte = Reporte("diccionario_cubso")

    with Cronometro(log, "construcción del diccionario"):
        # Si el Excel oficial está presente se usa aunque no se pida por
        # bandera. El pipeline invoca este módulo sin argumentos, y obligarlo a
        # recordar `--oficial` significaría que colocar el archivo no sirviera
        # de nada en la corrida automática, que es donde más importa.
        usar_oficial = args.oficial or args.solo_oficial or EXCEL_OFICIAL.exists()
        if usar_oficial and not (args.oficial or args.solo_oficial):
            log.info("Excel oficial detectado | se usa sin necesidad de --oficial")

        if args.solo_oficial:
            dic = leer_oficial()
            origen = "excel_oficial"
        elif usar_oficial:
            dic = combinar(leer_oficial(), derivar_desde_ocds())
            origen = "oficial_mas_derivado"
        else:
            dic = derivar_desde_ocds()
            origen = "derivado_ocds"

        dic = dic.drop_duplicates(subset=["cubso_descripcion"])
        dic.to_parquet(PARQUET_DICCIONARIO, engine="pyarrow",
                       compression="snappy", index=False)
        log.info("Archivo escrito | %s", PARQUET_DICCIONARIO.name)

    reporte.metrica("origen", origen)
    reporte.metrica("categorias", int(len(dic)))
    reporte.seccion("por_capitulo", dic["capitulo_rnp"].value_counts().to_dict())
    reporte.seccion("por_origen", dic["origen"].value_counts().to_dict())

    # Cobertura contra lo que realmente aparece en los datos: el número que
    # importa no es cuántas categorías tiene el catálogo, sino cuántas de las
    # que el Estado compró quedaron clasificadas.
    if config.PARQUET_DEMANDA.exists():
        demanda = pd.read_parquet(config.PARQUET_DEMANDA,
                                  columns=["cubso_descripcion"])
        con_capitulo = demanda["cubso_descripcion"].isin(
            set(dic["cubso_descripcion"])).mean()
        reporte.metrica("cobertura_sobre_demanda_pct", round(100 * con_capitulo, 2))
        log.info("Cobertura del diccionario sobre la demanda | pct=%.2f",
                 100 * con_capitulo)

    ruta = reporte.guardar()
    log.info("Reporte de metricas escrito | %s", ruta.name)
    log.info("FIN diccionario CUBSO | estado=EXITO")


if __name__ == "__main__":
    main()

"""
formalidades.py — Fuente 4: qué hay que cumplir para presentarse.

EL PROBLEMA QUE RESUELVE
------------------------
Encontrar una convocatoria pertinente es solo la mitad del camino. La otra
mitad —y la que efectivamente deja afuera a los proveedores nuevos— es
formal: no estar inscrito en el registro que corresponde, perder el plazo de
registro de participantes, preparar la oferta sobre las bases originales sin
leer las integradas, o descubrir después de ganar que no se puede constituir
la garantía de fiel cumplimiento.

Este módulo construye, para cada convocatoria vigente, una ficha de
requisitos que combina dos capas:

  CAPA NORMATIVA (transversal) — catálogo curado a partir de la Ley N.º 32069
  y su Reglamento (D.S. 009-2025-EF), con la base legal citada en cada
  requisito. Se filtra según el tipo de objeto del llamado: a un servicio no
  se le exige capacidad máxima de contratación, que solo aplica a obras.

  CAPA DOCUMENTAL (específica del llamado) — los documentos efectivamente
  publicados en el procedimiento (bases administrativas, pliego absolutorio,
  especificaciones técnicas), extraídos por monitor_convocatorias.py, más el
  cronograma con los plazos reales de cada etapa.

LÍMITE DECLARADO
----------------
La ficha es orientativa. Los requisitos exigibles en un procedimiento
concreto son los de sus bases integradas, que prevalecen sobre cualquier
resumen normativo. El módulo lo hace explícito en su salida en lugar de
dejarlo librado a la interpretación del usuario.

Uso:
    python formalidades.py                      # ficha de todas las vigentes
    python formalidades.py --ocid <ocid>        # ficha de una convocatoria
    python formalidades.py --tipo servicios     # solo requisitos de un objeto
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

import config
from utils import Cronometro, Reporte, crear_logger

log = crear_logger("formalidades")

# Mapeo del vocabulario OCDS (mainProcurementCategory) al del catálogo.
OBJETO_OCDS = {
    "goods": "bienes",
    "services": "servicios",
    "works": "obras",
    "consultingServices": "consultoria",
}


# ---------------------------------------------------------------------------
# 1. Catálogo normativo
# ---------------------------------------------------------------------------
def cargar_catalogo() -> dict:
    """Carga el catálogo de formalidades versionado con el proyecto."""
    if not config.CATALOGO_FORMALIDADES.exists():
        raise FileNotFoundError(
            f"No se encontró el catálogo en {config.CATALOGO_FORMALIDADES}. "
            "Debe acompañar al código (carpeta normativa/)."
        )
    with open(config.CATALOGO_FORMALIDADES, encoding="utf-8") as f:
        return json.load(f)


def requisitos_por_objeto(catalogo: dict, tipo_objeto: str | None) -> pd.DataFrame:
    """Devuelve los requisitos aplicables a un tipo de objeto contractual.

    Si el tipo es desconocido o el release no lo declara, se devuelven los
    requisitos transversales (los que aplican a los cuatro objetos), en vez
    de suponer una categoría que podría exigir de más o de menos.
    """
    objeto = OBJETO_OCDS.get(tipo_objeto or "", None)
    filas = []
    for req in catalogo["requisitos"]:
        aplica = req["aplica_a"]
        if objeto is None:
            pertinente = len(aplica) == 4  # solo los transversales
        else:
            pertinente = objeto in aplica
        if pertinente:
            filas.append({
                "id": req["id"],
                "etapa": req["etapa"],
                "requisito": req["requisito"],
                "detalle": req["detalle"],
                "base_legal": req["base_legal"],
                "critico": req["critico"],
            })
    orden = {e["clave"]: e["orden"] for e in catalogo["etapas"]}
    df = pd.DataFrame(filas)
    if not df.empty:
        df["orden_etapa"] = df["etapa"].map(orden)
        df = df.sort_values(["orden_etapa", "id"]).drop(columns="orden_etapa")
    return df


# ---------------------------------------------------------------------------
# 2. Ficha por convocatoria
# ---------------------------------------------------------------------------
def ficha_convocatoria(ocid: str, convocatorias: pd.DataFrame,
                       documentos: pd.DataFrame, cronograma: pd.DataFrame,
                       catalogo: dict) -> dict:
    """Arma la ficha completa de formalidades de una convocatoria.

    Combina la capa normativa (según el objeto contractual) con la capa
    documental (documentos y cronograma publicados en el propio llamado).
    """
    fila = convocatorias.loc[convocatorias["ocid"] == ocid]
    if fila.empty:
        raise KeyError(f"La convocatoria {ocid} no está en las vigentes descargadas.")
    conv = fila.iloc[0]

    reqs = requisitos_por_objeto(catalogo, conv.get("tipo_objeto"))

    docs = documentos[documentos["ocid"] == ocid] if not documentos.empty \
        else pd.DataFrame()
    tipos = catalogo["tipos_documento_ocds"]
    lista_docs = []
    for _, d in docs.iterrows():
        meta = tipos.get(d["tipo_documento"], {})
        lista_docs.append({
            "titulo": d["titulo"],
            "tipo": meta.get("nombre", d["tipo_documento"]),
            "por_que_importa": meta.get("por_que_importa", ""),
            "formato": d["formato"],
            "url": d["url"],
        })

    hitos = cronograma[cronograma["ocid"] == ocid] if not cronograma.empty \
        else pd.DataFrame()
    lista_hitos = []
    if not hitos.empty:
        hitos = hitos.sort_values("fecha_programada")
        ahora = pd.Timestamp.now(tz="UTC")
        for _, h in hitos.iterrows():
            dias = ((h["fecha_programada"] - ahora).total_seconds() / 86400
                    if pd.notna(h["fecha_programada"]) else None)
            lista_hitos.append({
                "hito": h["hito"],
                "fecha": (h["fecha_programada"].isoformat()
                          if pd.notna(h["fecha_programada"]) else None),
                "dias_restantes": round(dias, 1) if dias is not None else None,
                "vencido": bool(dias is not None and dias < 0),
            })

    # Alerta de documento faltante: si el llamado no publicó bases, el
    # proveedor no tiene con qué preparar la oferta todavía.
    tiene_bases = any(d["tipo"] == "Bases administrativas" for d in lista_docs)

    return {
        "ocid": ocid,
        "titulo": conv.get("titulo"),
        "entidad": conv.get("entidad"),
        "metodo_contratacion": conv.get("metodo_contratacion"),
        "tipo_objeto": conv.get("tipo_objeto"),
        "monto_referencial": (float(conv["monto_referencial"])
                              if pd.notna(conv.get("monto_referencial")) else None),
        "moneda": conv.get("moneda"),
        "vigencia": conv.get("vigencia"),
        "dias_para_cierre": (float(conv["dias_para_cierre"])
                             if pd.notna(conv.get("dias_para_cierre")) else None),
        "categoria_cubso": conv.get("cubso_descripcion"),
        "url_ficha": conv.get("url_ficha"),
        "requisitos": reqs.to_dict(orient="records"),
        "documentos": lista_docs,
        "cronograma": lista_hitos,
        "alertas": ([] if tiene_bases else
                    ["El llamado aún no publica bases administrativas; "
                     "los requisitos definitivos no están disponibles."]),
        "advertencia": catalogo["advertencia"],
        "marco_legal": catalogo["marco_legal"],
    }


# ---------------------------------------------------------------------------
# 3. Orquestación
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ficha de formalidades para presentarse a un llamado"
    )
    parser.add_argument("--ocid", help="Genera la ficha de una convocatoria puntual")
    parser.add_argument("--tipo", choices=sorted(set(OBJETO_OCDS.values())),
                        help="Lista los requisitos de un tipo de objeto y termina")
    args = parser.parse_args()

    log.info("INICIO formalidades | ocid=%s | tipo=%s", args.ocid, args.tipo)
    catalogo = cargar_catalogo()
    reporte = Reporte("formalidades")
    reporte.metrica("version_catalogo", catalogo["version"])
    reporte.metrica("requisitos_en_catalogo", len(catalogo["requisitos"]))

    # --- Modo consulta del catálogo (no requiere convocatorias) -------------
    if args.tipo:
        inverso = {v: k for k, v in OBJETO_OCDS.items()}
        reqs = requisitos_por_objeto(catalogo, inverso[args.tipo])
        reporte.metrica("tipo_objeto_consultado", args.tipo)
        reporte.seccion("requisitos", reqs.to_dict(orient="records"))
        ruta = reporte.guardar()
        log.info("Reporte escrito | %s", ruta.name)
        log.info("FIN formalidades | estado=EXITO")
        return

    # --- Modo ficha sobre convocatorias vigentes ---------------------------
    if not config.PARQUET_CONVOCATORIAS.exists():
        raise FileNotFoundError(
            "No existe convocatorias_vigentes.parquet. "
            "Ejecute primero monitor_convocatorias.py (admite --demo)."
        )

    with Cronometro(log, "carga de convocatorias y documentos"):
        convocatorias = pd.read_parquet(config.PARQUET_CONVOCATORIAS)
        documentos = (pd.read_parquet(config.PARQUET_DOCUMENTOS)
                      if config.PARQUET_DOCUMENTOS.exists() else pd.DataFrame())
        cronograma = (pd.read_parquet(config.PARQUET_CRONOGRAMA)
                      if config.PARQUET_CRONOGRAMA.exists() else pd.DataFrame())

    vigentes = convocatorias[convocatorias["vigencia"].isin(["VIGENTE", "POR CERRAR"])]

    with Cronometro(log, "armado de fichas de formalidades"):
        objetivos = [args.ocid] if args.ocid else vigentes["ocid"].tolist()
        fichas = []
        errores = 0
        for ocid in objetivos:
            try:
                fichas.append(ficha_convocatoria(ocid, convocatorias, documentos,
                                                 cronograma, catalogo))
            except KeyError:
                errores += 1
                log.warning("Convocatoria no encontrada | se omite")

    reporte.metrica("fichas_generadas", len(fichas))
    reporte.metrica("fichas_omitidas", errores)
    reporte.seccion("fichas", fichas[:20])  # muestra acotada en el reporte
    ruta = reporte.guardar()
    log.info("Reporte escrito | %s", ruta.name)
    log.info("FIN formalidades | estado=EXITO")


if __name__ == "__main__":
    main()

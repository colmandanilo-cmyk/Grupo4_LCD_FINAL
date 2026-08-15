"""revisar_documentos.py — diagnóstico rápido del parquet de documentos.

Responde tres preguntas antes de la demo:
  1. ¿La descarga trae documentos?
  2. ¿Qué llamados tienen más documentos?
  3. ¿Alguno de esos llamados sigue vigente?

Uso (CMD, desde la carpeta del proyecto):
    python revisar_documentos.py
"""

import sys

import pandas as pd

import config

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 70)


def cargar(ruta):
    if not ruta.exists():
        print(f"[FALTA] No existe el archivo: {ruta}")
        return None
    return pd.read_parquet(ruta)


documentos = cargar(config.PARQUET_DOCUMENTOS)
convocatorias = cargar(config.PARQUET_CONVOCATORIAS)

print("=" * 78)
print("1. ¿HAY DOCUMENTOS EN LA DESCARGA?")
print("=" * 78)

if documentos is None or documentos.empty:
    print("RESULTADO: el parquet de documentos está vacío.")
    print("El Paso 3 nunca va a mostrar documentos reales hasta que")
    print("monitor_convocatorias.py guarde el bloque 'documents' de los releases.")
    raise SystemExit(0)

print(f"Filas de documentos      : {len(documentos):,}")
print(f"Llamados con documentos  : {documentos['ocid'].nunique():,}")
print(f"Columnas disponibles     : {list(documentos.columns)}")
print()
print("Tipos de documento más frecuentes:")
print(documentos["tipo_documento"].value_counts().head(10).to_string())

print()
print("=" * 78)
print("2. LLAMADOS CON MÁS DOCUMENTOS")
print("=" * 78)

conteo = (
    documentos.groupby("ocid")
    .size()
    .reset_index(name="n_documentos")
    .sort_values("n_documentos", ascending=False)
)

if convocatorias is None or convocatorias.empty:
    print(conteo.head(15).to_string(index=False))
    raise SystemExit(0)

detalle = conteo.merge(convocatorias, on="ocid", how="left")

columnas = [
    c
    for c in [
        "ocid", "n_documentos", "fecha_publicacion", "vigencia",
        "entidad", "titulo", "cubso_descripcion", "monto_referencial",
    ]
    if c in detalle.columns
]
print(detalle[columnas].head(15).to_string(index=False))

print()
print("=" * 78)
print("3. ¿ALGUNO SIGUE VIGENTE? (los mejores para la demo)")
print("=" * 78)

if "vigencia" in detalle.columns:
    vigentes = detalle[detalle["vigencia"].isin(["VIGENTE", "POR CERRAR"])]
    if vigentes.empty:
        print("Ningún llamado con documentos sigue vigente.")
        print("Para la demo igual sirven: en el Paso 2 desmarca el filtro de")
        print("categoría y marca 'Solo llamados con documentos publicados'.")
    else:
        print(f"{len(vigentes)} llamados vigentes con documentos:")
        print(vigentes[columnas].head(10).to_string(index=False))
        mejor = vigentes.iloc[0]
        print()
        print("SUGERIDO PARA LA DEMO:")
        print(f"  ocid      : {mejor['ocid']}")
        print(f"  documentos: {mejor['n_documentos']}")
        print(f"  titulo    : {mejor.get('titulo', '—')}")
        print(f"  categoria : {mejor.get('cubso_descripcion', '—')}")
else:
    print("La tabla de convocatorias no tiene columna 'vigencia'.")

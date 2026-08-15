"""
diag_fichas.py — Diagnóstico puntual de dos anomalías observadas.

No forma parte del pipeline: es una herramienta de investigación para entender
por qué (a) solo 80 de ~7900 fichas quedan como habilitadas y (b) solo 4 de
30 701 categorías obtienen saturación. Se puede borrar después.

Uso:
    python diag_fichas.py
"""

import json
from collections import Counter

import pandas as pd

import config

pd.set_option("display.width", 160)
pd.set_option("display.max_colwidth", 60)

print("=" * 72)
print("A. QUÉ HAY REALMENTE EN EL CACHÉ DE FICHAS")
print("=" * 72)

ruta_cache = config.CHECKPOINT_DIR / "fichas_proveedores_cache.json"
cache = json.load(open(ruta_cache, encoding="utf-8"))
print(f"Fichas en caché: {len(cache):,}\n")

fichas = pd.DataFrame(cache.values())
print("Columnas guardadas:", list(fichas.columns), "\n")

print("-- es_habilitado --")
print(fichas["es_habilitado"].value_counts(dropna=False).to_string())

print("\n-- es_apto_contratar --")
print(fichas["es_apto_contratar"].value_counts(dropna=False).to_string())

print("\n-- codigo_respuesta del endpoint --")
print(fichas["codigo_respuesta"].value_counts(dropna=False).head(10).to_string())

print("\n-- razon_social nula (ficha vacía = RUC sin registro) --")
vacias = fichas["razon_social"].isna()
print(f"Fichas sin razón social: {vacias.sum():,} de {len(fichas):,} "
      f"({vacias.mean():.1%})")

print("\n-- ids_capitulos_raw (el campo lscIdTipRegVig crudo) --")
print(fichas["ids_capitulos_raw"].value_counts(dropna=False).head(12).to_string())

print("\n-- capitulos_vigentes desplegados --")
plano = Counter()
for lista in fichas["capitulos_vigentes"]:
    plano.update(lista or [])
print(pd.Series(plano).sort_values(ascending=False).to_string() or "(vacío)")

print("\n-- cruce: habilitado x tiene capítulos --")
fichas["tiene_capitulos"] = fichas["capitulos_vigentes"].apply(
    lambda x: bool(x) and not all(str(c).startswith("DESCONOCIDO") for c in x))
print(pd.crosstab(fichas["es_habilitado"], fichas["tiene_capitulos"]).to_string())

print("\n-- una ficha CON habilitación, cruda --")
con = fichas[fichas["es_habilitado"]]
if not con.empty:
    print(json.dumps(cache[con.iloc[0]["proveedor_id"]], indent=2,
                     ensure_ascii=False)[:900])
else:
    print("(ninguna)")

print("\n-- una ficha SIN habilitación, cruda --")
sin = fichas[~fichas["es_habilitado"]]
if not sin.empty:
    print(json.dumps(cache[sin.iloc[0]["proveedor_id"]], indent=2,
                     ensure_ascii=False)[:900])

print("\n" + "=" * 72)
print("B. POR QUÉ EL CRUCE CUBSO -> CAPÍTULO NO PEGA")
print("=" * 72)

ruta_dic = config.PROCESSED_DIR / "diccionario_cubso.parquet"
if not ruta_dic.exists():
    print("NO EXISTE diccionario_cubso.parquet -> ejecutar diccionario_cubso.py")
else:
    dic = pd.read_parquet(ruta_dic)
    print(f"Filas del diccionario: {len(dic):,}")
    print(f"Columnas: {list(dic.columns)}\n")
    print("-- capitulo_rnp en el diccionario --")
    print(dic["capitulo_rnp"].value_counts(dropna=False).to_string())

densidad = pd.read_parquet(config.PARQUET_DENSIDAD)
print(f"\nFilas de densidad: {len(densidad):,}")
print(f"Columnas: {list(densidad.columns)}\n")

for col in ("capitulo_rnp", "habilitados_capitulo", "saturacion"):
    if col in densidad.columns:
        nn = densidad[col].notna().sum()
        print(f"  {col:24s} no nulos: {nn:,} ({nn/len(densidad):.2%})")

if "capitulo_rnp" in densidad.columns:
    print("\n-- capitulo_rnp que quedó en densidad --")
    print(densidad["capitulo_rnp"].value_counts(dropna=False).head(10).to_string())

# El punto crítico: ¿la clave de texto coincide entre las dos tablas?
if ruta_dic.exists():
    izq = set(densidad["cubso_descripcion"].dropna().astype(str))
    der = set(dic["cubso_descripcion"].dropna().astype(str))
    print(f"\n-- coincidencia de la clave cubso_descripcion --")
    print(f"  categorías en densidad     : {len(izq):,}")
    print(f"  categorías en diccionario  : {len(der):,}")
    print(f"  intersección               : {len(izq & der):,}")
    solo_izq = list(izq - der)[:3]
    if solo_izq:
        print(f"  ejemplos solo en densidad  : {solo_izq}")

# Y el otro punto: ¿el padrón tiene habilitados para esos capítulos?
if config.PARQUET_PADRON.exists():
    padron = pd.read_parquet(config.PARQUET_PADRON)
    print(f"\n-- padrón consolidado: {len(padron):,} filas --")
    print(padron["es_habilitado"].value_counts(dropna=False).to_string())

"""
sembrar_metadata.py — Siembra única de data/processed/metadata_corridas.json.

Reconstruye el metadato de corridas a partir de los nombres de los logs y
reportes que ya existen en local, sin volver a ejecutar ningún módulo. Toma
la marca de tiempo más reciente por módulo. Después de esta siembra, cada
módulo del pipeline mantiene el archivo al día por sí solo (registrar_corrida
en utils.py), así que este script se ejecuta UNA sola vez.

Incluye a ficha_proveedores aunque su módulo no registra corridas: su caché
no se vuelve a ejecutar (bloqueo de IP), de modo que la fecha sembrada acá es
la definitiva y así queda documentado.

Uso (desde la carpeta del proyecto):
    python sembrar_metadata.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import config

PREFIJOS = [
    "ingesta_ocds",
    "ficha_proveedores",
    "consulta_proveedores",
    "monitor_convocatorias",
    "diagnostico",
    "transformacion",
    "formalidades",
]

patron = re.compile(r"(\d{8}_\d{6})")
datos: dict[str, str] = {}

for carpeta in (config.LOG_DIR, config.REPORT_DIR):
    carpeta = Path(carpeta)
    if not carpeta.exists():
        continue
    for prefijo in PREFIJOS:
        for archivo in carpeta.glob(f"{prefijo}_*"):
            m = patron.search(archivo.name)
            if m and m.group(1) > datos.get(prefijo, ""):
                datos[prefijo] = m.group(1)

if not datos:
    raise SystemExit("No se encontró ningún log/reporte con marca de tiempo. "
                     "Ejecute este script desde la carpeta del proyecto.")

config.RUTA_METADATA_CORRIDAS.write_text(
    json.dumps(datos, indent=2, ensure_ascii=False, sort_keys=True),
    encoding="utf-8",
)

print(f"Escrito: {config.RUTA_METADATA_CORRIDAS}")
for prefijo in PREFIJOS:
    print(f"  {prefijo:24s} {datos.get(prefijo, 'sin corridas detectadas')}")

"""
pipeline.py — Orquestador de la actualización automática.

QUÉ RESUELVE
------------
El proyecto tiene siete etapas que deben correr en un orden concreto (cada una
depende de las anteriores). Ejecutarlas a mano es frágil: un comando olvidado o
un orden equivocado rompe la corrida. Este orquestador las encadena en un solo
comando, se detiene con un mensaje claro si alguna falla, y —pensado para
correr sin supervisión— limpia los logs y reportes antiguos para no acumular
archivos sin límite.

DOS FRECUENCIAS, POR LA NATURALEZA DE CADA FUENTE
-------------------------------------------------
No todas las fuentes cambian al mismo ritmo, así que actualizarlas todas a
diario sería un desperdicio (y descortés con los servidores del OECE):

  DIARIO   — Convocatorias vigentes (Fuente 3) + diagnóstico. Es lo único
             urgente: un llamado tiene fecha de cierre, y mostrarlo tarde
             equivale a no mostrarlo. También se refresca el año OCDS en curso,
             porque se publican procesos nuevos día a día.

  SEMANAL  — Todo: además de lo diario, la demanda histórica completa
             (Fuente 1), la habilitación de proveedores en lotes (Fuente 2) y
             el diccionario CUBSO (Fuente 5). Estas cambian de forma lenta;
             semanal va sobrado. El propio OECE replica el OCDS mensualmente.

El diseño de despliegue (a qué hora corre cada frecuencia en un servidor) está
documentado en crontab.txt. En Windows se demuestra con el Programador de
tareas apuntando a los .bat que llaman a este orquestador.

Uso:
    python pipeline.py --diario           # actualización diaria
    python pipeline.py --semanal          # actualización semanal completa
    python pipeline.py --semanal --demo   # ensayo sin red (para la demo)
    python pipeline.py --diario --retencion 15   # conserva 15 días de logs
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime

import config
from utils import Reporte, crear_logger, limpiar_antiguos

log = crear_logger("pipeline")

# Definición de las etapas. Cada una es (nombre, módulo, args, frecuencia).
# 'diario' corre en ambas frecuencias; 'semanal' solo en la corrida semanal.
# El orden de la lista ES el orden de ejecución y respeta las dependencias.
ETAPAS = [
    ("Ingesta OCDS (demanda + adjudicados)", "ingesta_ocds",
     ["--refrescar"], "diario"),
    ("Diccionario CUBSO (puente a capítulo RNP)", "diccionario_cubso",
     [], "semanal"),
    ("Ficha de proveedores (habilitación por RUC)", "ficha_proveedores",
     ["--limite", "500"], "semanal"),
    ("Densidad de dos capas (adjudicados + habilitados)", "consulta_proveedores",
     [], "semanal"),
    ("Monitor de convocatorias vigentes", "monitor_convocatorias",
     [], "diario"),
    ("Ficha de formalidades", "formalidades",
     [], "diario"),
    ("Diagnóstico e integración (dataset maestro)", "diagnostico",
     [], "diario"),
]


def correr_etapa(nombre: str, modulo: str, args: list[str], demo: bool) -> bool:
    """Ejecuta un módulo como subproceso y devuelve True si terminó bien.

    Se ejecuta cada etapa en su propio proceso (python -m modulo) para que un
    fallo quede aislado: no contamina el estado del orquestador y su traza de
    error queda en el log del propio módulo.
    """
    comando = [sys.executable, f"{modulo}.py", *args]
    if demo and modulo in ("ingesta_ocds", "ficha_proveedores",
                           "monitor_convocatorias"):
        comando.append("--demo")

    log.info("Etapa INICIO | %s", nombre)
    inicio = time.perf_counter()
    resultado = subprocess.run(comando, cwd=str(config.BASE_DIR),
                               capture_output=True, text=True)
    duracion = time.perf_counter() - inicio

    if resultado.returncode == 0:
        log.info("Etapa OK | %s | duracion=%.1fs", nombre, duracion)
        return True

    # El detalle del error ya está en el log del módulo; acá solo se registra
    # el desenlace y la última línea de stderr para orientar (sin volcar datos).
    ultima = (resultado.stderr.strip().splitlines() or ["(sin stderr)"])[-1][:200]
    log.error("Etapa FALLA | %s | codigo=%s | detalle=%s",
              nombre, resultado.returncode, ultima)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orquestador de actualización del Radar de Oportunidades")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--diario", action="store_true",
                       help="Corre solo las etapas de frecuencia diaria")
    grupo.add_argument("--semanal", action="store_true",
                       help="Corre todas las etapas (actualización completa)")
    parser.add_argument("--demo", action="store_true",
                        help="Propaga --demo a las etapas de ingesta (sin red)")
    parser.add_argument("--retencion", type=int, default=30,
                        help="Días de logs/reportes a conservar (default 30)")
    args = parser.parse_args()

    frecuencia = "semanal" if args.semanal else "diario"
    log.info("=== INICIO PIPELINE | frecuencia=%s | demo=%s | %s ===",
             frecuencia, args.demo, datetime.now().isoformat(timespec="seconds"))
    reporte = Reporte("pipeline")
    reporte.metrica("frecuencia", frecuencia)
    reporte.metrica("modo_demo", args.demo)

    # En la corrida semanal se ejecutan todas las etapas; en la diaria, solo
    # las marcadas 'diario'.
    a_ejecutar = [e for e in ETAPAS
                  if frecuencia == "semanal" or e[3] == "diario"]

    inicio_total = time.perf_counter()
    ok, fallo = 0, None
    for nombre, modulo, etapa_args, _ in a_ejecutar:
        if correr_etapa(nombre, modulo, etapa_args, args.demo):
            ok += 1
        else:
            fallo = nombre
            break  # se detiene: las etapas siguientes dependen de esta

    # Higiene: borrar trazas viejas para que las corridas diarias no acumulen.
    borrados = limpiar_antiguos(args.retencion)
    log.info("Limpieza de trazas | logs_borrados=%d | reports_borrados=%d",
             borrados["logs"], borrados["reports"])

    duracion_total = time.perf_counter() - inicio_total
    reporte.metrica("etapas_ok", ok)
    reporte.metrica("etapas_totales", len(a_ejecutar))
    reporte.metrica("duracion_total_s", round(duracion_total, 1))
    reporte.metrica("trazas_borradas", borrados)

    if fallo is None:
        reporte.metrica("estado", "EXITO")
        reporte.guardar()
        log.info("=== FIN PIPELINE | estado=EXITO | etapas=%d | duracion=%.1fs ===",
                 ok, duracion_total)
    else:
        reporte.metrica("estado", "ERROR")
        reporte.metrica("etapa_fallida", fallo)
        reporte.guardar()
        log.error("=== FIN PIPELINE | estado=ERROR | fallo en: %s ===", fallo)
        sys.exit(1)  # código de salida ≠ 0: el Programador de tareas lo detecta


if __name__ == "__main__":
    main()

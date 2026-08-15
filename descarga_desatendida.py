"""Orquesta la descarga de fichas del RNP en ciclos, sin supervision.

Ejecuta N lotes seguidos de `ficha_proveedores.py`, pausa, y repite. La pausa
existe porque el servidor del OECE corta por IP cuando recibe peticiones
sostenidas: en las pruebas manuales aguanto tres corridas seguidas y empezo a
fallar en la cuarta.

El progreso se mide leyendo el cache, no la salida del subproceso. Asi el
orquestador no depende del formato de los logs y sigue funcionando si
`ficha_proveedores.py` cambia sus mensajes.

Uso tipico:

    python descarga_desatendida.py

Uso con parametros:

    python descarga_desatendida.py --lote 2000 --por-ciclo 3 --pausa 60 --tope 12000

Se corta con Ctrl+C en cualquier momento. El cache guarda tras cada ficha, asi
que nada de lo descargado se pierde.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent
MODULO = RAIZ / "ficha_proveedores.py"
CACHE = RAIZ / "data" / "checkpoints" / "fichas_proveedores_cache.json"

# Cuantos lotes seguidos sin avance se toleran antes de abandonar. Dos ciclos
# completos sin una sola ficha nueva significa bloqueo persistente o que ya no
# quedan RUC pendientes; en ninguno de los dos casos sirve seguir insistiendo.
CICLOS_ESTERILES_MAX = 2


def marca() -> str:
    return datetime.now().strftime("%H:%M:%S")


def estado_cache() -> tuple[int, int]:
    """Devuelve (fichas totales, fichas con razon social)."""
    if not CACHE.exists():
        return 0, 0
    try:
        datos = json.loads(CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # El cache puede estar a medio escribir si se lee justo durante un
        # volcado. No es un error: se reporta en la proxima vuelta.
        return -1, -1
    utiles = sum(1 for v in datos.values() if v.get("razon_social"))
    return len(datos), utiles


def correr_lote(limite: int) -> bool:
    """Lanza una corrida de ficha_proveedores.py. True si termino sin error."""
    proceso = subprocess.run(
        [sys.executable, str(MODULO), "--limite", str(limite)],
        cwd=RAIZ,
    )
    return proceso.returncode == 0


def esperar(minutos: int) -> None:
    fin = datetime.now() + timedelta(minutes=minutos)
    print(f"\n[{marca()}] Pausa de {minutos} min. Reanuda a las "
          f"{fin.strftime('%H:%M')}. Ctrl+C para cortar.\n")
    restante = minutos * 60
    while restante > 0:
        tramo = min(60, restante)
        time.sleep(tramo)
        restante -= tramo
        if restante and restante % 600 == 0:
            print(f"[{marca()}] Faltan {restante // 60} min de pausa.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lote", type=int, default=2000,
                    help="RUC por corrida (default 2000, ~52 min)")
    ap.add_argument("--por-ciclo", type=int, default=3,
                    help="corridas seguidas antes de pausar (default 3)")
    ap.add_argument("--pausa", type=int, default=60,
                    help="minutos de pausa entre ciclos (default 60)")
    ap.add_argument("--tope", type=int, default=0,
                    help="detenerse al alcanzar este total de fichas (0 = sin tope)")
    args = ap.parse_args()

    if not MODULO.exists():
        print(f"No encuentro {MODULO}. Corre esto desde la carpeta del proyecto.")
        return 1

    inicio = datetime.now()
    total_ini, utiles_ini = estado_cache()
    print(f"[{marca()}] Arranque. Cache: {total_ini:,} fichas "
          f"({utiles_ini:,} con razon social).")
    if args.tope:
        print(f"[{marca()}] Tope declarado: {args.tope:,} fichas.")

    ciclo = 0
    esteriles = 0

    try:
        while True:
            ciclo += 1
            antes_ciclo, _ = estado_cache()
            print(f"\n{'=' * 62}\n[{marca()}] CICLO {ciclo} — "
                  f"{args.por_ciclo} corridas de {args.lote} RUC\n{'=' * 62}")

            for n in range(1, args.por_ciclo + 1):
                antes, _ = estado_cache()
                print(f"\n[{marca()}] Ciclo {ciclo}, corrida {n}/{args.por_ciclo}")

                ok = correr_lote(args.lote)
                despues, utiles = estado_cache()
                nuevas = despues - antes if antes >= 0 and despues >= 0 else -1

                print(f"[{marca()}] Corrida {'OK' if ok else 'CON ERROR'} · "
                      f"nuevas={nuevas:,} · total={despues:,} · utiles={utiles:,}")

                if not ok:
                    print(f"[{marca()}] El modulo devolvio error. Corto el ciclo "
                          f"y paso a la pausa.")
                    break

                if nuevas == 0:
                    print(f"[{marca()}] Sin fichas nuevas: o el servidor esta "
                          f"cortando, o no quedan RUC pendientes.")
                    break

                if args.tope and despues >= args.tope:
                    print(f"\n[{marca()}] Tope de {args.tope:,} alcanzado.")
                    raise SystemExit(0)

            despues_ciclo, _ = estado_cache()
            avance = despues_ciclo - antes_ciclo
            print(f"\n[{marca()}] Fin del ciclo {ciclo}: +{avance:,} fichas.")

            esteriles = esteriles + 1 if avance <= 0 else 0
            if esteriles >= CICLOS_ESTERILES_MAX:
                print(f"[{marca()}] {esteriles} ciclos sin avance. Me detengo: "
                      f"revisa conectividad o si ya no quedan pendientes.")
                break

            esperar(args.pausa)

    except KeyboardInterrupt:
        print(f"\n[{marca()}] Interrumpido a mano.")
    except SystemExit:
        pass

    total_fin, utiles_fin = estado_cache()
    horas = (datetime.now() - inicio).total_seconds() / 3600
    print(f"\n{'=' * 62}")
    print(f"Fichas al inicio : {total_ini:,}")
    print(f"Fichas al final  : {total_fin:,}  (+{total_fin - total_ini:,})")
    print(f"Con razon social : {utiles_fin:,}")
    print(f"Tiempo total     : {horas:.1f} h")
    print(f"{'=' * 62}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
NOVA TECH - Simulador de dispositivos.

Reemplaza temporalmente a los equipos fisicos de cada obra (camaras, panel
solar, bateria, Starlink y modem 4G). Cada pocos segundos:

  1. Pregunta a Java por el inventario, la pausa/velocidad y las ordenes del
     Laboratorio de Simulacion (GET /api/ingest/sync).
  2. Ejecuta las ordenes y confirma cada una.
  3. Avanza el reloj virtual y los valores (simulacion automatica).
  4. Envia la telemetria de cada obra (POST /api/ingest/telemetry).

Ejecutar desde la carpeta simulator:   python main.py
Detener:                              Ctrl + C
"""
import sys
import time
from datetime import datetime

import config
import event_simulator
from api_client import ApiClient
from station_simulator import StationSimulator


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def wait_for_backend(client):
    """Espera a que el backend Java este listo (por ejemplo, si se inicio al mismo tiempo)."""
    if client.health():
        return
    log(f"Esperando al backend en {config.BACKEND_URL} ...")
    while not client.health():
        time.sleep(config.BACKEND_RETRY_SECONDS)


def apply_sync(client, stations, sync):
    """Actualiza las estaciones con el inventario de Java y ejecuta las ordenes pendientes."""
    codes = set()
    for site in sync.get("sites", []):
        codes.add(site["code"])
        station = stations.get(site["code"])
        if station is None:
            stations[site["code"]] = StationSimulator(site)
            log(f"Simulando la obra {site['code']} - {site.get('name', '')}")
        else:
            station.update_inventory(site)
    for code in list(stations):
        if code not in codes:
            del stations[code]
            log(f"La obra {code} ya no está en el inventario; se deja de simular")

    for command in sync.get("commands", []):
        execute_command(client, stations, command)


def execute_command(client, stations, command):
    name = command["command"]
    if name == "RESET":
        for station in stations.values():
            station.apply_command("RESET")
        success, message, events = True, "Simulación reiniciada en todas las obras", []
    else:
        station = stations.get(command.get("siteCode"))
        if station is None:
            success, message, events = False, f"Obra desconocida para el simulador: {command.get('siteCode')}", []
        else:
            success, message, events = station.apply_command(name, command.get("deviceCode"))
    log(f"Orden #{command['id']} {name}: {message}")
    for event in events:
        result = client.send_event(event)
        if result:
            alert = f", alerta #{result['alertId']}" if result.get("alertId") else ""
            log(f"  Evento {event['type']} enviado (severidad {result.get('severity')}{alert})")
    client.acknowledge(command["id"], success, message)


def send_telemetry(client, station):
    response = client.send_telemetry(station.telemetry_payload())
    if response is None:
        return
    before = station.connectivity.active_connection
    station.connectivity.apply_active_connection(response.get("activeConnection"))
    after = station.connectivity.active_connection
    if before != after:
        labels = {"STARLINK": "Starlink", "CELLULAR_4G": "4G de respaldo", "NONE": "sin conexión"}
        log(f"{station.code}: Java cambió la conexión activa a {labels.get(after, after)}")
    if response.get("eventsCreated") or response.get("alertsCreated"):
        log(f"{station.code}: Java registró {response.get('eventsCreated', 0)} evento(s) y "
            f"{response.get('alertsCreated', 0)} alerta(s). Estado general: {response.get('generalState')}")


def run():
    print("=" * 72)
    print(" NOVA TECH - Simulador de dispositivos (valores demostrativos)")
    print(f" Backend: {config.BACKEND_URL}")
    print(" Detener con Ctrl + C")
    print("=" * 72, flush=True)

    client = ApiClient()
    wait_for_backend(client)

    stations = {}
    last_tick = time.monotonic()
    last_sync = 0.0
    last_sent = {}
    last_status = time.monotonic()

    while True:
        now = time.monotonic()
        real_seconds = now - last_tick
        last_tick = now

        if now - last_sync >= config.SYNC_INTERVAL_SECONDS:
            last_sync = now
            sync = client.sync()
            if sync is not None:
                apply_sync(client, stations, sync)

        for station in list(stations.values()):
            station.advance(real_seconds)
            event = event_simulator.maybe_random_motion(station, real_seconds)
            if event:
                if client.send_event(event):
                    log(f"{station.code}: movimiento rutinario en {event['deviceCode']}")
                station.send_now = True

            due = now - last_sent.get(station.code, 0.0) >= config.TELEMETRY_INTERVAL_SECONDS
            if station.complete and (due or station.send_now):
                send_telemetry(client, station)
                last_sent[station.code] = now
                station.send_now = False

        if now - last_status >= config.STATUS_PRINT_SECONDS and stations:
            last_status = now
            log("Estado de las estaciones:")
            for station in stations.values():
                print("   " + station.status_line(), flush=True)

        time.sleep(config.LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nSimulador detenido.")
        sys.exit(0)

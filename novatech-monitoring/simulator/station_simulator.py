"""
Estacion de vigilancia simulada: una por obra.

Reune las camaras, la energia y la conectividad de la obra, mantiene su reloj
virtual (x1, x5, x20, pausa) y aplica las ordenes del Laboratorio de Simulacion.
"""
import random
from datetime import datetime, timedelta

import config
import event_simulator
from camera_simulator import CameraSimulator
from connectivity_simulator import ConnectivitySimulator
from energy_simulator import EnergySimulator


def _parse_time(value):
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


class StationSimulator:

    def __init__(self, site):
        """site: bloque de una obra tal como llega en GET /api/ingest/sync."""
        self.code = site["code"]
        self.name = site.get("name", self.code)
        self.enabled = site.get("enabled", True)
        self.speed = site.get("speed", 1)
        self.virtual_time = datetime.now().replace(microsecond=0)
        self.cameras = {}
        self.solar_code = self.battery_code = self.starlink_code = self.cellular_code = None
        self.send_now = True

        params = config.SITE_PARAMETERS.get(self.code, {})
        last = site.get("lastKnown") or {}
        battery = last.get("batteryPercent")
        energy_today = last.get("solarEnergyTodayKwh") or 0.0
        last_time = _parse_time(last.get("deviceTime"))
        if last_time is None or last_time.date() != self.virtual_time.date():
            energy_today = 0.0
        # La bateria continua desde el ultimo valor conocido por Java, asi el grafico no salta.
        self.energy = EnergySimulator(
            panel_w=params.get("panel_w", config.DEFAULT_PANEL_W),
            capacity_wh=params.get("capacity_wh", config.DEFAULT_CAPACITY_WH),
            battery_percent=battery if battery is not None else config.INITIAL_BATTERY_PERCENT,
            energy_today_kwh=energy_today)
        self.connectivity = ConnectivitySimulator()
        self.update_inventory(site)

    # ============================================================
    # Inventario y estado de simulacion que informa Java
    # ============================================================

    def update_inventory(self, site):
        self.name = site.get("name", self.name)
        self.enabled = site.get("enabled", self.enabled)
        speed = site.get("speed", self.speed)
        self.speed = speed if speed in config.ALLOWED_SPEEDS else 1
        seen = set()
        for device in site.get("devices", []):
            code, kind, status = device["code"], device["type"], device.get("status")
            if kind == "CAMERA":
                seen.add(code)
                camera = self.cameras.get(code)
                if camera is None:
                    self.cameras[code] = CameraSimulator(code, device.get("name", code), status)
                    self.send_now = True
                else:
                    camera.name = device.get("name", camera.name)
                    camera.apply_inventory_status(status)
            elif kind == "SOLAR_PANEL":
                self.solar_code = code
            elif kind == "BATTERY":
                self.battery_code = code
            elif kind == "STARLINK":
                self.starlink_code = code
            elif kind == "CELLULAR_4G":
                self.cellular_code = code
        for code in list(self.cameras):
            if code not in seen:
                del self.cameras[code]

    @property
    def complete(self):
        """True si la obra tiene todos sus equipos (se puede enviar telemetria)."""
        return all((self.solar_code, self.battery_code, self.starlink_code, self.cellular_code))

    # ============================================================
    # Avance del tiempo (simulacion automatica, seccion 34)
    # ============================================================

    def advance(self, real_seconds):
        """Avanza la estacion. En pausa el reloj no avanza y los valores quedan fijos."""
        virtual_seconds = real_seconds * self.speed if self.enabled else 0
        if virtual_seconds > 0:
            self.virtual_time += timedelta(seconds=virtual_seconds)
            self.connectivity.step()
            for camera in self.cameras.values():
                camera.step()
        self.energy.step(virtual_seconds, self.virtual_time, self.cameras.values(),
                         self.connectivity.starlink_online, self.connectivity.active_connection)

    # ============================================================
    # Ordenes del laboratorio (seccion 32)
    # ============================================================

    def apply_command(self, command, device_code=None):
        """
        Aplica una orden. Devuelve (exito, mensaje, eventos) donde eventos es la
        lista de eventos puntuales que hay que enviar a Java.
        """
        handler = {
            "RESTORE_NORMAL": self._restore_normal,
            "MOTION": self._motion,
            "INTRUSION": self._intrusion,
            "CAMERA_FAILURE": self._camera_failure,
            "CAMERA_RESTORE": self._camera_restore,
            "STARLINK_FAILURE": self._starlink_failure,
            "STARLINK_RESTORE": self._starlink_restore,
            "NETWORK_FAILURE": self._network_failure,
            "LOW_BATTERY": self._low_battery,
            "CRITICAL_BATTERY": self._critical_battery,
            "CLOUDY_DAY": self._cloudy_day,
            "SOLAR_FAILURE": self._solar_failure,
            "RESTORE_ENERGY": self._restore_energy,
            "RESET": self._reset,
        }.get(command)
        if handler is None:
            return False, f"Orden desconocida: {command}", []
        self.send_now = True
        return handler(device_code)

    def _restore_normal(self, _device_code):
        for camera in self.cameras.values():
            camera.restore()
            camera.motion_until = 0.0
        self.connectivity.restore_all()
        self.energy.restore()
        return True, f"{self.code}: todos los sistemas restaurados", []

    def _motion(self, device_code):
        camera = event_simulator.pick_camera(self.cameras, device_code)
        if camera is None:
            return False, "No hay una cámara en línea para detectar movimiento", []
        camera.trigger_motion()
        return True, f"Movimiento generado en {camera.code} ({camera.name})", [
            event_simulator.motion_event(self.code, camera, self.virtual_time)]

    def _intrusion(self, device_code):
        camera = event_simulator.pick_camera(self.cameras, device_code, for_intrusion=True)
        if camera is None:
            return False, "No hay una cámara en línea para simular la intrusión", []
        camera.trigger_motion()
        return True, f"Intrusión generada en {camera.code} ({camera.name})", [
            event_simulator.intrusion_event(self.code, camera, self.virtual_time)]

    def _camera_failure(self, device_code):
        camera = event_simulator.pick_camera(self.cameras, device_code)
        if camera is None:
            return False, "No hay una cámara en línea para desconectar", []
        camera.fail()
        return True, f"Cámara {camera.code} desconectada", []

    def _camera_restore(self, device_code):
        if device_code:
            camera = self.cameras.get(device_code)
            if camera is None:
                return False, f"La cámara {device_code} no existe en {self.code}", []
            camera.restore()
            return True, f"Cámara {camera.code} recuperada", []
        restored = [c.code for c in self.cameras.values() if c.status == "OFFLINE"]
        for camera in self.cameras.values():
            camera.restore()
        if not restored:
            return True, "No había cámaras desconectadas", []
        return True, "Cámaras recuperadas: " + ", ".join(restored), []

    def _starlink_failure(self, _device_code):
        self.connectivity.fail_starlink()
        return True, f"{self.code}: Starlink fuera de línea", []

    def _starlink_restore(self, _device_code):
        self.connectivity.restore_starlink()
        return True, f"{self.code}: Starlink en línea", []

    def _network_failure(self, _device_code):
        self.connectivity.fail_network()
        return True, f"{self.code}: Starlink y 4G fuera de línea", []

    def _low_battery(self, _device_code):
        self.energy.set_battery(config.LOW_BATTERY_PERCENT + random.uniform(-1, 1))
        return True, f"{self.code}: batería llevada a {self.energy.battery_percent:.1f} %", []

    def _critical_battery(self, _device_code):
        self.energy.set_battery(config.CRITICAL_BATTERY_PERCENT + random.uniform(-1, 1))
        return True, f"{self.code}: batería llevada a {self.energy.battery_percent:.1f} %", []

    def _cloudy_day(self, _device_code):
        self.energy.cloudy = True
        return True, f"{self.code}: día nublado (generación x{config.CLOUDY_FACTOR})", []

    def _solar_failure(self, _device_code):
        self.energy.panel_failed = True
        return True, f"{self.code}: falla del panel solar (generación 0 W)", []

    def _restore_energy(self, _device_code):
        self.energy.restore()
        return True, f"{self.code}: energía restaurada", []

    def _reset(self, _device_code):
        """REINICIAR: todo normal, bateria inicial y reloj virtual en la hora real."""
        self._restore_normal(None)
        self.energy.set_battery(config.INITIAL_BATTERY_PERCENT)
        self.virtual_time = datetime.now().replace(microsecond=0)
        return True, f"{self.code}: simulación reiniciada", []

    # ============================================================
    # JSON de telemetria (POST /api/ingest/telemetry)
    # ============================================================

    def telemetry_payload(self):
        self.energy.step(0, self.virtual_time, self.cameras.values(),
                         self.connectivity.starlink_online, self.connectivity.active_connection)
        return {
            "siteCode": self.code,
            "deviceTime": self.virtual_time.isoformat(timespec="seconds"),
            "cameras": [camera.reading() for camera in self.cameras.values()],
            "solarPanel": self.energy.solar_reading(self.solar_code),
            "battery": self.energy.battery_reading(self.battery_code),
            "consumption": self.energy.consumption_reading(),
            "starlink": self.connectivity.starlink_reading(self.starlink_code),
            "cellular": self.connectivity.cellular_reading(self.cellular_code),
        }

    def status_line(self):
        cams = sum(1 for c in self.cameras.values() if c.online)
        state = "en marcha" if self.enabled else "en pausa"
        return (f"{self.code} | {self.virtual_time:%H:%M} x{self.speed} {state:9s} | "
                f"batería {self.energy.battery_percent:5.1f} % | solar {self.energy.generation_w:5.0f} W | "
                f"consumo {self.energy.consumption_w:4.0f} W | cámaras {cams}/{len(self.cameras)} | "
                f"conexión {self.connectivity.active_connection}")

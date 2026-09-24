"""
Energia simulada de una estacion: panel solar, bateria y consumo.

Ciclo solar (seccion 23): generacion 0 de noche, sube por la manana, maxima al
mediodia, baja por la tarde. Bateria (seccion 24):
    bateria nueva = bateria actual + generacion - consumo
siempre entre 0 % y 100 %. Todos los valores son demostrativos.
"""
import math
import random

import config
from sim_utils import RandomWalk, clamp


def solar_fraction(hour):
    """Fraccion de la potencia nominal segun la hora (0.0 a 1.0). Sol entre las 6 y las 18."""
    if hour < 6 or hour >= 18:
        return 0.0
    return math.sin(math.pi * (hour - 6) / 12)


def is_night(hour):
    return hour < 6 or hour >= 18


class EnergySimulator:

    def __init__(self, panel_w, capacity_wh, battery_percent, energy_today_kwh=0.0):
        self.panel_w = panel_w
        self.capacity_wh = capacity_wh
        self.energy_wh = capacity_wh * clamp(battery_percent, 0, 100) / 100
        self.energy_today_kwh = energy_today_kwh
        self.cloudy = False
        self.panel_failed = False
        self.solar_noise = RandomWalk(config.SOLAR_RANDOM_MIN, config.SOLAR_RANDOM_MAX,
                                      config.SOLAR_RANDOM_STEP, 0.98)
        self.generation_w = 0.0
        self.cameras_w = 0.0
        self.connectivity_w = 0.0
        self.control_w = config.CONTROL_W
        self._day = None

    # ---------------- lecturas ----------------

    @property
    def battery_percent(self):
        return self.energy_wh / self.capacity_wh * 100

    @property
    def consumption_w(self):
        return self.cameras_w + self.connectivity_w + self.control_w

    @property
    def voltage(self):
        span = config.BATTERY_VOLTAGE_FULL - config.BATTERY_VOLTAGE_EMPTY
        return config.BATTERY_VOLTAGE_EMPTY + span * self.battery_percent / 100

    @property
    def autonomy_hours(self):
        """Horas que dura la bateria con el consumo actual."""
        return self.energy_wh / self.consumption_w if self.consumption_w > 0 else 0.0

    # ---------------- escenarios ----------------

    def set_battery(self, percent):
        self.energy_wh = self.capacity_wh * clamp(percent, 0, 100) / 100

    def restore(self):
        """RESTAURAR ENERGIA: panel operativo, sin nubes y bateria al menos en el nivel normal."""
        self.cloudy = False
        self.panel_failed = False
        if self.battery_percent < config.RESTORED_BATTERY_PERCENT:
            self.set_battery(config.RESTORED_BATTERY_PERCENT)

    # ---------------- simulacion ----------------

    def update_loads(self, hour, cameras, starlink_online, active_connection):
        """Recalcula generacion y consumo instantaneos (tambien en pausa)."""
        if self.panel_failed:
            self.generation_w = 0.0
        else:
            cloud = config.CLOUDY_FACTOR if self.cloudy else 1.0
            self.generation_w = self.panel_w * solar_fraction(hour) * self.solar_noise.value * cloud
        night = is_night(hour)
        self.cameras_w = sum(camera.consumption_w(night) for camera in cameras)
        starlink = config.STARLINK_ONLINE_W if starlink_online else config.STARLINK_SEARCHING_W
        cellular = config.CELLULAR_ACTIVE_W if active_connection == "CELLULAR_4G" else config.CELLULAR_STANDBY_W
        self.connectivity_w = starlink + cellular

    def step(self, virtual_seconds, virtual_time, cameras, starlink_online, active_connection):
        """
        Avanza la energia "virtual_seconds" segundos de tiempo simulado.
        Con virtual_seconds = 0 (pausa) solo actualiza los valores instantaneos.
        """
        hour = virtual_time.hour + virtual_time.minute / 60 + virtual_time.second / 3600
        if virtual_seconds > 0:
            self.solar_noise.next()
            self.control_w = config.CONTROL_W + random.uniform(-0.5, 0.5)
        self.update_loads(hour, cameras, starlink_online, active_connection)
        if virtual_seconds <= 0:
            return

        hours = virtual_seconds / 3600
        balance = min(self.generation_w - self.consumption_w, config.MAX_CHARGE_W)
        self.energy_wh = clamp(self.energy_wh + balance * hours, 0, self.capacity_wh)

        # Energia generada en el dia virtual (se reinicia a medianoche).
        if self._day != virtual_time.date():
            if self._day is not None:
                self.energy_today_kwh = 0.0
            self._day = virtual_time.date()
        self.energy_today_kwh += self.generation_w * hours / 1000

    # ---------------- JSON ----------------

    def solar_reading(self, code):
        return {
            "code": code,
            "status": "FALLA" if self.panel_failed else "ONLINE",
            "ratedPowerW": self.panel_w,
            "generationW": round(self.generation_w, 2),
            "energyTodayKwh": round(self.energy_today_kwh, 3),
            "lowGeneration": self.cloudy,
        }

    def battery_reading(self, code):
        return {
            "code": code,
            "status": "ONLINE",
            "percent": round(self.battery_percent, 2),
            "voltage": round(self.voltage, 2),
            "autonomyHours": round(self.autonomy_hours, 2),
        }

    def consumption_reading(self):
        return {
            "totalW": round(self.consumption_w, 2),
            "camerasW": round(self.cameras_w, 2),
            "connectivityW": round(self.connectivity_w, 2),
            "controlW": round(self.control_w, 2),
        }

"""
Camara de seguridad simulada.

No hay video: la camara solo informa su estado, FPS, senal, si esta grabando
y si detecto movimiento. El movimiento dura MOTION_SECONDS segundos reales.
"""
import random
import time

import config
from sim_utils import RandomWalk

ONLINE = "ONLINE"
OFFLINE = "OFFLINE"
MAINTENANCE = "MANTENIMIENTO"


class CameraSimulator:

    def __init__(self, code, name, status=ONLINE):
        self.code = code
        self.name = name
        self.status = MAINTENANCE if status == MAINTENANCE else ONLINE
        self.signal = RandomWalk.from_config(config.CAMERA_SIGNAL)
        self.fps = config.CAMERA_FPS
        self.motion_until = 0.0

    # ---------------- estado ----------------

    @property
    def online(self):
        return self.status == ONLINE

    def fail(self):
        """Escenario DESCONECTAR CAMARA."""
        if self.status != MAINTENANCE:
            self.status = OFFLINE
            self.motion_until = 0.0

    def restore(self):
        """Escenario RECUPERAR CAMARA (una camara en mantenimiento no cambia)."""
        if self.status == OFFLINE:
            self.status = ONLINE

    def apply_inventory_status(self, backend_status):
        """
        El mantenimiento lo decide el administrador en la plataforma: si Java
        dice MANTENIMIENTO la camara se detiene; si lo quita, vuelve a funcionar.
        """
        if backend_status == MAINTENANCE and self.status != MAINTENANCE:
            self.status = MAINTENANCE
            self.motion_until = 0.0
        elif backend_status != MAINTENANCE and self.status == MAINTENANCE:
            self.status = ONLINE

    # ---------------- movimiento ----------------

    def trigger_motion(self, now=None):
        now = time.monotonic() if now is None else now
        if self.online:
            self.motion_until = now + config.MOTION_SECONDS

    def motion_active(self, now=None):
        now = time.monotonic() if now is None else now
        return self.online and now < self.motion_until

    # ---------------- simulacion ----------------

    def step(self):
        """Variacion pequena de senal y FPS (solo si esta en linea)."""
        if self.online:
            self.signal.next()
            self.fps = config.CAMERA_FPS if random.random() > 0.1 else config.CAMERA_FPS - 1

    def consumption_w(self, night):
        if not self.online:
            return 0.0
        return config.CAMERA_NIGHT_W if night else config.CAMERA_DAY_W

    def reading(self, now=None):
        """Bloque de la camara en el JSON de telemetria."""
        online = self.online
        return {
            "code": self.code,
            "status": self.status,
            "fps": self.fps if online else 0,
            "signal": round(self.signal.value) if online else 0,
            "motion": self.motion_active(now),
            "recording": online,
        }

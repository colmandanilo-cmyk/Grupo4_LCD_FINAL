"""
Eventos puntuales que informan las camaras: movimiento e intrusion.

Solo se arma el JSON; la severidad y la alerta las decide Java.
No hay reconocimiento de personas ni vision artificial: son eventos simulados.
"""
import random

import config

MOTION = "MOTION_DETECTED"
INTRUSION = "INTRUSION_DETECTED"

# Para una intrusion elegida al azar se prefieren camaras de perimetro o acceso.
_INTRUSION_KEYWORDS = ("perímetro", "perimetro", "acceso")


def _device_time(virtual_time):
    return virtual_time.isoformat(timespec="seconds")


def motion_event(site_code, camera, virtual_time):
    return {
        "siteCode": site_code,
        "deviceCode": camera.code,
        "type": MOTION,
        "deviceTime": _device_time(virtual_time),
        "description": f"Movimiento detectado en {camera.name}",
    }


def intrusion_event(site_code, camera, virtual_time):
    return {
        "siteCode": site_code,
        "deviceCode": camera.code,
        "type": INTRUSION,
        "deviceTime": _device_time(virtual_time),
        "description": f"Intrusión detectada en {camera.name}: movimiento en zona restringida",
    }


def pick_camera(cameras, device_code=None, for_intrusion=False):
    """
    Camara destino de un escenario: la indicada por el laboratorio o una
    en linea elegida al azar. Devuelve None si no hay ninguna disponible.
    """
    if device_code:
        camera = cameras.get(device_code)
        return camera if camera is not None and camera.online else None
    online = [c for c in cameras.values() if c.online]
    if not online:
        return None
    if for_intrusion:
        preferred = [c for c in online if any(k in c.name.lower() for k in _INTRUSION_KEYWORDS)]
        if preferred:
            return random.choice(preferred)
    return random.choice(online)


def maybe_random_motion(station, real_seconds):
    """
    Movimiento ocasional de personal de obra en horario laboral (simulacion automatica).
    Devuelve el evento generado o None. Nunca genera intrusiones: esas son manuales.
    """
    if not config.RANDOM_MOTION_ENABLED or not station.enabled:
        return None
    hour = station.virtual_time.hour
    if not (config.WORK_HOUR_START <= hour < config.WORK_HOUR_END):
        return None
    probability = config.RANDOM_MOTION_PER_SITE_PER_MINUTE * real_seconds / 60
    if random.random() >= probability:
        return None
    camera = pick_camera(station.cameras)
    if camera is None:
        return None
    camera.trigger_motion()
    return motion_event(station.code, camera, station.virtual_time)

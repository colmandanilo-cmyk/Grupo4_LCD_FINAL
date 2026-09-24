"""
Configuracion del simulador de NOVA TECH.

Todos los valores de potencia, bateria, consumo, latencia, velocidad, senal,
autonomia y FPS son DEMOSTRATIVOS. No describen productos comerciales reales
(seccion 57 del enunciado) y pueden cambiarse libremente aqui.
"""
import os

# ---------------------------------------------------------------------------
# Conexion con el backend Java
# ---------------------------------------------------------------------------
# Se usa 127.0.0.1 y no "localhost": en algunas computadoras "localhost" apunta
# primero a IPv6 (::1) y el backend solo escucha en IPv4.
BACKEND_URL = os.environ.get("NOVATECH_BACKEND_URL", "http://127.0.0.1:8080/api")

# Clave del canal de dispositivos (cabecera X-Device-Key). Debe coincidir con
# novatech.ingest.api-key en backend/src/main/resources/application.properties.
DEVICE_KEY = os.environ.get("NOVATECH_INGEST_API_KEY", "novatech-sim-2026")

HTTP_TIMEOUT_SECONDS = 5

# ---------------------------------------------------------------------------
# Ritmo del simulador (segundos REALES, no dependen de la velocidad x1/x5/x20)
# ---------------------------------------------------------------------------
SYNC_INTERVAL_SECONDS = 2        # consulta de ordenes e inventario
TELEMETRY_INTERVAL_SECONDS = 5   # envio de telemetria de cada obra
LOOP_SLEEP_SECONDS = 0.5         # pausa del bucle principal
STATUS_PRINT_SECONDS = 30        # resumen en consola
BACKEND_RETRY_SECONDS = 5        # espera entre reintentos si Java no responde

ALLOWED_SPEEDS = (1, 5, 20)

# ---------------------------------------------------------------------------
# Energia
# ---------------------------------------------------------------------------
DEFAULT_PANEL_W = 800            # potencia nominal del panel solar (W)
DEFAULT_CAPACITY_WH = 5000       # capacidad del banco de baterias (Wh)

# Valores propios de algunas obras (los mismos que usa DataSeeder en Java).
SITE_PARAMETERS = {
    "OBRA-003": {"capacity_wh": 6000},
    "OBRA-004": {"panel_w": 600, "capacity_wh": 3500},
}

MAX_CHARGE_W = 400               # potencia maxima de carga de la bateria (W)

CAMERA_DAY_W = 7                 # consumo por camara de dia (W)
CAMERA_NIGHT_W = 9               # de noche (iluminacion infrarroja)
STARLINK_ONLINE_W = 45           # Starlink en linea
STARLINK_SEARCHING_W = 15        # Starlink caido, buscando senal
CELLULAR_ACTIVE_W = 6            # modem 4G en uso
CELLULAR_STANDBY_W = 2           # modem 4G en espera
CONTROL_W = 15                   # sistema de control (grabador, router, controlador)

BATTERY_VOLTAGE_EMPTY = 22.0     # voltaje con 0 %
BATTERY_VOLTAGE_FULL = 27.2      # voltaje con 100 %

SOLAR_RANDOM_MIN = 0.92          # variacion aleatoria de la generacion
SOLAR_RANDOM_MAX = 1.03
SOLAR_RANDOM_STEP = 0.01         # cambio maximo del factor en cada paso
CLOUDY_FACTOR = 0.25             # escenario DIA NUBLADO

INITIAL_BATTERY_PERCENT = 85     # bateria al iniciar (si Java no informa otra) y al reiniciar
LOW_BATTERY_PERCENT = 30         # escenario BATERIA BAJA
CRITICAL_BATTERY_PERCENT = 15    # escenario BATERIA CRITICA
RESTORED_BATTERY_PERCENT = 85    # minimo al RESTAURAR ENERGIA / OPERACION NORMAL

# ---------------------------------------------------------------------------
# Conectividad: (minimo, maximo, paso maximo por actualizacion, valor inicial)
# ---------------------------------------------------------------------------
STARLINK_LATENCY_MS = (30, 60, 3, 42)
STARLINK_DOWNLOAD_MBPS = (80, 220, 12, 150)
STARLINK_UPLOAD_MBPS = (10, 30, 2, 18)
STARLINK_PACKET_LOSS = (0.0, 1.5, 0.15, 0.3)

CELLULAR_SIGNAL = (55, 90, 2, 72)
CELLULAR_LATENCY_MS = (45, 95, 4, 65)
CELLULAR_DOWNLOAD_MBPS = (10, 45, 3, 28)
CELLULAR_UPLOAD_MBPS = (4, 15, 1, 9)

# ---------------------------------------------------------------------------
# Camaras
# ---------------------------------------------------------------------------
CAMERA_FPS = 25
CAMERA_SIGNAL = (75, 99, 1.5, 90)
MOTION_SECONDS = 30              # segundos reales que se ve "MOVIMIENTO DETECTADO"

# Movimiento ocasional automatico (personal de obra) en horario laboral.
RANDOM_MOTION_ENABLED = True
RANDOM_MOTION_PER_SITE_PER_MINUTE = 0.05   # probabilidad por obra y minuto real (~1 cada 20 min)
WORK_HOUR_START = 7
WORK_HOUR_END = 18

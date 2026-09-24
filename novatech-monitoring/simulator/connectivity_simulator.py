"""
Conectividad simulada de una estacion: Starlink (principal) y 4G (respaldo).

El simulador solo informa si cada enlace esta en linea y sus metricas.
QUIEN decide la conexion activa es Java (contingencia de la seccion 26):
la respuesta a cada telemetria trae "activeConnection" y aqui solo se aplica.
"""
import config
from sim_utils import RandomWalk

ONLINE = "ONLINE"
OFFLINE = "OFFLINE"


class ConnectivitySimulator:

    def __init__(self):
        self.starlink_online = True
        self.cellular_online = True
        self.active_connection = "STARLINK"
        self.latency = RandomWalk.from_config(config.STARLINK_LATENCY_MS)
        self.download = RandomWalk.from_config(config.STARLINK_DOWNLOAD_MBPS)
        self.upload = RandomWalk.from_config(config.STARLINK_UPLOAD_MBPS)
        self.packet_loss = RandomWalk.from_config(config.STARLINK_PACKET_LOSS)
        self.cell_signal = RandomWalk.from_config(config.CELLULAR_SIGNAL)
        self.cell_latency = RandomWalk.from_config(config.CELLULAR_LATENCY_MS)
        self.cell_download = RandomWalk.from_config(config.CELLULAR_DOWNLOAD_MBPS)
        self.cell_upload = RandomWalk.from_config(config.CELLULAR_UPLOAD_MBPS)

    # ---------------- escenarios ----------------

    def fail_starlink(self):
        self.starlink_online = False

    def restore_starlink(self):
        self.starlink_online = True

    def fail_network(self):
        """FALLA STARLINK + 4G: la obra queda sin conectividad."""
        self.starlink_online = False
        self.cellular_online = False

    def restore_all(self):
        self.starlink_online = True
        self.cellular_online = True

    def apply_active_connection(self, value):
        """Aplica la decision de Java (STARLINK, CELLULAR_4G o NONE)."""
        if value in ("STARLINK", "CELLULAR_4G", "NONE"):
            self.active_connection = value

    # ---------------- simulacion ----------------

    def step(self):
        """Variaciones pequenas de latencia, velocidades, perdida y senal."""
        if self.starlink_online:
            for walk in (self.latency, self.download, self.upload, self.packet_loss):
                walk.next()
        if self.cellular_online:
            for walk in (self.cell_signal, self.cell_latency, self.cell_download, self.cell_upload):
                walk.next()

    def expected_connection(self):
        """Conexion que deberia quedar activa; se usa hasta que Java responda."""
        if self.starlink_online:
            return "STARLINK"
        return "CELLULAR_4G" if self.cellular_online else "NONE"

    # ---------------- JSON ----------------

    def starlink_reading(self, code):
        up = self.starlink_online
        return {
            "code": code,
            "status": ONLINE if up else OFFLINE,
            "latencyMs": round(self.latency.value, 1) if up else None,
            "downloadMbps": round(self.download.value, 1) if up else None,
            "uploadMbps": round(self.upload.value, 1) if up else None,
            "packetLoss": round(self.packet_loss.value, 2) if up else None,
        }

    def cellular_reading(self, code):
        up = self.cellular_online
        return {
            "code": code,
            "status": ONLINE if up else OFFLINE,
            "signal": round(self.cell_signal.value) if up else None,
            "latencyMs": round(self.cell_latency.value, 1) if up else None,
            "downloadMbps": round(self.cell_download.value, 1) if up else None,
            "uploadMbps": round(self.cell_upload.value, 1) if up else None,
        }

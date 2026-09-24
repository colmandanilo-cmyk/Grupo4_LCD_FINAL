"""
Comunicacion HTTP con el backend Java (seccion 8).

El simulador solo HACE peticiones (no recibe conexiones), como un equipo en obra:
    GET  /api/ingest/sync                  inventario, pausa/velocidad y ordenes pendientes
    POST /api/ingest/telemetry             lectura completa de una estacion
    POST /api/ingest/events                evento puntual (movimiento, intrusion)
    POST /api/ingest/commands/{id}/ack     confirmacion de una orden
"""
import requests

import config


class ApiClient:

    def __init__(self, base_url=config.BACKEND_URL, device_key=config.DEVICE_KEY,
                 timeout=config.HTTP_TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        # El trafico es local: se ignoran los proxies configurados en el sistema.
        self.session.trust_env = False
        self.session.headers.update({"X-Device-Key": device_key, "Content-Type": "application/json"})
        self.connected = None

    # ---------------- endpoints ----------------

    def health(self):
        return self._request("GET", "/health", quiet=True) is not None

    def sync(self):
        return self._request("GET", "/ingest/sync")

    def send_telemetry(self, payload):
        return self._request("POST", "/ingest/telemetry", payload)

    def send_event(self, payload):
        return self._request("POST", "/ingest/events", payload)

    def acknowledge(self, command_id, success, message):
        self._request("POST", f"/ingest/commands/{command_id}/ack",
                      {"success": success, "message": message[:300]}, expect_body=False)

    # ---------------- auxiliares ----------------

    def _request(self, method, path, payload=None, expect_body=True, quiet=False):
        """Devuelve el JSON de respuesta, o None si hubo un error (ya informado en consola)."""
        try:
            response = self.session.request(method, self.base_url + path, json=payload, timeout=self.timeout)
        except requests.RequestException:
            self._set_connected(False, quiet)
            return None
        self._set_connected(True, quiet)
        if response.status_code >= 400:
            print(f"  [!] {method} {path} respondió {response.status_code}: {self._error_message(response)}")
            return None
        if not expect_body or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    def _set_connected(self, connected, quiet):
        if connected == self.connected:
            return
        if not quiet or connected:
            if connected:
                print(f"[OK] Conectado al backend en {self.base_url}")
            else:
                print(f"[!] El backend no responde en {self.base_url}. Reintentando...")
        self.connected = connected

    @staticmethod
    def _error_message(response):
        try:
            body = response.json()
            return body.get("message") or body.get("error") or response.text[:200]
        except ValueError:
            return response.text[:200]

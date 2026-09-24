"""
Verificacion del escenario completo de demostracion (seccion 56) por API.

Recorre los 30 pasos con el sistema en marcha (backend Java y simulador
Python) y muestra el resultado de cada uno. No reemplaza a la interfaz: hace
por HTTP lo mismo que haria una persona desde React.

Uso, desde la carpeta simulator/ y con el backend y el simulador corriendo:
    .venv\\Scripts\\python tests\\check_demo_flow.py        (Windows)
    .venv/bin/python tests/check_demo_flow.py               (Linux/macOS)

Conviene ejecutarlo con los datos recien reiniciados (reset_demo.bat): el
paso 5 exige que las cuatro obras esten en OPERACION NORMAL.
Termina con codigo 0 si todos los pasos pasan y 1 si alguno falla.
"""
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

SITE_CODE = "OBRA-001"
CAMERA_CODE = "CAM-001"
WAIT_SECONDS = 30          # espera maxima para que el simulador ejecute una orden
POLL_SECONDS = 0.5


class DemoFlowError(Exception):
    """Un paso no cumplio lo esperado."""


class Api:
    """Cliente minimo con sesion de usuario (Bearer token)."""

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers["Content-Type"] = "application/json"

    def request(self, method, path, body=None, expected=(200,)):
        try:
            response = self.session.request(method, self.base_url + path, json=body,
                                            timeout=config.HTTP_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise DemoFlowError(f"No se pudo conectar con {self.base_url}: {exc}") from exc
        if response.status_code not in expected:
            try:
                detail = response.json().get("message", response.text)
            except ValueError:
                detail = response.text
            raise DemoFlowError(f"{method} {path} respondio {response.status_code}: {detail}")
        return response.json() if response.content else None

    def get(self, path):
        return self.request("GET", path)

    def login(self, email, password):
        data = self.request("POST", "/auth/login", {"email": email, "password": password})
        self.session.headers["Authorization"] = "Bearer " + data["token"]
        return data["user"]


def wait_for(description, check, timeout=WAIT_SECONDS):
    """Repite "check" hasta que devuelva un valor verdadero o se acabe el tiempo."""
    deadline = time.time() + timeout
    while True:
        value = check()
        if value:
            return value
        if time.time() > deadline:
            raise DemoFlowError(f"Tiempo agotado esperando: {description}")
        time.sleep(POLL_SECONDS)


class DemoFlow:

    def __init__(self, api):
        self.api = api
        self.site = None
        self.camera_id = None
        self.alert_id = None
        self.incident_id = None
        self.results = []

    # ---------------- utilidades ----------------

    def site_detail(self):
        return self.api.get(f"/sites/{self.site['id']}")

    def general_state(self):
        return self.site_detail()["site"]["generalState"]

    def active_alerts(self):
        return self.api.get(f"/alerts?siteId={self.site['id']}&status=ACTIVAS&size=100")["items"]

    def run_scenario(self, path, device_id=None):
        body = {"siteId": self.site["id"]}
        if device_id is not None:
            body["deviceId"] = device_id
        data = self.api.request("POST", f"/simulation/{path}", body, expected=(202,))
        return data["command"]["id"]

    def wait_command(self, command_id):
        def executed():
            for command in self.api.get("/simulation/status")["commands"]:
                if command["id"] == command_id:
                    if command["status"] in ("FALLIDO", "EXPIRADO"):
                        raise DemoFlowError(f"La orden termino en {command['status']}: {command.get('result')}")
                    return command if command["status"] == "EJECUTADO" else None
            return None
        return wait_for(f"que el simulador ejecute la orden {command_id}", executed)

    def connectivity(self):
        return self.api.get(f"/connectivity/sites/{self.site['id']}")

    # ---------------- los 30 pasos ----------------

    def steps(self):
        api = self.api
        state = {}

        def step1():
            health = api.get("/health")
            if health.get("status") != "UP":
                raise DemoFlowError(f"El backend no esta listo: {health}")
            return f"backend en {config.BACKEND_URL}"

        def step2():
            user = api.login("admin@novatech.local", "Admin123*")
            if user["role"] != "ADMINISTRADOR":
                raise DemoFlowError(f"Rol inesperado: {user['role']}")
            return user["name"]

        def step3():
            sites = api.get("/sites")
            codes = sorted(s["code"] for s in sites)
            expected = ["OBRA-001", "OBRA-002", "OBRA-003", "OBRA-004"]
            if not all(code in codes for code in expected):
                raise DemoFlowError(f"Obras encontradas: {codes}")
            self.site = next(s for s in sites if s["code"] == SITE_CODE)
            state["sites"] = sites
            return ", ".join(expected)

        def step4():
            summary = api.get("/dashboard/summary")
            kpis = summary["kpis"]
            if len(summary["alerts24h"]) != 24 or kpis["camerasTotal"] < 12:
                raise DemoFlowError("El dashboard no trae los datos esperados")
            return f"{kpis['camerasOnline']}/{kpis['camerasTotal']} cámaras, batería promedio {kpis['averageBattery']:.0f} %"

        def step5():
            states = {s["code"]: s["generalState"] for s in state["sites"] if s["code"].startswith("OBRA-00")}
            not_normal = {code: st for code, st in states.items() if st != "NORMAL"}
            if not_normal:
                raise DemoFlowError(f"Obras fuera de la normalidad: {not_normal}. Ejecute reset_demo.bat")
            return "las cuatro en OPERACIÓN NORMAL"

        def step6():
            detail = self.site_detail()
            camera = next(d for d in detail["devices"] if d["code"] == CAMERA_CODE)
            self.camera_id = camera["id"]
            return detail["site"]["name"]

        def step7():
            cameras = api.get(f"/cameras?siteId={self.site['id']}")
            online = sum(1 for c in cameras if c["status"] == "ONLINE")
            if not cameras:
                raise DemoFlowError("La obra no tiene cámaras")
            return f"{online} de {len(cameras)} cámaras en línea"

        def step8():
            energy = api.get(f"/energy/sites/{self.site['id']}")
            return f"batería {energy['batteryPercent']:.1f} % ({energy['batteryLevel']})"

        def step9():
            connectivity = self.connectivity()
            if connectivity["activeConnection"] != "STARLINK":
                raise DemoFlowError(f"Conexión activa: {connectivity['activeConnection']}")
            return f"Starlink {connectivity['starlinkStatus']}"

        def step10():
            status = api.get("/simulation/status")
            if not status["simulatorOnline"]:
                raise DemoFlowError("El simulador Python no está conectado; inícielo antes de esta prueba")
            return "simulador conectado"

        def step11():
            state["events_before"] = api.get(
                f"/events?siteId={self.site['id']}&type=INTRUSION_DETECTED&size=1")["total"]
            state["intrusion_command"] = self.run_scenario("intrusion", self.camera_id)
            return f"orden #{state['intrusion_command']}"

        def step12():
            command = self.wait_command(state["intrusion_command"])
            return command.get("result") or "orden ejecutada"

        def step13():
            def new_event():
                page = api.get(f"/events?siteId={self.site['id']}&type=INTRUSION_DETECTED&size=1")
                return page["items"][0] if page["total"] > state["events_before"] else None
            event = wait_for("el evento de intrusión", new_event, timeout=10)
            state["event_id"] = event["id"]
            return f"evento #{event['id']} ({event['severity']})"

        def step14():
            def intrusion_alert():
                for alert in self.active_alerts():
                    if alert["alertType"] == "INTRUSION" and alert["eventId"] == state["event_id"]:
                        return alert
                return None
            alert = wait_for("la alerta de intrusión", intrusion_alert, timeout=10)
            self.alert_id = alert["id"]
            return f"alerta #{alert['id']} {alert['severity']}"

        def step15():
            alert = api.get(f"/alerts/{self.alert_id}")
            if alert["status"] != "NUEVA":
                raise DemoFlowError(f"Estado guardado: {alert['status']}")
            return "alerta guardada en la base (estado NUEVA)"

        def step16():
            ids = [a["id"] for a in api.get("/alerts?status=ACTIVAS&size=100")["items"]]
            if self.alert_id not in ids:
                raise DemoFlowError("La alerta no aparece en la lista que consulta la interfaz")
            return "visible en la lista de alertas activas"

        def step17():
            general = self.general_state()
            if general not in ("ADVERTENCIA", "CRITICO"):
                raise DemoFlowError(f"Estado general: {general}")
            return general

        def step18():
            alert = api.request("PUT", f"/alerts/{self.alert_id}/acknowledge")
            if alert["status"] != "RECONOCIDA":
                raise DemoFlowError(f"Estado: {alert['status']}")
            return "RECONOCIDA"

        def step19():
            incident = api.request("POST", "/incidents", {
                "alertId": self.alert_id,
                "title": "Verificar intrusión en acceso principal",
                "description": "Prueba automática del flujo de demostración.",
                "assignedToId": 2,
            }, expected=(201,))
            self.incident_id = incident["id"]
            alert = api.get(f"/alerts/{self.alert_id}")
            if alert["status"] != "EN_ATENCION":
                raise DemoFlowError(f"La alerta quedó en {alert['status']}")
            return f"{incident['code']}, alerta EN ATENCIÓN"

        def step20():
            api.request("PUT", f"/incidents/{self.incident_id}/status",
                        {"status": "EN_PROCESO", "observation": "Vigilante en camino"})
            incident = api.request("PUT", f"/incidents/{self.incident_id}/status",
                                   {"status": "RESUELTA", "observation": "Sin hallazgos"})
            alert = api.get(f"/alerts/{self.alert_id}")
            if incident["status"] != "RESUELTA" or alert["status"] != "RESUELTA":
                raise DemoFlowError(f"Incidencia {incident['status']}, alerta {alert['status']}")
            return "incidencia y alerta RESUELTAS"

        def step21():
            state["starlink_command"] = self.run_scenario("starlink-failure")
            return f"orden #{state['starlink_command']}"

        def step22():
            command = self.wait_command(state["starlink_command"])
            return command.get("result") or "orden ejecutada"

        def step23():
            connectivity = wait_for("Starlink OFFLINE",
                                    lambda: (c := self.connectivity())["starlinkStatus"] == "OFFLINE" and c,
                                    timeout=15)
            return f"Starlink {connectivity['starlinkStatus']}"

        def step24():
            connectivity = self.connectivity()
            if connectivity["activeConnection"] != "CELLULAR_4G":
                raise DemoFlowError(f"Conexión activa: {connectivity['activeConnection']}")
            return "conexión activa CELLULAR_4G"

        def step25():
            site = self.site_detail()["site"]
            if site["activeConnection"] != "CELLULAR_4G":
                raise DemoFlowError(f"La obra informa {site['activeConnection']}")
            return "la obra informa 4G DE RESPALDO"

        def step26():
            command_id = self.run_scenario("starlink-restore")
            self.wait_command(command_id)
            return f"orden #{command_id} ejecutada"

        def step27():
            connectivity = wait_for("vuelta a Starlink",
                                    lambda: (c := self.connectivity())["activeConnection"] == "STARLINK" and c,
                                    timeout=15)
            return f"conexión activa {connectivity['activeConnection']}"

        def step28():
            command_id = self.run_scenario("critical-battery")
            self.wait_command(command_id)
            return f"orden #{command_id} ejecutada"

        def step29():
            def battery_alert():
                return next((a for a in self.active_alerts() if a["alertType"] == "BATTERY_CRITICAL"), None)
            alert = wait_for("la alerta de batería crítica", battery_alert, timeout=15)
            return f"alerta #{alert['id']} {alert['severity']}"

        def step30():
            command_id = self.run_scenario("restore-normal")
            self.wait_command(command_id)
            wait_for("OPERACIÓN NORMAL", lambda: self.general_state() == "NORMAL" and not self.active_alerts(),
                     timeout=20)
            return "OPERACIÓN NORMAL, sin alertas activas"

        return [
            ("Ejecutar la aplicación", step1),
            ("Iniciar sesión como administrador", step2),
            ("Ver cuatro obras", step3),
            ("Ver dashboard completo", step4),
            ("Todas las obras comienzan normales", step5),
            (f"Entrar a {SITE_CODE}", step6),
            ("Visualizar cámaras", step7),
            ("Visualizar batería", step8),
            ("Visualizar Starlink", step9),
            ("Abrir Laboratorio de Simulación", step10),
            ("Ejecutar SIMULAR INTRUSIÓN", step11),
            ("Python genera evento", step12),
            ("Java recibe evento", step13),
            ("Java genera alerta", step14),
            ("SQLite almacena información", step15),
            ("React muestra la alerta", step16),
            ("Cambia el estado general", step17),
            ("Usuario reconoce alerta", step18),
            ("Usuario crea incidencia", step19),
            ("Usuario resuelve incidencia", step20),
            ("Ejecutar FALLA STARLINK", step21),
            ("Python coloca Starlink offline", step22),
            ("Java detecta el cambio", step23),
            ("Sistema activa 4G", step24),
            ("React muestra 4G DE RESPALDO", step25),
            ("Restaurar Starlink", step26),
            ("Sistema vuelve a conexión principal", step27),
            ("Ejecutar BATERÍA CRÍTICA", step28),
            ("Generar alerta", step29),
            ("Restaurar operación normal", step30),
        ]

    def run(self):
        print("NOVA TECH - Verificación del escenario de demostración (sección 56)\n")
        failed = 0
        for number, (title, action) in enumerate(self.steps(), start=1):
            try:
                detail = action()
                print(f"  OK     {number:2d}. {title}" + (f": {detail}" if detail else ""))
            except DemoFlowError as exc:
                failed += 1
                print(f"  FALLA  {number:2d}. {title}: {exc}")
                if number <= 10:
                    print("\nSin los pasos iniciales no se puede seguir. Revise que el backend y el simulador estén en marcha.")
                    break
        print()
        if failed:
            print(f"Resultado: {failed} paso(s) con falla.")
        else:
            print("Resultado: los 30 pasos funcionan.")
        return failed == 0


def main():
    ok = DemoFlow(Api(config.BACKEND_URL)).run()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

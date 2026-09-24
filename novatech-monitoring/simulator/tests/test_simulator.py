"""
Pruebas unitarias del simulador (no necesitan el backend).

Ejecutar desde la carpeta simulator:
    python -m unittest discover -s tests -t . -v
"""
import unittest
from datetime import datetime

import config
import event_simulator
from camera_simulator import CameraSimulator
from connectivity_simulator import ConnectivitySimulator
from energy_simulator import EnergySimulator, solar_fraction
from sim_utils import RandomWalk
from station_simulator import StationSimulator


def sample_site(code="OBRA-001", enabled=True, speed=1, battery=80.0, camera_status="ONLINE"):
    """Bloque de obra con la misma forma que GET /api/ingest/sync."""
    return {
        "code": code, "name": "Obra de prueba", "enabled": enabled, "speed": speed,
        "lastKnown": {"batteryPercent": battery, "solarEnergyTodayKwh": 1.0, "deviceTime": None},
        "devices": [
            {"code": "CAM-001", "type": "CAMERA", "name": "Acceso principal", "status": "ONLINE"},
            {"code": "CAM-002", "type": "CAMERA", "name": "Perímetro norte", "status": camera_status},
            {"code": "SOL-001", "type": "SOLAR_PANEL", "name": "Panel solar", "status": "ONLINE"},
            {"code": "BAT-001", "type": "BATTERY", "name": "Banco de baterías", "status": "ONLINE"},
            {"code": "STL-001", "type": "STARLINK", "name": "Antena Starlink", "status": "ONLINE"},
            {"code": "LTE-001", "type": "CELLULAR_4G", "name": "Módem 4G", "status": "ONLINE"},
        ],
    }


class SolarCycleTest(unittest.TestCase):

    def test_no_generation_at_night(self):
        self.assertEqual(solar_fraction(2), 0)
        self.assertEqual(solar_fraction(5.9), 0)
        self.assertEqual(solar_fraction(20), 0)

    def test_maximum_at_noon(self):
        self.assertAlmostEqual(solar_fraction(12), 1.0)
        self.assertLess(solar_fraction(8), solar_fraction(11))
        self.assertLess(solar_fraction(16), solar_fraction(13))

    def test_cloudy_day_reduces_generation(self):
        noon = datetime(2026, 9, 24, 12, 0)
        clear = EnergySimulator(800, 5000, 50)
        cloudy = EnergySimulator(800, 5000, 50)
        cloudy.cloudy = True
        clear.step(0, noon, [], True, "STARLINK")
        cloudy.step(0, noon, [], True, "STARLINK")
        self.assertAlmostEqual(cloudy.generation_w, clear.generation_w * config.CLOUDY_FACTOR, places=3)

    def test_panel_failure_means_zero_generation(self):
        energy = EnergySimulator(800, 5000, 50)
        energy.panel_failed = True
        energy.step(60, datetime(2026, 9, 24, 12, 0), [], True, "STARLINK")
        self.assertEqual(energy.generation_w, 0)
        self.assertEqual(energy.solar_reading("SOL-001")["status"], "FALLA")


class BatteryTest(unittest.TestCase):

    def test_battery_drains_at_night(self):
        energy = EnergySimulator(800, 5000, 80)
        energy.step(3600, datetime(2026, 9, 24, 23, 0), [CameraSimulator("CAM-001", "A")], True, "STARLINK")
        self.assertLess(energy.battery_percent, 80)

    def test_battery_charges_at_noon(self):
        energy = EnergySimulator(800, 5000, 50)
        energy.step(3600, datetime(2026, 9, 24, 12, 0), [], True, "STARLINK")
        self.assertGreater(energy.battery_percent, 50)

    def test_battery_never_leaves_0_100(self):
        energy = EnergySimulator(800, 5000, 99)
        for _ in range(10):
            energy.step(3600 * 5, datetime(2026, 9, 24, 12, 0), [], True, "STARLINK")
        self.assertLessEqual(energy.battery_percent, 100)
        energy.panel_failed = True
        for _ in range(50):
            energy.step(3600 * 5, datetime(2026, 9, 24, 23, 0), [], False, "NONE")
        self.assertGreaterEqual(energy.battery_percent, 0)
        self.assertEqual(round(energy.battery_percent), 0)

    def test_pause_does_not_change_battery(self):
        energy = EnergySimulator(800, 5000, 60)
        energy.step(0, datetime(2026, 9, 24, 12, 0), [], True, "STARLINK")
        self.assertAlmostEqual(energy.battery_percent, 60)


class RandomWalkTest(unittest.TestCase):

    def test_values_stay_in_range_and_change_little(self):
        walk = RandomWalk(30, 60, 3, 42)
        previous = walk.value
        for _ in range(1000):
            value = walk.next()
            self.assertTrue(30 <= value <= 60)
            self.assertLessEqual(abs(value - previous), 3 + 1e-9)
            previous = value


class CameraTest(unittest.TestCase):

    def test_offline_camera_reports_zero(self):
        camera = CameraSimulator("CAM-001", "Acceso principal")
        camera.fail()
        reading = camera.reading()
        self.assertEqual(reading["status"], "OFFLINE")
        self.assertEqual(reading["fps"], 0)
        self.assertFalse(reading["recording"])

    def test_motion_lasts_configured_seconds(self):
        camera = CameraSimulator("CAM-001", "Acceso principal")
        camera.trigger_motion(now=100.0)
        self.assertTrue(camera.motion_active(now=100.0 + config.MOTION_SECONDS - 1))
        self.assertFalse(camera.motion_active(now=100.0 + config.MOTION_SECONDS + 1))

    def test_maintenance_is_controlled_by_platform(self):
        camera = CameraSimulator("CAM-001", "Acceso principal")
        camera.apply_inventory_status("MANTENIMIENTO")
        camera.restore()
        self.assertEqual(camera.status, "MANTENIMIENTO")
        camera.apply_inventory_status("ONLINE")
        self.assertEqual(camera.status, "ONLINE")


class ConnectivityTest(unittest.TestCase):

    def test_starlink_failure_hides_metrics(self):
        connectivity = ConnectivitySimulator()
        connectivity.fail_starlink()
        reading = connectivity.starlink_reading("STL-001")
        self.assertEqual(reading["status"], "OFFLINE")
        self.assertIsNone(reading["latencyMs"])
        self.assertEqual(connectivity.expected_connection(), "CELLULAR_4G")

    def test_network_failure(self):
        connectivity = ConnectivitySimulator()
        connectivity.fail_network()
        self.assertEqual(connectivity.expected_connection(), "NONE")
        connectivity.restore_all()
        self.assertEqual(connectivity.expected_connection(), "STARLINK")

    def test_active_connection_comes_from_java(self):
        connectivity = ConnectivitySimulator()
        connectivity.apply_active_connection("CELLULAR_4G")
        self.assertEqual(connectivity.active_connection, "CELLULAR_4G")
        connectivity.apply_active_connection("VALOR_INVALIDO")
        self.assertEqual(connectivity.active_connection, "CELLULAR_4G")


class StationTest(unittest.TestCase):

    def test_battery_continues_from_last_known_value(self):
        station = StationSimulator(sample_site(battery=73.5))
        self.assertAlmostEqual(station.energy.battery_percent, 73.5)

    def test_virtual_clock_uses_speed_and_pause(self):
        station = StationSimulator(sample_site(speed=20))
        start = station.virtual_time
        station.advance(10)
        self.assertEqual((station.virtual_time - start).total_seconds(), 200)
        station.update_inventory(sample_site(enabled=False, speed=20))
        paused_at = station.virtual_time
        station.advance(10)
        self.assertEqual(station.virtual_time, paused_at)

    def test_battery_scenarios(self):
        station = StationSimulator(sample_site())
        ok, _, _ = station.apply_command("LOW_BATTERY")
        self.assertTrue(ok)
        self.assertAlmostEqual(station.energy.battery_percent, config.LOW_BATTERY_PERCENT, delta=1.01)
        station.apply_command("CRITICAL_BATTERY")
        self.assertAlmostEqual(station.energy.battery_percent, config.CRITICAL_BATTERY_PERCENT, delta=1.01)
        station.apply_command("RESTORE_ENERGY")
        self.assertGreaterEqual(station.energy.battery_percent, config.RESTORED_BATTERY_PERCENT)

    def test_intrusion_creates_event_on_chosen_camera(self):
        station = StationSimulator(sample_site())
        ok, _, events = station.apply_command("INTRUSION", "CAM-002")
        self.assertTrue(ok)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], event_simulator.INTRUSION)
        self.assertEqual(events[0]["deviceCode"], "CAM-002")
        self.assertTrue(station.cameras["CAM-002"].motion_active())

    def test_camera_failure_and_restore(self):
        station = StationSimulator(sample_site())
        station.apply_command("CAMERA_FAILURE", "CAM-001")
        self.assertEqual(station.cameras["CAM-001"].status, "OFFLINE")
        station.apply_command("CAMERA_RESTORE")
        self.assertEqual(station.cameras["CAM-001"].status, "ONLINE")

    def test_restore_normal_restores_everything(self):
        station = StationSimulator(sample_site(battery=10))
        station.apply_command("NETWORK_FAILURE")
        station.apply_command("SOLAR_FAILURE")
        station.apply_command("CAMERA_FAILURE", "CAM-001")
        station.apply_command("RESTORE_NORMAL")
        self.assertTrue(station.connectivity.starlink_online and station.connectivity.cellular_online)
        self.assertFalse(station.energy.panel_failed)
        self.assertEqual(station.cameras["CAM-001"].status, "ONLINE")
        self.assertGreaterEqual(station.energy.battery_percent, config.RESTORED_BATTERY_PERCENT)

    def test_camera_in_maintenance_cannot_be_targeted(self):
        station = StationSimulator(sample_site(camera_status="MANTENIMIENTO"))
        ok, _, events = station.apply_command("INTRUSION", "CAM-002")
        self.assertFalse(ok)
        self.assertEqual(events, [])

    def test_unknown_command(self):
        station = StationSimulator(sample_site())
        ok, message, _ = station.apply_command("NO_EXISTE")
        self.assertFalse(ok)
        self.assertIn("desconocida", message)

    def test_telemetry_payload_has_contract_shape(self):
        station = StationSimulator(sample_site())
        station.advance(5)
        payload = station.telemetry_payload()
        for key in ("siteCode", "deviceTime", "cameras", "solarPanel", "battery", "consumption", "starlink", "cellular"):
            self.assertIn(key, payload)
        self.assertEqual(len(payload["cameras"]), 2)
        self.assertEqual(payload["battery"]["code"], "BAT-001")
        self.assertTrue(0 <= payload["battery"]["percent"] <= 100)
        self.assertGreater(payload["consumption"]["totalW"], 0)

    def test_new_camera_in_inventory_is_simulated(self):
        station = StationSimulator(sample_site())
        site = sample_site()
        site["devices"].append({"code": "CAM-013", "type": "CAMERA", "name": "Nueva", "status": "ONLINE"})
        station.update_inventory(site)
        self.assertIn("CAM-013", station.cameras)


if __name__ == "__main__":
    unittest.main()

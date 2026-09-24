package com.novatech.monitoring;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Generación de eventos y alertas a partir de lo que informan los dispositivos (secciones 28, 29 y 55). */
class IngestEventsAlertsTest extends ApiTestSupport {

    private static final LocalDateTime NIGHT = LocalDateTime.of(LocalDate.now(), LocalTime.of(22, 5));
    private static final LocalDateTime WORK_HOURS = LocalDateTime.of(LocalDate.now(), LocalTime.of(10, 30));

    @AfterEach
    void cleanUp() {
        restoreNormal(OBRA_001);
    }

    @Test
    @DisplayName("Un movimiento genera un evento INFO sin alerta")
    void motionCreatesEventOnly() {
        JsonNode result = cameraEvent(OBRA_001, "CAM-001", "MOTION_DETECTED", WORK_HOURS);
        assertEquals("INFO", result.get("severity").asText());
        assertTrue(result.get("alertId").isNull());

        long eventId = result.get("eventId").asLong();
        String type = jdbc.queryForObject("SELECT event_type FROM events WHERE id = ?", String.class, eventId);
        assertEquals("MOTION_DETECTED", type);
        assertEquals("NORMAL", generalState(OBRA_001));
    }

    @Test
    @DisplayName("Una intrusión nocturna genera evento y alerta CRÍTICA; la obra pasa a ESTADO CRÍTICO")
    void nightIntrusionIsCritical() {
        JsonNode result = cameraEvent(OBRA_001, "CAM-002", "INTRUSION_DETECTED", NIGHT);
        assertEquals("CRITICA", result.get("severity").asText());
        assertTrue(result.get("alertId").isNumber(), "Debe crear una alerta");

        JsonNode alert = alert(result.get("alertId").asLong());
        assertEquals("INTRUSION", alert.get("alertType").asText());
        assertEquals("CRITICA", alert.get("severity").asText());
        assertEquals("NUEVA", alert.get("status").asText());
        assertEquals("CAM-002", alert.get("deviceCode").asText());
        assertEquals(result.get("eventId").asLong(), alert.get("eventId").asLong());
        assertEquals("CRITICO", generalState(OBRA_001));

        JsonNode camera = findCamera("CAM-002");
        assertTrue(camera.get("intrusionActive").asBoolean(), "La cámara debe mostrar la intrusión");
    }

    @Test
    @DisplayName("En horario laboral la intrusión es ALTA y la obra queda en ADVERTENCIA")
    void workHoursIntrusionIsHigh() {
        JsonNode result = cameraEvent(OBRA_001, "CAM-001", "INTRUSION_DETECTED", WORK_HOURS);
        assertEquals("ALTA", result.get("severity").asText());
        assertEquals("ALTA", alert(result.get("alertId").asLong()).get("severity").asText());
        assertEquals("ADVERTENCIA", generalState(OBRA_001));
    }

    @Test
    @DisplayName("Cada intrusión crea su propia alerta")
    void everyIntrusionIsANewAlert() {
        long first = cameraEvent(OBRA_001, "CAM-002", "INTRUSION_DETECTED", NIGHT).get("alertId").asLong();
        long second = cameraEvent(OBRA_001, "CAM-002", "INTRUSION_DETECTED", NIGHT).get("alertId").asLong();
        assertTrue(second != first);
        assertEquals(2, activeAlerts(OBRA_001).size());
    }

    @Test
    @DisplayName("Una cámara desconectada genera alerta ALTA que se resuelve sola al volver")
    void cameraOfflineAlertResolvesItself() {
        JsonNode offline = reading(OBRA_001).camerasOffline("CAM-003").send();
        assertEquals(1, offline.get("alertsCreated").asInt());
        assertEquals("ADVERTENCIA", offline.get("generalState").asText());
        assertEquals("OFFLINE", findCamera("CAM-003").get("status").asText());

        JsonNode alerts = activeAlerts(OBRA_001);
        assertEquals(1, alerts.size());
        assertEquals("CAMERA_OFFLINE", alerts.get(0).get("alertType").asText());
        long alertId = alerts.get(0).get("id").asLong();

        JsonNode repeated = reading(OBRA_001).camerasOffline("CAM-003").send();
        assertEquals(0, repeated.get("alertsCreated").asInt(), "No se duplica la alerta de una condición activa");

        JsonNode back = reading(OBRA_001).send();
        assertEquals("NORMAL", back.get("generalState").asText());
        JsonNode resolved = alert(alertId);
        assertEquals("RESUELTA", resolved.get("status").asText());
        assertTrue(resolved.get("resolvedByName").isNull(), "La resolvió el sistema, no una persona");
        assertTrue(resolved.get("resolutionNote").asText().startsWith("Resuelta automáticamente"));
    }

    @Test
    @DisplayName("Un tipo de evento que solo detecta Java no se acepta desde un dispositivo")
    void devicesCannotReportDerivedEvents() {
        int status = deviceCall(HttpMethod.POST, "/ingest/events", DEVICE_KEY,
                Map.of("siteCode", "OBRA-001", "type", "STARLINK_DOWN")).status();
        assertEquals(400, status);
    }

    private JsonNode findCamera(String code) {
        for (JsonNode camera : get("/cameras?siteId=" + OBRA_001.id(), token(OPERATOR))) {
            if (code.equals(camera.get("code").asText())) {
                return camera;
            }
        }
        throw new AssertionError("No existe la cámara " + code);
    }
}

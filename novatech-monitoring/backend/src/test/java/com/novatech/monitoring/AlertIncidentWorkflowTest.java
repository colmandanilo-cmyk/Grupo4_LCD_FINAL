package com.novatech.monitoring;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Reconocer y resolver alertas; crear, resolver y cerrar incidencias (secciones 30, 31 y 55). */
class AlertIncidentWorkflowTest extends ApiTestSupport {

    private static final LocalDateTime NIGHT = LocalDateTime.of(LocalDate.now(), LocalTime.of(23, 10));

    @AfterEach
    void cleanUp() {
        restoreNormal(OBRA_002);
    }

    private long newIntrusionAlert() {
        return cameraEvent(OBRA_002, "CAM-006", "INTRUSION_DETECTED", NIGHT).get("alertId").asLong();
    }

    private JsonNode createIncident(long alertId, String token) {
        Map<String, Object> body = new HashMap<>();
        body.put("alertId", alertId);
        body.put("title", "Verificar intrusión en perímetro sur");
        body.put("description", "Se envía al vigilante de turno a revisar el cerco.");
        body.put("assignedToId", 2);
        return expect(201, HttpMethod.POST, "/incidents", token, body);
    }

    @Test
    @DisplayName("Cualquier rol reconoce una alerta; no se reconoce dos veces")
    void acknowledgeAlert() {
        long alertId = newIntrusionAlert();
        JsonNode acknowledged = expect(200, HttpMethod.PUT, "/alerts/" + alertId + "/acknowledge", token(OPERATOR), null);
        assertEquals("RECONOCIDA", acknowledged.get("status").asText());
        assertEquals("Operador de Centro de Control", acknowledged.get("acknowledgedByName").asText());
        assertNotNull(acknowledged.get("acknowledgedAt").asText());

        assertEquals(409, call(HttpMethod.PUT, "/alerts/" + alertId + "/acknowledge", token(OPERATOR), null).status());
        assertEquals("CRITICO", generalState(OBRA_002), "Reconocer no resuelve la alerta");
    }

    @Test
    @DisplayName("El operador no resuelve alertas ni crea incidencias")
    void operatorCannotResolveOrCreateIncidents() {
        long alertId = newIntrusionAlert();
        assertEquals(403, call(HttpMethod.PUT, "/alerts/" + alertId + "/resolve", token(OPERATOR),
                Map.of("note", "x")).status());
        Map<String, Object> body = Map.of("alertId", alertId, "title", "Revisión", "description", "Detalle");
        assertEquals(403, call(HttpMethod.POST, "/incidents", token(OPERATOR), body).status());
    }

    @Test
    @DisplayName("El supervisor resuelve una alerta con nota y la obra vuelve a la normalidad")
    void supervisorResolvesAlert() {
        long alertId = newIntrusionAlert();
        JsonNode resolved = expect(200, HttpMethod.PUT, "/alerts/" + alertId + "/resolve", token(SUPERVISOR),
                Map.of("note", "Falsa alarma: personal autorizado"));
        assertEquals("RESUELTA", resolved.get("status").asText());
        assertEquals("Supervisor de Monitoreo", resolved.get("resolvedByName").asText());
        assertEquals("Falsa alarma: personal autorizado", resolved.get("resolutionNote").asText());
        assertEquals("NORMAL", generalState(OBRA_002));
        assertEquals(409, call(HttpMethod.PUT, "/alerts/" + alertId + "/resolve", token(SUPERVISOR),
                Map.of("note", "otra vez")).status());
    }

    @Test
    @DisplayName("Flujo completo: reconocer, crear incidencia, resolverla y cerrarla")
    void fullIncidentWorkflow() {
        long alertId = newIntrusionAlert();
        expect(200, HttpMethod.PUT, "/alerts/" + alertId + "/acknowledge", token(OPERATOR), null);

        JsonNode incident = createIncident(alertId, token(ADMIN));
        long incidentId = incident.get("id").asLong();
        assertTrue(incident.get("code").asText().matches("INC-\\d{4}-\\d{4}"), incident.get("code").asText());
        assertEquals("ABIERTA", incident.get("status").asText());
        assertEquals("CRITICA", incident.get("priority").asText(), "La prioridad sale de la severidad de la alerta");
        assertEquals("EN_ATENCION", alert(alertId).get("status").asText());

        assertEquals(409, call(HttpMethod.POST, "/incidents", token(ADMIN),
                Map.of("alertId", alertId, "title", "Duplicada", "description", "x")).status(),
                "Una alerta tiene una sola incidencia");
        assertEquals(409, call(HttpMethod.PUT, "/incidents/" + incidentId + "/status", token(ADMIN),
                Map.of("status", "CERRADA")).status(), "No se cierra una incidencia abierta");

        JsonNode inProgress = expect(200, HttpMethod.PUT, "/incidents/" + incidentId + "/status", token(SUPERVISOR),
                Map.of("status", "EN_PROCESO", "observation", "Vigilante en camino"));
        assertEquals("EN_PROCESO", inProgress.get("status").asText());
        assertTrue(inProgress.get("observations").asText().contains("ABIERTA → EN PROCESO"));

        JsonNode resolved = expect(200, HttpMethod.PUT, "/incidents/" + incidentId + "/status", token(SUPERVISOR),
                Map.of("status", "RESUELTA", "observation", "Sin hallazgos"));
        assertFalse(resolved.get("resolvedAt").isNull());
        assertEquals("RESUELTA", alert(alertId).get("status").asText(), "Resolver la incidencia resuelve su alerta");
        assertEquals("NORMAL", generalState(OBRA_002));

        JsonNode closed = expect(200, HttpMethod.PUT, "/incidents/" + incidentId + "/status", token(SUPERVISOR),
                Map.of("status", "CERRADA"));
        assertEquals("CERRADA", closed.get("status").asText());
        assertFalse(closed.get("closedAt").isNull());

        Integer audited = jdbc.queryForObject(
                "SELECT COUNT(*) FROM audit_log WHERE entity = 'INCIDENT' AND entity_id = ?", Integer.class, incidentId);
        assertTrue(audited != null && audited >= 4, "Creación y cambios de estado quedan en auditoría: " + audited);
    }

    @Test
    @DisplayName("Una incidencia requiere título y descripción")
    void incidentValidation() {
        JsonNode body = expect(400, HttpMethod.POST, "/incidents", token(ADMIN),
                Map.of("siteId", OBRA_002.id(), "title", "", "description", ""));
        assertTrue(body.get("fieldErrors").has("title"));
        assertTrue(body.get("fieldErrors").has("description"));
    }
}

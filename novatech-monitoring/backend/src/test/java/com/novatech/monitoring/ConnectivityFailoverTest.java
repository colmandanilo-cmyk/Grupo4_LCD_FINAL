package com.novatech.monitoring;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Falla de Starlink y contingencia a 4G (secciones 25, 26 y 55). */
class ConnectivityFailoverTest extends ApiTestSupport {

    @AfterEach
    void cleanUp() {
        restoreNormal(OBRA_003);
    }

    @Test
    @DisplayName("Falla Starlink: Java activa el 4G, registra los eventos y crea una alerta MEDIA")
    void starlinkFailureSwitchesTo4g() {
        JsonNode result = reading(OBRA_003).starlink("OFFLINE").send();
        assertEquals("CELLULAR_4G", result.get("activeConnection").asText());
        assertEquals("ADVERTENCIA", result.get("generalState").asText());
        assertEquals(1, result.get("alertsCreated").asInt());

        JsonNode connectivity = get("/connectivity/sites/" + OBRA_003.id(), token(OPERATOR));
        assertEquals("CELLULAR_4G", connectivity.get("activeConnection").asText());
        assertEquals("OFFLINE", connectivity.get("starlinkStatus").asText());

        JsonNode alerts = activeAlerts(OBRA_003);
        assertEquals(1, alerts.size());
        assertEquals("STARLINK", alerts.get(0).get("alertType").asText());
        assertEquals("MEDIA", alerts.get(0).get("severity").asText());

        List<String> timeline = new ArrayList<>();
        get("/connectivity/sites/" + OBRA_003.id() + "/timeline", token(OPERATOR))
                .forEach(e -> timeline.add(e.get("eventType").asText()));
        assertTrue(timeline.contains("STARLINK_DOWN"), timeline::toString);
        assertTrue(timeline.contains("CELLULAR_ACTIVATED"), timeline::toString);

        String stored = jdbc.queryForObject(
                "SELECT active_connection FROM connectivity_status WHERE site_id = ? ORDER BY id DESC LIMIT 1",
                String.class, OBRA_003.id());
        assertEquals("CELLULAR_4G", stored, "El cambio queda guardado en SQLite");
    }

    @Test
    @DisplayName("Mientras sigue caído no se repiten eventos ni alertas")
    void noDuplicatesWhileDown() {
        reading(OBRA_003).starlink("OFFLINE").send();
        JsonNode again = reading(OBRA_003).starlink("OFFLINE").send();
        assertEquals(0, again.get("eventsCreated").asInt());
        assertEquals(0, again.get("alertsCreated").asInt());
    }

    @Test
    @DisplayName("Starlink vuelve: conexión principal restablecida y alerta resuelta automáticamente")
    void starlinkRestores() {
        reading(OBRA_003).starlink("OFFLINE").send();
        long alertId = activeAlerts(OBRA_003).get(0).get("id").asLong();

        JsonNode result = reading(OBRA_003).send();
        assertEquals("STARLINK", result.get("activeConnection").asText());
        assertEquals("NORMAL", result.get("generalState").asText());

        JsonNode alert = alert(alertId);
        assertEquals("RESUELTA", alert.get("status").asText());
        assertTrue(alert.get("resolvedByName").isNull());
    }

    @Test
    @DisplayName("Starlink y 4G caídos: sin conexión, alerta CRÍTICA y obra SIN CONEXIÓN")
    void bothLinksDown() {
        JsonNode result = reading(OBRA_003).starlink("OFFLINE").cellular("OFFLINE").send();
        assertEquals("NONE", result.get("activeConnection").asText());
        assertEquals("CRITICO", result.get("generalState").asText());

        JsonNode site = siteDetail(OBRA_003);
        assertEquals("SIN_CONEXION", site.get("status").asText());

        boolean critical = false;
        for (JsonNode alert : activeAlerts(OBRA_003)) {
            critical |= "CONNECTIVITY".equals(alert.get("alertType").asText())
                    && "CRITICA".equals(alert.get("severity").asText());
        }
        assertTrue(critical, "Debe existir la alerta CRÍTICA de conectividad");

        reading(OBRA_003).send();
        assertEquals("ACTIVA", siteDetail(OBRA_003).get("status").asText());
    }

    @Test
    @DisplayName("Si el 4G falla con Starlink en línea, la conexión principal no cambia")
    void cellularFailureAloneKeepsStarlink() {
        JsonNode result = reading(OBRA_003).cellular("OFFLINE").send();
        assertEquals("STARLINK", result.get("activeConnection").asText());
        assertEquals(0, result.get("alertsCreated").asInt());
    }
}

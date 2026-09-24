package com.novatech.monitoring;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

/** Batería baja y crítica, con histéresis (secciones 24 y 55). Umbrales iniciales: 35 % y 20 %. */
class BatteryAlertsTest extends ApiTestSupport {

    @AfterEach
    void cleanUp() {
        restoreNormal(OBRA_004);
    }

    @Test
    @DisplayName("Batería baja (30 %): alerta MEDIA y obra en ADVERTENCIA")
    void lowBattery() {
        JsonNode result = reading(OBRA_004).battery(30).send();
        assertEquals(1, result.get("alertsCreated").asInt());
        assertEquals("ADVERTENCIA", result.get("generalState").asText());
        JsonNode alerts = activeAlerts(OBRA_004);
        assertEquals(List.of("BATTERY_LOW"), types(alerts));
        assertEquals("MEDIA", alerts.get(0).get("severity").asText());
    }

    @Test
    @DisplayName("Batería crítica (15 %): alerta ALTA que reemplaza a la de batería baja")
    void criticalBattery() {
        reading(OBRA_004).battery(30).send();
        JsonNode result = reading(OBRA_004).battery(15).send();
        assertEquals(1, result.get("alertsCreated").asInt());

        JsonNode alerts = activeAlerts(OBRA_004);
        assertEquals(List.of("BATTERY_CRITICAL"), types(alerts), "Solo queda activa la alerta de batería crítica");
        assertEquals("ALTA", alerts.get(0).get("severity").asText());

        JsonNode energy = get("/energy/sites/" + OBRA_004.id(), token(OPERATOR));
        assertEquals("CRITICA", energy.get("batteryLevel").asText());
    }

    @Test
    @DisplayName("Histéresis: a 22 % sigue crítica y no genera eventos nuevos")
    void hysteresisAvoidsFlapping() {
        reading(OBRA_004).battery(15).send();
        JsonNode result = reading(OBRA_004).battery(22).send();
        assertEquals(0, result.get("eventsCreated").asInt());
        assertEquals(List.of("BATTERY_CRITICAL"), types(activeAlerts(OBRA_004)));
    }

    @Test
    @DisplayName("Al recuperarse la batería las alertas se resuelven solas")
    void recoveryResolvesAlerts() {
        reading(OBRA_004).battery(15).send();
        long alertId = activeAlerts(OBRA_004).get(0).get("id").asLong();

        JsonNode result = reading(OBRA_004).battery(85).send();
        assertEquals("NORMAL", result.get("generalState").asText());
        assertEquals(0, activeAlerts(OBRA_004).size());
        assertEquals("RESUELTA", alert(alertId).get("status").asText());
    }

    private static List<String> types(JsonNode alerts) {
        List<String> types = new ArrayList<>();
        alerts.forEach(a -> types.add(a.get("alertType").asText()));
        return types;
    }
}

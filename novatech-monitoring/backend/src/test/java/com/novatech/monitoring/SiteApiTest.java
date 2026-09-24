package com.novatech.monitoring;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Consulta de obras y datos iniciales (secciones 12, 13 y 55). */
class SiteApiTest extends ApiTestSupport {

    @Test
    @DisplayName("Existen las cuatro obras de demostración")
    void fourDemoSites() {
        JsonNode sites = get("/sites", token(OPERATOR));
        List<String> codes = new ArrayList<>();
        sites.forEach(site -> codes.add(site.get("code").asText()));
        assertTrue(codes.containsAll(List.of("OBRA-001", "OBRA-002", "OBRA-003", "OBRA-004")), codes::toString);
        assertEquals(4, codes.stream().filter(c -> c.matches("OBRA-00[1-4]")).count());
    }

    @Test
    @DisplayName("Detalle de OBRA-001: 4 cámaras, 8 dispositivos y conexión Starlink")
    void siteDetail() {
        JsonNode detail = get("/sites/1", token(OPERATOR));
        JsonNode site = detail.get("site");
        assertEquals("OBRA-001", site.get("code").asText());
        assertEquals("Edificio Empresarial San Isidro", site.get("name").asText());
        assertEquals(4, site.get("cameraCount").asInt());
        assertEquals(8, detail.get("devices").size());
        assertEquals("STARLINK", site.get("activeConnection").asText());
    }

    @Test
    @DisplayName("Cada obra tiene entre 2 y 4 cámaras (12 en total)")
    void cameraCounts() {
        int total = 0;
        for (long id = 1; id <= 4; id++) {
            int cameras = get("/sites/" + id, token(OPERATOR)).get("site").get("cameraCount").asInt();
            assertTrue(cameras >= 2 && cameras <= 4, "Obra " + id + " con " + cameras + " cámaras");
            total += cameras;
        }
        assertEquals(12, total);
    }

    @Test
    @DisplayName("Filtro por estado y búsqueda por texto")
    void filterAndSearch() {
        JsonNode result = get("/sites?status=ACTIVA&q=callao", token(OPERATOR));
        assertEquals(1, result.size());
        assertEquals("OBRA-003", result.get(0).get("code").asText());
    }

    @Test
    @DisplayName("Una obra inexistente responde 404 con mensaje en español")
    void unknownSite() {
        JsonNode body = expect(404, HttpMethod.GET, "/sites/9999", token(OPERATOR), null);
        assertTrue(body.get("message").asText().length() > 0);
    }

    @Test
    @DisplayName("El dashboard trae indicadores, 24 horas de alertas y las obras")
    void dashboardHasData() {
        JsonNode summary = get("/dashboard/summary", token(OPERATOR));
        assertEquals(12, summary.get("kpis").get("camerasTotal").asInt());
        assertEquals(24, summary.get("alerts24h").size());
        assertTrue(summary.get("sites").size() >= 4);
        assertTrue(summary.get("latestAlerts").size() > 0, "Los datos iniciales incluyen alertas históricas");
    }

    @Test
    @DisplayName("Los datos iniciales incluyen historia de energía de las últimas 24 horas")
    void seededHistory() {
        JsonNode history = get("/energy/sites/1/history?hours=24", token(OPERATOR));
        assertTrue(history.size() > 200, "Puntos de energía: " + history.size());
    }
}

package com.novatech.monitoring;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.request;

/**
 * Base de las pruebas de la API. Levanta el backend completo (con los datos
 * iniciales) sobre una base SQLite propia en target/test-data/, que se borra
 * al comenzar la ejecucion. Todas las clases comparten el mismo contexto y la
 * misma base; por eso cada una trabaja sobre una obra distinta y la deja en
 * OPERACION NORMAL al terminar.
 *
 * Reparto: OBRA-001 eventos e intrusion, OBRA-002 alertas e incidencias,
 * OBRA-003 conectividad, OBRA-004 bateria.
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
public abstract class ApiTestSupport {

    protected static final String DEVICE_KEY = "clave-dispositivo-pruebas";
    protected static final DateTimeFormatter DEVICE_TIME = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss");

    protected static final String ADMIN = "admin@novatech.local";
    protected static final String SUPERVISOR = "supervisor@novatech.local";
    protected static final String OPERATOR = "operador@novatech.local";
    private static final Map<String, String> PASSWORDS = Map.of(
            ADMIN, "Admin123*",
            SUPERVISOR, "Supervisor123*",
            OPERATOR, "Operador123*");

    /** Obras de los datos iniciales: id y codigos de sus dispositivos. */
    protected record SiteFixture(long id, String code, List<String> cameras, String number) {
        String solar() {
            return "SOL-" + number;
        }

        String battery() {
            return "BAT-" + number;
        }

        String starlink() {
            return "STL-" + number;
        }

        String cellular() {
            return "LTE-" + number;
        }
    }

    protected static final SiteFixture OBRA_001 =
            new SiteFixture(1, "OBRA-001", List.of("CAM-001", "CAM-002", "CAM-003", "CAM-004"), "001");
    protected static final SiteFixture OBRA_002 =
            new SiteFixture(2, "OBRA-002", List.of("CAM-005", "CAM-006", "CAM-007"), "002");
    protected static final SiteFixture OBRA_003 =
            new SiteFixture(3, "OBRA-003", List.of("CAM-008", "CAM-009", "CAM-010"), "003");
    protected static final SiteFixture OBRA_004 =
            new SiteFixture(4, "OBRA-004", List.of("CAM-011", "CAM-012"), "004");

    private static final Path TEST_DB = prepareTestDatabase();
    private static final Map<String, String> TOKENS = new HashMap<>();

    /** Borra la base de una ejecucion anterior para empezar siempre con los datos iniciales. */
    private static Path prepareTestDatabase() {
        Path dir = Path.of("target", "test-data").toAbsolutePath();
        Path db = dir.resolve("novatech-test.db");
        try {
            Files.createDirectories(dir);
            for (String suffix : List.of("", "-wal", "-shm")) {
                Files.deleteIfExists(Path.of(db + suffix));
            }
        } catch (IOException e) {
            throw new UncheckedIOException("No se pudo preparar la base de datos de pruebas", e);
        }
        return db;
    }

    @DynamicPropertySource
    static void testDatabase(DynamicPropertyRegistry registry) {
        registry.add("novatech.db.path", TEST_DB::toString);
    }

    @Autowired
    protected MockMvc mvc;

    @Autowired
    protected ObjectMapper json;

    @Autowired
    protected JdbcTemplate jdbc;

    // ============================================================
    // Llamadas a la API
    // ============================================================

    /** Respuesta de una llamada: codigo HTTP y cuerpo JSON (null si no tiene). */
    protected record Response(int status, JsonNode body) {
    }

    protected Response call(HttpMethod method, String path, String token, Object body) {
        MockHttpServletRequestBuilder builder = request(method, "/api" + path).accept(MediaType.APPLICATION_JSON);
        if (token != null) {
            builder.header("Authorization", "Bearer " + token);
        }
        return perform(builder, body);
    }

    protected Response deviceCall(HttpMethod method, String path, String deviceKey, Object body) {
        MockHttpServletRequestBuilder builder = request(method, "/api" + path).accept(MediaType.APPLICATION_JSON);
        if (deviceKey != null) {
            builder.header("X-Device-Key", deviceKey);
        }
        return perform(builder, body);
    }

    private Response perform(MockHttpServletRequestBuilder builder, Object body) {
        try {
            if (body != null) {
                builder.contentType(MediaType.APPLICATION_JSON)
                        .content(body instanceof String text ? text : json.writeValueAsString(body));
            }
            MvcResult result = mvc.perform(builder).andReturn();
            String content = result.getResponse().getContentAsString(StandardCharsets.UTF_8);
            JsonNode node = content.isBlank() ? null : json.readTree(content);
            return new Response(result.getResponse().getStatus(), node);
        } catch (Exception e) {
            throw new IllegalStateException("Fallo la llamada a la API", e);
        }
    }

    /** Llamada que debe responder con el codigo indicado; devuelve el cuerpo. */
    protected JsonNode expect(int status, HttpMethod method, String path, String token, Object body) {
        Response response = call(method, path, token, body);
        assertEquals(status, response.status(), () -> method + " " + path + " respondio " + response.body());
        return response.body();
    }

    protected JsonNode get(String path, String token) {
        return expect(200, HttpMethod.GET, path, token, null);
    }

    /** Token de sesion del usuario (se inicia sesion una sola vez por ejecucion). */
    protected String token(String email) {
        return TOKENS.computeIfAbsent(email, e -> {
            JsonNode body = expect(200, HttpMethod.POST, "/auth/login", null,
                    Map.of("email", e, "password", PASSWORDS.get(e)));
            return body.get("token").asText();
        });
    }

    // ============================================================
    // Telemetria y eventos simulados (lo que envia el simulador Python)
    // ============================================================

    /** Lectura de una estacion. Por defecto todo funciona y la bateria esta en 85 %. */
    protected final class Reading {
        private final SiteFixture site;
        private Set<String> offlineCameras = Set.of();
        private String starlink = "ONLINE";
        private String cellular = "ONLINE";
        private String solar = "ONLINE";
        private double battery = 85;

        private Reading(SiteFixture site) {
            this.site = site;
        }

        public Reading camerasOffline(String... codes) {
            this.offlineCameras = Set.of(codes);
            return this;
        }

        public Reading starlink(String status) {
            this.starlink = status;
            return this;
        }

        public Reading cellular(String status) {
            this.cellular = status;
            return this;
        }

        public Reading solar(String status) {
            this.solar = status;
            return this;
        }

        public Reading battery(double percent) {
            this.battery = percent;
            return this;
        }

        /** Envia la lectura a POST /api/ingest/telemetry y devuelve la respuesta de Java. */
        public JsonNode send() {
            Response response = deviceCall(HttpMethod.POST, "/ingest/telemetry", DEVICE_KEY, toJson());
            assertEquals(200, response.status(), () -> "Telemetria rechazada: " + response.body());
            return response.body();
        }

        private ObjectNode toJson() {
            ObjectNode root = json.createObjectNode();
            root.put("siteCode", site.code());
            root.put("deviceTime", LocalDateTime.now().format(DEVICE_TIME));
            ArrayNode cameras = root.putArray("cameras");
            for (String code : site.cameras()) {
                boolean online = !offlineCameras.contains(code);
                cameras.addObject()
                        .put("code", code)
                        .put("status", online ? "ONLINE" : "OFFLINE")
                        .put("fps", online ? 25 : 0)
                        .put("signal", online ? 90 : 0)
                        .put("motion", false)
                        .put("recording", online);
            }
            root.putObject("solarPanel")
                    .put("code", site.solar())
                    .put("status", solar)
                    .put("ratedPowerW", 800)
                    .put("generationW", "FALLA".equals(solar) ? 0 : 420)
                    .put("energyTodayKwh", 2.4)
                    .put("lowGeneration", false);
            root.putObject("battery")
                    .put("code", site.battery())
                    .put("status", "ONLINE")
                    .put("percent", battery)
                    .put("voltage", 26.4)
                    .put("autonomyHours", 40);
            root.putObject("consumption")
                    .put("totalW", 95)
                    .put("camerasW", 33)
                    .put("connectivityW", 47)
                    .put("controlW", 15);
            ObjectNode starlinkNode = root.putObject("starlink")
                    .put("code", site.starlink())
                    .put("status", starlink);
            if ("ONLINE".equals(starlink)) {
                starlinkNode.put("latencyMs", 42).put("downloadMbps", 150).put("uploadMbps", 18).put("packetLoss", 0.3);
            }
            ObjectNode cellularNode = root.putObject("cellular")
                    .put("code", site.cellular())
                    .put("status", cellular);
            if ("ONLINE".equals(cellular)) {
                cellularNode.put("signal", 72).put("latencyMs", 65).put("downloadMbps", 28).put("uploadMbps", 9);
            }
            return root;
        }
    }

    protected Reading reading(SiteFixture site) {
        return new Reading(site);
    }

    /** Evento puntual de una camara (movimiento o intrusion) con la hora del equipo indicada. */
    protected JsonNode cameraEvent(SiteFixture site, String cameraCode, String type, LocalDateTime deviceTime) {
        Map<String, Object> body = new HashMap<>();
        body.put("siteCode", site.code());
        body.put("deviceCode", cameraCode);
        body.put("type", type);
        body.put("deviceTime", deviceTime.format(DEVICE_TIME));
        Response response = deviceCall(HttpMethod.POST, "/ingest/events", DEVICE_KEY, body);
        assertEquals(201, response.status(), () -> "Evento rechazado: " + response.body());
        return response.body();
    }

    // ============================================================
    // Consultas frecuentes
    // ============================================================

    protected JsonNode siteDetail(SiteFixture site) {
        return get("/sites/" + site.id(), token(OPERATOR)).get("site");
    }

    protected String generalState(SiteFixture site) {
        return siteDetail(site).get("generalState").asText();
    }

    /** Alertas no resueltas de la obra. */
    protected JsonNode activeAlerts(SiteFixture site) {
        return get("/alerts?siteId=" + site.id() + "&status=ACTIVAS&size=100", token(OPERATOR)).get("items");
    }

    protected JsonNode alert(long id) {
        return get("/alerts/" + id, token(ADMIN));
    }

    /**
     * Deja la obra como al principio: telemetria normal (resuelve sola las
     * alertas de condicion) y, si quedo alguna intrusion abierta, la resuelve
     * el administrador. Termina comprobando OPERACION NORMAL.
     */
    protected void restoreNormal(SiteFixture site) {
        reading(site).send();
        for (JsonNode alert : activeAlerts(site)) {
            expect(200, HttpMethod.PUT, "/alerts/" + alert.get("id").asLong() + "/resolve", token(ADMIN),
                    Map.of("note", "Cierre al terminar la prueba"));
        }
        assertEquals("NORMAL", generalState(site), "La obra " + site.code() + " no volvio a la normalidad");
    }
}

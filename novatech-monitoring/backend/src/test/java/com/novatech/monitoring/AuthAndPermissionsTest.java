package com.novatech.monitoring;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Inicio de sesion y permisos por rol (secciones 9, 10 y 55). */
class AuthAndPermissionsTest extends ApiTestSupport {

    @Test
    @DisplayName("Los tres usuarios de demostración inician sesión y reciben su rol")
    void demoUsersCanLogIn() {
        Map<String, String> roles = Map.of(
                ADMIN, "ADMINISTRADOR",
                SUPERVISOR, "SUPERVISOR",
                OPERATOR, "OPERADOR");
        roles.forEach((email, role) -> {
            JsonNode me = get("/auth/me", token(email));
            assertEquals(email, me.get("user").get("email").asText());
            assertEquals(role, me.get("user").get("role").asText());
        });
    }

    @Test
    @DisplayName("Contraseña incorrecta o usuario inexistente: 401 con mensaje genérico")
    void wrongCredentialsAreRejected() {
        JsonNode wrongPassword = expect(401, HttpMethod.POST, "/auth/login", null,
                Map.of("email", ADMIN, "password", "otra-clave"));
        JsonNode unknownUser = expect(401, HttpMethod.POST, "/auth/login", null,
                Map.of("email", "nadie@novatech.local", "password", "Admin123*"));
        assertEquals(wrongPassword.get("message").asText(), unknownUser.get("message").asText(),
                "El mensaje no debe revelar si el correo existe");
    }

    @Test
    @DisplayName("Las contraseñas se guardan con BCrypt, nunca en texto plano")
    void passwordsAreHashed() {
        List<String> hashes = jdbc.queryForList("SELECT password_hash FROM users", String.class);
        assertFalse(hashes.isEmpty());
        for (String hash : hashes) {
            assertTrue(hash.startsWith("$2"), "Hash no BCrypt: " + hash);
            assertFalse(hash.contains("123*"), "La contraseña parece estar en texto plano");
        }
    }

    @Test
    @DisplayName("Sin token o con un token inválido la API responde 401")
    void protectedEndpointsNeedToken() {
        assertEquals(401, call(HttpMethod.GET, "/sites", null, null).status());
        assertEquals(401, call(HttpMethod.GET, "/sites", "token.invalido.firma", null).status());
    }

    @Test
    @DisplayName("El operador consulta, pero no administra ni gestiona incidencias")
    void operatorPermissions() {
        String operator = token(OPERATOR);
        assertEquals(200, call(HttpMethod.GET, "/sites", operator, null).status());
        assertEquals(200, call(HttpMethod.GET, "/alerts", operator, null).status());
        assertEquals(403, call(HttpMethod.GET, "/users", operator, null).status());
        assertEquals(403, call(HttpMethod.GET, "/incidents", operator, null).status());
        assertEquals(403, call(HttpMethod.GET, "/reports/energy", operator, null).status());
        assertEquals(403, call(HttpMethod.GET, "/simulation/status", operator, null).status());
        assertEquals(403, call(HttpMethod.GET, "/audit", operator, null).status());
    }

    @Test
    @DisplayName("El supervisor gestiona incidencias y reportes, pero no usuarios ni simulación")
    void supervisorPermissions() {
        String supervisor = token(SUPERVISOR);
        assertEquals(200, call(HttpMethod.GET, "/incidents", supervisor, null).status());
        assertEquals(200, call(HttpMethod.GET, "/reports/energy", supervisor, null).status());
        assertEquals(403, call(HttpMethod.GET, "/users", supervisor, null).status());
        assertEquals(403, call(HttpMethod.GET, "/simulation/status", supervisor, null).status());
        assertEquals(403, call(HttpMethod.PUT, "/config", supervisor,
                Map.of("values", Map.of("ui.refresh_seconds", "5"))).status());
    }

    @Test
    @DisplayName("El administrador accede a usuarios, simulación, configuración y auditoría")
    void adminPermissions() {
        String admin = token(ADMIN);
        assertEquals(200, call(HttpMethod.GET, "/users", admin, null).status());
        assertEquals(200, call(HttpMethod.GET, "/simulation/status", admin, null).status());
        assertEquals(200, call(HttpMethod.GET, "/config", admin, null).status());
        assertEquals(200, call(HttpMethod.GET, "/audit", admin, null).status());
    }

    @Test
    @DisplayName("La ingesta de dispositivos exige la clave X-Device-Key correcta")
    void ingestNeedsDeviceKey() {
        assertEquals(401, deviceCall(HttpMethod.GET, "/ingest/sync", null, null).status());
        assertEquals(401, deviceCall(HttpMethod.GET, "/ingest/sync", "clave-equivocada", null).status());
        assertEquals(200, deviceCall(HttpMethod.GET, "/ingest/sync", DEVICE_KEY, null).status());
        assertEquals(403, call(HttpMethod.GET, "/ingest/sync", token(ADMIN), null).status(),
                "Un token de usuario no reemplaza la clave del dispositivo");
    }

    @Test
    @DisplayName("El inicio de sesión queda registrado en auditoría")
    void loginIsAudited() {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM audit_log WHERE action = 'LOGIN'", Integer.class);
        expect(200, HttpMethod.POST, "/auth/login", null, Map.of("email", SUPERVISOR, "password", "Supervisor123*"));
        Integer after = jdbc.queryForObject(
                "SELECT COUNT(*) FROM audit_log WHERE action = 'LOGIN'", Integer.class);
        assertEquals(count + 1, after);
    }
}

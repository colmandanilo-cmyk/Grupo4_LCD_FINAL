package com.novatech.monitoring.dto;

import jakarta.validation.constraints.NotEmpty;

import java.time.LocalDateTime;
import java.util.Map;

/** Datos de /api/config y /api/audit. */
public final class ConfigDtos {

    private ConfigDtos() {
    }

    public record ConfigEntry(String key, String value, String description, LocalDateTime updatedAt,
                              String updatedByName) {
    }

    /** Parametros a cambiar: clave -> nuevo valor. */
    public record ConfigUpdateRequest(@NotEmpty(message = "No hay parámetros para guardar") Map<String, String> values) {
    }

    public record AuditView(Long id, Long userId, String userName, String userEmail, String action, String entity,
                            Long entityId, String details, LocalDateTime timestamp) {
    }
}

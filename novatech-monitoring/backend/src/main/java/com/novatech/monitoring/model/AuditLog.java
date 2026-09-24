package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila de audit_log. userId es null para acciones del sistema o logins fallidos. */
public record AuditLog(
        Long id,
        Long userId,
        String action,
        String entity,
        Long entityId,
        String details,
        LocalDateTime timestamp) {
}

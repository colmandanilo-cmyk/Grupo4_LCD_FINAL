package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila de la tabla incidents. La prioridad usa la escala de severidad (sin INFO). */
public record Incident(
        Long id,
        Long siteId,
        Long alertId,
        String code,
        String title,
        String description,
        Severity priority,
        Status status,
        Long assignedTo,
        Long createdBy,
        LocalDateTime createdAt,
        LocalDateTime updatedAt,
        LocalDateTime resolvedAt,
        LocalDateTime closedAt,
        String observations) {

    /** Estados de una incidencia (seccion 31). */
    public enum Status {
        ABIERTA,
        EN_PROCESO,
        RESUELTA,
        CERRADA
    }
}

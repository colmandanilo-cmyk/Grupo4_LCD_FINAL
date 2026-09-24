package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila de la tabla events. deviceId es null si el evento es de la obra completa. */
public record Event(
        Long id,
        Long siteId,
        Long deviceId,
        LocalDateTime timestamp,
        EventType eventType,
        Severity severity,
        String description) {
}

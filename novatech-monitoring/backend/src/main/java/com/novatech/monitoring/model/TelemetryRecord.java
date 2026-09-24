package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila de la tabla telemetry: una metrica de un dispositivo en un momento. */
public record TelemetryRecord(
        Long id,
        Long siteId,
        Long deviceId,
        LocalDateTime timestamp,
        String metric,
        double value,
        String unit) {
}

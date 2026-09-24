package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila de la tabla alerts. */
public record Alert(
        Long id,
        Long siteId,
        Long deviceId,
        Long eventId,
        Type alertType,
        LocalDateTime createdAt,
        Severity severity,
        Status status,
        String title,
        String description,
        Long responsibleId,
        Long acknowledgedBy,
        LocalDateTime acknowledgedAt,
        Long resolvedBy,
        LocalDateTime resolvedAt,
        String resolutionNote) {

    /** Estados de una alerta (seccion 30). */
    public enum Status {
        NUEVA,
        RECONOCIDA,
        EN_ATENCION,
        RESUELTA
    }

    /**
     * Condicion que representa la alerta. Sirve para no duplicarlas
     * y para resolverlas automaticamente cuando la condicion desaparece.
     */
    public enum Type {
        INTRUSION,
        CAMERA_OFFLINE,
        BATTERY_LOW,
        BATTERY_CRITICAL,
        STARLINK,
        CONNECTIVITY,
        SOLAR_PANEL
    }
}

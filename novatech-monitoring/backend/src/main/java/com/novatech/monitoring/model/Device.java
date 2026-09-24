package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila de la tabla devices (equipo instalado en una obra). */
public record Device(
        Long id,
        Long siteId,
        String code,
        String name,
        Type type,
        Status status,
        boolean simulated,
        LocalDateTime lastSeen,
        LocalDateTime createdAt) {

    public enum Type {
        CAMERA,
        SOLAR_PANEL,
        BATTERY,
        STARLINK,
        CELLULAR_4G
    }

    /** FALLA se usa para el panel solar; MANTENIMIENTO lo fija el administrador. */
    public enum Status {
        ONLINE,
        OFFLINE,
        MANTENIMIENTO,
        FALLA
    }
}

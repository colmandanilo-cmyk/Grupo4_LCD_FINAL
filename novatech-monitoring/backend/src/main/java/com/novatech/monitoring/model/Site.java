package com.novatech.monitoring.model;

import java.time.LocalDate;
import java.time.LocalDateTime;

/** Fila de la tabla sites (obra monitoreada). */
public record Site(
        Long id,
        String code,
        String name,
        String client,
        String location,
        Status status,
        LocalDate installationDate,
        LocalDateTime createdAt) {

    /**
     * ACTIVA y MANTENIMIENTO los fija el administrador.
     * SIN_CONEXION lo fija el sistema cuando caen Starlink y 4G.
     */
    public enum Status {
        ACTIVA,
        MANTENIMIENTO,
        SIN_CONEXION
    }
}

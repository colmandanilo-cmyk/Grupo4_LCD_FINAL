package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila de simulation_commands: orden del laboratorio que el simulador recoge. */
public record SimulationCommand(
        Long id,
        Long siteId,
        Long deviceId,
        Scenario command,
        Status status,
        Long createdBy,
        LocalDateTime createdAt,
        LocalDateTime sentAt,
        LocalDateTime executedAt,
        String result) {

    public enum Status {
        PENDIENTE,
        ENVIADO,
        EJECUTADO,
        ERROR,
        EXPIRADO
    }
}

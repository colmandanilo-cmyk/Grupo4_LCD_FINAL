package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila del historial energy_status. Potencias en W, autonomia en horas. */
public record EnergyStatus(
        Long id,
        Long siteId,
        LocalDateTime timestamp,
        double batteryPercent,
        double batteryVoltage,
        double solarGeneration,
        double consumption,
        double estimatedAutonomy) {
}

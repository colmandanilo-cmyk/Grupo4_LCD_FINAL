package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila de simulation_state: simulacion de una obra (en marcha o en pausa, velocidad). */
public record SimulationState(
        Long id,
        Long siteId,
        boolean enabled,
        int speed,
        String scenario,
        LocalDateTime updatedAt) {
}

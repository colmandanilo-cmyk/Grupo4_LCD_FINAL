package com.novatech.monitoring.dto;

import com.novatech.monitoring.model.Scenario;
import com.novatech.monitoring.model.SimulationCommand;
import jakarta.validation.constraints.NotNull;

import java.time.LocalDateTime;
import java.util.List;

/** Datos de entrada y salida de /api/simulation (Laboratorio de Simulacion). */
public final class SimulationDtos {

    private SimulationDtos() {
    }

    public record ScenarioRequest(@NotNull(message = "Seleccione la obra a simular") Long siteId, Long deviceId) {
    }

    public record SpeedRequest(@NotNull(message = "Indique la velocidad") Integer speed) {
    }

    public record CommandView(
            Long id,
            Long siteId,
            String siteCode,
            Long deviceId,
            String deviceCode,
            Scenario command,
            String commandLabel,
            SimulationCommand.Status status,
            String createdByName,
            LocalDateTime createdAt,
            LocalDateTime sentAt,
            LocalDateTime executedAt,
            String result) {
    }

    public record SiteSimulation(
            Long siteId,
            String code,
            String name,
            boolean enabled,
            int speed,
            String scenario,
            LocalDateTime deviceTime,
            LocalDateTime lastTelemetry) {
    }

    public record SimulationStatus(
            boolean simulatorOnline,
            LocalDateTime lastContact,
            boolean autoEnabled,
            int defaultSpeed,
            List<SiteSimulation> sites,
            List<CommandView> commands) {
    }

    public record CommandResponse(CommandView command, boolean simulatorOnline, String message) {
    }
}

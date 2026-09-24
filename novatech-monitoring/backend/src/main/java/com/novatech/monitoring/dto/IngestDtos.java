package com.novatech.monitoring.dto;

import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.GeneralState;
import com.novatech.monitoring.model.Scenario;
import com.novatech.monitoring.model.Severity;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Contrato del canal de dispositivos (/api/ingest).
 *
 * Hoy lo usa el simulador Python; un gateway real enviaria exactamente
 * el mismo JSON. Los equipos se identifican por su codigo, nunca por id.
 */
public final class IngestDtos {

    private IngestDtos() {
    }

    // ---------------- Telemetria (POST /api/ingest/telemetry) ----------------

    public record TelemetryRequest(
            @NotBlank(message = "siteCode es obligatorio") String siteCode,
            LocalDateTime deviceTime,
            @Valid List<CameraReading> cameras,
            @Valid @NotNull(message = "Falta el bloque solarPanel") SolarReading solarPanel,
            @Valid @NotNull(message = "Falta el bloque battery") BatteryReading battery,
            @Valid @NotNull(message = "Falta el bloque consumption") ConsumptionReading consumption,
            @Valid @NotNull(message = "Falta el bloque starlink") StarlinkReading starlink,
            @Valid @NotNull(message = "Falta el bloque cellular") CellularReading cellular) {
    }

    public record CameraReading(
            @NotBlank String code,
            @NotNull Device.Status status,
            @Min(0) @Max(120) int fps,
            @Min(0) @Max(100) int signal,
            boolean motion,
            boolean recording) {
    }

    public record SolarReading(
            @NotBlank String code,
            @NotNull Device.Status status,
            @PositiveOrZero double ratedPowerW,
            @PositiveOrZero double generationW,
            @PositiveOrZero double energyTodayKwh,
            boolean lowGeneration) {
    }

    public record BatteryReading(
            @NotBlank String code,
            @NotNull Device.Status status,
            @DecimalMin("0") @DecimalMax("100") double percent,
            @PositiveOrZero double voltage,
            @PositiveOrZero double autonomyHours) {
    }

    public record ConsumptionReading(
            @PositiveOrZero double totalW,
            @PositiveOrZero double camerasW,
            @PositiveOrZero double connectivityW,
            @PositiveOrZero double controlW) {
    }

    public record StarlinkReading(
            @NotBlank String code,
            @NotNull Device.Status status,
            Double latencyMs,
            Double downloadMbps,
            Double uploadMbps,
            @DecimalMin("0") @DecimalMax("100") Double packetLoss) {
    }

    public record CellularReading(
            @NotBlank String code,
            @NotNull Device.Status status,
            @Min(0) @Max(100) Integer signal,
            Double latencyMs,
            Double downloadMbps,
            Double uploadMbps) {
    }

    /** Respuesta: Java informa que conexion decidio usar y el estado general de la obra. */
    public record TelemetryResponse(ConnectionType activeConnection, GeneralState generalState,
                                    int eventsCreated, int alertsCreated) {
    }

    // ---------------- Eventos puntuales (POST /api/ingest/events) ----------------

    public record DeviceEventRequest(
            @NotBlank(message = "siteCode es obligatorio") String siteCode,
            String deviceCode,
            @NotNull(message = "type es obligatorio") EventType type,
            LocalDateTime deviceTime,
            @Size(max = 300) String description) {
    }

    public record DeviceEventResponse(Long eventId, Severity severity, Long alertId) {
    }

    // ---------------- Sincronizacion (GET /api/ingest/sync) ----------------

    public record SyncDevice(String code, Device.Type type, String name, Device.Status status) {
    }

    public record LastKnown(Double batteryPercent, Double solarEnergyTodayKwh, LocalDateTime deviceTime) {
    }

    public record SyncSite(String code, String name, boolean enabled, int speed, LastKnown lastKnown,
                           List<SyncDevice> devices) {
    }

    public record SyncCommand(Long id, String siteCode, String deviceCode, Scenario command,
                              LocalDateTime createdAt) {
    }

    public record SyncResponse(LocalDateTime serverTime, List<SyncSite> sites, List<SyncCommand> commands) {
    }

    // ---------------- Confirmacion de ordenes ----------------

    public record CommandAckRequest(boolean success, @Size(max = 300) String message) {
    }
}

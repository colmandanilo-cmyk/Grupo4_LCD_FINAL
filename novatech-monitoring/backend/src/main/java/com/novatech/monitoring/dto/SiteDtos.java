package com.novatech.monitoring.dto;

import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.GeneralState;
import com.novatech.monitoring.model.Site;
import com.novatech.monitoring.model.SiteLiveStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/** Datos de entrada y salida de /api/sites. */
public final class SiteDtos {

    private SiteDtos() {
    }

    /**
     * Alta o edicion de una obra. cameraCount solo se usa al crear
     * (cantidad de camaras de la estacion estandar, de 2 a 4).
     */
    public record SiteRequest(
            @NotBlank(message = "El código es obligatorio")
            @Pattern(regexp = "OBRA-\\d{3}", message = "El código debe tener el formato OBRA-000") String code,
            @NotBlank(message = "El nombre es obligatorio") @Size(max = 120, message = "Máximo 120 caracteres") String name,
            @NotBlank(message = "El cliente es obligatorio") @Size(max = 120, message = "Máximo 120 caracteres") String client,
            @NotBlank(message = "La ubicación es obligatoria") @Size(max = 120, message = "Máximo 120 caracteres") String location,
            @NotNull(message = "Seleccione un estado") Site.Status status,
            @NotNull(message = "La fecha de instalación es obligatoria") LocalDate installationDate,
            @Min(value = 2, message = "Mínimo 2 cámaras") @Max(value = 4, message = "Máximo 4 cámaras") Integer cameraCount) {
    }

    /** Fila de la tabla de obras (pantalla Obras y dashboard). */
    public record SiteSummary(
            Long id,
            String code,
            String name,
            String client,
            String location,
            Site.Status status,
            LocalDate installationDate,
            int cameraCount,
            int camerasOnline,
            Double batteryPercent,
            SiteLiveStatus.BatteryLevel batteryLevel,
            ConnectionType activeConnection,
            int activeAlerts,
            GeneralState generalState,
            LocalDateTime lastUpdate,
            boolean dataStale) {
    }

    /** Datos del Centro de Control de una obra. */
    public record SiteDetail(
            SiteSummary site,
            SiteLiveStatus live,
            Map<String, Integer> activeAlertsBySeverity,
            int openIncidents,
            int devicesTotal,
            int devicesOnline,
            boolean simulated,
            List<DeviceDtos.DeviceView> devices) {
    }
}

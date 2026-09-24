package com.novatech.monitoring.dto;

import com.novatech.monitoring.model.Incident;
import com.novatech.monitoring.model.Severity;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

/** Datos de entrada y salida de /api/incidents. */
public final class IncidentDtos {

    private IncidentDtos() {
    }

    public record IncidentView(
            Long id,
            Long siteId,
            String siteCode,
            String siteName,
            Long alertId,
            String alertTitle,
            String code,
            String title,
            String description,
            Severity priority,
            Incident.Status status,
            Long assignedToId,
            String assignedToName,
            Long createdById,
            String createdByName,
            LocalDateTime createdAt,
            LocalDateTime updatedAt,
            LocalDateTime resolvedAt,
            LocalDateTime closedAt,
            String observations) {
    }

    /** Alta de incidencia: con alertId (desde una alerta) o con siteId (manual). */
    public record IncidentCreateRequest(
            Long siteId,
            Long alertId,
            @NotBlank(message = "El título es obligatorio") @Size(max = 150, message = "Máximo 150 caracteres") String title,
            @NotBlank(message = "La descripción es obligatoria") @Size(max = 1000, message = "Máximo 1000 caracteres") String description,
            Severity priority,
            Long assignedToId) {
    }

    /** Edicion: todos los campos son opcionales. */
    public record IncidentUpdateRequest(
            @Size(min = 1, max = 150, message = "El título debe tener entre 1 y 150 caracteres") String title,
            @Size(min = 1, max = 1000, message = "La descripción debe tener entre 1 y 1000 caracteres") String description,
            Severity priority,
            Long assignedToId,
            @Size(max = 4000, message = "Máximo 4000 caracteres") String observations) {
    }

    public record IncidentStatusRequest(
            @NotNull(message = "Indique el nuevo estado") Incident.Status status,
            @Size(max = 500, message = "Máximo 500 caracteres") String observation) {
    }
}

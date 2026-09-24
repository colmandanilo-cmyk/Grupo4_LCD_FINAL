package com.novatech.monitoring.dto;

import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.Severity;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

/** Datos de entrada y salida de /api/alerts. */
public final class AlertDtos {

    private AlertDtos() {
    }

    public record AlertView(
            Long id,
            Long siteId,
            String siteCode,
            String siteName,
            Long deviceId,
            String deviceCode,
            String deviceName,
            Long eventId,
            Alert.Type alertType,
            LocalDateTime createdAt,
            Severity severity,
            Alert.Status status,
            String title,
            String description,
            Long responsibleId,
            String responsibleName,
            String acknowledgedByName,
            LocalDateTime acknowledgedAt,
            String resolvedByName,
            LocalDateTime resolvedAt,
            String resolutionNote,
            Long incidentId,
            String incidentCode) {
    }

    public record ResolveRequest(@Size(max = 500, message = "Máximo 500 caracteres") String note) {
    }
}

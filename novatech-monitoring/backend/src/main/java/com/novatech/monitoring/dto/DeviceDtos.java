package com.novatech.monitoring.dto;

import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.EventType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

/** Datos de entrada y salida de /api/devices y /api/cameras. */
public final class DeviceDtos {

    private DeviceDtos() {
    }

    /** Dispositivo del inventario. Los campos de camara son null para otros tipos. */
    public record DeviceView(
            Long id,
            Long siteId,
            String siteCode,
            String code,
            String name,
            Device.Type type,
            Device.Status status,
            boolean simulated,
            LocalDateTime lastSeen,
            String position,
            String resolution,
            String scene) {
    }

    public record CameraCreateRequest(
            @NotNull(message = "Seleccione la obra") Long siteId,
            @NotBlank(message = "El nombre es obligatorio") @Size(max = 80, message = "Máximo 80 caracteres") String name,
            @NotBlank(message = "La ubicación es obligatoria") @Size(max = 120, message = "Máximo 120 caracteres") String position,
            @Pattern(regexp = "\\d{3,4}x\\d{3,4}", message = "Resolución inválida (ejemplo: 1920x1080)") String resolution,
            String scene) {
    }

    /** Edicion de un dispositivo. status solo admite ONLINE o MANTENIMIENTO y solo en camaras. */
    public record DeviceUpdateRequest(
            @Size(min = 1, max = 80, message = "El nombre debe tener entre 1 y 80 caracteres") String name,
            @Size(max = 120, message = "Máximo 120 caracteres") String position,
            @Pattern(regexp = "\\d{3,4}x\\d{3,4}", message = "Resolución inválida (ejemplo: 1920x1080)") String resolution,
            String scene,
            Device.Status status) {
    }

    /** Camara con su estado en vivo (vista CCTV). */
    public record CameraView(
            Long deviceId,
            Long siteId,
            String siteCode,
            String siteName,
            String code,
            String name,
            String position,
            String resolution,
            Device.Status status,
            int fps,
            int signal,
            boolean motionDetection,
            boolean recording,
            boolean motionActive,
            LocalDateTime lastMotionAt,
            LocalDateTime lastSeen,
            String scene,
            boolean simulated,
            boolean intrusionActive,
            EventType lastEventType,
            LocalDateTime lastEventAt,
            String lastEventDescription,
            LocalDateTime deviceTime,
            LocalDateTime deviceTimeReceivedAt,
            int speed,
            boolean running) {
    }
}

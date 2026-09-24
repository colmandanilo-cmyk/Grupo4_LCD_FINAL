package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila de la tabla cameras: datos propios de un dispositivo de tipo CAMERA. */
public record Camera(
        Long id,
        Long deviceId,
        String position,
        String resolution,
        int fps,
        boolean motionDetection,
        boolean recording,
        int signalPercent,
        boolean motionActive,
        LocalDateTime lastMotionAt,
        String scene) {
}

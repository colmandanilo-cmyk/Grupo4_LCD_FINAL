package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila del historial connectivity_status. Metricas nulas cuando el enlace esta caido. */
public record ConnectivityStatus(
        Long id,
        Long siteId,
        LocalDateTime timestamp,
        Device.Status starlinkStatus,
        Double starlinkLatency,
        Double starlinkDownload,
        Double starlinkUpload,
        Double starlinkPacketLoss,
        Device.Status cellularStatus,
        Integer cellularSignal,
        Double cellularLatency,
        Double cellularDownload,
        Double cellularUpload,
        ConnectionType activeConnection) {
}

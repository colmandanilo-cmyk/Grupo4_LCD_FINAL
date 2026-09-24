package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/**
 * Fila de site_live_status: el ultimo estado conocido de una obra.
 * Se reemplaza con cada telemetria (no guarda historia).
 */
public record SiteLiveStatus(
        Long siteId,
        LocalDateTime updatedAt,
        LocalDateTime deviceTime,
        Double batteryPercent,
        Double batteryVoltage,
        BatteryLevel batteryLevel,
        String batteryTrend,
        Device.Status solarStatus,
        Double solarRatedPower,
        Double solarGeneration,
        Double solarEnergyToday,
        boolean lowGeneration,
        Double consumption,
        Double consumptionCameras,
        Double consumptionConnectivity,
        Double consumptionControl,
        Double estimatedAutonomy,
        Device.Status starlinkStatus,
        Double starlinkLatency,
        Double starlinkDownload,
        Double starlinkUpload,
        Double starlinkPacketLoss,
        LocalDateTime starlinkLastSeen,
        Device.Status cellularStatus,
        Integer cellularSignal,
        Double cellularLatency,
        Double cellularDownload,
        Double cellularUpload,
        LocalDateTime cellularLastSeen,
        ConnectionType activeConnection,
        LocalDateTime lastHistoryAt) {

    /** Nivel de alarma de la bateria (se calcula con histeresis en MonitoringRules). */
    public enum BatteryLevel {
        NORMAL,
        BAJA,
        CRITICA
    }
}

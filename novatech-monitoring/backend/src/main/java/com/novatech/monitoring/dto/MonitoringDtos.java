package com.novatech.monitoring.dto;

import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.model.SiteLiveStatus;

import java.time.LocalDateTime;
import java.util.List;

/** Salidas de /api/energy, /api/connectivity, /api/telemetry y /api/events. */
public final class MonitoringDtos {

    private MonitoringDtos() {
    }

    /** Estado energetico actual de una obra. */
    public record EnergyView(
            Long siteId,
            String siteCode,
            String siteName,
            LocalDateTime updatedAt,
            boolean dataStale,
            LocalDateTime deviceTime,
            String solarPanelCode,
            Device.Status solarStatus,
            Double solarRatedPower,
            Double solarGeneration,
            Double solarEnergyToday,
            boolean lowGeneration,
            String batteryCode,
            Double batteryPercent,
            Double batteryVoltage,
            SiteLiveStatus.BatteryLevel batteryLevel,
            String batteryTrend,
            Double estimatedAutonomy,
            Double consumption,
            Double consumptionCameras,
            Double consumptionConnectivity,
            Double consumptionControl) {
    }

    /** Punto de los graficos de energia (promedio de un intervalo). */
    public record EnergyPoint(LocalDateTime timestamp, double batteryPercent, double batteryVoltage,
                              double solarGeneration, double consumption) {
    }

    /** Estado actual de Starlink y 4G de una obra. */
    public record ConnectivityView(
            Long siteId,
            String siteCode,
            String siteName,
            LocalDateTime updatedAt,
            boolean dataStale,
            ConnectionType activeConnection,
            String starlinkCode,
            Device.Status starlinkStatus,
            Double starlinkLatency,
            Double starlinkDownload,
            Double starlinkUpload,
            Double starlinkPacketLoss,
            LocalDateTime starlinkLastSeen,
            String cellularCode,
            Device.Status cellularStatus,
            Integer cellularSignal,
            Double cellularLatency,
            Double cellularDownload,
            Double cellularUpload,
            LocalDateTime cellularLastSeen) {
    }

    public record ConnectivityCounts(int starlink, int cellular, int none) {
    }

    public record ConnectivityOverview(ConnectivityCounts counts, List<ConnectivityView> sites,
                                       List<EventView> recentEvents) {
    }

    /** Punto de los graficos de conectividad. activeConnection es la peor del intervalo. */
    public record ConnectivityPoint(LocalDateTime timestamp, Double starlinkLatency, Double cellularLatency,
                                    Double cellularSignal, ConnectionType activeConnection) {
    }

    public record EventView(
            Long id,
            Long siteId,
            String siteCode,
            String siteName,
            Long deviceId,
            String deviceCode,
            String deviceName,
            LocalDateTime timestamp,
            EventType eventType,
            Severity severity,
            String description) {
    }

    /** Metrica disponible para graficar en la pestana Telemetria. */
    public record TelemetryMetric(Long deviceId, String deviceCode, String deviceName, Device.Type deviceType,
                                  String metric, String unit) {
    }

    public record TelemetryPoint(LocalDateTime timestamp, double value) {
    }

    public record TelemetrySeries(Long deviceId, String deviceCode, String metric, String unit,
                                  List<TelemetryPoint> points) {
    }

    public record TelemetryRow(LocalDateTime timestamp, String deviceCode, String deviceName, String metric,
                               double value, String unit) {
    }
}

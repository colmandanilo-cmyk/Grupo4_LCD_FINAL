package com.novatech.monitoring.dto;

import com.novatech.monitoring.model.GeneralState;
import com.novatech.monitoring.model.SiteLiveStatus;

import java.time.LocalDateTime;
import java.util.List;

/** Salidas de /api/dashboard. */
public final class DashboardDtos {

    private DashboardDtos() {
    }

    public record Kpis(
            int sitesTotal,
            int camerasOnline,
            int camerasTotal,
            double availabilityPercent,
            int activeAlerts,
            int criticalIncidents,
            Double averageBattery,
            int sitesOnStarlink,
            int sitesOnCellular,
            int sitesWithoutConnection) {
    }

    public record CameraStatusCounts(int online, int offline, int maintenance) {
    }

    /** Alertas creadas en una hora, por severidad. */
    public record AlertHourBucket(String hour, LocalDateTime start, int media, int alta, int critica, int otras,
                                  int total) {
    }

    public record SiteBattery(Long siteId, String code, String name, Double percent,
                              SiteLiveStatus.BatteryLevel level) {
    }

    public record Thresholds(int batteryLow, int batteryCritical) {
    }

    public record Summary(
            Kpis kpis,
            CameraStatusCounts cameraStatus,
            List<AlertHourBucket> alerts24h,
            List<SiteBattery> batteryBySite,
            MonitoringDtos.ConnectivityCounts connectivity,
            List<SiteDtos.SiteSummary> sites,
            List<AlertDtos.AlertView> latestAlerts,
            Thresholds thresholds,
            LocalDateTime generatedAt) {
    }

    /** Fuente de datos: SIMULADO o REAL, y si esta enviando datos. */
    public record DataSource(String mode, boolean online, LocalDateTime lastContact) {
    }

    /** Datos de la cabecera: estado general de la plataforma. */
    public record Status(
            GeneralState generalState,
            int sitesNormal,
            int sitesWarning,
            int sitesCritical,
            int activeAlerts,
            int newAlerts,
            AlertDtos.AlertView latestAlert,
            DataSource dataSource,
            LocalDateTime serverTime) {
    }
}

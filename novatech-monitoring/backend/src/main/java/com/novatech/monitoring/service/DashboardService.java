package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.AlertDtos.AlertView;
import com.novatech.monitoring.dto.DashboardDtos.AlertHourBucket;
import com.novatech.monitoring.dto.DashboardDtos.CameraStatusCounts;
import com.novatech.monitoring.dto.DashboardDtos.DataSource;
import com.novatech.monitoring.dto.DashboardDtos.Kpis;
import com.novatech.monitoring.dto.DashboardDtos.SiteBattery;
import com.novatech.monitoring.dto.DashboardDtos.Status;
import com.novatech.monitoring.dto.DashboardDtos.Summary;
import com.novatech.monitoring.dto.DashboardDtos.Thresholds;
import com.novatech.monitoring.dto.MonitoringDtos.ConnectivityCounts;
import com.novatech.monitoring.dto.SiteDtos.SiteSummary;
import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.GeneralState;
import com.novatech.monitoring.repository.AlertRepository;
import com.novatech.monitoring.repository.DeviceRepository;
import com.novatech.monitoring.repository.IncidentRepository;
import com.novatech.monitoring.repository.SqlUtils;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/** DASHBOARD GENERAL (seccion 14) y estado de la cabecera. */
@Service
public class DashboardService {

    private final SiteService siteService;
    private final DeviceRepository deviceRepository;
    private final AlertRepository alertRepository;
    private final IncidentRepository incidentRepository;
    private final ConfigService configService;
    private final SimulationService simulationService;

    public DashboardService(SiteService siteService, DeviceRepository deviceRepository, AlertRepository alertRepository,
                            IncidentRepository incidentRepository, ConfigService configService,
                            SimulationService simulationService) {
        this.siteService = siteService;
        this.deviceRepository = deviceRepository;
        this.alertRepository = alertRepository;
        this.incidentRepository = incidentRepository;
        this.configService = configService;
        this.simulationService = simulationService;
    }

    public Summary summary() {
        LocalDateTime now = SqlUtils.now();
        List<SiteSummary> sites = siteService.summaries();
        List<Device> devices = deviceRepository.findAll();
        List<Device> cameras = devices.stream().filter(d -> d.type() == Device.Type.CAMERA).toList();

        int camerasOnline = count(cameras, Device.Status.ONLINE);
        CameraStatusCounts cameraStatus = new CameraStatusCounts(camerasOnline,
                cameras.size() - camerasOnline - count(cameras, Device.Status.MANTENIMIENTO),
                count(cameras, Device.Status.MANTENIMIENTO));

        // Disponibilidad: dispositivos operativos sobre dispositivos monitoreados
        // (los que estan en mantenimiento programado no cuentan).
        List<Device> monitored = devices.stream().filter(d -> d.status() != Device.Status.MANTENIMIENTO).toList();
        double availability = monitored.isEmpty() ? 100.0
                : Math.round(count(monitored, Device.Status.ONLINE) * 1000.0 / monitored.size()) / 10.0;

        Double averageBattery = sites.stream().map(SiteSummary::batteryPercent).filter(Objects::nonNull)
                .mapToDouble(Double::doubleValue).average().stream().boxed().findFirst()
                .map(v -> Math.round(v * 10.0) / 10.0).orElse(null);

        ConnectivityCounts connectivity = connectivityCounts(sites);
        Kpis kpis = new Kpis(sites.size(), camerasOnline, cameras.size(), availability, alertRepository.countActive(),
                incidentRepository.countOpenCritical(), averageBattery, connectivity.starlink(),
                connectivity.cellular(), connectivity.none());

        List<SiteBattery> battery = sites.stream()
                .map(s -> new SiteBattery(s.id(), s.code(), s.name(), s.batteryPercent(), s.batteryLevel()))
                .toList();
        return new Summary(kpis, cameraStatus, alertsLast24h(now), battery, connectivity, sites,
                alertRepository.findLatest(6),
                new Thresholds(configService.batteryLowThreshold(), configService.batteryCriticalThreshold()), now);
    }

    /** Datos livianos para la cabecera (se consultan cada pocos segundos). */
    public Status status() {
        List<SiteSummary> sites = siteService.summaries();
        List<GeneralState> states = sites.stream().map(SiteSummary::generalState).toList();
        AlertView latest = alertRepository.findLatestActive().orElse(null);
        String mode = deviceRepository.anySimulated() ? "SIMULADO" : "REAL";
        return new Status(MonitoringRules.worst(states),
                (int) states.stream().filter(s -> s == GeneralState.NORMAL).count(),
                (int) states.stream().filter(s -> s == GeneralState.ADVERTENCIA).count(),
                (int) states.stream().filter(s -> s == GeneralState.CRITICO).count(),
                alertRepository.countActive(), alertRepository.countByStatus(Alert.Status.NUEVA), latest,
                new DataSource(mode, simulationService.dataSourceOnline(), simulationService.lastContact()),
                SqlUtils.now());
    }

    /** 24 barras, una por hora, con la cantidad de alertas creadas por severidad. */
    private List<AlertHourBucket> alertsLast24h(LocalDateTime now) {
        LocalDateTime firstHour = now.truncatedTo(ChronoUnit.HOURS).minusHours(23);
        List<AlertView> alerts = alertRepository.findCreatedBetween(firstHour, now);
        List<AlertHourBucket> buckets = new ArrayList<>();
        for (int i = 0; i < 24; i++) {
            LocalDateTime start = firstHour.plusHours(i);
            LocalDateTime end = start.plusHours(1);
            List<AlertView> inHour = alerts.stream()
                    .filter(a -> !a.createdAt().isBefore(start) && a.createdAt().isBefore(end)).toList();
            int media = (int) inHour.stream().filter(a -> a.severity().name().equals("MEDIA")).count();
            int alta = (int) inHour.stream().filter(a -> a.severity().name().equals("ALTA")).count();
            int critica = (int) inHour.stream().filter(a -> a.severity().name().equals("CRITICA")).count();
            buckets.add(new AlertHourBucket(String.format("%02d:00", start.getHour()), start, media, alta, critica,
                    inHour.size() - media - alta - critica, inHour.size()));
        }
        return buckets;
    }

    private static ConnectivityCounts connectivityCounts(List<SiteSummary> sites) {
        int starlink = (int) sites.stream().filter(s -> s.activeConnection() == ConnectionType.STARLINK).count();
        int cellular = (int) sites.stream().filter(s -> s.activeConnection() == ConnectionType.CELLULAR_4G).count();
        return new ConnectivityCounts(starlink, cellular, sites.size() - starlink - cellular);
    }

    private static int count(List<Device> devices, Device.Status status) {
        return (int) devices.stream().filter(d -> d.status() == status).count();
    }
}

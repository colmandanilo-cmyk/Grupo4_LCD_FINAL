package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.AlertDtos.AlertView;
import com.novatech.monitoring.dto.IncidentDtos.IncidentView;
import com.novatech.monitoring.dto.MonitoringDtos.TelemetryPoint;
import com.novatech.monitoring.dto.ReportDtos.ReportResult;
import com.novatech.monitoring.dto.ReportDtos.SummaryItem;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.ConnectivityStatus;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.EnergyStatus;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.Incident;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.model.Site;
import com.novatech.monitoring.repository.AlertRepository;
import com.novatech.monitoring.repository.ConnectivityStatusRepository;
import com.novatech.monitoring.repository.DeviceRepository;
import com.novatech.monitoring.repository.EnergyStatusRepository;
import com.novatech.monitoring.repository.EventRepository;
import com.novatech.monitoring.repository.IncidentRepository;
import com.novatech.monitoring.repository.SiteRepository;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.repository.TelemetryRepository;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.OptionalDouble;
import java.util.stream.Collectors;

/**
 * REPORTES (seccion 37): disponibilidad, alertas, energia, conectividad e incidencias.
 *
 * Los promedios de tiempo son "ponderados": cada muestra pesa lo que dura hasta
 * la siguiente (con un tope de 15 minutos para no inflar los huecos sin datos).
 */
@Service
public class ReportService {

    public static final List<String> TYPES = List.of("availability", "alerts", "energy", "connectivity", "incidents");

    private static final long MAX_GAP_SECONDS = 15 * 60;
    private static final DateTimeFormatter FILE_TIME = DateTimeFormatter.ofPattern("yyyyMMdd-HHmm");

    private final SiteRepository siteRepository;
    private final DeviceRepository deviceRepository;
    private final TelemetryRepository telemetryRepository;
    private final EnergyStatusRepository energyRepository;
    private final ConnectivityStatusRepository connectivityRepository;
    private final EventRepository eventRepository;
    private final AlertRepository alertRepository;
    private final IncidentRepository incidentRepository;

    public ReportService(SiteRepository siteRepository, DeviceRepository deviceRepository,
                         TelemetryRepository telemetryRepository, EnergyStatusRepository energyRepository,
                         ConnectivityStatusRepository connectivityRepository, EventRepository eventRepository,
                         AlertRepository alertRepository, IncidentRepository incidentRepository) {
        this.siteRepository = siteRepository;
        this.deviceRepository = deviceRepository;
        this.telemetryRepository = telemetryRepository;
        this.energyRepository = energyRepository;
        this.connectivityRepository = connectivityRepository;
        this.eventRepository = eventRepository;
        this.alertRepository = alertRepository;
        this.incidentRepository = incidentRepository;
    }

    /** Genera un reporte. Sin fechas: ultimas 24 horas. */
    public ReportResult generate(String type, LocalDateTime from, LocalDateTime to) {
        LocalDateTime end = to == null ? SqlUtils.now() : to;
        LocalDateTime start = from == null ? end.minusHours(24) : from;
        if (!start.isBefore(end)) {
            throw ApiException.badRequest("La fecha inicial debe ser anterior a la final");
        }
        if (Duration.between(start, end).toDays() > 31) {
            throw ApiException.badRequest("El período máximo de un reporte es de 31 días");
        }
        return switch (type) {
            case "availability" -> availability(start, end);
            case "alerts" -> alerts(start, end);
            case "energy" -> energy(start, end);
            case "connectivity" -> connectivity(start, end);
            case "incidents" -> incidents(start, end);
            default -> throw ApiException.notFound("Reporte desconocido: " + type
                    + ". Opciones: " + String.join(", ", TYPES));
        };
    }

    // ============================================================
    // Disponibilidad por obra y camara
    // ============================================================

    private ReportResult availability(LocalDateTime from, LocalDateTime to) {
        List<Site> sites = siteRepository.findAll();
        Map<Long, List<Device>> cameras = deviceRepository.findAll().stream()
                .filter(d -> d.type() == Device.Type.CAMERA).collect(Collectors.groupingBy(Device::siteId));
        Map<Long, List<ConnectivityStatus>> connectivity = connectivityRepository.findBetween(null, from, to).stream()
                .collect(Collectors.groupingBy(ConnectivityStatus::siteId));

        List<List<Object>> rows = new ArrayList<>();
        List<Double> cameraValues = new ArrayList<>();
        List<Double> connectivityValues = new ArrayList<>();
        String worstCamera = "-";
        double worstValue = 101;
        for (Site site : sites) {
            List<Double> siteCameras = new ArrayList<>();
            for (Device camera : cameras.getOrDefault(site.id(), List.of())) {
                List<TelemetryPoint> points = telemetryRepository.series(camera.id(), "online", from, to);
                Double value = weightedAverage(points.stream().map(TelemetryPoint::timestamp).toList(),
                        points.stream().map(TelemetryPoint::value).toList(), to);
                Double percent = value == null ? null : round1(value * 100);
                rows.add(row(site.code(), camera.code(), "Cámara " + camera.name(), percent, points.size()));
                if (percent != null) {
                    siteCameras.add(percent);
                    cameraValues.add(percent);
                    if (percent < worstValue) {
                        worstValue = percent;
                        worstCamera = camera.code() + " (" + percent + " %)";
                    }
                }
            }
            List<ConnectivityStatus> conn = connectivity.getOrDefault(site.id(), List.of());
            Double connected = weightedAverage(conn.stream().map(ConnectivityStatus::timestamp).toList(),
                    conn.stream().map(c -> c.activeConnection() == ConnectionType.NONE ? 0.0 : 1.0).toList(), to);
            Double connectedPercent = connected == null ? null : round1(connected * 100);
            rows.add(row(site.code(), "-", "Promedio de cámaras de la obra", average(siteCameras), ""));
            rows.add(row(site.code(), "-", "Conectividad (Starlink o 4G)", connectedPercent, conn.size()));
            if (connectedPercent != null) {
                connectivityValues.add(connectedPercent);
            }
        }
        List<SummaryItem> summary = List.of(
                new SummaryItem("Disponibilidad promedio de cámaras", percentText(average(cameraValues))),
                new SummaryItem("Disponibilidad promedio de conectividad", percentText(average(connectivityValues))),
                new SummaryItem("Cámara con menor disponibilidad", worstCamera),
                new SummaryItem("Cámaras evaluadas", String.valueOf(cameraValues.size())));
        return result("availability", "Reporte de disponibilidad", from, to, summary,
                List.of("Obra", "Código", "Elemento", "Disponibilidad (%)", "Muestras"), rows);
    }

    // ============================================================
    // Alertas por obra, severidad y estado
    // ============================================================

    private ReportResult alerts(LocalDateTime from, LocalDateTime to) {
        List<AlertView> alerts = alertRepository.findCreatedBetween(from, to);
        List<List<Object>> rows = new ArrayList<>();
        for (Site site : siteRepository.findAll()) {
            List<AlertView> own = alerts.stream().filter(a -> a.siteId().equals(site.id())).toList();
            rows.add(row(site.code(), site.name(), own.size(),
                    bySeverity(own, Severity.CRITICA), bySeverity(own, Severity.ALTA), bySeverity(own, Severity.MEDIA),
                    byStatus(own, Alert.Status.NUEVA), byStatus(own, Alert.Status.RECONOCIDA),
                    byStatus(own, Alert.Status.EN_ATENCION), byStatus(own, Alert.Status.RESUELTA)));
        }
        long automatic = alerts.stream().filter(a -> a.status() == Alert.Status.RESUELTA && a.resolvedByName() == null).count();
        List<SummaryItem> summary = List.of(
                new SummaryItem("Alertas generadas", String.valueOf(alerts.size())),
                new SummaryItem("Críticas / Altas / Medias", bySeverity(alerts, Severity.CRITICA) + " / "
                        + bySeverity(alerts, Severity.ALTA) + " / " + bySeverity(alerts, Severity.MEDIA)),
                new SummaryItem("Activas (sin resolver)", String.valueOf(alerts.stream()
                        .filter(a -> a.status() != Alert.Status.RESUELTA).count())),
                new SummaryItem("Resueltas automáticamente", String.valueOf(automatic)));
        return result("alerts", "Reporte de alertas", from, to, summary,
                List.of("Obra", "Nombre", "Total", "Críticas", "Altas", "Medias", "Nuevas", "Reconocidas",
                        "En atención", "Resueltas"), rows);
    }

    // ============================================================
    // Energia: bateria promedio, minima, maxima y generacion
    // ============================================================

    private ReportResult energy(LocalDateTime from, LocalDateTime to) {
        Map<Long, List<EnergyStatus>> bySite = energyRepository.findBetween(null, from, to).stream()
                .collect(Collectors.groupingBy(EnergyStatus::siteId));
        List<List<Object>> rows = new ArrayList<>();
        double totalGeneration = 0;
        List<Double> averages = new ArrayList<>();
        String lowest = "-";
        double lowestValue = 101;
        for (Site site : siteRepository.findAll()) {
            List<EnergyStatus> data = bySite.getOrDefault(site.id(), List.of());
            if (data.isEmpty()) {
                rows.add(row(site.code(), site.name(), null, null, null, null, null, null));
                continue;
            }
            List<LocalDateTime> times = data.stream().map(EnergyStatus::timestamp).toList();
            Double avgBattery = weightedAverage(times, data.stream().map(EnergyStatus::batteryPercent).toList(), to);
            double min = data.stream().mapToDouble(EnergyStatus::batteryPercent).min().orElse(0);
            double max = data.stream().mapToDouble(EnergyStatus::batteryPercent).max().orElse(0);
            double generationKwh = integrateKwh(times, data.stream().map(EnergyStatus::solarGeneration).toList(), to);
            double consumptionKwh = integrateKwh(times, data.stream().map(EnergyStatus::consumption).toList(), to);
            Double avgConsumption = weightedAverage(times, data.stream().map(EnergyStatus::consumption).toList(), to);
            rows.add(row(site.code(), site.name(), round1(avgBattery), round1(min), round1(max), round2(generationKwh),
                    round2(consumptionKwh), round1(avgConsumption)));
            totalGeneration += generationKwh;
            if (avgBattery != null) {
                averages.add(avgBattery);
            }
            if (min < lowestValue) {
                lowestValue = min;
                lowest = site.code() + " (" + round1(min) + " %)";
            }
        }
        List<SummaryItem> summary = List.of(
                new SummaryItem("Batería promedio", percentText(average(averages))),
                new SummaryItem("Batería mínima registrada", lowest),
                new SummaryItem("Generación solar total", String.format(Locale.ROOT, "%.2f kWh", totalGeneration)),
                new SummaryItem("Nota", "Valores simulados con fines demostrativos"));
        return result("energy", "Reporte de energía", from, to, summary,
                List.of("Obra", "Nombre", "Batería prom. (%)", "Batería mín. (%)", "Batería máx. (%)",
                        "Generación (kWh)", "Consumo (kWh)", "Consumo prom. (W)"), rows);
    }

    // ============================================================
    // Conectividad: tiempo en Starlink, en 4G e interrupciones
    // ============================================================

    private ReportResult connectivity(LocalDateTime from, LocalDateTime to) {
        Map<Long, List<ConnectivityStatus>> bySite = connectivityRepository.findBetween(null, from, to).stream()
                .collect(Collectors.groupingBy(ConnectivityStatus::siteId));
        List<List<Object>> rows = new ArrayList<>();
        double totalStarlink = 0;
        double totalCellular = 0;
        long totalInterruptions = 0;
        for (Site site : siteRepository.findAll()) {
            List<ConnectivityStatus> data = bySite.getOrDefault(site.id(), List.of());
            double starlinkHours = 0;
            double cellularHours = 0;
            double noneHours = 0;
            for (int i = 0; i < data.size(); i++) {
                double hours = weightSeconds(data, i, to) / 3600.0;
                switch (data.get(i).activeConnection()) {
                    case STARLINK -> starlinkHours += hours;
                    case CELLULAR_4G -> cellularHours += hours;
                    case NONE -> noneHours += hours;
                }
            }
            double total = starlinkHours + cellularHours + noneHours;
            long interruptions = eventRepository.count(site.id(),
                    List.of(EventType.STARLINK_DOWN, EventType.CONNECTIVITY_LOST), from, to);
            Double latency = weightedAverage(
                    data.stream().filter(c -> c.starlinkLatency() != null).map(ConnectivityStatus::timestamp).toList(),
                    data.stream().map(ConnectivityStatus::starlinkLatency).filter(Objects::nonNull).toList(), to);
            rows.add(row(site.code(), site.name(), round2(starlinkHours), round2(cellularHours), round2(noneHours),
                    total == 0 ? null : round1(starlinkHours * 100 / total), interruptions, round1(latency)));
            totalStarlink += starlinkHours;
            totalCellular += cellularHours;
            totalInterruptions += interruptions;
        }
        List<SummaryItem> summary = List.of(
                new SummaryItem("Tiempo total en Starlink", String.format(Locale.ROOT, "%.1f h", totalStarlink)),
                new SummaryItem("Tiempo total en 4G de respaldo", String.format(Locale.ROOT, "%.1f h", totalCellular)),
                new SummaryItem("Interrupciones de Starlink", String.valueOf(totalInterruptions)),
                new SummaryItem("Nota", "Valores simulados con fines demostrativos"));
        return result("connectivity", "Reporte de conectividad", from, to, summary,
                List.of("Obra", "Nombre", "Horas Starlink", "Horas 4G", "Horas sin conexión", "Starlink (%)",
                        "Interrupciones", "Latencia Starlink prom. (ms)"), rows);
    }

    // ============================================================
    // Incidencias: abiertas, cerradas y tiempo promedio de atencion
    // ============================================================

    private ReportResult incidents(LocalDateTime from, LocalDateTime to) {
        List<IncidentView> incidents = incidentRepository.findCreatedBetween(from, to);
        List<List<Object>> rows = new ArrayList<>();
        for (Site site : siteRepository.findAll()) {
            List<IncidentView> own = incidents.stream().filter(i -> i.siteId().equals(site.id())).toList();
            rows.add(row(site.code(), site.name(), own.size(), byIncidentStatus(own, Incident.Status.ABIERTA),
                    byIncidentStatus(own, Incident.Status.EN_PROCESO), byIncidentStatus(own, Incident.Status.RESUELTA),
                    byIncidentStatus(own, Incident.Status.CERRADA), round1(attentionMinutes(own))));
        }
        Double attention = attentionMinutes(incidents);
        OptionalDouble closing = incidents.stream().filter(i -> i.closedAt() != null)
                .mapToDouble(i -> Duration.between(i.createdAt(), i.closedAt()).toMinutes()).average();
        long open = incidents.stream().filter(i -> i.status() == Incident.Status.ABIERTA
                || i.status() == Incident.Status.EN_PROCESO).count();
        long closed = incidents.stream().filter(i -> i.status() == Incident.Status.CERRADA).count();
        List<SummaryItem> summary = List.of(
                new SummaryItem("Incidencias registradas", String.valueOf(incidents.size())),
                new SummaryItem("Abiertas o en proceso", String.valueOf(open)),
                new SummaryItem("Cerradas", String.valueOf(closed)),
                new SummaryItem("Tiempo promedio de atención", minutesText(attention)),
                new SummaryItem("Tiempo promedio hasta el cierre",
                        minutesText(closing.isPresent() ? closing.getAsDouble() : null)));
        return result("incidents", "Reporte de incidencias", from, to, summary,
                List.of("Obra", "Nombre", "Total", "Abiertas", "En proceso", "Resueltas", "Cerradas",
                        "Atención prom. (min)"), rows);
    }

    // ============================================================
    // Exportacion CSV
    // ============================================================

    /** CSV en UTF-8 con BOM (Excel en Windows muestra bien las tildes), separado por comas. */
    public byte[] toCsv(ReportResult report) {
        StringBuilder csv = new StringBuilder("﻿");
        csv.append(line(List.of("NOVA TECH - " + report.title()))).append("\r\n");
        csv.append(line(List.of("Período", SqlUtils.ts(report.from()) + " a " + SqlUtils.ts(report.to())))).append("\r\n");
        for (SummaryItem item : report.summary()) {
            csv.append(line(List.of(item.label(), item.value()))).append("\r\n");
        }
        csv.append("\r\n");
        csv.append(line(new ArrayList<>(report.columns()))).append("\r\n");
        for (List<Object> row : report.rows()) {
            csv.append(line(row)).append("\r\n");
        }
        return csv.toString().getBytes(StandardCharsets.UTF_8);
    }

    public String csvFileName(String type) {
        return "reporte-" + type + "-" + SqlUtils.now().format(FILE_TIME) + ".csv";
    }

    private static String line(List<?> values) {
        return values.stream().map(ReportService::csvValue).collect(Collectors.joining(","));
    }

    private static String csvValue(Object value) {
        if (value == null) {
            return "";
        }
        String text = value instanceof Double d ? String.format(Locale.ROOT, "%.2f", d) : value.toString();
        if (text.contains(",") || text.contains("\"") || text.contains("\n")) {
            text = "\"" + text.replace("\"", "\"\"") + "\"";
        }
        return text;
    }

    // ============================================================
    // Calculos auxiliares
    // ============================================================

    /** Segundos que "pesa" la muestra i: hasta la siguiente, con tope de 15 minutos. */
    private static long weightSeconds(List<ConnectivityStatus> data, int i, LocalDateTime to) {
        LocalDateTime next = i + 1 < data.size() ? data.get(i + 1).timestamp() : to;
        return Math.max(0, Math.min(Duration.between(data.get(i).timestamp(), next).getSeconds(), MAX_GAP_SECONDS));
    }

    /** Promedio ponderado por tiempo. null si no hay datos. */
    static Double weightedAverage(List<LocalDateTime> times, List<Double> values, LocalDateTime to) {
        if (times.isEmpty() || times.size() != values.size()) {
            return null;
        }
        double sum = 0;
        double weights = 0;
        for (int i = 0; i < times.size(); i++) {
            LocalDateTime next = i + 1 < times.size() ? times.get(i + 1) : to;
            double weight = Math.max(1, Math.min(Duration.between(times.get(i), next).getSeconds(), MAX_GAP_SECONDS));
            sum += values.get(i) * weight;
            weights += weight;
        }
        return sum / weights;
    }

    /** Energia en kWh a partir de potencias en W (potencia x horas). */
    static double integrateKwh(List<LocalDateTime> times, List<Double> watts, LocalDateTime to) {
        double wattHours = 0;
        for (int i = 0; i < times.size(); i++) {
            LocalDateTime next = i + 1 < times.size() ? times.get(i + 1) : to;
            double seconds = Math.max(0, Math.min(Duration.between(times.get(i), next).getSeconds(), MAX_GAP_SECONDS));
            wattHours += watts.get(i) * seconds / 3600.0;
        }
        return wattHours / 1000.0;
    }

    private static Double attentionMinutes(List<IncidentView> incidents) {
        OptionalDouble avg = incidents.stream().filter(i -> i.resolvedAt() != null)
                .mapToDouble(i -> Duration.between(i.createdAt(), i.resolvedAt()).toMinutes()).average();
        return avg.isPresent() ? avg.getAsDouble() : null;
    }

    private static long bySeverity(List<AlertView> alerts, Severity severity) {
        return alerts.stream().filter(a -> a.severity() == severity).count();
    }

    private static long byStatus(List<AlertView> alerts, Alert.Status status) {
        return alerts.stream().filter(a -> a.status() == status).count();
    }

    private static long byIncidentStatus(List<IncidentView> incidents, Incident.Status status) {
        return incidents.stream().filter(i -> i.status() == status).count();
    }

    private static Double average(List<Double> values) {
        return values.isEmpty() ? null : round1(values.stream().mapToDouble(Double::doubleValue).average().orElse(0));
    }

    private static Double round1(Double value) {
        return value == null ? null : Math.round(value * 10.0) / 10.0;
    }

    private static Double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private static String percentText(Double value) {
        return value == null ? "Sin datos" : String.format(Locale.ROOT, "%.1f %%", value);
    }

    private static String minutesText(Double minutes) {
        if (minutes == null) {
            return "Sin datos";
        }
        long total = Math.round(minutes);
        return total >= 60 ? (total / 60) + " h " + (total % 60) + " min" : total + " min";
    }

    private static List<Object> row(Object... values) {
        return new ArrayList<>(Arrays.asList(values));
    }

    private static ReportResult result(String type, String title, LocalDateTime from, LocalDateTime to,
                                       List<SummaryItem> summary, List<String> columns, List<List<Object>> rows) {
        return new ReportResult(type, title, from, to, SqlUtils.now(), summary, columns, rows);
    }
}

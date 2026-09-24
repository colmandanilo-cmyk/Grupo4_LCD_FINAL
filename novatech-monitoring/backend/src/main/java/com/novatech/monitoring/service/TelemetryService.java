package com.novatech.monitoring.service;

import com.novatech.monitoring.config.AppProperties;
import com.novatech.monitoring.dto.MonitoringDtos.TelemetryMetric;
import com.novatech.monitoring.dto.MonitoringDtos.TelemetryPoint;
import com.novatech.monitoring.dto.MonitoringDtos.TelemetryRow;
import com.novatech.monitoring.dto.MonitoringDtos.TelemetrySeries;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.repository.ConnectivityStatusRepository;
import com.novatech.monitoring.repository.DeviceRepository;
import com.novatech.monitoring.repository.EnergyStatusRepository;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.repository.TelemetryRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * Consultas de la pestana Telemetria (seccion 36) y limpieza de datos antiguos.
 */
@Service
public class TelemetryService {

    private static final Logger log = LoggerFactory.getLogger(TelemetryService.class);

    /** Maximo de puntos que se envian al navegador por grafico. */
    public static final int MAX_POINTS = 288;

    private final TelemetryRepository repository;
    private final DeviceRepository deviceRepository;
    private final EnergyStatusRepository energyRepository;
    private final ConnectivityStatusRepository connectivityRepository;
    private final AppProperties properties;

    public TelemetryService(TelemetryRepository repository, DeviceRepository deviceRepository,
                            EnergyStatusRepository energyRepository,
                            ConnectivityStatusRepository connectivityRepository, AppProperties properties) {
        this.repository = repository;
        this.deviceRepository = deviceRepository;
        this.energyRepository = energyRepository;
        this.connectivityRepository = connectivityRepository;
        this.properties = properties;
    }

    public List<TelemetryMetric> metrics(long siteId) {
        return repository.metrics(siteId, SqlUtils.now().minusDays(properties.retention().telemetryDays()));
    }

    public List<TelemetryRow> latest(long siteId, Integer limit) {
        int rows = limit == null ? 100 : Math.max(1, Math.min(limit, 500));
        return repository.latest(siteId, rows);
    }

    /** Serie de una metrica, promediada en intervalos para no superar MAX_POINTS. */
    public TelemetrySeries series(long deviceId, String metric, Integer hours) {
        Device device = deviceRepository.findById(deviceId)
                .orElseThrow(() -> ApiException.notFound("El dispositivo " + deviceId + " no existe"));
        int span = hours == null ? 24 : Math.max(1, Math.min(hours, 24 * 7));
        LocalDateTime to = SqlUtils.now();
        LocalDateTime from = to.minusHours(span);
        List<TelemetryPoint> raw = repository.series(deviceId, metric, from, to);
        String unit = switch (metric) {
            case "battery_percent", "signal" -> "%";
            case "battery_voltage" -> "V";
            case "solar_generation", "consumption" -> "W";
            case "latency" -> "ms";
            default -> "estado";
        };
        return new TelemetrySeries(device.id(), device.code(), metric, unit, downsample(raw, from, to));
    }

    /** Agrupa puntos en intervalos iguales y promedia cada uno. */
    static List<TelemetryPoint> downsample(List<TelemetryPoint> raw, LocalDateTime from, LocalDateTime to) {
        if (raw.size() <= MAX_POINTS) {
            return raw;
        }
        long bucketSeconds = Math.max(60, Duration.between(from, to).getSeconds() / MAX_POINTS);
        List<TelemetryPoint> result = new ArrayList<>();
        long currentBucket = -1;
        double sum = 0;
        int count = 0;
        LocalDateTime bucketStart = null;
        for (TelemetryPoint p : raw) {
            long bucket = Duration.between(from, p.timestamp()).getSeconds() / bucketSeconds;
            if (bucket != currentBucket && count > 0) {
                result.add(new TelemetryPoint(bucketStart, Math.round(sum / count * 100.0) / 100.0));
                sum = 0;
                count = 0;
            }
            if (count == 0) {
                bucketStart = p.timestamp();
                currentBucket = bucket;
            }
            sum += p.value();
            count++;
        }
        if (count > 0) {
            result.add(new TelemetryPoint(bucketStart, Math.round(sum / count * 100.0) / 100.0));
        }
        return result;
    }

    /** Borra datos que superan la retencion: al minuto de arrancar y luego cada 6 horas. */
    @Scheduled(initialDelay = 60_000, fixedDelay = 6 * 60 * 60 * 1000)
    public void purgeOldData() {
        LocalDateTime now = SqlUtils.now();
        int telemetry = repository.deleteBefore(now.minusDays(properties.retention().telemetryDays()));
        int energy = energyRepository.deleteBefore(now.minusDays(properties.retention().historyDays()));
        int connectivity = connectivityRepository.deleteBefore(now.minusDays(properties.retention().historyDays()));
        if (telemetry + energy + connectivity > 0) {
            log.info("Limpieza de datos antiguos: {} telemetría, {} energía, {} conectividad",
                    telemetry, energy, connectivity);
        }
    }
}

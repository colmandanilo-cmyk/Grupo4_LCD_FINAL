package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.MonitoringDtos.EnergyPoint;
import com.novatech.monitoring.dto.MonitoringDtos.EnergyView;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.EnergyStatus;
import com.novatech.monitoring.model.Site;
import com.novatech.monitoring.model.SiteLiveStatus;
import com.novatech.monitoring.repository.DeviceRepository;
import com.novatech.monitoring.repository.EnergyStatusRepository;
import com.novatech.monitoring.repository.SiteLiveStatusRepository;
import com.novatech.monitoring.repository.SiteRepository;
import com.novatech.monitoring.repository.SqlUtils;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/** Modulo de energia: panel solar, bateria y consumo (seccion 22). Valores simulados. */
@Service
public class EnergyService {

    private final SiteRepository siteRepository;
    private final SiteLiveStatusRepository liveRepository;
    private final DeviceRepository deviceRepository;
    private final EnergyStatusRepository energyRepository;
    private final SiteService siteService;

    public EnergyService(SiteRepository siteRepository, SiteLiveStatusRepository liveRepository,
                         DeviceRepository deviceRepository, EnergyStatusRepository energyRepository,
                         SiteService siteService) {
        this.siteRepository = siteRepository;
        this.liveRepository = liveRepository;
        this.deviceRepository = deviceRepository;
        this.energyRepository = energyRepository;
        this.siteService = siteService;
    }

    public List<EnergyView> overview() {
        Map<Long, SiteLiveStatus> live = liveRepository.findAll().stream()
                .collect(Collectors.toMap(SiteLiveStatus::siteId, Function.identity()));
        Map<Long, List<Device>> devices = deviceRepository.findAll().stream().collect(Collectors.groupingBy(Device::siteId));
        return siteRepository.findAll().stream()
                .map(site -> view(site, live.get(site.id()), devices.getOrDefault(site.id(), List.of())))
                .toList();
    }

    public EnergyView site(long siteId) {
        Site site = siteService.get(siteId);
        return view(site, liveRepository.find(siteId).orElse(null), deviceRepository.findBySite(siteId));
    }

    /** Series para los graficos NIVEL DE BATERIA y GENERACION SOLAR VS CONSUMO. */
    public List<EnergyPoint> history(long siteId, Integer hours) {
        siteService.get(siteId);
        int span = hours == null ? 24 : Math.max(1, Math.min(hours, 24 * 7));
        LocalDateTime to = SqlUtils.now();
        LocalDateTime from = to.minusHours(span);
        List<EnergyStatus> rows = energyRepository.findBetween(siteId, from, to);
        long bucketSeconds = Math.max(60, Duration.between(from, to).getSeconds() / TelemetryService.MAX_POINTS);

        List<EnergyPoint> points = new ArrayList<>();
        List<EnergyStatus> bucket = new ArrayList<>();
        long currentBucket = -1;
        for (EnergyStatus row : rows) {
            long index = Duration.between(from, row.timestamp()).getSeconds() / bucketSeconds;
            if (index != currentBucket && !bucket.isEmpty()) {
                points.add(average(bucket));
                bucket.clear();
            }
            currentBucket = index;
            bucket.add(row);
        }
        if (!bucket.isEmpty()) {
            points.add(average(bucket));
        }
        return points;
    }

    private static EnergyPoint average(List<EnergyStatus> rows) {
        double battery = rows.stream().mapToDouble(EnergyStatus::batteryPercent).average().orElse(0);
        double voltage = rows.stream().mapToDouble(EnergyStatus::batteryVoltage).average().orElse(0);
        double solar = rows.stream().mapToDouble(EnergyStatus::solarGeneration).average().orElse(0);
        double consumption = rows.stream().mapToDouble(EnergyStatus::consumption).average().orElse(0);
        return new EnergyPoint(rows.get(0).timestamp(), round(battery), round(voltage), round(solar), round(consumption));
    }

    private static double round(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private static EnergyView view(Site site, SiteLiveStatus live, List<Device> devices) {
        String solarCode = code(devices, Device.Type.SOLAR_PANEL);
        String batteryCode = code(devices, Device.Type.BATTERY);
        LocalDateTime now = SqlUtils.now();
        if (live == null) {
            return new EnergyView(site.id(), site.code(), site.name(), null, true, null, solarCode, null, null, null,
                    null, false, batteryCode, null, null, null, null, null, null, null, null, null);
        }
        return new EnergyView(site.id(), site.code(), site.name(), live.updatedAt(),
                MonitoringRules.isOlderThan(live.updatedAt(), now, MonitoringRules.STALE_DATA_SECONDS),
                live.deviceTime(), solarCode, live.solarStatus(), live.solarRatedPower(), live.solarGeneration(),
                live.solarEnergyToday(), live.lowGeneration(), batteryCode, live.batteryPercent(),
                live.batteryVoltage(), live.batteryLevel(), live.batteryTrend(), live.estimatedAutonomy(),
                live.consumption(), live.consumptionCameras(), live.consumptionConnectivity(),
                live.consumptionControl());
    }

    private static String code(List<Device> devices, Device.Type type) {
        return devices.stream().filter(d -> d.type() == type).map(Device::code).findFirst().orElse(null);
    }
}

package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.MonitoringDtos.ConnectivityCounts;
import com.novatech.monitoring.dto.MonitoringDtos.ConnectivityOverview;
import com.novatech.monitoring.dto.MonitoringDtos.ConnectivityPoint;
import com.novatech.monitoring.dto.MonitoringDtos.ConnectivityView;
import com.novatech.monitoring.dto.MonitoringDtos.EventView;
import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.ConnectivityStatus;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.Site;
import com.novatech.monitoring.model.SiteLiveStatus;
import com.novatech.monitoring.repository.ConnectivityStatusRepository;
import com.novatech.monitoring.repository.DeviceRepository;
import com.novatech.monitoring.repository.SiteLiveStatusRepository;
import com.novatech.monitoring.repository.SiteRepository;
import com.novatech.monitoring.repository.SqlUtils;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.Collectors;

/** Modulo de conectividad: Starlink, 4G y contingencia (secciones 25 y 26). Valores simulados. */
@Service
public class ConnectivityService {

    /** Eventos que forman la linea de tiempo de contingencias. */
    public static final List<EventType> FAILOVER_EVENTS = List.of(EventType.STARLINK_DOWN,
            EventType.CELLULAR_ACTIVATED, EventType.STARLINK_RESTORED, EventType.CELLULAR_DOWN,
            EventType.CELLULAR_RESTORED, EventType.CONNECTIVITY_LOST, EventType.SYSTEM_RESTORED);

    private final SiteRepository siteRepository;
    private final SiteLiveStatusRepository liveRepository;
    private final DeviceRepository deviceRepository;
    private final ConnectivityStatusRepository connectivityRepository;
    private final EventService eventService;
    private final SiteService siteService;

    public ConnectivityService(SiteRepository siteRepository, SiteLiveStatusRepository liveRepository,
                               DeviceRepository deviceRepository, ConnectivityStatusRepository connectivityRepository,
                               EventService eventService, SiteService siteService) {
        this.siteRepository = siteRepository;
        this.liveRepository = liveRepository;
        this.deviceRepository = deviceRepository;
        this.connectivityRepository = connectivityRepository;
        this.eventService = eventService;
        this.siteService = siteService;
    }

    public ConnectivityOverview overview() {
        Map<Long, SiteLiveStatus> live = liveRepository.findAll().stream()
                .collect(Collectors.toMap(SiteLiveStatus::siteId, Function.identity()));
        Map<Long, List<Device>> devices = deviceRepository.findAll().stream().collect(Collectors.groupingBy(Device::siteId));
        List<ConnectivityView> views = siteRepository.findAll().stream()
                .map(site -> view(site, live.get(site.id()), devices.getOrDefault(site.id(), List.of())))
                .toList();
        return new ConnectivityOverview(counts(views), views,
                eventService.recent(null, connectivityTimelineTypes(), 15));
    }

    public ConnectivityView site(long siteId) {
        Site site = siteService.get(siteId);
        return view(site, liveRepository.find(siteId).orElse(null), deviceRepository.findBySite(siteId));
    }

    /** Cantidad de obras usando Starlink, 4G o sin conexion. */
    public static ConnectivityCounts counts(List<ConnectivityView> views) {
        int starlink = (int) views.stream().filter(v -> v.activeConnection() == ConnectionType.STARLINK).count();
        int cellular = (int) views.stream().filter(v -> v.activeConnection() == ConnectionType.CELLULAR_4G).count();
        return new ConnectivityCounts(starlink, cellular, views.size() - starlink - cellular);
    }

    /** Linea de tiempo de contingencias de una obra (mas recientes primero). */
    public List<EventView> timeline(long siteId, Integer limit) {
        siteService.get(siteId);
        return eventService.recent(siteId, connectivityTimelineTypes(), limit == null ? 20 : Math.min(limit, 100));
    }

    public List<ConnectivityPoint> history(long siteId, Integer hours) {
        siteService.get(siteId);
        int span = hours == null ? 24 : Math.max(1, Math.min(hours, 24 * 7));
        LocalDateTime to = SqlUtils.now();
        LocalDateTime from = to.minusHours(span);
        List<ConnectivityStatus> rows = connectivityRepository.findBetween(siteId, from, to);
        long bucketSeconds = Math.max(60, Duration.between(from, to).getSeconds() / TelemetryService.MAX_POINTS);

        List<ConnectivityPoint> points = new ArrayList<>();
        List<ConnectivityStatus> bucket = new ArrayList<>();
        long currentBucket = -1;
        for (ConnectivityStatus row : rows) {
            long index = Duration.between(from, row.timestamp()).getSeconds() / bucketSeconds;
            if (index != currentBucket && !bucket.isEmpty()) {
                points.add(aggregate(bucket));
                bucket.clear();
            }
            currentBucket = index;
            bucket.add(row);
        }
        if (!bucket.isEmpty()) {
            points.add(aggregate(bucket));
        }
        return points;
    }

    /** Promedia el intervalo; como conexion se informa la peor (para no ocultar cortes breves). */
    private static ConnectivityPoint aggregate(List<ConnectivityStatus> rows) {
        ConnectionType worst = ConnectionType.STARLINK;
        for (ConnectivityStatus row : rows) {
            if (row.activeConnection() == ConnectionType.NONE) {
                worst = ConnectionType.NONE;
            } else if (row.activeConnection() == ConnectionType.CELLULAR_4G && worst == ConnectionType.STARLINK) {
                worst = ConnectionType.CELLULAR_4G;
            }
        }
        return new ConnectivityPoint(rows.get(0).timestamp(),
                avg(rows.stream().map(ConnectivityStatus::starlinkLatency).toList()),
                avg(rows.stream().map(ConnectivityStatus::cellularLatency).toList()),
                avg(rows.stream().map(r -> r.cellularSignal() == null ? null : r.cellularSignal().doubleValue()).toList()),
                worst);
    }

    private static Double avg(List<Double> values) {
        List<Double> present = values.stream().filter(Objects::nonNull).toList();
        if (present.isEmpty()) {
            return null;
        }
        return Math.round(present.stream().mapToDouble(Double::doubleValue).average().orElse(0) * 100.0) / 100.0;
    }

    private static List<EventType> connectivityTimelineTypes() {
        return FAILOVER_EVENTS.stream().filter(t -> t != EventType.SYSTEM_RESTORED).toList();
    }

    private static ConnectivityView view(Site site, SiteLiveStatus live, List<Device> devices) {
        String starlinkCode = code(devices, Device.Type.STARLINK);
        String cellularCode = code(devices, Device.Type.CELLULAR_4G);
        if (live == null) {
            return new ConnectivityView(site.id(), site.code(), site.name(), null, true, null, starlinkCode, null,
                    null, null, null, null, null, cellularCode, null, null, null, null, null, null);
        }
        boolean stale = MonitoringRules.isOlderThan(live.updatedAt(), SqlUtils.now(), MonitoringRules.STALE_DATA_SECONDS);
        return new ConnectivityView(site.id(), site.code(), site.name(), live.updatedAt(), stale,
                live.activeConnection(), starlinkCode, live.starlinkStatus(), live.starlinkLatency(),
                live.starlinkDownload(), live.starlinkUpload(), live.starlinkPacketLoss(), live.starlinkLastSeen(),
                cellularCode, live.cellularStatus(), live.cellularSignal(), live.cellularLatency(),
                live.cellularDownload(), live.cellularUpload(), live.cellularLastSeen());
    }

    private static String code(List<Device> devices, Device.Type type) {
        return devices.stream().filter(d -> d.type() == type).map(Device::code).findFirst().orElse(null);
    }
}

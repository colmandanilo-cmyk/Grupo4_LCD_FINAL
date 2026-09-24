package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.DeviceDtos.DeviceView;
import com.novatech.monitoring.dto.SiteDtos.SiteDetail;
import com.novatech.monitoring.dto.SiteDtos.SiteRequest;
import com.novatech.monitoring.dto.SiteDtos.SiteSummary;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.GeneralState;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.model.Site;
import com.novatech.monitoring.model.SiteLiveStatus;
import com.novatech.monitoring.repository.CameraRepository;
import com.novatech.monitoring.repository.DeviceRepository;
import com.novatech.monitoring.repository.IncidentRepository;
import com.novatech.monitoring.repository.SimulationRepository;
import com.novatech.monitoring.repository.SiteLiveStatusRepository;
import com.novatech.monitoring.repository.SiteRepository;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.security.AuthenticatedUser;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/** Obras monitoreadas (secciones 15 a 17). */
@Service
public class SiteService {

    /** Camaras de la estacion estandar que se instala al crear una obra. */
    private record CameraTemplate(String name, String position, String scene) {
    }

    private static final List<CameraTemplate> CAMERA_TEMPLATES = List.of(
            new CameraTemplate("Acceso principal", "Portón de ingreso principal", "acceso"),
            new CameraTemplate("Perímetro", "Cerco perimétrico", "perimetro"),
            new CameraTemplate("Zona de materiales", "Patio de acopio de materiales", "materiales"),
            new CameraTemplate("Acceso vehicular", "Portón de ingreso de camiones", "vehicular"));

    private final SiteRepository siteRepository;
    private final DeviceRepository deviceRepository;
    private final CameraRepository cameraRepository;
    private final SiteLiveStatusRepository liveRepository;
    private final IncidentRepository incidentRepository;
    private final SimulationRepository simulationRepository;
    private final AlertService alertService;
    private final ConfigService configService;
    private final AuditService auditService;

    public SiteService(SiteRepository siteRepository, DeviceRepository deviceRepository,
                       CameraRepository cameraRepository, SiteLiveStatusRepository liveRepository,
                       IncidentRepository incidentRepository, SimulationRepository simulationRepository,
                       AlertService alertService, ConfigService configService, AuditService auditService) {
        this.siteRepository = siteRepository;
        this.deviceRepository = deviceRepository;
        this.cameraRepository = cameraRepository;
        this.liveRepository = liveRepository;
        this.incidentRepository = incidentRepository;
        this.simulationRepository = simulationRepository;
        this.alertService = alertService;
        this.configService = configService;
        this.auditService = auditService;
    }

    /** Lista de obras con filtro por estado y busqueda por nombre, cliente o ubicacion. */
    public List<SiteSummary> list(Site.Status status, String query) {
        String q = query == null ? "" : query.trim().toLowerCase(Locale.ROOT);
        return summaries().stream()
                .filter(s -> status == null || s.status() == status)
                .filter(s -> q.isEmpty() || contains(s.name(), q) || contains(s.client(), q)
                        || contains(s.location(), q) || contains(s.code(), q))
                .toList();
    }

    /** Resumen de todas las obras (lo usa tambien el dashboard). */
    public List<SiteSummary> summaries() {
        LocalDateTime now = SqlUtils.now();
        Map<Long, SiteLiveStatus> live = liveRepository.findAll().stream()
                .collect(Collectors.toMap(SiteLiveStatus::siteId, Function.identity()));
        Map<Long, List<Device>> cameras = deviceRepository.findAll().stream()
                .filter(d -> d.type() == Device.Type.CAMERA)
                .collect(Collectors.groupingBy(Device::siteId));
        Map<Long, List<Severity>> alerts = alertService.activeSeveritiesBySite();
        return siteRepository.findAll().stream()
                .map(site -> summary(site, live.get(site.id()), cameras.getOrDefault(site.id(), List.of()),
                        alerts.getOrDefault(site.id(), List.of()), now))
                .toList();
    }

    public SiteDetail detail(long id) {
        Site site = get(id);
        LocalDateTime now = SqlUtils.now();
        SiteLiveStatus live = liveRepository.find(id).orElse(null);
        List<Device> devices = deviceRepository.findBySite(id);
        List<Severity> activeAlerts = alertService.activeSeveritiesBySite().getOrDefault(id, List.of());
        SiteSummary summary = summary(site, live,
                devices.stream().filter(d -> d.type() == Device.Type.CAMERA).toList(), activeAlerts, now);

        Map<String, Integer> bySeverity = new LinkedHashMap<>();
        for (Severity severity : List.of(Severity.CRITICA, Severity.ALTA, Severity.MEDIA, Severity.BAJA)) {
            bySeverity.put(severity.name(), (int) activeAlerts.stream().filter(s -> s == severity).count());
        }
        List<DeviceView> views = deviceRepository.findViews(id);
        int online = (int) devices.stream().filter(d -> d.status() == Device.Status.ONLINE).count();
        boolean simulated = devices.stream().anyMatch(Device::simulated);
        return new SiteDetail(summary, live, bySeverity, incidentRepository.countOpen(id), devices.size(), online,
                simulated, views);
    }

    /** Crea la obra con su estacion estandar: camaras, panel, bateria, Starlink y 4G. */
    @Transactional
    public SiteDetail create(SiteRequest request, AuthenticatedUser user) {
        if (siteRepository.findByCode(request.code()).isPresent()) {
            throw ApiException.conflict("Ya existe una obra con el código " + request.code());
        }
        checkAdminStatus(request.status());
        int cameraCount = request.cameraCount() == null ? MonitoringRules.MIN_CAMERAS : request.cameraCount();
        String number = request.code().substring("OBRA-".length());
        for (String prefix : List.of("SOL-", "BAT-", "STL-", "LTE-")) {
            if (deviceRepository.findByCode(prefix + number).isPresent()) {
                throw ApiException.conflict("Ya existe el dispositivo " + prefix + number);
            }
        }

        LocalDateTime now = SqlUtils.now();
        long siteId = siteRepository.insert(request.code(), request.name().trim(), request.client().trim(),
                request.location().trim(), request.status(), request.installationDate(), now);

        int nextCamera = deviceRepository.maxCameraNumber() + 1;
        for (int i = 0; i < cameraCount; i++) {
            CameraTemplate template = CAMERA_TEMPLATES.get(i);
            String code = String.format("CAM-%03d", nextCamera + i);
            long deviceId = deviceRepository.insert(siteId, code, template.name(), Device.Type.CAMERA,
                    Device.Status.ONLINE, true, null, now);
            cameraRepository.insert(deviceId, template.position(), "1920x1080", 25, true, true, 0, template.scene());
        }
        deviceRepository.insert(siteId, "SOL-" + number, "Panel solar", Device.Type.SOLAR_PANEL, Device.Status.ONLINE, true, null, now);
        deviceRepository.insert(siteId, "BAT-" + number, "Banco de baterías", Device.Type.BATTERY, Device.Status.ONLINE, true, null, now);
        deviceRepository.insert(siteId, "STL-" + number, "Antena Starlink", Device.Type.STARLINK, Device.Status.ONLINE, true, null, now);
        deviceRepository.insert(siteId, "LTE-" + number, "Módem 4G de respaldo", Device.Type.CELLULAR_4G, Device.Status.ONLINE, true, null, now);
        simulationRepository.insertState(siteId, configService.simulationEnabled(), configService.defaultSpeed(), "NORMAL", now);

        auditService.log(user.id(), "OBRA_CREADA", "SITE", siteId,
                request.code() + " " + request.name() + " con " + cameraCount + " cámaras");
        return detail(siteId);
    }

    @Transactional
    public SiteDetail update(long id, SiteRequest request, AuthenticatedUser user) {
        Site site = get(id);
        checkAdminStatus(request.status());
        siteRepository.findByCode(request.code()).filter(other -> !other.id().equals(id)).ifPresent(other -> {
            throw ApiException.conflict("Ya existe una obra con el código " + request.code());
        });
        if (!request.code().equals(site.code())) {
            throw ApiException.badRequest("El código de una obra no se puede cambiar (lo usan sus dispositivos)");
        }
        // Si la obra estaba SIN_CONEXION y la dejan ACTIVA, la proxima telemetria vuelve a evaluarla.
        siteRepository.update(id, request.code(), request.name().trim(), request.client().trim(),
                request.location().trim(), request.status(), request.installationDate());
        auditService.log(user.id(), "OBRA_ACTUALIZADA", "SITE", id, site.code() + ": estado " + site.status()
                + " → " + request.status() + ", nombre \"" + request.name().trim() + "\"");
        return detail(id);
    }

    public Site get(long id) {
        return siteRepository.findById(id).orElseThrow(() -> ApiException.notFound("La obra " + id + " no existe"));
    }

    // ---------------- auxiliares ----------------

    private SiteSummary summary(Site site, SiteLiveStatus live, List<Device> cameras, List<Severity> activeAlerts,
                                LocalDateTime now) {
        int online = (int) cameras.stream().filter(c -> c.status() == Device.Status.ONLINE).count();
        GeneralState state = MonitoringRules.generalState(activeAlerts);
        boolean stale = live == null
                || MonitoringRules.isOlderThan(live.updatedAt(), now, MonitoringRules.STALE_DATA_SECONDS);
        return new SiteSummary(site.id(), site.code(), site.name(), site.client(), site.location(), site.status(),
                site.installationDate(), cameras.size(), online,
                live == null ? null : live.batteryPercent(),
                live == null ? null : live.batteryLevel(),
                live == null ? null : live.activeConnection(),
                activeAlerts.size(), state,
                live == null ? null : live.updatedAt(), stale);
    }

    private static void checkAdminStatus(Site.Status status) {
        if (status == Site.Status.SIN_CONEXION) {
            throw ApiException.badRequest("El estado SIN CONEXIÓN lo asigna el sistema; elija ACTIVA o MANTENIMIENTO");
        }
    }

    private static boolean contains(String value, String q) {
        return value != null && value.toLowerCase(Locale.ROOT).contains(q);
    }
}

package com.novatech.monitoring.config;

import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.ConnectivityStatus;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.EnergyStatus;
import com.novatech.monitoring.model.Event;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.Incident;
import com.novatech.monitoring.model.Role;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.model.Site;
import com.novatech.monitoring.model.SiteLiveStatus;
import com.novatech.monitoring.model.TelemetryRecord;
import com.novatech.monitoring.repository.AlertRepository;
import com.novatech.monitoring.repository.AuditLogRepository;
import com.novatech.monitoring.repository.CameraRepository;
import com.novatech.monitoring.repository.ConnectivityStatusRepository;
import com.novatech.monitoring.repository.DeviceRepository;
import com.novatech.monitoring.repository.EnergyStatusRepository;
import com.novatech.monitoring.repository.EventRepository;
import com.novatech.monitoring.repository.IncidentRepository;
import com.novatech.monitoring.repository.SimulationRepository;
import com.novatech.monitoring.repository.SiteLiveStatusRepository;
import com.novatech.monitoring.repository.SiteRepository;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.repository.TelemetryRepository;
import com.novatech.monitoring.repository.UserRepository;
import com.novatech.monitoring.service.ConfigService;
import com.novatech.monitoring.service.MonitoringRules;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * DATOS INICIALES (secciones 45 y 46).
 *
 * Si la base esta vacia, carga: 3 usuarios, 4 obras con sus 28 dispositivos,
 * 24 horas de historia de energia, conectividad y telemetria, y varios episodios
 * pasados con sus eventos, alertas, incidencias y registros de auditoria.
 *
 * La historia se calcula con el mismo modelo que usa el simulador Python
 * (sol segun la hora, bateria = bateria + generacion - consumo, variaciones
 * pequenas), con una semilla fija para que cada instalacion tenga los mismos datos.
 * Todas las alertas historicas quedan resueltas: las obras empiezan en OPERACION NORMAL.
 *
 * Todos los valores son demostrativos.
 */
@Component
public class DataSeeder implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);
    private static final DateTimeFormatter NOTE_TIME = DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm");

    /** Un punto de historia cada 5 minutos durante 24 horas. */
    private static final int STEP_MINUTES = 5;
    private static final int POINTS = 24 * 60 / STEP_MINUTES;

    // Parametros del modelo energetico (los mismos por defecto que simulator/config.py).
    private static final double MAX_CHARGE_W = 400;
    private static final double CAMERA_DAY_W = 7;
    private static final double CAMERA_NIGHT_W = 9;
    private static final double STARLINK_ONLINE_W = 45;
    private static final double STARLINK_SEARCHING_W = 15;
    private static final double CELLULAR_ACTIVE_W = 6;
    private static final double CELLULAR_STANDBY_W = 2;
    private static final double CONTROL_W = 15;

    private record CameraSeed(String name, String position, String resolution, String scene) {
    }

    private record SiteSeed(String code, String name, String client, String location, int daysInstalled,
                            double panelW, double capacityWh, List<CameraSeed> cameras) {
    }

    /** Intervalo de tiempo [start, end). */
    private record Window(LocalDateTime start, LocalDateTime end) {
        boolean contains(LocalDateTime t) {
            return !t.isBefore(start) && t.isBefore(end);
        }
    }

    /** Ids de una obra y sus dispositivos una vez insertados. */
    private static final class SiteData {
        final long id;
        final SiteSeed seed;
        final Map<String, Long> cameras = new LinkedHashMap<>();
        long solar;
        long battery;
        long starlink;
        long cellular;

        SiteData(long id, SiteSeed seed) {
            this.id = id;
            this.seed = seed;
        }

        long camera(String code) {
            return cameras.get(code);
        }
    }

    /** Variacion aleatoria acotada: cada paso se mueve poco respecto del anterior. */
    private static final class Walk {
        double value;
        final double min;
        final double max;
        final double step;

        Walk(double start, double min, double max, double step) {
            this.value = start;
            this.min = min;
            this.max = max;
            this.step = step;
        }

        double next(Random rnd) {
            value = Math.max(min, Math.min(max, value + (rnd.nextDouble() * 2 - 1) * step));
            return value;
        }
    }

    private static final List<SiteSeed> SITES = List.of(
            new SiteSeed("OBRA-001", "Edificio Empresarial San Isidro", "Constructora Andina", "Lima", 205, 800, 5000,
                    List.of(new CameraSeed("Acceso principal", "Portón peatonal de ingreso", "1920x1080", "acceso"),
                            new CameraSeed("Perímetro norte", "Cerco perimétrico, lado norte", "1920x1080", "perimetro"),
                            new CameraSeed("Zona de materiales", "Patio de acopio de fierro y agregados", "1920x1080", "materiales"),
                            new CameraSeed("Acceso vehicular", "Portón de ingreso de camiones", "2560x1440", "vehicular"))),
            new SiteSeed("OBRA-002", "Proyecto Residencial Miraflores", "Inmobiliaria Horizonte", "Lima", 160, 800, 5000,
                    List.of(new CameraSeed("Acceso principal", "Caseta de control de ingreso", "1920x1080", "acceso"),
                            new CameraSeed("Perímetro sur", "Cerco perimétrico, lado sur", "1920x1080", "perimetro"),
                            new CameraSeed("Grúa torre", "Base de la grúa torre y losa en construcción", "2560x1440", "grua"))),
            new SiteSeed("OBRA-003", "Centro Logístico Callao", "Logística del Pacífico", "Callao", 125, 800, 6000,
                    List.of(new CameraSeed("Patio de maniobras", "Patio de maniobras de camiones", "2560x1440", "vehicular"),
                            new CameraSeed("Almacén de materiales", "Almacén temporal y contenedores", "1920x1080", "materiales"),
                            new CameraSeed("Perímetro este", "Cerco perimétrico, lado este", "1920x1080", "perimetro"))),
            new SiteSeed("OBRA-004", "Proyecto Industrial Lurín", "Ingeniería Sur", "Lurín", 105, 600, 3500,
                    List.of(new CameraSeed("Acceso vehicular", "Portón de ingreso principal", "1920x1080", "acceso"),
                            new CameraSeed("Zona de maquinaria", "Estacionamiento de maquinaria pesada", "1920x1080", "maquinaria"))));

    private final UserRepository userRepository;
    private final SiteRepository siteRepository;
    private final DeviceRepository deviceRepository;
    private final CameraRepository cameraRepository;
    private final SiteLiveStatusRepository liveRepository;
    private final EnergyStatusRepository energyRepository;
    private final ConnectivityStatusRepository connectivityRepository;
    private final TelemetryRepository telemetryRepository;
    private final EventRepository eventRepository;
    private final AlertRepository alertRepository;
    private final IncidentRepository incidentRepository;
    private final SimulationRepository simulationRepository;
    private final AuditLogRepository auditRepository;
    private final ConfigService configService;
    private final PasswordEncoder passwordEncoder;
    private final TransactionTemplate transactionTemplate;

    public DataSeeder(UserRepository userRepository, SiteRepository siteRepository, DeviceRepository deviceRepository,
                      CameraRepository cameraRepository, SiteLiveStatusRepository liveRepository,
                      EnergyStatusRepository energyRepository, ConnectivityStatusRepository connectivityRepository,
                      TelemetryRepository telemetryRepository, EventRepository eventRepository,
                      AlertRepository alertRepository, IncidentRepository incidentRepository,
                      SimulationRepository simulationRepository, AuditLogRepository auditRepository,
                      ConfigService configService, PasswordEncoder passwordEncoder,
                      TransactionTemplate transactionTemplate) {
        this.userRepository = userRepository;
        this.siteRepository = siteRepository;
        this.deviceRepository = deviceRepository;
        this.cameraRepository = cameraRepository;
        this.liveRepository = liveRepository;
        this.energyRepository = energyRepository;
        this.connectivityRepository = connectivityRepository;
        this.telemetryRepository = telemetryRepository;
        this.eventRepository = eventRepository;
        this.alertRepository = alertRepository;
        this.incidentRepository = incidentRepository;
        this.simulationRepository = simulationRepository;
        this.auditRepository = auditRepository;
        this.configService = configService;
        this.passwordEncoder = passwordEncoder;
        this.transactionTemplate = transactionTemplate;
    }

    @Override
    public void run(ApplicationArguments args) {
        configService.ensureDefaults();
        if (userRepository.count() > 0) {
            log.info("La base de datos ya tiene datos: no se cargan datos iniciales.");
            return;
        }
        log.info("Base de datos vacía: cargando datos iniciales de demostración...");
        long start = System.currentTimeMillis();
        transactionTemplate.executeWithoutResult(status -> seed());
        log.info("Datos iniciales cargados en {} ms: 3 usuarios, 4 obras, 28 dispositivos y 24 h de historia.",
                System.currentTimeMillis() - start);
    }

    private void seed() {
        LocalDateTime now = SqlUtils.now();
        Random rnd = new Random(20260924L);

        // ---------------- Usuarios (seccion 11) ----------------
        long admin = userRepository.insert("Administrador del Sistema", "admin@novatech.local",
                passwordEncoder.encode("Admin123*"), Role.ADMINISTRADOR, true, now.minusDays(60));
        long supervisor = userRepository.insert("Supervisor de Monitoreo", "supervisor@novatech.local",
                passwordEncoder.encode("Supervisor123*"), Role.SUPERVISOR, true, now.minusDays(60));
        long operator = userRepository.insert("Operador de Centro de Control", "operador@novatech.local",
                passwordEncoder.encode("Operador123*"), Role.OPERADOR, true, now.minusDays(60));

        // ---------------- Obras y dispositivos (secciones 16 y 20) ----------------
        List<SiteData> sites = new ArrayList<>();
        int cameraNumber = 1;
        for (int i = 0; i < SITES.size(); i++) {
            SiteSeed seed = SITES.get(i);
            String number = String.format("%03d", i + 1);
            LocalDateTime installed = now.minusDays(seed.daysInstalled());
            long siteId = siteRepository.insert(seed.code(), seed.name(), seed.client(), seed.location(),
                    Site.Status.ACTIVA, installed.toLocalDate(), installed);
            SiteData data = new SiteData(siteId, seed);
            for (CameraSeed camera : seed.cameras()) {
                String code = String.format("CAM-%03d", cameraNumber++);
                long deviceId = deviceRepository.insert(siteId, code, camera.name(), Device.Type.CAMERA,
                        Device.Status.ONLINE, true, now, installed);
                cameraRepository.insert(deviceId, camera.position(), camera.resolution(), 25, true, true, 90, camera.scene());
                data.cameras.put(code, deviceId);
            }
            data.solar = deviceRepository.insert(siteId, "SOL-" + number, "Panel solar", Device.Type.SOLAR_PANEL,
                    Device.Status.ONLINE, true, now, installed);
            data.battery = deviceRepository.insert(siteId, "BAT-" + number, "Banco de baterías", Device.Type.BATTERY,
                    Device.Status.ONLINE, true, now, installed);
            data.starlink = deviceRepository.insert(siteId, "STL-" + number, "Antena Starlink", Device.Type.STARLINK,
                    Device.Status.ONLINE, true, now, installed);
            data.cellular = deviceRepository.insert(siteId, "LTE-" + number, "Módem 4G de respaldo",
                    Device.Type.CELLULAR_4G, Device.Status.ONLINE, true, now, installed);
            simulationRepository.insertState(siteId, configService.simulationEnabled(), configService.defaultSpeed(),
                    "NORMAL", now);
            sites.add(data);
        }
        SiteData o1 = sites.get(0);
        SiteData o2 = sites.get(1);
        SiteData o3 = sites.get(2);
        SiteData o4 = sites.get(3);

        // ---------------- Episodios de las ultimas 24 horas ----------------
        // Momentos relativos a la hora de carga; la severidad se calcula con las reglas del sistema.
        Window cam006Offline = new Window(now.minusMinutes(500), now.minusMinutes(460));
        Window cam011Offline = new Window(now.minusMinutes(190), now.minusMinutes(175));
        Window starlinkOutage = new Window(now.minusMinutes(360), now.minusMinutes(335));
        Window cloudy = findDaylightWindow(now);

        generateHistory(o1, now, rnd, Map.of(), null, null);
        generateHistory(o2, now, rnd, Map.of(o2.camera("CAM-006"), cam006Offline), null, null);
        generateHistory(o3, now, rnd, Map.of(), starlinkOutage, null);
        generateHistory(o4, now, rnd, Map.of(o4.camera("CAM-011"), cam011Offline), null, cloudy);

        seedEpisodes(now, admin, supervisor, operator, o1, o2, o3, o4, cam006Offline, cam011Offline, starlinkOutage, cloudy);
    }

    // ============================================================
    // Historia de energia, conectividad y telemetria
    // ============================================================

    private void generateHistory(SiteData site, LocalDateTime now, Random rnd, Map<Long, Window> cameraOffline,
                                 Window starlinkDown, Window cloudy) {
        SiteSeed seed = site.seed;
        double capacity = seed.capacityWh();
        double dtHours = STEP_MINUTES / 60.0;

        // Un dia previo "de calentamiento" para que la bateria llegue a un nivel realista.
        double energy = capacity * 0.70;
        Walk solarNoise = new Walk(0.98, 0.92, 1.03, 0.01);
        for (LocalDateTime t = now.minusHours(48); t.isBefore(now.minusHours(24)); t = t.plusMinutes(STEP_MINUTES)) {
            double hour = hourOf(t);
            double consumption = seed.cameras().size() * cameraWatts(hour) + STARLINK_ONLINE_W + CELLULAR_STANDBY_W + CONTROL_W;
            energy = integrate(energy, solarWatts(hour, seed.panelW(), 1.0, solarNoise.next(rnd)), consumption, dtHours, capacity);
        }

        Walk latency = new Walk(42, 30, 60, 3);
        Walk download = new Walk(150, 80, 220, 12);
        Walk upload = new Walk(18, 10, 30, 2);
        Walk loss = new Walk(0.3, 0, 1.5, 0.15);
        Walk cellSignal = new Walk(72, 55, 90, 2);
        Walk cellLatency = new Walk(65, 45, 95, 4);
        Walk cellDownload = new Walk(28, 10, 45, 3);
        Walk cellUpload = new Walk(9, 4, 15, 1);
        Map<Long, Walk> cameraSignal = new LinkedHashMap<>();
        site.cameras.values().forEach(id -> cameraSignal.put(id, new Walk(90, 75, 99, 1.5)));

        List<EnergyStatus> energyRows = new ArrayList<>();
        List<ConnectivityStatus> connectivityRows = new ArrayList<>();
        List<TelemetryRecord> telemetryRows = new ArrayList<>();
        double energyToday = 0;
        LocalDate day = null;
        double gen = 0;
        double camerasW = 0;
        double connectivityW = 0;
        double controlW = CONTROL_W;
        double consumption = 0;
        boolean starlinkUp = true;

        for (int k = 0; k <= POINTS; k++) {
            LocalDateTime ts = now.minusMinutes((long) (POINTS - k) * STEP_MINUTES);
            double hour = hourOf(ts);
            starlinkUp = starlinkDown == null || !starlinkDown.contains(ts);
            double cloudFactor = cloudy != null && cloudy.contains(ts) ? 0.3 : 1.0;

            int camerasOnline = 0;
            for (Long cameraId : site.cameras.values()) {
                Window off = cameraOffline.get(cameraId);
                if (off == null || !off.contains(ts)) {
                    camerasOnline++;
                }
            }
            gen = solarWatts(hour, seed.panelW(), cloudFactor, solarNoise.next(rnd));
            camerasW = camerasOnline * cameraWatts(hour);
            connectivityW = (starlinkUp ? STARLINK_ONLINE_W : STARLINK_SEARCHING_W)
                    + (starlinkUp ? CELLULAR_STANDBY_W : CELLULAR_ACTIVE_W);
            controlW = CONTROL_W + (rnd.nextDouble() - 0.5);
            consumption = camerasW + connectivityW + controlW;
            if (k > 0) {
                energy = integrate(energy, gen, consumption, dtHours, capacity);
            }
            if (!ts.toLocalDate().equals(day)) {
                day = ts.toLocalDate();
                energyToday = 0;
            }
            energyToday += gen * dtHours / 1000.0;

            double percent = energy / capacity * 100;
            double voltage = 22.0 + 5.2 * percent / 100;
            double autonomy = energy / consumption;
            energyRows.add(new EnergyStatus(null, site.id, ts, r2(percent), r2(voltage), r2(gen), r2(consumption), r2(autonomy)));

            double lat = latency.next(rnd);
            double down = download.next(rnd);
            double up = upload.next(rnd);
            double pl = loss.next(rnd);
            double signal = cellSignal.next(rnd);
            double cLat = cellLatency.next(rnd);
            double cDown = cellDownload.next(rnd);
            double cUp = cellUpload.next(rnd);
            connectivityRows.add(new ConnectivityStatus(null, site.id, ts,
                    starlinkUp ? Device.Status.ONLINE : Device.Status.OFFLINE,
                    starlinkUp ? r2(lat) : null, starlinkUp ? r2(down) : null, starlinkUp ? r2(up) : null,
                    starlinkUp ? r2(pl) : null, Device.Status.ONLINE, (int) Math.round(signal), r2(cLat), r2(cDown), r2(cUp),
                    starlinkUp ? ConnectionType.STARLINK : ConnectionType.CELLULAR_4G));

            telemetryRows.add(new TelemetryRecord(null, site.id, site.battery, ts, "battery_percent", r2(percent), "%"));
            telemetryRows.add(new TelemetryRecord(null, site.id, site.battery, ts, "battery_voltage", r2(voltage), "V"));
            telemetryRows.add(new TelemetryRecord(null, site.id, site.battery, ts, "consumption", r2(consumption), "W"));
            telemetryRows.add(new TelemetryRecord(null, site.id, site.solar, ts, "solar_generation", r2(gen), "W"));
            telemetryRows.add(new TelemetryRecord(null, site.id, site.starlink, ts, "online", starlinkUp ? 1 : 0, "estado"));
            if (starlinkUp) {
                telemetryRows.add(new TelemetryRecord(null, site.id, site.starlink, ts, "latency", r2(lat), "ms"));
            }
            telemetryRows.add(new TelemetryRecord(null, site.id, site.cellular, ts, "online", 1, "estado"));
            telemetryRows.add(new TelemetryRecord(null, site.id, site.cellular, ts, "signal", Math.round(signal), "%"));
            for (Map.Entry<Long, Walk> camera : cameraSignal.entrySet()) {
                Window off = cameraOffline.get(camera.getKey());
                boolean online = off == null || !off.contains(ts);
                double camSignal = camera.getValue().next(rnd);
                telemetryRows.add(new TelemetryRecord(null, site.id, camera.getKey(), ts, "online", online ? 1 : 0, "estado"));
                telemetryRows.add(new TelemetryRecord(null, site.id, camera.getKey(), ts, "signal",
                        online ? Math.round(camSignal) : 0, "%"));
            }
        }
        energyRepository.insertAll(energyRows);
        connectivityRepository.insertAll(connectivityRows);
        telemetryRepository.insertAll(telemetryRows);

        // Estado actual = ultimo punto de la historia.
        double percent = energy / capacity * 100;
        SiteLiveStatus.BatteryLevel level = MonitoringRules.batteryLevel(SiteLiveStatus.BatteryLevel.NORMAL, percent,
                configService.batteryLowThreshold(), configService.batteryCriticalThreshold());
        liveRepository.save(new SiteLiveStatus(site.id, now, now, r2(percent), r2(22.0 + 5.2 * percent / 100), level,
                MonitoringRules.batteryTrend(gen, consumption, percent), Device.Status.ONLINE, seed.panelW(), r2(gen),
                r2(energyToday), false, r2(consumption), r2(camerasW), r2(connectivityW), r2(controlW),
                r2(energy / consumption), Device.Status.ONLINE, r2(latency.value), r2(download.value), r2(upload.value),
                r2(loss.value), now, Device.Status.ONLINE, (int) Math.round(cellSignal.value), r2(cellLatency.value),
                r2(cellDownload.value), r2(cellUpload.value), now, ConnectionType.STARLINK, now));
        for (Map.Entry<Long, Walk> camera : cameraSignal.entrySet()) {
            cameraRepository.updateLive(camera.getKey(), 25, (int) Math.round(camera.getValue().value), false, true, null);
        }
    }

    /** Busca el tramo de 2 horas de sol (inicio entre 8:00 y 14:00) mas reciente dentro de las ultimas 23 h. */
    private static Window findDaylightWindow(LocalDateTime now) {
        LocalDateTime start = now.minusMinutes(135).withMinute(0);
        while (!start.isBefore(now.minusHours(23))) {
            int hour = start.getHour();
            if (hour >= 8 && hour <= 14) {
                return new Window(start, start.plusHours(2));
            }
            start = start.minusMinutes(30);
        }
        return null;
    }

    private static double hourOf(LocalDateTime t) {
        return t.getHour() + t.getMinute() / 60.0;
    }

    /** Ciclo solar: 0 de noche, maximo al mediodia; "noise" aporta pequenas variaciones graduales. */
    private static double solarWatts(double hour, double panelW, double cloudFactor, double noise) {
        if (hour < 6 || hour >= 18) {
            return 0;
        }
        double base = panelW * Math.sin(Math.PI * (hour - 6) / 12);
        return Math.max(0, base * noise * cloudFactor);
    }

    private static double cameraWatts(double hour) {
        return hour < 6 || hour >= 18 ? CAMERA_NIGHT_W : CAMERA_DAY_W;
    }

    /** Bateria nueva = bateria actual + generacion - consumo (con limite de carga y entre 0 y 100 %). */
    private static double integrate(double energyWh, double generationW, double consumptionW, double hours,
                                    double capacityWh) {
        double balance = Math.min(generationW - consumptionW, MAX_CHARGE_W);
        return Math.max(0, Math.min(capacityWh, energyWh + balance * hours));
    }

    private static double r2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    // ============================================================
    // Eventos, alertas, incidencias y auditoria
    // ============================================================

    private void seedEpisodes(LocalDateTime now, long admin, long supervisor, long operator,
                              SiteData o1, SiteData o2, SiteData o3, SiteData o4,
                              Window cam006Offline, Window cam011Offline, Window starlinkOutage, Window cloudy) {
        // ----- Dias anteriores (sin telemetria: solo registros) -----
        LocalDateTime t0 = now.minusDays(6).minusMinutes(130);
        audit(operator, "LOGIN", "SESSION", operator, "Inicio de sesión de operador@novatech.local", t0.minusMinutes(60));
        Event e0 = event(o1, o1.camera("CAM-004"), EventType.CAMERA_OFFLINE, "Cámara sin señal: CAM-004 (Acceso vehicular)", t0);
        long a0 = alert(o1, o1.camera("CAM-004"), e0, Alert.Type.CAMERA_OFFLINE, "Cámara desconectada – Acceso vehicular",
                "La cámara CAM-004 (Acceso vehicular) dejó de transmitir. Verificar alimentación y red.", t0);
        acknowledge(a0, operator, t0.plusMinutes(5), "Cámara desconectada – Acceso vehicular");
        event(o1, o1.camera("CAM-004"), EventType.CAMERA_RESTORED, "Cámara recuperada: CAM-004 (Acceso vehicular)", t0.plusMinutes(48));
        resolve(a0, supervisor, t0.plusMinutes(50), "Cámara reiniciada remotamente; transmisión normal.",
                "Cámara desconectada – Acceso vehicular");

        LocalDateTime t1 = now.minusDays(5).minusMinutes(240);
        audit(supervisor, "LOGIN", "SESSION", supervisor, "Inicio de sesión de supervisor@novatech.local", t1.minusMinutes(20));
        incident(o3, null, "Mantenimiento preventivo de cámaras",
                "Limpieza de lentes y revisión de conectores de las cámaras del Centro Logístico Callao.", Severity.BAJA,
                Incident.Status.CERRADA, supervisor, supervisor, t1, t1.plusMinutes(180), t1.plusDays(1),
                note(t1.plusMinutes(10), "Supervisor de Monitoreo", "ABIERTA → EN_PROCESO. Técnico asignado en obra")
                        + "\n" + note(t1.plusMinutes(180), "Supervisor de Monitoreo", "EN_PROCESO → RESUELTA. Lentes limpios y conectores ajustados")
                        + "\n" + note(t1.plusDays(1), "Supervisor de Monitoreo", "RESUELTA → CERRADA"));
        event(o3, o3.camera("CAM-009"), EventType.DEVICE_MAINTENANCE, "Cámara CAM-009 en mantenimiento programado", t1.plusMinutes(30));
        event(o3, o3.camera("CAM-009"), EventType.SYSTEM_RESTORED, "Cámara CAM-009 operativa tras mantenimiento", t1.plusMinutes(150));

        LocalDateTime t2 = now.minusDays(4).minusMinutes(300);
        Event e2 = event(o4, o4.battery, EventType.BATTERY_LOW, "Batería baja: 34.6 % (límite 35 %)", t2);
        long a2 = alert(o4, o4.battery, e2, Alert.Type.BATTERY_LOW, "Batería baja – Proyecto Industrial Lurín",
                "La batería está en 34.6 %, por debajo del límite de 35 %.", t2);
        event(o4, o4.battery, EventType.SYSTEM_RESTORED, "Batería normalizada: 40.2 %", t2.plusMinutes(180));
        alertRepository.resolve(a2, null, t2.plusMinutes(180), "Resuelta automáticamente: batería normalizada");

        // ----- Ultimas 24 horas -----
        audit(admin, "LOGIN", "SESSION", admin, "Inicio de sesión de admin@novatech.local", now.minusHours(23));
        audit(operator, "LOGIN", "SESSION", operator, "Inicio de sesión de operador@novatech.local", now.minusMinutes(760));
        audit(supervisor, "LOGIN", "SESSION", supervisor, "Inicio de sesión de supervisor@novatech.local", now.minusMinutes(710));

        // OBRA-004: movimiento de madrugada en la zona de maquinaria
        event(o4, o4.camera("CAM-012"), EventType.MOTION_DETECTED, "Movimiento detectado en Zona de maquinaria", now.minusMinutes(780));

        // OBRA-001: intrusion en el perimetro norte -> incidencia resuelta y cerrada
        LocalDateTime t3 = now.minusMinutes(700);
        Severity s3 = MonitoringRules.intrusionSeverity(t3.toLocalTime());
        String d3 = "Intrusión detectada en Perímetro norte: movimiento en zona restringida (hora del equipo "
                + t3.toLocalTime().withSecond(0) + (s3 == Severity.CRITICA ? ", fuera del horario laboral)" : ", en horario laboral)");
        Event e3 = eventRepository.insert(o1.id, o1.camera("CAM-002"), t3, EventType.INTRUSION_DETECTED, s3, d3);
        long a3 = alertRepository.insert(o1.id, o1.camera("CAM-002"), e3.id(), Alert.Type.INTRUSION, t3, s3,
                Alert.Status.NUEVA, "Intrusión detectada – Perímetro norte", d3);
        acknowledge(a3, operator, t3.plusMinutes(2), "Intrusión detectada – Perímetro norte");
        LocalDateTime i3 = t3.plusMinutes(5);
        long inc3 = incident(o1, a3, "Intrusión en perímetro norte",
                "Se detectó una intrusión en el cerco norte. Coordinar verificación con el personal de seguridad de la obra.",
                MonitoringRules.incidentPriorityFor(s3), Incident.Status.CERRADA, supervisor, supervisor, i3,
                t3.plusMinutes(50), t3.plusMinutes(360),
                note(i3.plusMinutes(3), "Supervisor de Monitoreo", "ABIERTA → EN_PROCESO. Se contactó al vigilante de la obra")
                        + "\n" + note(t3.plusMinutes(50), "Supervisor de Monitoreo",
                        "EN_PROCESO → RESUELTA. Recorrido del perímetro sin hallazgos; se reforzó el cerco en el sector norte")
                        + "\n" + note(t3.plusMinutes(360), "Supervisor de Monitoreo", "RESUELTA → CERRADA"));
        alertRepository.setInAttention(a3, supervisor, supervisor, i3);
        String code3 = incidentCode(inc3);
        alertRepository.resolve(a3, supervisor, t3.plusMinutes(50), "Resuelta con la incidencia " + code3);
        audit(supervisor, "INCIDENCIA_CREADA", "INCIDENT", inc3, code3 + " desde la alerta " + a3 + ": Intrusión en perímetro norte", i3);
        audit(supervisor, "ALERTA_RESUELTA", "ALERT", a3, "Intrusión detectada – Perímetro norte | incidencia " + code3, t3.plusMinutes(50));
        audit(supervisor, "INCIDENCIA_CERRADA", "INCIDENT", inc3, code3 + ": RESUELTA → CERRADA", t3.plusMinutes(360));

        // OBRA-001: movimiento en acceso principal
        event(o1, o1.camera("CAM-001"), EventType.MOTION_DETECTED, "Movimiento detectado en Acceso principal", now.minusMinutes(540));

        // OBRA-002: CAM-006 sin senal 40 minutos
        LocalDateTime t4 = cam006Offline.start();
        Event e4 = event(o2, o2.camera("CAM-006"), EventType.CAMERA_OFFLINE, "Cámara sin señal: CAM-006 (Perímetro sur)", t4);
        long a4 = alert(o2, o2.camera("CAM-006"), e4, Alert.Type.CAMERA_OFFLINE, "Cámara desconectada – Perímetro sur",
                "La cámara CAM-006 (Perímetro sur) dejó de transmitir. Verificar alimentación y red.", t4);
        acknowledge(a4, operator, t4.plusMinutes(4), "Cámara desconectada – Perímetro sur");
        LocalDateTime i4 = t4.plusMinutes(10);
        long inc4 = incident(o2, a4, "Cámara del perímetro sur sin señal",
                "La cámara CAM-006 no transmite. Revisar cableado de red y alimentación.", Severity.ALTA,
                Incident.Status.RESUELTA, supervisor, supervisor, i4, cam006Offline.end().plusMinutes(15), null,
                note(cam006Offline.end().plusMinutes(15), "Supervisor de Monitoreo",
                        "ABIERTA → RESUELTA. Conector de red reasentado; la cámara volvió a transmitir"));
        alertRepository.setInAttention(a4, supervisor, supervisor, i4);
        audit(supervisor, "INCIDENCIA_CREADA", "INCIDENT", inc4, incidentCode(inc4) + " desde la alerta " + a4
                + ": Cámara del perímetro sur sin señal", i4);
        event(o2, o2.camera("CAM-006"), EventType.CAMERA_RESTORED, "Cámara recuperada: CAM-006 (Perímetro sur)", cam006Offline.end());
        alertRepository.resolve(a4, null, cam006Offline.end(), "Resuelta automáticamente: la cámara volvió a transmitir");
        audit(supervisor, "INCIDENCIA_ACTUALIZADA", "INCIDENT", inc4, incidentCode(inc4) + ": ABIERTA → RESUELTA",
                cam006Offline.end().plusMinutes(15));

        // OBRA-002: movimiento en acceso principal
        event(o2, o2.camera("CAM-005"), EventType.MOTION_DETECTED, "Movimiento detectado en Acceso principal", now.minusMinutes(420));

        // OBRA-003: corte de Starlink de 25 minutos con contingencia a 4G
        LocalDateTime t5 = starlinkOutage.start();
        Event e5 = event(o3, o3.starlink, EventType.STARLINK_DOWN, "CONEXIÓN STARLINK PERDIDA", t5);
        event(o3, o3.cellular, EventType.CELLULAR_ACTIVATED, "ACTIVANDO RESPALDO 4G. CONEXIÓN RESTABLECIDA MEDIANTE 4G", t5);
        long a5 = alert(o3, o3.starlink, e5, Alert.Type.STARLINK, "Starlink caído: operando con respaldo 4G – Centro Logístico Callao",
                "Se perdió la conexión Starlink. El sistema activó el respaldo 4G automáticamente.", t5);
        acknowledge(a5, operator, t5.plusMinutes(3), "Starlink caído: operando con respaldo 4G – Centro Logístico Callao");
        LocalDateTime i5 = t5.plusMinutes(10);
        long inc5 = incident(o3, a5, "Revisión de la antena Starlink",
                "Corte de Starlink en el Centro Logístico Callao. Revisar obstrucciones y estado de la antena.",
                Severity.MEDIA, Incident.Status.EN_PROCESO, supervisor, supervisor, i5, null, null,
                note(i5.plusMinutes(5), "Supervisor de Monitoreo",
                        "ABIERTA → EN_PROCESO. Se solicitó visita técnica para revisar obstrucciones"));
        alertRepository.setInAttention(a5, supervisor, supervisor, i5);
        audit(supervisor, "INCIDENCIA_CREADA", "INCIDENT", inc5, incidentCode(inc5) + " desde la alerta " + a5
                + ": Revisión de la antena Starlink", i5);
        event(o3, o3.starlink, EventType.STARLINK_RESTORED, "Starlink recuperado: la obra vuelve a la conexión principal",
                starlinkOutage.end());
        alertRepository.resolve(a5, null, starlinkOutage.end(), "Resuelta automáticamente: Starlink recuperado");

        // OBRA-002: intrusion en horario de trabajo, falsa alarma
        LocalDateTime t6 = now.minusMinutes(300);
        Severity s6 = MonitoringRules.intrusionSeverity(t6.toLocalTime());
        String d6 = "Intrusión detectada en Grúa torre: movimiento en zona restringida (hora del equipo "
                + t6.toLocalTime().withSecond(0) + (s6 == Severity.CRITICA ? ", fuera del horario laboral)" : ", en horario laboral)");
        Event e6 = eventRepository.insert(o2.id, o2.camera("CAM-007"), t6, EventType.INTRUSION_DETECTED, s6, d6);
        long a6 = alertRepository.insert(o2.id, o2.camera("CAM-007"), e6.id(), Alert.Type.INTRUSION, t6, s6,
                Alert.Status.NUEVA, "Intrusión detectada – Grúa torre", d6);
        acknowledge(a6, operator, t6.plusMinutes(2), "Intrusión detectada – Grúa torre");
        resolve(a6, supervisor, t6.plusMinutes(20),
                "Falsa alarma: personal de la obra en zona restringida. Se reforzó la señalización.",
                "Intrusión detectada – Grúa torre");

        // OBRA-001: movimiento en acceso vehicular
        event(o1, o1.camera("CAM-004"), EventType.MOTION_DETECTED, "Movimiento detectado en Acceso vehicular", now.minusMinutes(270));

        // OBRA-004: CAM-011 sin senal 15 minutos, se resolvio sola
        Event e7 = event(o4, o4.camera("CAM-011"), EventType.CAMERA_OFFLINE, "Cámara sin señal: CAM-011 (Acceso vehicular)",
                cam011Offline.start());
        long a7 = alert(o4, o4.camera("CAM-011"), e7, Alert.Type.CAMERA_OFFLINE, "Cámara desconectada – Acceso vehicular",
                "La cámara CAM-011 (Acceso vehicular) dejó de transmitir. Verificar alimentación y red.", cam011Offline.start());
        event(o4, o4.camera("CAM-011"), EventType.CAMERA_RESTORED, "Cámara recuperada: CAM-011 (Acceso vehicular)", cam011Offline.end());
        alertRepository.resolve(a7, null, cam011Offline.end(), "Resuelta automáticamente: la cámara volvió a transmitir");

        // OBRA-003: movimiento en patio de maniobras
        event(o3, o3.camera("CAM-008"), EventType.MOTION_DETECTED, "Movimiento detectado en Patio de maniobras", now.minusMinutes(160));

        // OBRA-004: tramo nublado
        if (cloudy != null) {
            event(o4, o4.solar, EventType.LOW_SOLAR_GENERATION, "Baja generación solar: condición nublada", cloudy.start());
            event(o4, o4.solar, EventType.SYSTEM_RESTORED, "Generación solar normalizada", cloudy.end());
        }

        // OBRA-001: movimiento en zona de materiales
        event(o1, o1.camera("CAM-003"), EventType.MOTION_DETECTED, "Movimiento detectado en Zona de materiales", now.minusMinutes(80));

        audit(null, "SISTEMA", "CONFIG", null, "Datos iniciales de demostración cargados", now);
    }

    private Event event(SiteData site, Long deviceId, EventType type, String description, LocalDateTime at) {
        return eventRepository.insert(site.id, deviceId, at, type, MonitoringRules.eventSeverity(type), description);
    }

    private long alert(SiteData site, Long deviceId, Event event, Alert.Type type, String title, String description,
                       LocalDateTime at) {
        return alertRepository.insert(site.id, deviceId, event.id(), type, at, MonitoringRules.alertSeverity(type),
                Alert.Status.NUEVA, title, description);
    }

    private void acknowledge(long alertId, long userId, LocalDateTime at, String title) {
        alertRepository.acknowledge(alertId, userId, at);
        audit(userId, "ALERTA_RECONOCIDA", "ALERT", alertId, title, at);
    }

    private void resolve(long alertId, long userId, LocalDateTime at, String note, String title) {
        alertRepository.resolve(alertId, userId, at, note);
        audit(userId, "ALERTA_RESUELTA", "ALERT", alertId, title + " | " + note, at);
    }

    private long incident(SiteData site, Long alertId, String title, String description, Severity priority,
                          Incident.Status status, long assignedTo, long createdBy, LocalDateTime createdAt,
                          LocalDateTime resolvedAt, LocalDateTime closedAt, String observations) {
        int year = createdAt.getYear();
        String code = String.format("INC-%d-%04d", year, incidentRepository.maxSequence(year) + 1);
        LocalDateTime updated = closedAt != null ? closedAt : resolvedAt != null ? resolvedAt : createdAt;
        return incidentRepository.insert(new Incident(null, site.id, alertId, code, title, description, priority, status,
                assignedTo, createdBy, createdAt, updated, resolvedAt, closedAt, observations));
    }

    private String incidentCode(long incidentId) {
        return incidentRepository.findById(incidentId).map(Incident::code).orElse("");
    }

    private static String note(LocalDateTime at, String user, String text) {
        return "[" + at.format(NOTE_TIME) + "] " + user + ": " + text;
    }

    private void audit(Long userId, String action, String entity, Long entityId, String details, LocalDateTime at) {
        auditRepository.insert(userId, action, entity, entityId, details, at);
    }
}

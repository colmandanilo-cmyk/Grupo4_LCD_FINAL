package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.IngestDtos.BatteryReading;
import com.novatech.monitoring.dto.IngestDtos.CameraReading;
import com.novatech.monitoring.dto.IngestDtos.CellularReading;
import com.novatech.monitoring.dto.IngestDtos.DeviceEventRequest;
import com.novatech.monitoring.dto.IngestDtos.DeviceEventResponse;
import com.novatech.monitoring.dto.IngestDtos.SolarReading;
import com.novatech.monitoring.dto.IngestDtos.StarlinkReading;
import com.novatech.monitoring.dto.IngestDtos.TelemetryRequest;
import com.novatech.monitoring.dto.IngestDtos.TelemetryResponse;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.ConnectivityStatus;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.EnergyStatus;
import com.novatech.monitoring.model.Event;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.model.Site;
import com.novatech.monitoring.model.SiteLiveStatus;
import com.novatech.monitoring.model.SiteLiveStatus.BatteryLevel;
import com.novatech.monitoring.model.TelemetryRecord;
import com.novatech.monitoring.repository.CameraRepository;
import com.novatech.monitoring.repository.ConnectivityStatusRepository;
import com.novatech.monitoring.repository.DeviceRepository;
import com.novatech.monitoring.repository.EnergyStatusRepository;
import com.novatech.monitoring.repository.SiteLiveStatusRepository;
import com.novatech.monitoring.repository.SiteRepository;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.repository.TelemetryRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import static com.novatech.monitoring.repository.SqlUtils.round2;

/**
 * Procesa lo que envian los dispositivos por /api/ingest (hoy el simulador Python).
 *
 * Python envia lecturas crudas; aqui Java compara cada lectura con el estado
 * anterior, registra un evento por cada cambio, crea o resuelve alertas segun
 * MonitoringRules, decide la conexion activa (contingencia Starlink -> 4G),
 * actualiza el estado actual y guarda el historial.
 */
@Service
public class IngestService {

    private static final Logger log = LoggerFactory.getLogger(IngestService.class);
    private static final DateTimeFormatter HOUR = DateTimeFormatter.ofPattern("HH:mm");

    private final SiteRepository siteRepository;
    private final DeviceRepository deviceRepository;
    private final CameraRepository cameraRepository;
    private final SiteLiveStatusRepository liveRepository;
    private final EnergyStatusRepository energyRepository;
    private final ConnectivityStatusRepository connectivityRepository;
    private final TelemetryRepository telemetryRepository;
    private final EventService eventService;
    private final AlertService alertService;
    private final ConfigService configService;

    public IngestService(SiteRepository siteRepository, DeviceRepository deviceRepository,
                         CameraRepository cameraRepository, SiteLiveStatusRepository liveRepository,
                         EnergyStatusRepository energyRepository, ConnectivityStatusRepository connectivityRepository,
                         TelemetryRepository telemetryRepository, EventService eventService,
                         AlertService alertService, ConfigService configService) {
        this.siteRepository = siteRepository;
        this.deviceRepository = deviceRepository;
        this.cameraRepository = cameraRepository;
        this.liveRepository = liveRepository;
        this.energyRepository = energyRepository;
        this.connectivityRepository = connectivityRepository;
        this.telemetryRepository = telemetryRepository;
        this.eventService = eventService;
        this.alertService = alertService;
        this.configService = configService;
    }

    /** Cuenta lo que se genero al procesar un paquete. */
    private static final class Changes {
        int events;
        int alerts;
    }

    /** Estado final de una camara despues de procesarla (para el historial). */
    private record CameraState(Device device, boolean online, int signal) {
    }

    // ============================================================
    // Telemetria completa de una estacion
    // ============================================================

    @Transactional
    public TelemetryResponse processTelemetry(TelemetryRequest request) {
        LocalDateTime now = SqlUtils.now();
        Site site = siteRepository.findByCode(request.siteCode())
                .orElseThrow(() -> ApiException.notFound("Obra no registrada: " + request.siteCode()));
        Map<String, Device> devices = deviceRepository.findBySite(site.id()).stream()
                .collect(Collectors.toMap(Device::code, Function.identity()));
        SiteLiveStatus previous = liveRepository.find(site.id()).orElse(null);
        Changes changes = new Changes();

        Device solar = requireDevice(devices, request.solarPanel().code(), Device.Type.SOLAR_PANEL, site);
        Device battery = requireDevice(devices, request.battery().code(), Device.Type.BATTERY, site);
        Device starlink = requireDevice(devices, request.starlink().code(), Device.Type.STARLINK, site);
        Device cellular = requireDevice(devices, request.cellular().code(), Device.Type.CELLULAR_4G, site);

        List<CameraState> cameras = processCameras(site, request.cameras(), devices, changes, now);
        BatteryLevel batteryLevel = processBattery(site, battery, request.battery(), previous, changes, now);
        boolean solarFailed = processSolar(site, solar, request.solarPanel(), previous, changes, now);
        ConnectionType active = processConnectivity(site, starlink, cellular, request.starlink(),
                request.cellular(), previous, changes, now);

        // Historial: cada "frecuencia de telemetria" segundos, o de inmediato si algo cambio.
        boolean saveHistory = previous == null || previous.lastHistoryAt() == null || changes.events > 0
                || Duration.between(previous.lastHistoryAt(), now).getSeconds()
                >= configService.telemetryIntervalSeconds();

        SiteLiveStatus current = buildLiveStatus(site, request, previous, batteryLevel, solarFailed, active,
                now, saveHistory ? now : previous.lastHistoryAt());
        liveRepository.save(current);
        if (saveHistory) {
            saveHistory(site, current, cameras, battery, solar, starlink, cellular, now);
        }
        return new TelemetryResponse(active, alertService.generalStateOf(site.id()), changes.events, changes.alerts);
    }

    // ---------------- Camaras ----------------

    private List<CameraState> processCameras(Site site, List<CameraReading> readings, Map<String, Device> devices,
                                             Changes changes, LocalDateTime now) {
        List<CameraState> states = new ArrayList<>();
        if (readings == null) {
            return states;
        }
        for (CameraReading reading : readings) {
            Device device = devices.get(reading.code());
            if (device == null || device.type() != Device.Type.CAMERA) {
                log.warn("Telemetría de {}: la cámara {} no pertenece a la obra; se ignora", site.code(), reading.code());
                continue;
            }
            Device.Status current = device.status();
            // Una camara no puede estar en FALLA: se trata como fuera de linea.
            Device.Status reported = reading.status() == Device.Status.FALLA ? Device.Status.OFFLINE : reading.status();
            Device.Status effective = current;

            // MANTENIMIENTO lo controla el administrador: la telemetria no lo pone ni lo quita.
            boolean maintenance = current == Device.Status.MANTENIMIENTO || reported == Device.Status.MANTENIMIENTO;
            if (!maintenance && reported != current) {
                effective = reported;
                String label = device.code() + " (" + device.name() + ")";
                if (reported == Device.Status.OFFLINE) {
                    Event event = event(changes, site, device.id(), EventType.CAMERA_OFFLINE,
                            "Cámara sin señal: " + label, now);
                    raise(changes, site, device.id(), event, Alert.Type.CAMERA_OFFLINE,
                            "Cámara desconectada – " + device.name(),
                            "La cámara " + label + " dejó de transmitir. Verificar alimentación y red.", now);
                } else if (reported == Device.Status.ONLINE) {
                    event(changes, site, device.id(), EventType.CAMERA_RESTORED, "Cámara recuperada: " + label, now);
                    alertService.autoResolve(site.id(), device.id(), Alert.Type.CAMERA_OFFLINE, "la cámara volvió a transmitir", now);
                }
            }

            boolean online = effective == Device.Status.ONLINE;
            boolean motion = online && reading.motion();
            cameraRepository.updateLive(device.id(), online ? reading.fps() : 0, online ? reading.signal() : 0,
                    motion, online && reading.recording(), motion ? now : null);
            deviceRepository.updateStatus(device.id(), effective, online ? now : null);
            states.add(new CameraState(device, online, online ? reading.signal() : 0));
        }
        return states;
    }

    // ---------------- Bateria ----------------

    private BatteryLevel processBattery(Site site, Device battery, BatteryReading reading, SiteLiveStatus previous,
                                        Changes changes, LocalDateTime now) {
        int low = configService.batteryLowThreshold();
        int critical = configService.batteryCriticalThreshold();
        BatteryLevel before = previous == null ? BatteryLevel.NORMAL : previous.batteryLevel();
        BatteryLevel after = MonitoringRules.batteryLevel(before, reading.percent(), low, critical);
        String percent = String.format("%.1f %%", reading.percent());

        if (after != before) {
            if (after == BatteryLevel.BAJA) {
                if (before == BatteryLevel.CRITICA) {
                    alertService.autoResolve(site.id(), battery.id(), Alert.Type.BATTERY_CRITICAL,
                            "la batería superó el nivel crítico (" + percent + ")", now);
                }
                Event event = event(changes, site, battery.id(), EventType.BATTERY_LOW,
                        "Batería baja: " + percent + " (límite " + low + " %)", now);
                raise(changes, site, battery.id(), event, Alert.Type.BATTERY_LOW, "Batería baja – " + site.name(),
                        "La batería está en " + percent + ", por debajo del límite de " + low + " %.", now);
            } else if (after == BatteryLevel.CRITICA) {
                alertService.autoResolve(site.id(), battery.id(), Alert.Type.BATTERY_LOW,
                        "escalada a batería crítica", now);
                Event event = event(changes, site, battery.id(), EventType.BATTERY_CRITICAL,
                        "Batería crítica: " + percent + " (límite " + critical + " %)", now);
                raise(changes, site, battery.id(), event, Alert.Type.BATTERY_CRITICAL, "Batería crítica – " + site.name(),
                        "La batería está en " + percent + ". Autonomía estimada: "
                                + String.format("%.1f h", reading.autonomyHours()) + ".", now);
            } else {
                alertService.autoResolve(site.id(), battery.id(), Alert.Type.BATTERY_LOW, "batería normalizada", now);
                alertService.autoResolve(site.id(), battery.id(), Alert.Type.BATTERY_CRITICAL, "batería normalizada", now);
                event(changes, site, battery.id(), EventType.SYSTEM_RESTORED, "Batería normalizada: " + percent, now);
            }
        }
        deviceRepository.updateStatus(battery.id(), Device.Status.ONLINE, now);
        return after;
    }

    // ---------------- Panel solar ----------------

    private boolean processSolar(Site site, Device solar, SolarReading reading, SiteLiveStatus previous,
                                 Changes changes, LocalDateTime now) {
        boolean failed = reading.status() == Device.Status.FALLA || reading.status() == Device.Status.OFFLINE;
        boolean failedBefore = solar.status() == Device.Status.FALLA;
        if (failed && !failedBefore) {
            Event event = event(changes, site, solar.id(), EventType.SOLAR_PANEL_FAILURE,
                    "Falla del panel solar: generación en 0 W", now);
            raise(changes, site, solar.id(), event, Alert.Type.SOLAR_PANEL, "Falla panel solar – " + site.name(),
                    "El panel solar no genera energía. La estación funciona solo con batería.", now);
        } else if (!failed && failedBefore) {
            event(changes, site, solar.id(), EventType.SYSTEM_RESTORED, "Panel solar operativo nuevamente", now);
            alertService.autoResolve(site.id(), solar.id(), Alert.Type.SOLAR_PANEL, "el panel solar volvió a generar", now);
        }

        boolean lowGeneration = reading.lowGeneration() && !failed;
        boolean lowBefore = previous != null && previous.lowGeneration();
        if (lowGeneration && !lowBefore) {
            event(changes, site, solar.id(), EventType.LOW_SOLAR_GENERATION,
                    String.format("Baja generación solar: %.0f W (condición nublada)", reading.generationW()), now);
        } else if (!lowGeneration && lowBefore) {
            event(changes, site, solar.id(), EventType.SYSTEM_RESTORED, "Generación solar normalizada", now);
        }
        deviceRepository.updateStatus(solar.id(), failed ? Device.Status.FALLA : Device.Status.ONLINE,
                failed ? null : now);
        return failed;
    }

    // ---------------- Conectividad: contingencia Starlink -> 4G (seccion 26) ----------------

    private ConnectionType processConnectivity(Site site, Device starlink, Device cellular, StarlinkReading sl,
                                               CellularReading cell, SiteLiveStatus previous, Changes changes,
                                               LocalDateTime now) {
        boolean starlinkUp = sl.status() == Device.Status.ONLINE;
        boolean cellularUp = cell.status() == Device.Status.ONLINE;
        boolean starlinkUpBefore = previous == null || previous.starlinkStatus() == Device.Status.ONLINE;
        boolean cellularUpBefore = previous == null || previous.cellularStatus() == Device.Status.ONLINE;
        ConnectionType activeBefore = previous == null ? ConnectionType.STARLINK : previous.activeConnection();
        ConnectionType active = MonitoringRules.activeConnection(starlinkUp, cellularUp);

        Event starlinkEvent = null;
        // 1. Registrar el cambio de cada enlace
        if (starlinkUpBefore && !starlinkUp) {
            starlinkEvent = event(changes, site, starlink.id(), EventType.STARLINK_DOWN,
                    "CONEXIÓN STARLINK PERDIDA", now);
        } else if (!starlinkUpBefore && starlinkUp) {
            event(changes, site, starlink.id(), EventType.STARLINK_RESTORED,
                    "Starlink recuperado: la obra vuelve a la conexión principal", now);
        }
        if (cellularUpBefore && !cellularUp) {
            event(changes, site, cellular.id(), EventType.CELLULAR_DOWN,
                    starlinkUp ? "Respaldo 4G no disponible (Starlink sigue activo)" : "Conexión 4G perdida", now);
        } else if (!cellularUpBefore && cellularUp) {
            event(changes, site, cellular.id(), EventType.CELLULAR_RESTORED, "Respaldo 4G disponible nuevamente", now);
        }
        // 2. Verificar el 4G y activarlo si corresponde
        if (active == ConnectionType.CELLULAR_4G && activeBefore != ConnectionType.CELLULAR_4G) {
            Event activation = event(changes, site, cellular.id(), EventType.CELLULAR_ACTIVATED,
                    "ACTIVANDO RESPALDO 4G. CONEXIÓN RESTABLECIDA MEDIANTE 4G", now);
            if (starlinkEvent == null) {
                starlinkEvent = activation;
            }
        }

        // 3. Alertas de las dos condiciones de la contingencia
        boolean degraded = MonitoringRules.starlinkDegraded(starlinkUp, cellularUp);
        boolean degradedBefore = MonitoringRules.starlinkDegraded(starlinkUpBefore, cellularUpBefore);
        boolean lost = MonitoringRules.connectivityLost(starlinkUp, cellularUp);
        boolean lostBefore = MonitoringRules.connectivityLost(starlinkUpBefore, cellularUpBefore);

        if (degraded && !degradedBefore) {
            raise(changes, site, starlink.id(), starlinkEvent == null ? null : starlinkEvent, Alert.Type.STARLINK,
                    "Starlink caído: operando con respaldo 4G – " + site.name(),
                    "Se perdió la conexión Starlink. El sistema activó el respaldo 4G automáticamente.", now);
        } else if (!degraded && degradedBefore) {
            alertService.autoResolve(site.id(), starlink.id(), Alert.Type.STARLINK,
                    starlinkUp ? "Starlink recuperado" : "la obra quedó sin conectividad (escalada)", now);
        }
        if (lost && !lostBefore) {
            Event event = event(changes, site, null, EventType.CONNECTIVITY_LOST,
                    "OBRA SIN CONECTIVIDAD: Starlink y 4G caídos", now);
            raise(changes, site, null, event, Alert.Type.CONNECTIVITY, "Obra sin conectividad – " + site.name(),
                    "Starlink y el respaldo 4G están caídos. La estación no puede comunicarse.", now);
        } else if (!lost && lostBefore) {
            event(changes, site, null, EventType.SYSTEM_RESTORED,
                    "Comunicación restablecida mediante " + (starlinkUp ? "Starlink" : "4G de respaldo"), now);
            alertService.autoResolve(site.id(), null, Alert.Type.CONNECTIVITY, "comunicación restablecida", now);
        }

        // 4. Estado de la obra: SIN_CONEXION mientras no haya enlaces (salvo mantenimiento)
        if (lost && site.status() == Site.Status.ACTIVA) {
            siteRepository.updateStatus(site.id(), Site.Status.SIN_CONEXION);
        } else if (!lost && site.status() == Site.Status.SIN_CONEXION) {
            siteRepository.updateStatus(site.id(), Site.Status.ACTIVA);
        }
        deviceRepository.updateStatus(starlink.id(), starlinkUp ? Device.Status.ONLINE : Device.Status.OFFLINE,
                starlinkUp ? now : null);
        deviceRepository.updateStatus(cellular.id(), cellularUp ? Device.Status.ONLINE : Device.Status.OFFLINE,
                cellularUp ? now : null);
        return active;
    }

    // ---------------- Estado actual e historial ----------------

    private SiteLiveStatus buildLiveStatus(Site site, TelemetryRequest r, SiteLiveStatus previous,
                                           BatteryLevel batteryLevel, boolean solarFailed, ConnectionType active,
                                           LocalDateTime now, LocalDateTime lastHistoryAt) {
        boolean starlinkUp = r.starlink().status() == Device.Status.ONLINE;
        boolean cellularUp = r.cellular().status() == Device.Status.ONLINE;
        double generation = solarFailed ? 0 : r.solarPanel().generationW();
        return new SiteLiveStatus(
                site.id(), now, r.deviceTime(),
                round2(r.battery().percent()), round2(r.battery().voltage()), batteryLevel,
                MonitoringRules.batteryTrend(generation, r.consumption().totalW(), r.battery().percent()),
                solarFailed ? Device.Status.FALLA : Device.Status.ONLINE,
                round2(r.solarPanel().ratedPowerW()), round2(generation), round2(r.solarPanel().energyTodayKwh()),
                r.solarPanel().lowGeneration() && !solarFailed,
                round2(r.consumption().totalW()), round2(r.consumption().camerasW()),
                round2(r.consumption().connectivityW()), round2(r.consumption().controlW()),
                round2(r.battery().autonomyHours()),
                starlinkUp ? Device.Status.ONLINE : Device.Status.OFFLINE,
                starlinkUp ? round2(r.starlink().latencyMs()) : null,
                starlinkUp ? round2(r.starlink().downloadMbps()) : null,
                starlinkUp ? round2(r.starlink().uploadMbps()) : null,
                starlinkUp ? round2(r.starlink().packetLoss()) : null,
                starlinkUp ? now : (previous == null ? null : previous.starlinkLastSeen()),
                cellularUp ? Device.Status.ONLINE : Device.Status.OFFLINE,
                cellularUp ? r.cellular().signal() : null,
                cellularUp ? round2(r.cellular().latencyMs()) : null,
                cellularUp ? round2(r.cellular().downloadMbps()) : null,
                cellularUp ? round2(r.cellular().uploadMbps()) : null,
                cellularUp ? now : (previous == null ? null : previous.cellularLastSeen()),
                active, lastHistoryAt);
    }

    private void saveHistory(Site site, SiteLiveStatus s, List<CameraState> cameras, Device battery, Device solar,
                             Device starlink, Device cellular, LocalDateTime now) {
        energyRepository.insert(new EnergyStatus(null, site.id(), now, s.batteryPercent(), s.batteryVoltage(),
                s.solarGeneration(), s.consumption(), s.estimatedAutonomy()));
        connectivityRepository.insert(new ConnectivityStatus(null, site.id(), now, s.starlinkStatus(),
                s.starlinkLatency(), s.starlinkDownload(), s.starlinkUpload(), s.starlinkPacketLoss(),
                s.cellularStatus(), s.cellularSignal(), s.cellularLatency(), s.cellularDownload(),
                s.cellularUpload(), s.activeConnection()));

        List<TelemetryRecord> rows = new ArrayList<>();
        rows.add(metric(site, battery, now, "battery_percent", s.batteryPercent(), "%"));
        rows.add(metric(site, battery, now, "battery_voltage", s.batteryVoltage(), "V"));
        rows.add(metric(site, battery, now, "consumption", s.consumption(), "W"));
        rows.add(metric(site, solar, now, "solar_generation", s.solarGeneration(), "W"));
        boolean starlinkUp = s.starlinkStatus() == Device.Status.ONLINE;
        rows.add(metric(site, starlink, now, "online", starlinkUp ? 1.0 : 0.0, "estado"));
        if (starlinkUp && s.starlinkLatency() != null) {
            rows.add(metric(site, starlink, now, "latency", s.starlinkLatency(), "ms"));
        }
        boolean cellularUp = s.cellularStatus() == Device.Status.ONLINE;
        rows.add(metric(site, cellular, now, "online", cellularUp ? 1.0 : 0.0, "estado"));
        if (cellularUp && s.cellularSignal() != null) {
            rows.add(metric(site, cellular, now, "signal", s.cellularSignal().doubleValue(), "%"));
        }
        for (CameraState camera : cameras) {
            rows.add(metric(site, camera.device(), now, "online", camera.online() ? 1.0 : 0.0, "estado"));
            rows.add(metric(site, camera.device(), now, "signal", (double) camera.signal(), "%"));
        }
        telemetryRepository.insertAll(rows.stream().filter(r -> !Double.isNaN(r.value())).toList());
    }

    private static TelemetryRecord metric(Site site, Device device, LocalDateTime when, String metric, Double value,
                                          String unit) {
        return new TelemetryRecord(null, site.id(), device.id(), when, metric, value == null ? Double.NaN : value, unit);
    }

    // ============================================================
    // Eventos puntuales informados por un dispositivo
    // ============================================================

    @Transactional
    public DeviceEventResponse processDeviceEvent(DeviceEventRequest request) {
        LocalDateTime now = SqlUtils.now();
        Site site = siteRepository.findByCode(request.siteCode())
                .orElseThrow(() -> ApiException.notFound("Obra no registrada: " + request.siteCode()));
        if (!MonitoringRules.DEVICE_REPORTED_EVENTS.contains(request.type())) {
            throw ApiException.badRequest("Un dispositivo solo puede informar MOTION_DETECTED o INTRUSION_DETECTED; "
                    + "los demás eventos los detecta el sistema");
        }
        Device device = null;
        if (request.deviceCode() != null && !request.deviceCode().isBlank()) {
            device = deviceRepository.findByCode(request.deviceCode())
                    .filter(d -> d.siteId().equals(site.id()))
                    .orElseThrow(() -> ApiException.badRequest("El dispositivo " + request.deviceCode()
                            + " no pertenece a la obra " + site.code()));
        }
        String where = device != null ? device.name() : site.name();
        LocalTime deviceTime = (request.deviceTime() != null ? request.deviceTime() : now).toLocalTime();

        if (request.type() == EventType.MOTION_DETECTED) {
            String description = describe(request.description(), "Movimiento detectado en " + where);
            Event event = eventService.record(site.id(), device == null ? null : device.id(),
                    EventType.MOTION_DETECTED, description, now);
            markMotion(device, now);
            return new DeviceEventResponse(event.id(), event.severity(), null);
        }

        // Intrusion: la severidad depende de la hora del equipo (horario laboral o no).
        Severity severity = MonitoringRules.intrusionSeverity(deviceTime);
        String description = describe(request.description(), "Intrusión detectada en " + where)
                + " (hora del equipo " + deviceTime.format(HOUR)
                + (severity == Severity.CRITICA ? ", fuera del horario laboral)" : ", en horario laboral)");
        Event event = eventService.record(site.id(), device == null ? null : device.id(),
                EventType.INTRUSION_DETECTED, severity, description, now);
        long alertId = alertService.createIntrusion(site.id(), device == null ? null : device.id(), event.id(),
                severity, "Intrusión detectada – " + where, description, now);
        markMotion(device, now);
        return new DeviceEventResponse(event.id(), severity, alertId);
    }

    // ============================================================
    // Auxiliares
    // ============================================================

    private Event event(Changes changes, Site site, Long deviceId, EventType type, String description,
                        LocalDateTime now) {
        changes.events++;
        return eventService.record(site.id(), deviceId, type, description, now);
    }

    private void raise(Changes changes, Site site, Long deviceId, Event event, Alert.Type type, String title,
                       String description, LocalDateTime now) {
        alertService.raiseCondition(site.id(), deviceId, event == null ? null : event.id(), type, title, description, now)
                .ifPresent(id -> changes.alerts++);
    }

    private void markMotion(Device device, LocalDateTime now) {
        if (device != null && device.type() == Device.Type.CAMERA) {
            cameraRepository.markMotion(device.id(), now);
        }
    }

    private static String describe(String provided, String fallback) {
        return provided == null || provided.isBlank() ? fallback : provided.trim();
    }

    private static Device requireDevice(Map<String, Device> devices, String code, Device.Type type, Site site) {
        Device device = devices.get(code);
        if (device == null || device.type() != type) {
            throw ApiException.badRequest("El dispositivo " + code + " (" + type + ") no pertenece a la obra " + site.code());
        }
        return device;
    }
}

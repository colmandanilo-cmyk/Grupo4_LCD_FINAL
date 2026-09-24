package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.IngestDtos.CommandAckRequest;
import com.novatech.monitoring.dto.IngestDtos.LastKnown;
import com.novatech.monitoring.dto.IngestDtos.SyncCommand;
import com.novatech.monitoring.dto.IngestDtos.SyncDevice;
import com.novatech.monitoring.dto.IngestDtos.SyncResponse;
import com.novatech.monitoring.dto.IngestDtos.SyncSite;
import com.novatech.monitoring.dto.SimulationDtos.CommandResponse;
import com.novatech.monitoring.dto.SimulationDtos.CommandView;
import com.novatech.monitoring.dto.SimulationDtos.SimulationStatus;
import com.novatech.monitoring.dto.SimulationDtos.SiteSimulation;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.Scenario;
import com.novatech.monitoring.model.SimulationCommand;
import com.novatech.monitoring.model.SimulationState;
import com.novatech.monitoring.model.Site;
import com.novatech.monitoring.model.SiteLiveStatus;
import com.novatech.monitoring.repository.DeviceRepository;
import com.novatech.monitoring.repository.SimulationRepository;
import com.novatech.monitoring.repository.SiteLiveStatusRepository;
import com.novatech.monitoring.repository.SiteRepository;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.security.AuthenticatedUser;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * Laboratorio de Simulacion (seccion 32) y canal de control del simulador.
 *
 * Java no llama a Python: guarda cada orden en simulation_commands y el
 * simulador la recoge al consultar GET /api/ingest/sync cada 2 segundos.
 */
@Service
public class SimulationService {

    private final SimulationRepository repository;
    private final SiteRepository siteRepository;
    private final DeviceRepository deviceRepository;
    private final SiteLiveStatusRepository liveRepository;
    private final ConfigService configService;
    private final AuditService auditService;

    /** Ultima vez que la fuente de datos (simulador o equipos) hablo con Java. */
    private volatile LocalDateTime lastContact;

    public SimulationService(SimulationRepository repository, SiteRepository siteRepository,
                             DeviceRepository deviceRepository, SiteLiveStatusRepository liveRepository,
                             ConfigService configService, AuditService auditService) {
        this.repository = repository;
        this.siteRepository = siteRepository;
        this.deviceRepository = deviceRepository;
        this.liveRepository = liveRepository;
        this.configService = configService;
        this.auditService = auditService;
    }

    // ============================================================
    // Estado de la fuente de datos
    // ============================================================

    public void recordContact() {
        lastContact = SqlUtils.now();
    }

    public LocalDateTime lastContact() {
        return lastContact;
    }

    public boolean dataSourceOnline() {
        return !MonitoringRules.isOlderThan(lastContact, SqlUtils.now(), MonitoringRules.DATA_SOURCE_ONLINE_SECONDS);
    }

    // ============================================================
    // Pantalla del laboratorio
    // ============================================================

    public SimulationStatus status() {
        Map<Long, SimulationState> states = repository.findStates().stream()
                .collect(Collectors.toMap(SimulationState::siteId, Function.identity()));
        Map<Long, SiteLiveStatus> live = liveRepository.findAll().stream()
                .collect(Collectors.toMap(SiteLiveStatus::siteId, Function.identity()));
        List<SiteSimulation> sites = siteRepository.findAll().stream().map(site -> {
            SimulationState state = states.get(site.id());
            SiteLiveStatus status = live.get(site.id());
            return new SiteSimulation(site.id(), site.code(), site.name(),
                    state != null && state.enabled(), state == null ? 1 : state.speed(),
                    state == null ? "NORMAL" : state.scenario(),
                    status == null ? null : status.deviceTime(), status == null ? null : status.updatedAt());
        }).toList();
        return new SimulationStatus(dataSourceOnline(), lastContact, configService.simulationEnabled(),
                configService.defaultSpeed(), sites, repository.findRecentViews(20));
    }

    @Transactional
    public SimulationStatus pause(AuthenticatedUser user) {
        repository.setEnabledAll(false, SqlUtils.now());
        auditService.log(user.id(), "SIMULACION_CONTROL", "SIMULATION", null, "Simulación pausada");
        return status();
    }

    @Transactional
    public SimulationStatus resume(AuthenticatedUser user) {
        if (!configService.simulationEnabled()) {
            throw ApiException.conflict("La simulación automática está desactivada en Configuración");
        }
        repository.setEnabledAll(true, SqlUtils.now());
        auditService.log(user.id(), "SIMULACION_CONTROL", "SIMULATION", null, "Simulación reanudada");
        return status();
    }

    @Transactional
    public SimulationStatus speed(int speed, AuthenticatedUser user) {
        if (!ConfigService.ALLOWED_SPEEDS.contains(speed)) {
            throw ApiException.badRequest("La velocidad debe ser 1, 5 o 20");
        }
        repository.setSpeedAll(speed, SqlUtils.now());
        auditService.log(user.id(), "SIMULACION_CONTROL", "SIMULATION", null, "Velocidad x" + speed);
        return status();
    }

    /** Reiniciar: todo vuelve a la normalidad con la pausa y velocidad de Configuracion. */
    @Transactional
    public CommandResponse reset(AuthenticatedUser user) {
        LocalDateTime now = SqlUtils.now();
        repository.expirePendingBefore(now.plusSeconds(1));
        repository.resetAll(configService.simulationEnabled(), configService.defaultSpeed(), now);
        long id = repository.insertCommand(null, null, Scenario.RESET, user.id(), now);
        auditService.log(user.id(), "SIMULACION_CONTROL", "SIMULATION", id, "Simulación reiniciada");
        return response(id);
    }

    /** Registra una orden de escenario para una obra (y opcionalmente una camara). */
    @Transactional
    public CommandResponse scenario(Scenario scenario, Long siteId, Long deviceId, AuthenticatedUser user) {
        if (scenario == Scenario.RESET) {
            return reset(user);
        }
        Site site = siteRepository.findById(siteId)
                .orElseThrow(() -> ApiException.notFound("La obra " + siteId + " no existe"));
        Long targetDevice = null;
        if (scenario.cameraScenario() && deviceId != null) {
            Device device = deviceRepository.findById(deviceId)
                    .filter(d -> d.siteId().equals(site.id()) && d.type() == Device.Type.CAMERA)
                    .orElseThrow(() -> ApiException.badRequest("La cámara elegida no pertenece a la obra " + site.code()));
            if (device.status() == Device.Status.MANTENIMIENTO) {
                throw ApiException.conflict("La cámara " + device.code() + " está en mantenimiento");
            }
            targetDevice = device.id();
        }
        LocalDateTime now = SqlUtils.now();
        long id = repository.insertCommand(site.id(), targetDevice, scenario, user.id(), now);
        repository.setScenario(site.id(), scenario.name(), now);
        auditService.log(user.id(), "ESCENARIO_EJECUTADO", "SIMULATION", id,
                scenario.label() + " en " + site.code());
        return response(id);
    }

    private CommandResponse response(long commandId) {
        CommandView view = repository.findCommandView(commandId).orElseThrow();
        boolean online = dataSourceOnline();
        String message = online
                ? "Orden registrada. El simulador la ejecutará en unos segundos."
                : "Orden registrada, pero el simulador no está conectado. Si no se conecta en 2 minutos, la orden expirará.";
        return new CommandResponse(view, online, message);
    }

    // ============================================================
    // Canal de control (lo consulta el simulador)
    // ============================================================

    /**
     * Inventario, estado de simulacion y ordenes pendientes.
     * Las ordenes entregadas pasan a ENVIADO.
     */
    @Transactional
    public SyncResponse sync() {
        LocalDateTime now = SqlUtils.now();
        repository.expirePendingBefore(now.minusSeconds(MonitoringRules.COMMAND_EXPIRY_SECONDS));
        repository.failUnconfirmedBefore(now.minusSeconds(MonitoringRules.COMMAND_CONFIRM_SECONDS));

        Map<Long, SimulationState> states = repository.findStates().stream()
                .collect(Collectors.toMap(SimulationState::siteId, Function.identity()));
        Map<Long, SiteLiveStatus> live = liveRepository.findAll().stream()
                .collect(Collectors.toMap(SiteLiveStatus::siteId, Function.identity()));
        Map<Long, List<Device>> devicesBySite = deviceRepository.findAll().stream()
                .collect(Collectors.groupingBy(Device::siteId));

        List<SyncSite> sites = siteRepository.findAll().stream().map(site -> {
            SimulationState state = states.get(site.id());
            SiteLiveStatus status = live.get(site.id());
            LastKnown lastKnown = status == null ? null
                    : new LastKnown(status.batteryPercent(), status.solarEnergyToday(), status.deviceTime());
            List<SyncDevice> devices = devicesBySite.getOrDefault(site.id(), List.of()).stream()
                    .map(d -> new SyncDevice(d.code(), d.type(), d.name(), d.status()))
                    .toList();
            return new SyncSite(site.code(), site.name(), state == null || state.enabled(),
                    state == null ? 1 : state.speed(), lastKnown, devices);
        }).toList();

        List<SyncCommand> commands = repository.findPendingViews().stream()
                .map(c -> new SyncCommand(c.id(), c.siteCode(), c.deviceCode(), c.command(), c.createdAt()))
                .toList();
        commands.forEach(c -> repository.markSent(c.id(), now));
        return new SyncResponse(now, sites, commands);
    }

    @Transactional
    public void acknowledge(long commandId, CommandAckRequest request) {
        SimulationCommand command = repository.findCommand(commandId)
                .orElseThrow(() -> ApiException.notFound("La orden " + commandId + " no existe"));
        if (command.status() == SimulationCommand.Status.EJECUTADO) {
            return;
        }
        SimulationCommand.Status status = request.success()
                ? SimulationCommand.Status.EJECUTADO : SimulationCommand.Status.ERROR;
        repository.markResult(commandId, status, request.message(), SqlUtils.now());
    }
}

package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.DeviceDtos.CameraCreateRequest;
import com.novatech.monitoring.dto.DeviceDtos.DeviceUpdateRequest;
import com.novatech.monitoring.dto.DeviceDtos.DeviceView;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.Site;
import com.novatech.monitoring.repository.CameraRepository;
import com.novatech.monitoring.repository.DeviceRepository;
import com.novatech.monitoring.repository.SiteRepository;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.security.AuthenticatedUser;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;

/** Administracion de dispositivos: inventario, alta de camaras y mantenimiento. */
@Service
public class DeviceService {

    public static final Set<String> SCENES = Set.of("acceso", "perimetro", "materiales", "vehicular", "grua", "maquinaria");

    private final DeviceRepository deviceRepository;
    private final CameraRepository cameraRepository;
    private final SiteRepository siteRepository;
    private final EventService eventService;
    private final AlertService alertService;
    private final AuditService auditService;

    public DeviceService(DeviceRepository deviceRepository, CameraRepository cameraRepository,
                         SiteRepository siteRepository, EventService eventService, AlertService alertService,
                         AuditService auditService) {
        this.deviceRepository = deviceRepository;
        this.cameraRepository = cameraRepository;
        this.siteRepository = siteRepository;
        this.eventService = eventService;
        this.alertService = alertService;
        this.auditService = auditService;
    }

    public List<DeviceView> list(Long siteId) {
        return deviceRepository.findViews(siteId);
    }

    /** Agrega una camara a una obra (maximo 4 por obra). */
    @Transactional
    public DeviceView createCamera(CameraCreateRequest request, AuthenticatedUser user) {
        Site site = siteRepository.findById(request.siteId())
                .orElseThrow(() -> ApiException.notFound("La obra " + request.siteId() + " no existe"));
        if (deviceRepository.countCameras(site.id()) >= MonitoringRules.MAX_CAMERAS) {
            throw ApiException.conflict("La obra " + site.code() + " ya tiene el máximo de "
                    + MonitoringRules.MAX_CAMERAS + " cámaras");
        }
        String scene = checkScene(request.scene() == null ? "acceso" : request.scene());
        String code = String.format("CAM-%03d", deviceRepository.maxCameraNumber() + 1);
        LocalDateTime now = SqlUtils.now();
        long id = deviceRepository.insert(site.id(), code, request.name().trim(), Device.Type.CAMERA,
                Device.Status.ONLINE, true, null, now);
        cameraRepository.insert(id, request.position().trim(),
                request.resolution() == null ? "1920x1080" : request.resolution(), 25, true, true, 0, scene);
        auditService.log(user.id(), "DISPOSITIVO_CREADO", "DEVICE", id, code + " en " + site.code());
        return view(id);
    }

    /**
     * Edita nombre y datos de camara. El estado solo se cambia en camaras y solo
     * para poner o quitar el mantenimiento (el resto lo informa la telemetria).
     */
    @Transactional
    public DeviceView update(long id, DeviceUpdateRequest request, AuthenticatedUser user) {
        Device device = deviceRepository.findById(id)
                .orElseThrow(() -> ApiException.notFound("El dispositivo " + id + " no existe"));
        LocalDateTime now = SqlUtils.now();

        if (request.name() != null) {
            deviceRepository.updateName(id, request.name().trim());
        }
        if (device.type() == Device.Type.CAMERA) {
            String scene = request.scene() == null ? null : checkScene(request.scene());
            cameraRepository.updateInfo(id, request.position() == null ? null : request.position().trim(),
                    request.resolution(), scene);
        } else if (request.position() != null || request.resolution() != null || request.scene() != null) {
            throw ApiException.badRequest("Ubicación, resolución y escena solo aplican a cámaras");
        }

        String statusChange = "";
        if (request.status() != null && request.status() != device.status()) {
            if (device.type() != Device.Type.CAMERA) {
                throw ApiException.badRequest("Solo se puede poner en mantenimiento una cámara");
            }
            if (request.status() == Device.Status.MANTENIMIENTO) {
                deviceRepository.updateStatus(id, Device.Status.MANTENIMIENTO, null);
                cameraRepository.updateLive(id, 0, 0, false, false, null);
                eventService.record(device.siteId(), id, EventType.DEVICE_MAINTENANCE,
                        "Cámara " + device.code() + " en mantenimiento programado", now);
                alertService.autoResolve(device.siteId(), id, Alert.Type.CAMERA_OFFLINE,
                        "cámara en mantenimiento programado", now);
            } else if (request.status() == Device.Status.ONLINE && device.status() == Device.Status.MANTENIMIENTO) {
                deviceRepository.updateStatus(id, Device.Status.ONLINE, now);
                eventService.record(device.siteId(), id, EventType.SYSTEM_RESTORED,
                        "Cámara " + device.code() + " operativa tras mantenimiento", now);
            } else {
                throw ApiException.badRequest("Solo se puede poner o quitar el mantenimiento; "
                        + "los demás estados los informa la propia cámara");
            }
            statusChange = ", estado " + device.status() + " → " + request.status();
        }
        auditService.log(user.id(), "DISPOSITIVO_ACTUALIZADO", "DEVICE", id, device.code() + statusChange);
        return view(id);
    }

    private DeviceView view(long id) {
        Device device = deviceRepository.findById(id).orElseThrow();
        return deviceRepository.findViews(device.siteId()).stream()
                .filter(v -> v.id().equals(id)).findFirst().orElseThrow();
    }

    private static String checkScene(String scene) {
        if (!SCENES.contains(scene)) {
            throw ApiException.badRequest("Escena desconocida. Opciones: " + String.join(", ", SCENES));
        }
        return scene;
    }
}

package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.DeviceDtos.CameraView;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.repository.CameraRepository;
import com.novatech.monitoring.repository.SqlUtils;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/** Vista de camaras para el CCTV (secciones 20 y 21). */
@Service
public class CameraService {

    private final CameraRepository repository;

    public CameraService(CameraRepository repository) {
        this.repository = repository;
    }

    /**
     * Camaras con su estado en vivo. El movimiento se considera vigente solo si
     * la ultima deteccion es reciente, asi no queda "pegado" si se apaga el simulador.
     */
    public List<CameraView> list(Long siteId) {
        LocalDateTime now = SqlUtils.now();
        return repository.findViews(siteId).stream().map(c -> {
            boolean motion = c.status() == Device.Status.ONLINE && c.motionActive()
                    && !MonitoringRules.isOlderThan(c.lastMotionAt(), now, MonitoringRules.MOTION_VISIBLE_SECONDS);
            return new CameraView(c.deviceId(), c.siteId(), c.siteCode(), c.siteName(), c.code(), c.name(),
                    c.position(), c.resolution(), c.status(), c.fps(), c.signal(), c.motionDetection(), c.recording(),
                    motion, c.lastMotionAt(), c.lastSeen(), c.scene(), c.simulated(), c.intrusionActive(),
                    c.lastEventType(), c.lastEventAt(), c.lastEventDescription(), c.deviceTime(),
                    c.deviceTimeReceivedAt(), c.speed(), c.running());
        }).toList();
    }
}

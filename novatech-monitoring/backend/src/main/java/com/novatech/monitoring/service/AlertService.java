package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.AlertDtos.AlertView;
import com.novatech.monitoring.dto.PageResponse;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.GeneralState;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.repository.AlertRepository;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.security.AuthenticatedUser;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * Alertas (secciones 29 y 30).
 *
 * - Alertas de condicion (camara, bateria, Starlink, conectividad, panel): como
 *   maximo una activa por condicion; el sistema la resuelve solo cuando la
 *   condicion desaparece.
 * - Alertas de intrusion: una nueva por cada evento; solo una persona las resuelve.
 */
@Service
public class AlertService {

    private final AlertRepository repository;
    private final AuditService auditService;

    public AlertService(AlertRepository repository, AuditService auditService) {
        this.repository = repository;
        this.auditService = auditService;
    }

    // ---------------- Creacion y resolucion automatica (las usa IngestService) ----------------

    /** Crea la alerta de una condicion si no hay otra activa igual. Devuelve el id si la creo. */
    public Optional<Long> raiseCondition(long siteId, Long deviceId, Long eventId, Alert.Type type, String title,
                                         String description, LocalDateTime when) {
        if (!repository.findActive(siteId, deviceId, type).isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(repository.insert(siteId, deviceId, eventId, type, when,
                MonitoringRules.alertSeverity(type), Alert.Status.NUEVA, title, description));
    }

    /** Crea una alerta de intrusion (siempre nueva). */
    public long createIntrusion(long siteId, Long deviceId, long eventId, Severity severity, String title,
                                String description, LocalDateTime when) {
        return repository.insert(siteId, deviceId, eventId, Alert.Type.INTRUSION, when, severity,
                Alert.Status.NUEVA, title, description);
    }

    /** Resuelve las alertas activas de una condicion que ya desaparecio. Devuelve cuantas resolvio. */
    public int autoResolve(long siteId, Long deviceId, Alert.Type type, String reason, LocalDateTime when) {
        List<Alert> active = repository.findActive(siteId, deviceId, type);
        active.forEach(a -> repository.resolve(a.id(), null, when, "Resuelta automáticamente: " + reason));
        return active.size();
    }

    // ---------------- Acciones de los usuarios ----------------

    @Transactional
    public AlertView acknowledge(long id, AuthenticatedUser user) {
        Alert alert = get(id);
        if (alert.status() != Alert.Status.NUEVA) {
            throw ApiException.conflict("Solo se pueden reconocer alertas en estado NUEVA (estado actual: "
                    + alert.status() + ")");
        }
        repository.acknowledge(id, user.id(), SqlUtils.now());
        auditService.log(user.id(), "ALERTA_RECONOCIDA", "ALERT", id, alert.title());
        return view(id);
    }

    @Transactional
    public AlertView resolve(long id, String note, AuthenticatedUser user) {
        Alert alert = get(id);
        if (alert.status() == Alert.Status.RESUELTA) {
            throw ApiException.conflict("La alerta ya está resuelta");
        }
        String cleanNote = note == null || note.isBlank() ? "Resuelta por " + user.name() : note.trim();
        repository.resolve(id, user.id(), SqlUtils.now(), cleanNote);
        auditService.log(user.id(), "ALERTA_RESUELTA", "ALERT", id, alert.title() + " | " + cleanNote);
        return view(id);
    }

    /** La alerta pasa a EN_ATENCION al crearse su incidencia. */
    public void markInAttention(long id, Long responsibleId, AuthenticatedUser user) {
        repository.setInAttention(id, responsibleId, user.id(), SqlUtils.now());
    }

    /** Al resolverse una incidencia se resuelve su alerta (si seguia activa). */
    public void resolveFromIncident(long id, String incidentCode, AuthenticatedUser user) {
        Alert alert = get(id);
        if (alert.status() != Alert.Status.RESUELTA) {
            repository.resolve(id, user.id(), SqlUtils.now(), "Resuelta con la incidencia " + incidentCode);
            auditService.log(user.id(), "ALERTA_RESUELTA", "ALERT", id, alert.title() + " | incidencia " + incidentCode);
        }
    }

    public void updateResponsible(long id, Long responsibleId) {
        repository.updateResponsible(id, responsibleId);
    }

    // ---------------- Consultas ----------------

    public Alert get(long id) {
        return repository.findById(id).orElseThrow(() -> ApiException.notFound("La alerta " + id + " no existe"));
    }

    public AlertView view(long id) {
        return repository.findView(id).orElseThrow(() -> ApiException.notFound("La alerta " + id + " no existe"));
    }

    public PageResponse<AlertView> find(Long siteId, String status, Severity severity, Integer page, Integer size) {
        if (status != null && !status.equals(AlertRepository.ACTIVE_FILTER)) {
            try {
                Alert.Status.valueOf(status);
            } catch (IllegalArgumentException e) {
                throw ApiException.badRequest("Estado de alerta desconocido: " + status);
            }
        }
        return repository.findPage(siteId, status, severity, SqlUtils.page(page), SqlUtils.pageSize(size));
    }

    /** Severidades de las alertas activas agrupadas por obra. */
    public Map<Long, List<Severity>> activeSeveritiesBySite() {
        return repository.activeSeverities().stream().collect(Collectors.groupingBy(
                AlertRepository.SiteSeverity::siteId,
                Collectors.mapping(AlertRepository.SiteSeverity::severity, Collectors.toList())));
    }

    public GeneralState generalStateOf(long siteId) {
        return MonitoringRules.generalState(activeSeveritiesBySite().getOrDefault(siteId, List.of()));
    }
}

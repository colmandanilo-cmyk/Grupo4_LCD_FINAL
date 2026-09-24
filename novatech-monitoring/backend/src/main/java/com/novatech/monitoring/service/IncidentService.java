package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.IncidentDtos.IncidentCreateRequest;
import com.novatech.monitoring.dto.IncidentDtos.IncidentStatusRequest;
import com.novatech.monitoring.dto.IncidentDtos.IncidentUpdateRequest;
import com.novatech.monitoring.dto.IncidentDtos.IncidentView;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.Incident;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.model.User;
import com.novatech.monitoring.repository.IncidentRepository;
import com.novatech.monitoring.repository.SiteRepository;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.repository.UserRepository;
import com.novatech.monitoring.security.AuthenticatedUser;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Objects;

/** Incidencias (seccion 31). Una alerta puede convertirse en una incidencia. */
@Service
public class IncidentService {

    private static final DateTimeFormatter NOTE_TIME = DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm");

    private final IncidentRepository repository;
    private final SiteRepository siteRepository;
    private final UserRepository userRepository;
    private final AlertService alertService;
    private final AuditService auditService;

    public IncidentService(IncidentRepository repository, SiteRepository siteRepository,
                           UserRepository userRepository, AlertService alertService, AuditService auditService) {
        this.repository = repository;
        this.siteRepository = siteRepository;
        this.userRepository = userRepository;
        this.alertService = alertService;
        this.auditService = auditService;
    }

    public List<IncidentView> list(Long siteId, Incident.Status status, Severity priority) {
        return repository.findAll(siteId, status, priority);
    }

    public IncidentView view(long id) {
        return repository.findView(id).orElseThrow(() -> ApiException.notFound("La incidencia " + id + " no existe"));
    }

    /** Crea una incidencia desde una alerta (alertId) o manual (siteId). */
    @Transactional
    public IncidentView create(IncidentCreateRequest request, AuthenticatedUser user) {
        Alert alert = null;
        long siteId;
        if (request.alertId() != null) {
            alert = alertService.get(request.alertId());
            if (alert.status() == Alert.Status.RESUELTA) {
                throw ApiException.conflict("La alerta ya está resuelta; no se puede crear una incidencia desde ella");
            }
            if (repository.existsByAlert(alert.id())) {
                throw ApiException.conflict("La alerta ya tiene una incidencia asociada");
            }
            if (request.siteId() != null && !request.siteId().equals(alert.siteId())) {
                throw ApiException.badRequest("La alerta pertenece a otra obra");
            }
            siteId = alert.siteId();
        } else {
            if (request.siteId() == null) {
                throw ApiException.badRequest("Indique la obra o la alerta de origen");
            }
            siteId = siteRepository.findById(request.siteId())
                    .orElseThrow(() -> ApiException.notFound("La obra " + request.siteId() + " no existe")).id();
        }

        Severity priority = request.priority() != null ? request.priority()
                : alert != null ? MonitoringRules.incidentPriorityFor(alert.severity()) : Severity.MEDIA;
        if (priority == Severity.INFO) {
            throw ApiException.badRequest("La prioridad debe ser BAJA, MEDIA, ALTA o CRITICA");
        }
        Long assignedTo = request.assignedToId() != null ? activeUser(request.assignedToId()).id() : user.id();

        LocalDateTime now = SqlUtils.now();
        int year = now.getYear();
        String code = String.format("INC-%d-%04d", year, repository.maxSequence(year) + 1);
        long id = repository.insert(new Incident(null, siteId, alert == null ? null : alert.id(), code,
                request.title().trim(), request.description().trim(), priority, Incident.Status.ABIERTA, assignedTo,
                user.id(), now, now, null, null, null));
        if (alert != null) {
            alertService.markInAttention(alert.id(), assignedTo, user);
        }
        auditService.log(user.id(), "INCIDENCIA_CREADA", "INCIDENT", id,
                code + (alert != null ? " desde la alerta " + alert.id() : " (manual)") + ": " + request.title().trim());
        return view(id);
    }

    @Transactional
    public IncidentView update(long id, IncidentUpdateRequest request, AuthenticatedUser user) {
        Incident incident = get(id);
        if (incident.status() == Incident.Status.CERRADA) {
            throw ApiException.conflict("Una incidencia cerrada no se puede modificar");
        }
        if (request.priority() == Severity.INFO) {
            throw ApiException.badRequest("La prioridad debe ser BAJA, MEDIA, ALTA o CRITICA");
        }
        Long assignedTo = request.assignedToId() != null ? activeUser(request.assignedToId()).id() : incident.assignedTo();
        Incident updated = new Incident(incident.id(), incident.siteId(), incident.alertId(), incident.code(),
                request.title() != null ? request.title().trim() : incident.title(),
                request.description() != null ? request.description().trim() : incident.description(),
                request.priority() != null ? request.priority() : incident.priority(),
                incident.status(), assignedTo, incident.createdBy(), incident.createdAt(), SqlUtils.now(),
                incident.resolvedAt(), incident.closedAt(),
                request.observations() != null ? request.observations() : incident.observations());
        repository.update(updated);
        if (incident.alertId() != null && !Objects.equals(assignedTo, incident.assignedTo())) {
            alertService.updateResponsible(incident.alertId(), assignedTo);
        }
        auditService.log(user.id(), "INCIDENCIA_ACTUALIZADA", "INCIDENT", id, incident.code() + ": datos editados");
        return view(id);
    }

    /** Cambia el estado respetando las transiciones permitidas en MonitoringRules. */
    @Transactional
    public IncidentView changeStatus(long id, IncidentStatusRequest request, AuthenticatedUser user) {
        Incident incident = get(id);
        Incident.Status target = request.status();
        if (!MonitoringRules.incidentTransitionAllowed(incident.status(), target)) {
            throw ApiException.conflict("No se puede pasar una incidencia de " + incident.status() + " a " + target);
        }
        LocalDateTime now = SqlUtils.now();
        LocalDateTime resolvedAt = incident.resolvedAt();
        LocalDateTime closedAt = incident.closedAt();
        if (target == Incident.Status.RESUELTA) {
            resolvedAt = now;
        } else if (target == Incident.Status.EN_PROCESO) {
            resolvedAt = null;
        } else if (target == Incident.Status.CERRADA) {
            closedAt = now;
        }

        String line = "[" + now.format(NOTE_TIME) + "] " + user.name() + ": " + incident.status() + " → " + target
                + (request.observation() == null || request.observation().isBlank() ? "" : ". " + request.observation().trim());
        String observations = incident.observations() == null || incident.observations().isBlank()
                ? line : incident.observations() + "\n" + line;

        repository.update(new Incident(incident.id(), incident.siteId(), incident.alertId(), incident.code(),
                incident.title(), incident.description(), incident.priority(), target, incident.assignedTo(),
                incident.createdBy(), incident.createdAt(), now, resolvedAt, closedAt, observations));

        if (target == Incident.Status.RESUELTA && incident.alertId() != null) {
            alertService.resolveFromIncident(incident.alertId(), incident.code(), user);
        }
        auditService.log(user.id(), target == Incident.Status.CERRADA ? "INCIDENCIA_CERRADA" : "INCIDENCIA_ACTUALIZADA",
                "INCIDENT", id, incident.code() + ": " + incident.status() + " → " + target);
        return view(id);
    }

    private Incident get(long id) {
        return repository.findById(id).orElseThrow(() -> ApiException.notFound("La incidencia " + id + " no existe"));
    }

    private User activeUser(long id) {
        return userRepository.findById(id).filter(User::active)
                .orElseThrow(() -> ApiException.badRequest("El responsable elegido no existe o está desactivado"));
    }
}

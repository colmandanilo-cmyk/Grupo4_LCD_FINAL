package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.IncidentDtos.IncidentCreateRequest;
import com.novatech.monitoring.dto.IncidentDtos.IncidentStatusRequest;
import com.novatech.monitoring.dto.IncidentDtos.IncidentUpdateRequest;
import com.novatech.monitoring.dto.IncidentDtos.IncidentView;
import com.novatech.monitoring.model.Incident;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.security.AuthenticatedUser;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.IncidentService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** /api/incidents: gestion de incidencias (administrador y supervisor). */
@RestController
@RequestMapping("/api/incidents")
@PreAuthorize(Roles.ADMIN_O_SUPERVISOR)
public class IncidentController {

    private final IncidentService incidentService;

    public IncidentController(IncidentService incidentService) {
        this.incidentService = incidentService;
    }

    @GetMapping
    public List<IncidentView> list(@RequestParam(required = false) Long siteId,
                                   @RequestParam(required = false) Incident.Status status,
                                   @RequestParam(required = false) Severity priority) {
        return incidentService.list(siteId, status, priority);
    }

    @GetMapping("/{id}")
    public IncidentView get(@PathVariable long id) {
        return incidentService.view(id);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public IncidentView create(@Valid @RequestBody IncidentCreateRequest request,
                               @AuthenticationPrincipal AuthenticatedUser user) {
        return incidentService.create(request, user);
    }

    @PutMapping("/{id}")
    public IncidentView update(@PathVariable long id, @Valid @RequestBody IncidentUpdateRequest request,
                               @AuthenticationPrincipal AuthenticatedUser user) {
        return incidentService.update(id, request, user);
    }

    @PutMapping("/{id}/status")
    public IncidentView changeStatus(@PathVariable long id, @Valid @RequestBody IncidentStatusRequest request,
                                     @AuthenticationPrincipal AuthenticatedUser user) {
        return incidentService.changeStatus(id, request, user);
    }
}

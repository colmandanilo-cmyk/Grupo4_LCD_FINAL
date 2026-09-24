package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.AlertDtos.AlertView;
import com.novatech.monitoring.dto.AlertDtos.ResolveRequest;
import com.novatech.monitoring.dto.PageResponse;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.security.AuthenticatedUser;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.AlertService;
import jakarta.validation.Valid;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** /api/alerts: consulta y gestion de alertas. */
@RestController
@RequestMapping("/api/alerts")
public class AlertController {

    private final AlertService alertService;

    public AlertController(AlertService alertService) {
        this.alertService = alertService;
    }

    /** status: NUEVA, RECONOCIDA, EN_ATENCION, RESUELTA o ACTIVAS (todas las no resueltas). */
    @GetMapping
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public PageResponse<AlertView> list(@RequestParam(required = false) Long siteId,
                                        @RequestParam(required = false) String status,
                                        @RequestParam(required = false) Severity severity,
                                        @RequestParam(required = false) Integer page,
                                        @RequestParam(required = false) Integer size) {
        return alertService.find(siteId, status, severity, page, size);
    }

    @GetMapping("/{id}")
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public AlertView get(@PathVariable long id) {
        return alertService.view(id);
    }

    /** Reconocer: cualquier rol, incluido el operador. */
    @PutMapping("/{id}/acknowledge")
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public AlertView acknowledge(@PathVariable long id, @AuthenticationPrincipal AuthenticatedUser user) {
        return alertService.acknowledge(id, user);
    }

    /** Resolver: administrador o supervisor. */
    @PutMapping("/{id}/resolve")
    @PreAuthorize(Roles.ADMIN_O_SUPERVISOR)
    public AlertView resolve(@PathVariable long id, @Valid @RequestBody(required = false) ResolveRequest request,
                             @AuthenticationPrincipal AuthenticatedUser user) {
        return alertService.resolve(id, request == null ? null : request.note(), user);
    }
}

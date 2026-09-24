package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.SiteDtos.SiteDetail;
import com.novatech.monitoring.dto.SiteDtos.SiteRequest;
import com.novatech.monitoring.dto.SiteDtos.SiteSummary;
import com.novatech.monitoring.model.Site;
import com.novatech.monitoring.security.AuthenticatedUser;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.SiteService;
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

/** /api/sites: obras monitoreadas y centro de control. */
@RestController
@RequestMapping("/api/sites")
public class SiteController {

    private final SiteService siteService;

    public SiteController(SiteService siteService) {
        this.siteService = siteService;
    }

    /** Lista con filtro por estado (ACTIVA, MANTENIMIENTO, SIN_CONEXION) y busqueda libre. */
    @GetMapping
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public List<SiteSummary> list(@RequestParam(required = false) Site.Status status,
                                  @RequestParam(required = false) String q) {
        return siteService.list(status, q);
    }

    @GetMapping("/{id}")
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public SiteDetail detail(@PathVariable long id) {
        return siteService.detail(id);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize(Roles.ADMIN)
    public SiteDetail create(@Valid @RequestBody SiteRequest request, @AuthenticationPrincipal AuthenticatedUser user) {
        return siteService.create(request, user);
    }

    @PutMapping("/{id}")
    @PreAuthorize(Roles.ADMIN)
    public SiteDetail update(@PathVariable long id, @Valid @RequestBody SiteRequest request,
                             @AuthenticationPrincipal AuthenticatedUser user) {
        return siteService.update(id, request, user);
    }
}

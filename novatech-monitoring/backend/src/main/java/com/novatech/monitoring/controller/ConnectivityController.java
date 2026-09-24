package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.MonitoringDtos.ConnectivityOverview;
import com.novatech.monitoring.dto.MonitoringDtos.ConnectivityPoint;
import com.novatech.monitoring.dto.MonitoringDtos.ConnectivityView;
import com.novatech.monitoring.dto.MonitoringDtos.EventView;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.ConnectivityService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** /api/connectivity: Starlink, 4G y contingencias (valores simulados). */
@RestController
@RequestMapping("/api/connectivity")
public class ConnectivityController {

    private final ConnectivityService connectivityService;

    public ConnectivityController(ConnectivityService connectivityService) {
        this.connectivityService = connectivityService;
    }

    @GetMapping
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public ConnectivityOverview overview() {
        return connectivityService.overview();
    }

    @GetMapping("/sites/{siteId}")
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public ConnectivityView site(@PathVariable long siteId) {
        return connectivityService.site(siteId);
    }

    @GetMapping("/sites/{siteId}/history")
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public List<ConnectivityPoint> history(@PathVariable long siteId, @RequestParam(required = false) Integer hours) {
        return connectivityService.history(siteId, hours);
    }

    /** Linea de tiempo: "Conexion Starlink perdida", "Activando respaldo 4G", ... */
    @GetMapping("/sites/{siteId}/timeline")
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public List<EventView> timeline(@PathVariable long siteId, @RequestParam(required = false) Integer limit) {
        return connectivityService.timeline(siteId, limit);
    }
}

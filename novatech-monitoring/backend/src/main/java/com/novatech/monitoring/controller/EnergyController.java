package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.MonitoringDtos.EnergyPoint;
import com.novatech.monitoring.dto.MonitoringDtos.EnergyView;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.EnergyService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** /api/energy: panel solar, bateria y consumo (valores simulados). */
@RestController
@RequestMapping("/api/energy")
public class EnergyController {

    private final EnergyService energyService;

    public EnergyController(EnergyService energyService) {
        this.energyService = energyService;
    }

    @GetMapping
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public List<EnergyView> overview() {
        return energyService.overview();
    }

    @GetMapping("/sites/{siteId}")
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public EnergyView site(@PathVariable long siteId) {
        return energyService.site(siteId);
    }

    @GetMapping("/sites/{siteId}/history")
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public List<EnergyPoint> history(@PathVariable long siteId, @RequestParam(required = false) Integer hours) {
        return energyService.history(siteId, hours);
    }
}

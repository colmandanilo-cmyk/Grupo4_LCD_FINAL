package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.DashboardDtos.Status;
import com.novatech.monitoring.dto.DashboardDtos.Summary;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.DashboardService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** /api/dashboard: KPIs, graficos y estado para la cabecera. */
@RestController
@RequestMapping("/api/dashboard")
@PreAuthorize(Roles.CUALQUIER_ROL)
public class DashboardController {

    private final DashboardService dashboardService;

    public DashboardController(DashboardService dashboardService) {
        this.dashboardService = dashboardService;
    }

    @GetMapping("/summary")
    public Summary summary() {
        return dashboardService.summary();
    }

    @GetMapping("/status")
    public Status status() {
        return dashboardService.status();
    }
}

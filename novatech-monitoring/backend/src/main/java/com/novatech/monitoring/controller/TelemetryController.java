package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.MonitoringDtos.TelemetryMetric;
import com.novatech.monitoring.dto.MonitoringDtos.TelemetryRow;
import com.novatech.monitoring.dto.MonitoringDtos.TelemetrySeries;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.TelemetryService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** /api/telemetry: series y ultimos registros de telemetria. */
@RestController
@RequestMapping("/api/telemetry")
public class TelemetryController {

    private final TelemetryService telemetryService;

    public TelemetryController(TelemetryService telemetryService) {
        this.telemetryService = telemetryService;
    }

    /** Serie de una metrica de un dispositivo. */
    @GetMapping
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public TelemetrySeries series(@RequestParam long deviceId, @RequestParam String metric,
                                  @RequestParam(required = false) Integer hours) {
        return telemetryService.series(deviceId, metric, hours);
    }

    @GetMapping("/latest")
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public List<TelemetryRow> latest(@RequestParam long siteId, @RequestParam(required = false) Integer limit) {
        return telemetryService.latest(siteId, limit);
    }

    @GetMapping("/metrics")
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public List<TelemetryMetric> metrics(@RequestParam long siteId) {
        return telemetryService.metrics(siteId);
    }
}

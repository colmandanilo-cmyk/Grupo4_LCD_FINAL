package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.ReportDtos.ReportResult;
import com.novatech.monitoring.security.AuthenticatedUser;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.AuditService;
import com.novatech.monitoring.service.ReportService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;

/** /api/reports/{tipo}: availability, alerts, energy, connectivity, incidents. */
@RestController
@RequestMapping("/api/reports")
@PreAuthorize(Roles.ADMIN_O_SUPERVISOR)
public class ReportController {

    private final ReportService reportService;
    private final AuditService auditService;

    public ReportController(ReportService reportService, AuditService auditService) {
        this.reportService = reportService;
        this.auditService = auditService;
    }

    @GetMapping("/{type}")
    public ReportResult report(
            @PathVariable String type,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime to) {
        return reportService.generate(type, from, to);
    }

    /** El mismo reporte como archivo CSV. */
    @GetMapping("/{type}/csv")
    public ResponseEntity<byte[]> csv(
            @PathVariable String type,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime to,
            @AuthenticationPrincipal AuthenticatedUser user) {
        ReportResult report = reportService.generate(type, from, to);
        String fileName = reportService.csvFileName(type);
        auditService.log(user.id(), "REPORTE_EXPORTADO", "REPORT", null, report.title() + " (" + fileName + ")");
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + fileName + "\"")
                .contentType(new MediaType("text", "csv", java.nio.charset.StandardCharsets.UTF_8))
                .body(reportService.toCsv(report));
    }
}

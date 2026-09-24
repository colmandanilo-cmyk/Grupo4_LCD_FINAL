package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.ConfigDtos.AuditView;
import com.novatech.monitoring.dto.PageResponse;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.AuditService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.List;

/** /api/audit: REGISTRO DE AUDITORIA (solo administrador). */
@RestController
@RequestMapping("/api/audit")
@PreAuthorize(Roles.ADMIN)
public class AuditController {

    private final AuditService auditService;

    public AuditController(AuditService auditService) {
        this.auditService = auditService;
    }

    @GetMapping
    public PageResponse<AuditView> list(
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) String action,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime to,
            @RequestParam(required = false) Integer page,
            @RequestParam(required = false) Integer size) {
        return auditService.find(userId, action, from, to, page, size);
    }

    /** Acciones registradas (para el filtro de la pantalla). */
    @GetMapping("/actions")
    public List<String> actions() {
        return auditService.actions();
    }
}

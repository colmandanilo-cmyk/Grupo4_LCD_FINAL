package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.ConfigDtos.ConfigEntry;
import com.novatech.monitoring.dto.ConfigDtos.ConfigUpdateRequest;
import com.novatech.monitoring.security.AuthenticatedUser;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.ConfigService;
import jakarta.validation.Valid;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** /api/config: parametros del sistema (lectura para todos, cambios solo administrador). */
@RestController
@RequestMapping("/api/config")
public class ConfigController {

    private final ConfigService configService;

    public ConfigController(ConfigService configService) {
        this.configService = configService;
    }

    @GetMapping
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public List<ConfigEntry> list() {
        return configService.findAll();
    }

    @PutMapping
    @PreAuthorize(Roles.ADMIN)
    public List<ConfigEntry> update(@Valid @RequestBody ConfigUpdateRequest request,
                                    @AuthenticationPrincipal AuthenticatedUser user) {
        return configService.update(request.values(), user);
    }
}

package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.DeviceDtos.CameraCreateRequest;
import com.novatech.monitoring.dto.DeviceDtos.DeviceUpdateRequest;
import com.novatech.monitoring.dto.DeviceDtos.DeviceView;
import com.novatech.monitoring.security.AuthenticatedUser;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.DeviceService;
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

/** /api/devices: inventario y administracion de dispositivos. */
@RestController
@RequestMapping("/api/devices")
public class DeviceController {

    private final DeviceService deviceService;

    public DeviceController(DeviceService deviceService) {
        this.deviceService = deviceService;
    }

    @GetMapping
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public List<DeviceView> list(@RequestParam(required = false) Long siteId) {
        return deviceService.list(siteId);
    }

    /** Agrega una camara a una obra. */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize(Roles.ADMIN)
    public DeviceView create(@Valid @RequestBody CameraCreateRequest request,
                             @AuthenticationPrincipal AuthenticatedUser user) {
        return deviceService.createCamera(request, user);
    }

    @PutMapping("/{id}")
    @PreAuthorize(Roles.ADMIN)
    public DeviceView update(@PathVariable long id, @Valid @RequestBody DeviceUpdateRequest request,
                             @AuthenticationPrincipal AuthenticatedUser user) {
        return deviceService.update(id, request, user);
    }
}

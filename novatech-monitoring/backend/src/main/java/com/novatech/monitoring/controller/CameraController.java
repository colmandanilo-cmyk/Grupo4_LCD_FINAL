package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.DeviceDtos.CameraView;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.CameraService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** /api/cameras: camaras con su estado en vivo (vista CCTV). */
@RestController
@RequestMapping("/api/cameras")
public class CameraController {

    private final CameraService cameraService;

    public CameraController(CameraService cameraService) {
        this.cameraService = cameraService;
    }

    @GetMapping
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public List<CameraView> list(@RequestParam(required = false) Long siteId) {
        return cameraService.list(siteId);
    }
}

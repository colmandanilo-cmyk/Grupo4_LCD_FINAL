package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.SimulationDtos.CommandResponse;
import com.novatech.monitoring.dto.SimulationDtos.ScenarioRequest;
import com.novatech.monitoring.dto.SimulationDtos.SimulationStatus;
import com.novatech.monitoring.dto.SimulationDtos.SpeedRequest;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.Scenario;
import com.novatech.monitoring.security.AuthenticatedUser;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.SimulationService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * /api/simulation: LABORATORIO DE SIMULACION (solo administrador, seccion 41).
 *
 * POST /start, /pause, /reset, /speed controlan el reloj de la simulacion.
 * POST /{escenario} (intrusion, starlink-failure, ...) registra una orden para el simulador.
 */
@RestController
@RequestMapping("/api/simulation")
@PreAuthorize(Roles.ADMIN)
public class SimulationController {

    private final SimulationService simulationService;

    public SimulationController(SimulationService simulationService) {
        this.simulationService = simulationService;
    }

    @GetMapping("/status")
    public SimulationStatus status() {
        return simulationService.status();
    }

    @PostMapping("/start")
    public SimulationStatus start(@AuthenticationPrincipal AuthenticatedUser user) {
        return simulationService.resume(user);
    }

    @PostMapping("/pause")
    public SimulationStatus pause(@AuthenticationPrincipal AuthenticatedUser user) {
        return simulationService.pause(user);
    }

    @PostMapping("/speed")
    public SimulationStatus speed(@Valid @RequestBody SpeedRequest request, @AuthenticationPrincipal AuthenticatedUser user) {
        return simulationService.speed(request.speed(), user);
    }

    @PostMapping("/reset")
    public ResponseEntity<CommandResponse> reset(@AuthenticationPrincipal AuthenticatedUser user) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(simulationService.reset(user));
    }

    /** Escenarios: restore-normal, motion, intrusion, camera-failure, camera-restore, starlink-failure, ... */
    @PostMapping("/{scenario}")
    public ResponseEntity<CommandResponse> scenario(@PathVariable String scenario,
                                                    @Valid @RequestBody ScenarioRequest request,
                                                    @AuthenticationPrincipal AuthenticatedUser user) {
        Scenario selected = Scenario.fromPath(scenario)
                .orElseThrow(() -> ApiException.notFound("Escenario desconocido: " + scenario));
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(simulationService.scenario(selected, request.siteId(), request.deviceId(), user));
    }
}

package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.IngestDtos.CommandAckRequest;
import com.novatech.monitoring.dto.IngestDtos.DeviceEventRequest;
import com.novatech.monitoring.dto.IngestDtos.DeviceEventResponse;
import com.novatech.monitoring.dto.IngestDtos.SyncResponse;
import com.novatech.monitoring.dto.IngestDtos.TelemetryRequest;
import com.novatech.monitoring.dto.IngestDtos.TelemetryResponse;
import com.novatech.monitoring.service.IngestService;
import com.novatech.monitoring.service.SimulationService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * /api/ingest: canal de los dispositivos (hoy el simulador Python; manana equipos reales).
 * Requiere la cabecera X-Device-Key (ver SecurityConfig y DeviceKeyFilter).
 */
@RestController
@RequestMapping("/api/ingest")
public class IngestController {

    private final IngestService ingestService;
    private final SimulationService simulationService;

    public IngestController(IngestService ingestService, SimulationService simulationService) {
        this.ingestService = ingestService;
        this.simulationService = simulationService;
    }

    /** Lectura completa de una estacion (camaras, energia, conectividad). */
    @PostMapping("/telemetry")
    public TelemetryResponse telemetry(@Valid @RequestBody TelemetryRequest request) {
        simulationService.recordContact();
        return ingestService.processTelemetry(request);
    }

    /** Evento puntual: movimiento o intrusion. */
    @PostMapping("/events")
    @ResponseStatus(HttpStatus.CREATED)
    public DeviceEventResponse event(@Valid @RequestBody DeviceEventRequest request) {
        simulationService.recordContact();
        return ingestService.processDeviceEvent(request);
    }

    /** Inventario, estado de la simulacion y ordenes pendientes. */
    @GetMapping("/sync")
    public SyncResponse sync() {
        simulationService.recordContact();
        return simulationService.sync();
    }

    @PostMapping("/commands/{id}/ack")
    public ResponseEntity<Void> ack(@PathVariable long id, @Valid @RequestBody CommandAckRequest request) {
        simulationService.recordContact();
        simulationService.acknowledge(id, request);
        return ResponseEntity.noContent().build();
    }
}

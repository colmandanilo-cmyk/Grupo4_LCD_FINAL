package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.MonitoringDtos.EventView;
import com.novatech.monitoring.dto.PageResponse;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.EventService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;

/** /api/events: historial de eventos. */
@RestController
@RequestMapping("/api/events")
public class EventController {

    private final EventService eventService;

    public EventController(EventService eventService) {
        this.eventService = eventService;
    }

    @GetMapping
    @PreAuthorize(Roles.CUALQUIER_ROL)
    public PageResponse<EventView> list(
            @RequestParam(required = false) Long siteId,
            @RequestParam(required = false) EventType type,
            @RequestParam(required = false) Severity severity,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime to,
            @RequestParam(required = false) Integer page,
            @RequestParam(required = false) Integer size) {
        return eventService.find(siteId, type, severity, from, to, page, size);
    }
}

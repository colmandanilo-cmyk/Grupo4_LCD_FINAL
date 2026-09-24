package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.MonitoringDtos.EventView;
import com.novatech.monitoring.dto.PageResponse;
import com.novatech.monitoring.model.Event;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.repository.EventRepository;
import com.novatech.monitoring.repository.SqlUtils;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;

/** Registro y consulta del historial de eventos (seccion 27). */
@Service
public class EventService {

    private final EventRepository repository;

    public EventService(EventRepository repository) {
        this.repository = repository;
    }

    /** Registra un evento con la severidad que indica MonitoringRules. */
    public Event record(long siteId, Long deviceId, EventType type, String description, LocalDateTime when) {
        return repository.insert(siteId, deviceId, when, type, MonitoringRules.eventSeverity(type), description);
    }

    /** Registra un evento con una severidad calculada aparte (intrusion). */
    public Event record(long siteId, Long deviceId, EventType type, Severity severity, String description,
                        LocalDateTime when) {
        return repository.insert(siteId, deviceId, when, type, severity, description);
    }

    public PageResponse<EventView> find(Long siteId, EventType type, Severity severity, LocalDateTime from,
                                        LocalDateTime to, Integer page, Integer size) {
        return repository.findPage(siteId, type, severity, from, to, SqlUtils.page(page), SqlUtils.pageSize(size));
    }

    public List<EventView> recent(Long siteId, Collection<EventType> types, int limit) {
        return repository.findRecent(siteId, types, limit);
    }
}

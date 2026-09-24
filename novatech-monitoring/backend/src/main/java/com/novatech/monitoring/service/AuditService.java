package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.ConfigDtos.AuditView;
import com.novatech.monitoring.dto.PageResponse;
import com.novatech.monitoring.repository.AuditLogRepository;
import com.novatech.monitoring.repository.SqlUtils;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/** Registro de auditoria de acciones importantes (seccion 44). */
@Service
public class AuditService {

    private final AuditLogRepository repository;

    public AuditService(AuditLogRepository repository) {
        this.repository = repository;
    }

    /** Registra una accion. userId null = accion del sistema o intento de login sin usuario. */
    public void log(Long userId, String action, String entity, Long entityId, String details) {
        repository.insert(userId, action, entity, entityId, details, SqlUtils.now());
    }

    public PageResponse<AuditView> find(Long userId, String action, LocalDateTime from, LocalDateTime to,
                                        Integer page, Integer size) {
        return repository.findPage(userId, action, from, to, SqlUtils.page(page), SqlUtils.pageSize(size));
    }

    public List<String> actions() {
        return repository.distinctActions();
    }
}

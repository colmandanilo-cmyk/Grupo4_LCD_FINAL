package com.novatech.monitoring.controller;

import com.novatech.monitoring.repository.SqlUtils;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** /api/health: indica si el backend y la base de datos responden (lo usan los scripts y el simulador). */
@RestController
public class HealthController {

    private final JdbcTemplate jdbc;

    public HealthController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping("/api/health")
    public Map<String, Object> health() {
        Integer sites = jdbc.queryForObject("SELECT COUNT(*) FROM sites", Integer.class);
        return Map.of("status", "UP", "application", "NOVA TECH", "sites", sites == null ? 0 : sites,
                "serverTime", SqlUtils.now());
    }
}

package com.novatech.monitoring.repository;

import com.novatech.monitoring.dto.ConfigDtos.ConfigEntry;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de system_config (parametros de la pantalla Configuracion). */
@Repository
public class ConfigRepository {

    private final JdbcTemplate jdbc;

    public ConfigRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<ConfigEntry> findAll() {
        return jdbc.query("""
                        SELECT c.key, c.value, c.description, c.updated_at, u.name AS user_name
                        FROM system_config c LEFT JOIN users u ON u.id = c.updated_by
                        ORDER BY c.key
                        """,
                (rs, n) -> new ConfigEntry(rs.getString("key"), rs.getString("value"), rs.getString("description"),
                        getDateTime(rs, "updated_at"), rs.getString("user_name")));
    }

    /** Crea el parametro si no existe (no pisa un valor ya guardado). */
    public void insertIfMissing(String key, String value, String description, LocalDateTime when) {
        jdbc.update("INSERT OR IGNORE INTO system_config (key, value, description, updated_at) VALUES (?, ?, ?, ?)",
                key, value, description, ts(when));
    }

    public void updateValue(String key, String value, Long userId, LocalDateTime when) {
        jdbc.update("UPDATE system_config SET value = ?, updated_by = ?, updated_at = ? WHERE key = ?",
                value, userId, ts(when), key);
    }
}

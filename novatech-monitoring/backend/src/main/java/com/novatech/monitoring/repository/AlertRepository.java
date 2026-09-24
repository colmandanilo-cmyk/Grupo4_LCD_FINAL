package com.novatech.monitoring.repository;

import com.novatech.monitoring.dto.AlertDtos.AlertView;
import com.novatech.monitoring.dto.PageResponse;
import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.Severity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de la tabla alerts. "Activa" = cualquier estado distinto de RESUELTA. */
@Repository
public class AlertRepository {

    /** Filtro especial de estado: todas las alertas no resueltas. */
    public static final String ACTIVE_FILTER = "ACTIVAS";

    private static final String VIEW_SELECT = """
            SELECT a.*, s.code AS site_code, s.name AS site_name, d.code AS device_code, d.name AS device_name,
                   ur.name AS responsible_name, ua.name AS ack_name, uv.name AS resolved_name,
                   i.id AS incident_id, i.code AS incident_code
            FROM alerts a
            JOIN sites s ON s.id = a.site_id
            LEFT JOIN devices d ON d.id = a.device_id
            LEFT JOIN users ur ON ur.id = a.responsible_id
            LEFT JOIN users ua ON ua.id = a.acknowledged_by
            LEFT JOIN users uv ON uv.id = a.resolved_by
            LEFT JOIN incidents i ON i.alert_id = a.id
            """;

    private static final RowMapper<Alert> MAPPER = (rs, n) -> new Alert(
            rs.getLong("id"),
            rs.getLong("site_id"),
            getLong(rs, "device_id"),
            getLong(rs, "event_id"),
            getEnum(rs, "alert_type", Alert.Type.class),
            getDateTime(rs, "created_at"),
            getEnum(rs, "severity", Severity.class),
            getEnum(rs, "status", Alert.Status.class),
            rs.getString("title"),
            rs.getString("description"),
            getLong(rs, "responsible_id"),
            getLong(rs, "acknowledged_by"),
            getDateTime(rs, "acknowledged_at"),
            getLong(rs, "resolved_by"),
            getDateTime(rs, "resolved_at"),
            rs.getString("resolution_note"));

    private static final RowMapper<AlertView> VIEW_MAPPER = (rs, n) -> new AlertView(
            rs.getLong("id"),
            rs.getLong("site_id"),
            rs.getString("site_code"),
            rs.getString("site_name"),
            getLong(rs, "device_id"),
            rs.getString("device_code"),
            rs.getString("device_name"),
            getLong(rs, "event_id"),
            getEnum(rs, "alert_type", Alert.Type.class),
            getDateTime(rs, "created_at"),
            getEnum(rs, "severity", Severity.class),
            getEnum(rs, "status", Alert.Status.class),
            rs.getString("title"),
            rs.getString("description"),
            getLong(rs, "responsible_id"),
            rs.getString("responsible_name"),
            rs.getString("ack_name"),
            getDateTime(rs, "acknowledged_at"),
            rs.getString("resolved_name"),
            getDateTime(rs, "resolved_at"),
            rs.getString("resolution_note"),
            getLong(rs, "incident_id"),
            rs.getString("incident_code"));

    /** Severidad de una alerta activa y la obra a la que pertenece. */
    public record SiteSeverity(long siteId, Severity severity) {
    }

    private final JdbcTemplate jdbc;

    public AlertRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public long insert(long siteId, Long deviceId, Long eventId, Alert.Type type, LocalDateTime createdAt,
                       Severity severity, Alert.Status status, String title, String description) {
        return jdbc.queryForObject("INSERT INTO alerts (site_id, device_id, event_id, alert_type, created_at, severity, "
                        + "status, title, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                Long.class, siteId, deviceId, eventId, type.name(), ts(createdAt), severity.name(), status.name(),
                title, description);
    }

    public Optional<Alert> findById(long id) {
        return jdbc.query("SELECT * FROM alerts WHERE id = ?", MAPPER, id).stream().findFirst();
    }

    public Optional<AlertView> findView(long id) {
        return jdbc.query(VIEW_SELECT + " WHERE a.id = ?", VIEW_MAPPER, id).stream().findFirst();
    }

    /**
     * Alertas paginadas. status puede ser un estado o "ACTIVAS".
     * Primero las no resueltas, luego por fecha descendente.
     */
    public PageResponse<AlertView> findPage(Long siteId, String status, Severity severity, int page, int size) {
        StringBuilder where = new StringBuilder(" WHERE 1 = 1");
        List<Object> args = new ArrayList<>();
        if (siteId != null) {
            where.append(" AND a.site_id = ?");
            args.add(siteId);
        }
        if (ACTIVE_FILTER.equals(status)) {
            where.append(" AND a.status <> 'RESUELTA'");
        } else if (status != null) {
            where.append(" AND a.status = ?");
            args.add(status);
        }
        if (severity != null) {
            where.append(" AND a.severity = ?");
            args.add(severity.name());
        }
        Long total = jdbc.queryForObject("SELECT COUNT(*) FROM alerts a" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(size);
        pageArgs.add(page * size);
        List<AlertView> items = jdbc.query(VIEW_SELECT + where
                        + " ORDER BY CASE WHEN a.status = 'RESUELTA' THEN 1 ELSE 0 END, a.created_at DESC, a.id DESC "
                        + "LIMIT ? OFFSET ?",
                VIEW_MAPPER, pageArgs.toArray());
        return new PageResponse<>(items, page, size, total == null ? 0 : total);
    }

    /** Alertas activas de una condicion (obra + dispositivo + tipo). deviceId null = alerta de la obra. */
    public List<Alert> findActive(long siteId, Long deviceId, Alert.Type type) {
        if (deviceId == null) {
            return jdbc.query("SELECT * FROM alerts WHERE site_id = ? AND device_id IS NULL AND alert_type = ? "
                    + "AND status <> 'RESUELTA'", MAPPER, siteId, type.name());
        }
        return jdbc.query("SELECT * FROM alerts WHERE site_id = ? AND device_id = ? AND alert_type = ? "
                + "AND status <> 'RESUELTA'", MAPPER, siteId, deviceId, type.name());
    }

    public List<SiteSeverity> activeSeverities() {
        return jdbc.query("SELECT site_id, severity FROM alerts WHERE status <> 'RESUELTA'",
                (rs, n) -> new SiteSeverity(rs.getLong("site_id"), getEnum(rs, "severity", Severity.class)));
    }

    public List<AlertView> findLatest(int limit) {
        return jdbc.query(VIEW_SELECT + " ORDER BY a.created_at DESC, a.id DESC LIMIT ?", VIEW_MAPPER, limit);
    }

    public Optional<AlertView> findLatestActive() {
        return jdbc.query(VIEW_SELECT + " WHERE a.status <> 'RESUELTA' ORDER BY a.created_at DESC, a.id DESC LIMIT 1",
                VIEW_MAPPER).stream().findFirst();
    }

    public int countActive() {
        Integer total = jdbc.queryForObject("SELECT COUNT(*) FROM alerts WHERE status <> 'RESUELTA'", Integer.class);
        return total == null ? 0 : total;
    }

    public int countByStatus(Alert.Status status) {
        Integer total = jdbc.queryForObject("SELECT COUNT(*) FROM alerts WHERE status = ?", Integer.class, status.name());
        return total == null ? 0 : total;
    }

    /** Alertas creadas en un periodo (para graficos y reportes). */
    public List<AlertView> findCreatedBetween(LocalDateTime from, LocalDateTime to) {
        return jdbc.query(VIEW_SELECT + " WHERE a.created_at BETWEEN ? AND ? ORDER BY a.created_at",
                VIEW_MAPPER, ts(from), ts(to));
    }

    public void acknowledge(long id, long userId, LocalDateTime when) {
        jdbc.update("UPDATE alerts SET status = 'RECONOCIDA', acknowledged_by = ?, acknowledged_at = ?, "
                + "responsible_id = COALESCE(responsible_id, ?) WHERE id = ?", userId, ts(when), userId, id);
    }

    /** La alerta pasa a EN_ATENCION porque se creo una incidencia. */
    public void setInAttention(long id, Long responsibleId, long actingUserId, LocalDateTime when) {
        jdbc.update("UPDATE alerts SET status = 'EN_ATENCION', responsible_id = ?, "
                        + "acknowledged_by = COALESCE(acknowledged_by, ?), acknowledged_at = COALESCE(acknowledged_at, ?) "
                        + "WHERE id = ?",
                responsibleId, actingUserId, ts(when), id);
    }

    /** Resuelve la alerta. userId null = la resolvio el sistema automaticamente. */
    public void resolve(long id, Long userId, LocalDateTime when, String note) {
        jdbc.update("UPDATE alerts SET status = 'RESUELTA', resolved_by = ?, resolved_at = ?, resolution_note = ? "
                + "WHERE id = ?", userId, ts(when), note, id);
    }

    public void updateResponsible(long id, Long responsibleId) {
        jdbc.update("UPDATE alerts SET responsible_id = ? WHERE id = ?", responsibleId, id);
    }
}

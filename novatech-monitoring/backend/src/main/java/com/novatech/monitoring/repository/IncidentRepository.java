package com.novatech.monitoring.repository;

import com.novatech.monitoring.dto.IncidentDtos.IncidentView;
import com.novatech.monitoring.model.Incident;
import com.novatech.monitoring.model.Severity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de la tabla incidents. */
@Repository
public class IncidentRepository {

    private static final String VIEW_SELECT = """
            SELECT i.*, s.code AS site_code, s.name AS site_name, a.title AS alert_title,
                   ua.name AS assigned_name, uc.name AS created_name
            FROM incidents i
            JOIN sites s ON s.id = i.site_id
            LEFT JOIN alerts a ON a.id = i.alert_id
            LEFT JOIN users ua ON ua.id = i.assigned_to
            LEFT JOIN users uc ON uc.id = i.created_by
            """;

    private static final RowMapper<Incident> MAPPER = (rs, n) -> new Incident(
            rs.getLong("id"),
            rs.getLong("site_id"),
            getLong(rs, "alert_id"),
            rs.getString("code"),
            rs.getString("title"),
            rs.getString("description"),
            getEnum(rs, "priority", Severity.class),
            getEnum(rs, "status", Incident.Status.class),
            getLong(rs, "assigned_to"),
            getLong(rs, "created_by"),
            getDateTime(rs, "created_at"),
            getDateTime(rs, "updated_at"),
            getDateTime(rs, "resolved_at"),
            getDateTime(rs, "closed_at"),
            rs.getString("observations"));

    private static final RowMapper<IncidentView> VIEW_MAPPER = (rs, n) -> new IncidentView(
            rs.getLong("id"),
            rs.getLong("site_id"),
            rs.getString("site_code"),
            rs.getString("site_name"),
            getLong(rs, "alert_id"),
            rs.getString("alert_title"),
            rs.getString("code"),
            rs.getString("title"),
            rs.getString("description"),
            getEnum(rs, "priority", Severity.class),
            getEnum(rs, "status", Incident.Status.class),
            getLong(rs, "assigned_to"),
            rs.getString("assigned_name"),
            getLong(rs, "created_by"),
            rs.getString("created_name"),
            getDateTime(rs, "created_at"),
            getDateTime(rs, "updated_at"),
            getDateTime(rs, "resolved_at"),
            getDateTime(rs, "closed_at"),
            rs.getString("observations"));

    private final JdbcTemplate jdbc;

    public IncidentRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public long insert(Incident i) {
        return jdbc.queryForObject("""
                        INSERT INTO incidents (site_id, alert_id, code, title, description, priority, status, assigned_to,
                                               created_by, created_at, updated_at, resolved_at, closed_at, observations)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
                        """,
                Long.class, i.siteId(), i.alertId(), i.code(), i.title(), i.description(), i.priority().name(),
                i.status().name(), i.assignedTo(), i.createdBy(), ts(i.createdAt()), ts(i.updatedAt()),
                ts(i.resolvedAt()), ts(i.closedAt()), i.observations());
    }

    /** Guarda todos los campos editables de la incidencia. */
    public void update(Incident i) {
        jdbc.update("""
                        UPDATE incidents SET title = ?, description = ?, priority = ?, status = ?, assigned_to = ?,
                               updated_at = ?, resolved_at = ?, closed_at = ?, observations = ?
                        WHERE id = ?
                        """,
                i.title(), i.description(), i.priority().name(), i.status().name(), i.assignedTo(),
                ts(i.updatedAt()), ts(i.resolvedAt()), ts(i.closedAt()), i.observations(), i.id());
    }

    public Optional<Incident> findById(long id) {
        return jdbc.query("SELECT * FROM incidents WHERE id = ?", MAPPER, id).stream().findFirst();
    }

    public Optional<IncidentView> findView(long id) {
        return jdbc.query(VIEW_SELECT + " WHERE i.id = ?", VIEW_MAPPER, id).stream().findFirst();
    }

    public List<IncidentView> findAll(Long siteId, Incident.Status status, Severity priority) {
        StringBuilder sql = new StringBuilder(VIEW_SELECT).append(" WHERE 1 = 1");
        List<Object> args = new ArrayList<>();
        if (siteId != null) {
            sql.append(" AND i.site_id = ?");
            args.add(siteId);
        }
        if (status != null) {
            sql.append(" AND i.status = ?");
            args.add(status.name());
        }
        if (priority != null) {
            sql.append(" AND i.priority = ?");
            args.add(priority.name());
        }
        sql.append(" ORDER BY CASE i.status WHEN 'ABIERTA' THEN 0 WHEN 'EN_PROCESO' THEN 1 WHEN 'RESUELTA' THEN 2 "
                + "ELSE 3 END, i.created_at DESC");
        return jdbc.query(sql.toString(), VIEW_MAPPER, args.toArray());
    }

    public List<IncidentView> findCreatedBetween(LocalDateTime from, LocalDateTime to) {
        return jdbc.query(VIEW_SELECT + " WHERE i.created_at BETWEEN ? AND ? ORDER BY i.created_at",
                VIEW_MAPPER, ts(from), ts(to));
    }

    public boolean existsByAlert(long alertId) {
        Integer total = jdbc.queryForObject("SELECT COUNT(*) FROM incidents WHERE alert_id = ?", Integer.class, alertId);
        return total != null && total > 0;
    }

    /** Mayor correlativo usado en un ano (INC-2026-0007 -> 7). */
    public int maxSequence(int year) {
        Integer max = jdbc.queryForObject("SELECT COALESCE(MAX(CAST(substr(code, 10) AS INTEGER)), 0) "
                + "FROM incidents WHERE code LIKE ?", Integer.class, "INC-" + year + "-%");
        return max == null ? 0 : max;
    }

    public int countOpen(Long siteId) {
        String sql = "SELECT COUNT(*) FROM incidents WHERE status IN ('ABIERTA','EN_PROCESO')";
        Integer total = siteId == null
                ? jdbc.queryForObject(sql, Integer.class)
                : jdbc.queryForObject(sql + " AND site_id = ?", Integer.class, siteId);
        return total == null ? 0 : total;
    }

    public int countOpenCritical() {
        Integer total = jdbc.queryForObject("SELECT COUNT(*) FROM incidents WHERE priority = 'CRITICA' "
                + "AND status IN ('ABIERTA','EN_PROCESO')", Integer.class);
        return total == null ? 0 : total;
    }
}

package com.novatech.monitoring.repository;

import com.novatech.monitoring.dto.MonitoringDtos.EventView;
import com.novatech.monitoring.dto.PageResponse;
import com.novatech.monitoring.model.Event;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.Severity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de la tabla events. */
@Repository
public class EventRepository {

    private static final String VIEW_SELECT = """
            SELECT e.*, s.code AS site_code, s.name AS site_name, d.code AS device_code, d.name AS device_name
            FROM events e
            JOIN sites s ON s.id = e.site_id
            LEFT JOIN devices d ON d.id = e.device_id
            """;

    private static final RowMapper<EventView> VIEW_MAPPER = (rs, n) -> new EventView(
            rs.getLong("id"),
            rs.getLong("site_id"),
            rs.getString("site_code"),
            rs.getString("site_name"),
            getLong(rs, "device_id"),
            rs.getString("device_code"),
            rs.getString("device_name"),
            getDateTime(rs, "timestamp"),
            getEnum(rs, "event_type", EventType.class),
            getEnum(rs, "severity", Severity.class),
            rs.getString("description"));

    private final JdbcTemplate jdbc;

    public EventRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Event insert(long siteId, Long deviceId, LocalDateTime timestamp, EventType type, Severity severity,
                        String description) {
        Long id = jdbc.queryForObject("INSERT INTO events (site_id, device_id, timestamp, event_type, severity, "
                        + "description) VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
                Long.class, siteId, deviceId, ts(timestamp), type.name(), severity.name(), description);
        return new Event(id, siteId, deviceId, timestamp, type, severity, description);
    }

    /** Historial paginado con filtros opcionales (null = sin filtro). */
    public PageResponse<EventView> findPage(Long siteId, EventType type, Severity severity, LocalDateTime from,
                                            LocalDateTime to, int page, int size) {
        StringBuilder where = new StringBuilder(" WHERE 1 = 1");
        List<Object> args = new ArrayList<>();
        if (siteId != null) {
            where.append(" AND e.site_id = ?");
            args.add(siteId);
        }
        if (type != null) {
            where.append(" AND e.event_type = ?");
            args.add(type.name());
        }
        if (severity != null) {
            where.append(" AND e.severity = ?");
            args.add(severity.name());
        }
        if (from != null) {
            where.append(" AND e.timestamp >= ?");
            args.add(ts(from));
        }
        if (to != null) {
            where.append(" AND e.timestamp <= ?");
            args.add(ts(to));
        }
        Long total = jdbc.queryForObject("SELECT COUNT(*) FROM events e" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(size);
        pageArgs.add(page * size);
        List<EventView> items = jdbc.query(VIEW_SELECT + where + " ORDER BY e.timestamp DESC, e.id DESC LIMIT ? OFFSET ?",
                VIEW_MAPPER, pageArgs.toArray());
        return new PageResponse<>(items, page, size, total == null ? 0 : total);
    }

    /** Ultimos eventos de ciertos tipos (siteId null = todas las obras). */
    public List<EventView> findRecent(Long siteId, Collection<EventType> types, int limit) {
        StringBuilder sql = new StringBuilder(VIEW_SELECT).append(" WHERE 1 = 1");
        List<Object> args = new ArrayList<>();
        if (siteId != null) {
            sql.append(" AND e.site_id = ?");
            args.add(siteId);
        }
        if (types != null && !types.isEmpty()) {
            sql.append(" AND e.event_type IN (").append(String.join(",", types.stream().map(t -> "?").toList())).append(")");
            types.forEach(t -> args.add(t.name()));
        }
        sql.append(" ORDER BY e.timestamp DESC, e.id DESC LIMIT ?");
        args.add(limit);
        return jdbc.query(sql.toString(), VIEW_MAPPER, args.toArray());
    }

    /** Cantidad de eventos de ciertos tipos por obra en un periodo (para reportes). */
    public long count(long siteId, Collection<EventType> types, LocalDateTime from, LocalDateTime to) {
        String in = String.join(",", types.stream().map(t -> "?").toList());
        List<Object> args = new ArrayList<>();
        args.add(siteId);
        types.forEach(t -> args.add(t.name()));
        args.add(ts(from));
        args.add(ts(to));
        Long total = jdbc.queryForObject("SELECT COUNT(*) FROM events WHERE site_id = ? AND event_type IN (" + in
                + ") AND timestamp BETWEEN ? AND ?", Long.class, args.toArray());
        return total == null ? 0 : total;
    }
}

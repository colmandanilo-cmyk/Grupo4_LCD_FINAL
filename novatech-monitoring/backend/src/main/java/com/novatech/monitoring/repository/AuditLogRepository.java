package com.novatech.monitoring.repository;

import com.novatech.monitoring.dto.ConfigDtos.AuditView;
import com.novatech.monitoring.dto.PageResponse;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de audit_log. */
@Repository
public class AuditLogRepository {

    private static final RowMapper<AuditView> VIEW_MAPPER = (rs, n) -> new AuditView(
            rs.getLong("id"),
            getLong(rs, "user_id"),
            rs.getString("user_name"),
            rs.getString("user_email"),
            rs.getString("action"),
            rs.getString("entity"),
            getLong(rs, "entity_id"),
            rs.getString("details"),
            getDateTime(rs, "timestamp"));

    private final JdbcTemplate jdbc;

    public AuditLogRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(Long userId, String action, String entity, Long entityId, String details, LocalDateTime when) {
        jdbc.update("INSERT INTO audit_log (user_id, action, entity, entity_id, details, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                userId, action, entity, entityId, details, ts(when));
    }

    public PageResponse<AuditView> findPage(Long userId, String action, LocalDateTime from, LocalDateTime to,
                                            int page, int size) {
        StringBuilder where = new StringBuilder(" WHERE 1 = 1");
        List<Object> args = new ArrayList<>();
        if (userId != null) {
            where.append(" AND l.user_id = ?");
            args.add(userId);
        }
        if (action != null && !action.isBlank()) {
            where.append(" AND l.action = ?");
            args.add(action);
        }
        if (from != null) {
            where.append(" AND l.timestamp >= ?");
            args.add(ts(from));
        }
        if (to != null) {
            where.append(" AND l.timestamp <= ?");
            args.add(ts(to));
        }
        Long total = jdbc.queryForObject("SELECT COUNT(*) FROM audit_log l" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(size);
        pageArgs.add(page * size);
        List<AuditView> items = jdbc.query("SELECT l.*, u.name AS user_name, u.email AS user_email "
                        + "FROM audit_log l LEFT JOIN users u ON u.id = l.user_id" + where
                        + " ORDER BY l.timestamp DESC, l.id DESC LIMIT ? OFFSET ?",
                VIEW_MAPPER, pageArgs.toArray());
        return new PageResponse<>(items, page, size, total == null ? 0 : total);
    }

    public List<String> distinctActions() {
        return jdbc.queryForList("SELECT DISTINCT action FROM audit_log ORDER BY action", String.class);
    }
}

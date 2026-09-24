package com.novatech.monitoring.repository;

import com.novatech.monitoring.dto.SimulationDtos.CommandView;
import com.novatech.monitoring.model.Scenario;
import com.novatech.monitoring.model.SimulationCommand;
import com.novatech.monitoring.model.SimulationState;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de simulation_state (una fila por obra) y simulation_commands (ordenes del laboratorio). */
@Repository
public class SimulationRepository {

    private static final String COMMAND_VIEW_SELECT = """
            SELECT c.*, s.code AS site_code, d.code AS device_code, u.name AS user_name
            FROM simulation_commands c
            LEFT JOIN sites s ON s.id = c.site_id
            LEFT JOIN devices d ON d.id = c.device_id
            LEFT JOIN users u ON u.id = c.created_by
            """;

    private static final RowMapper<SimulationState> STATE_MAPPER = (rs, n) -> new SimulationState(
            rs.getLong("id"),
            rs.getLong("site_id"),
            getBool(rs, "enabled"),
            rs.getInt("speed"),
            rs.getString("scenario"),
            getDateTime(rs, "updated_at"));

    private static final RowMapper<SimulationCommand> COMMAND_MAPPER = (rs, n) -> new SimulationCommand(
            rs.getLong("id"),
            getLong(rs, "site_id"),
            getLong(rs, "device_id"),
            getEnum(rs, "command", Scenario.class),
            getEnum(rs, "status", SimulationCommand.Status.class),
            getLong(rs, "created_by"),
            getDateTime(rs, "created_at"),
            getDateTime(rs, "sent_at"),
            getDateTime(rs, "executed_at"),
            rs.getString("result"));

    private static final RowMapper<CommandView> COMMAND_VIEW_MAPPER = (rs, n) -> {
        Scenario command = getEnum(rs, "command", Scenario.class);
        return new CommandView(
                rs.getLong("id"),
                getLong(rs, "site_id"),
                rs.getString("site_code"),
                getLong(rs, "device_id"),
                rs.getString("device_code"),
                command,
                command == null ? null : command.label(),
                getEnum(rs, "status", SimulationCommand.Status.class),
                rs.getString("user_name"),
                getDateTime(rs, "created_at"),
                getDateTime(rs, "sent_at"),
                getDateTime(rs, "executed_at"),
                rs.getString("result"));
    };

    private final JdbcTemplate jdbc;

    public SimulationRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // ---------------- Estado por obra ----------------

    public List<SimulationState> findStates() {
        return jdbc.query("SELECT * FROM simulation_state ORDER BY site_id", STATE_MAPPER);
    }

    public Optional<SimulationState> findState(long siteId) {
        return jdbc.query("SELECT * FROM simulation_state WHERE site_id = ?", STATE_MAPPER, siteId).stream().findFirst();
    }

    public void insertState(long siteId, boolean enabled, int speed, String scenario, LocalDateTime when) {
        jdbc.update("INSERT INTO simulation_state (site_id, enabled, speed, scenario, updated_at) VALUES (?, ?, ?, ?, ?)",
                siteId, bool(enabled), speed, scenario, ts(when));
    }

    public void setEnabledAll(boolean enabled, LocalDateTime when) {
        jdbc.update("UPDATE simulation_state SET enabled = ?, updated_at = ?", bool(enabled), ts(when));
    }

    public void setSpeedAll(int speed, LocalDateTime when) {
        jdbc.update("UPDATE simulation_state SET speed = ?, updated_at = ?", speed, ts(when));
    }

    public void resetAll(boolean enabled, int speed, LocalDateTime when) {
        jdbc.update("UPDATE simulation_state SET enabled = ?, speed = ?, scenario = 'NORMAL', updated_at = ?",
                bool(enabled), speed, ts(when));
    }

    public void setScenario(long siteId, String scenario, LocalDateTime when) {
        jdbc.update("UPDATE simulation_state SET scenario = ?, updated_at = ? WHERE site_id = ?",
                scenario, ts(when), siteId);
    }

    // ---------------- Ordenes ----------------

    public long insertCommand(Long siteId, Long deviceId, Scenario command, Long createdBy, LocalDateTime when) {
        return jdbc.queryForObject("INSERT INTO simulation_commands (site_id, device_id, command, status, created_by, "
                        + "created_at) VALUES (?, ?, ?, 'PENDIENTE', ?, ?) RETURNING id",
                Long.class, siteId, deviceId, command.name(), createdBy, ts(when));
    }

    public Optional<SimulationCommand> findCommand(long id) {
        return jdbc.query("SELECT * FROM simulation_commands WHERE id = ?", COMMAND_MAPPER, id).stream().findFirst();
    }

    public Optional<CommandView> findCommandView(long id) {
        return jdbc.query(COMMAND_VIEW_SELECT + " WHERE c.id = ?", COMMAND_VIEW_MAPPER, id).stream().findFirst();
    }

    public List<CommandView> findPendingViews() {
        return jdbc.query(COMMAND_VIEW_SELECT + " WHERE c.status = 'PENDIENTE' ORDER BY c.created_at, c.id",
                COMMAND_VIEW_MAPPER);
    }

    public List<CommandView> findRecentViews(int limit) {
        return jdbc.query(COMMAND_VIEW_SELECT + " ORDER BY c.created_at DESC, c.id DESC LIMIT ?",
                COMMAND_VIEW_MAPPER, limit);
    }

    public void markSent(long id, LocalDateTime when) {
        jdbc.update("UPDATE simulation_commands SET status = 'ENVIADO', sent_at = ? WHERE id = ?", ts(when), id);
    }

    public void markResult(long id, SimulationCommand.Status status, String result, LocalDateTime when) {
        jdbc.update("UPDATE simulation_commands SET status = ?, result = ?, executed_at = ? WHERE id = ?",
                status.name(), result, ts(when), id);
    }

    /** Ordenes pendientes creadas antes del limite pasan a EXPIRADO (nadie las recogio). */
    public int expirePendingBefore(LocalDateTime limit) {
        return jdbc.update("UPDATE simulation_commands SET status = 'EXPIRADO', "
                        + "result = 'El simulador no recogió la orden a tiempo' WHERE status = 'PENDIENTE' AND created_at < ?",
                ts(limit));
    }

    /** Ordenes enviadas que nunca se confirmaron pasan a ERROR. */
    public int failUnconfirmedBefore(LocalDateTime limit) {
        return jdbc.update("UPDATE simulation_commands SET status = 'ERROR', "
                        + "result = 'El simulador no confirmó la ejecución' WHERE status = 'ENVIADO' AND sent_at < ?",
                ts(limit));
    }
}

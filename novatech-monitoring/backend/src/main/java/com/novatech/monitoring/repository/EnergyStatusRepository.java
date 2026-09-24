package com.novatech.monitoring.repository;

import com.novatech.monitoring.model.EnergyStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL del historial energy_status. */
@Repository
public class EnergyStatusRepository {

    private static final String INSERT = "INSERT INTO energy_status (site_id, timestamp, battery_percent, "
            + "battery_voltage, solar_generation, consumption, estimated_autonomy) VALUES (?, ?, ?, ?, ?, ?, ?)";

    private final JdbcTemplate jdbc;

    private static final RowMapper<EnergyStatus> MAPPER = (rs, n) -> new EnergyStatus(
            rs.getLong("id"),
            rs.getLong("site_id"),
            getDateTime(rs, "timestamp"),
            rs.getDouble("battery_percent"),
            rs.getDouble("battery_voltage"),
            rs.getDouble("solar_generation"),
            rs.getDouble("consumption"),
            rs.getDouble("estimated_autonomy"));

    public EnergyStatusRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(EnergyStatus e) {
        jdbc.update(INSERT, args(e));
    }

    public void insertAll(List<EnergyStatus> rows) {
        jdbc.batchUpdate(INSERT, rows.stream().map(EnergyStatusRepository::args).toList());
    }

    /** Registros de una obra entre dos fechas, en orden cronologico. siteId null = todas. */
    public List<EnergyStatus> findBetween(Long siteId, LocalDateTime from, LocalDateTime to) {
        if (siteId == null) {
            return jdbc.query("SELECT * FROM energy_status WHERE timestamp BETWEEN ? AND ? ORDER BY site_id, timestamp",
                    MAPPER, ts(from), ts(to));
        }
        return jdbc.query("SELECT * FROM energy_status WHERE site_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp",
                MAPPER, siteId, ts(from), ts(to));
    }

    public int deleteBefore(LocalDateTime limit) {
        return jdbc.update("DELETE FROM energy_status WHERE timestamp < ?", ts(limit));
    }

    private static Object[] args(EnergyStatus e) {
        return new Object[]{e.siteId(), ts(e.timestamp()), e.batteryPercent(), e.batteryVoltage(),
                e.solarGeneration(), e.consumption(), e.estimatedAutonomy()};
    }
}

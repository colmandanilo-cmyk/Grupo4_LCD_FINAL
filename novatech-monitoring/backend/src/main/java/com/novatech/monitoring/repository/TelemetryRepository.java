package com.novatech.monitoring.repository;

import com.novatech.monitoring.dto.MonitoringDtos.TelemetryMetric;
import com.novatech.monitoring.dto.MonitoringDtos.TelemetryPoint;
import com.novatech.monitoring.dto.MonitoringDtos.TelemetryRow;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.TelemetryRecord;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de la tabla telemetry (metricas por dispositivo). */
@Repository
public class TelemetryRepository {

    private static final String INSERT = "INSERT INTO telemetry (site_id, device_id, timestamp, metric, value, unit) "
            + "VALUES (?, ?, ?, ?, ?, ?)";

    private final JdbcTemplate jdbc;

    public TelemetryRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insertAll(List<TelemetryRecord> rows) {
        if (rows.isEmpty()) {
            return;
        }
        jdbc.batchUpdate(INSERT, rows.stream()
                .map(r -> new Object[]{r.siteId(), r.deviceId(), ts(r.timestamp()), r.metric(), r.value(), r.unit()})
                .toList());
    }

    /** Valores de una metrica de un dispositivo entre dos fechas. */
    public List<TelemetryPoint> series(long deviceId, String metric, LocalDateTime from, LocalDateTime to) {
        return jdbc.query("SELECT timestamp, value FROM telemetry WHERE device_id = ? AND metric = ? "
                        + "AND timestamp BETWEEN ? AND ? ORDER BY timestamp",
                (rs, n) -> new TelemetryPoint(getDateTime(rs, "timestamp"), rs.getDouble("value")),
                deviceId, metric, ts(from), ts(to));
    }

    /** Ultimos registros de una obra (tabla de la pestana Telemetria). */
    public List<TelemetryRow> latest(long siteId, int limit) {
        return jdbc.query("""
                        SELECT t.timestamp, d.code, d.name, t.metric, t.value, t.unit
                        FROM telemetry t JOIN devices d ON d.id = t.device_id
                        WHERE t.site_id = ?
                        ORDER BY t.timestamp DESC, d.code, t.metric
                        LIMIT ?
                        """,
                (rs, n) -> new TelemetryRow(getDateTime(rs, "timestamp"), rs.getString("code"),
                        rs.getString("name"), rs.getString("metric"), rs.getDouble("value"), rs.getString("unit")),
                siteId, limit);
    }

    /** Combinaciones dispositivo + metrica que tienen datos en una obra. */
    public List<TelemetryMetric> metrics(long siteId, LocalDateTime since) {
        return jdbc.query("""
                        SELECT DISTINCT d.id, d.code, d.name, d.type, t.metric, t.unit
                        FROM telemetry t JOIN devices d ON d.id = t.device_id
                        WHERE t.site_id = ? AND t.timestamp >= ?
                        ORDER BY CASE d.type WHEN 'BATTERY' THEN 0 WHEN 'SOLAR_PANEL' THEN 1 WHEN 'STARLINK' THEN 2
                                 WHEN 'CELLULAR_4G' THEN 3 ELSE 4 END, d.code, t.metric
                        """,
                (rs, n) -> new TelemetryMetric(rs.getLong("id"), rs.getString("code"), rs.getString("name"),
                        getEnum(rs, "type", Device.Type.class), rs.getString("metric"), rs.getString("unit")),
                siteId, ts(since));
    }

    public int deleteBefore(LocalDateTime limit) {
        return jdbc.update("DELETE FROM telemetry WHERE timestamp < ?", ts(limit));
    }
}

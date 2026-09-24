package com.novatech.monitoring.repository;

import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.ConnectivityStatus;
import com.novatech.monitoring.model.Device;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL del historial connectivity_status. */
@Repository
public class ConnectivityStatusRepository {

    private static final String INSERT = "INSERT INTO connectivity_status (site_id, timestamp, starlink_status, "
            + "starlink_latency, starlink_download, starlink_upload, starlink_packet_loss, cellular_status, "
            + "cellular_signal, cellular_latency, cellular_download, cellular_upload, active_connection) "
            + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";

    private final JdbcTemplate jdbc;

    private static final RowMapper<ConnectivityStatus> MAPPER = (rs, n) -> new ConnectivityStatus(
            rs.getLong("id"),
            rs.getLong("site_id"),
            getDateTime(rs, "timestamp"),
            getEnum(rs, "starlink_status", Device.Status.class),
            getDouble(rs, "starlink_latency"),
            getDouble(rs, "starlink_download"),
            getDouble(rs, "starlink_upload"),
            getDouble(rs, "starlink_packet_loss"),
            getEnum(rs, "cellular_status", Device.Status.class),
            getInteger(rs, "cellular_signal"),
            getDouble(rs, "cellular_latency"),
            getDouble(rs, "cellular_download"),
            getDouble(rs, "cellular_upload"),
            getEnum(rs, "active_connection", ConnectionType.class));

    public ConnectivityStatusRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(ConnectivityStatus c) {
        jdbc.update(INSERT, args(c));
    }

    public void insertAll(List<ConnectivityStatus> rows) {
        jdbc.batchUpdate(INSERT, rows.stream().map(ConnectivityStatusRepository::args).toList());
    }

    /** Registros entre dos fechas en orden cronologico. siteId null = todas las obras. */
    public List<ConnectivityStatus> findBetween(Long siteId, LocalDateTime from, LocalDateTime to) {
        if (siteId == null) {
            return jdbc.query("SELECT * FROM connectivity_status WHERE timestamp BETWEEN ? AND ? "
                    + "ORDER BY site_id, timestamp", MAPPER, ts(from), ts(to));
        }
        return jdbc.query("SELECT * FROM connectivity_status WHERE site_id = ? AND timestamp BETWEEN ? AND ? "
                + "ORDER BY timestamp", MAPPER, siteId, ts(from), ts(to));
    }

    public int deleteBefore(LocalDateTime limit) {
        return jdbc.update("DELETE FROM connectivity_status WHERE timestamp < ?", ts(limit));
    }

    private static Object[] args(ConnectivityStatus c) {
        return new Object[]{c.siteId(), ts(c.timestamp()), name(c.starlinkStatus()), c.starlinkLatency(),
                c.starlinkDownload(), c.starlinkUpload(), c.starlinkPacketLoss(), name(c.cellularStatus()),
                c.cellularSignal(), c.cellularLatency(), c.cellularDownload(), c.cellularUpload(),
                name(c.activeConnection())};
    }
}

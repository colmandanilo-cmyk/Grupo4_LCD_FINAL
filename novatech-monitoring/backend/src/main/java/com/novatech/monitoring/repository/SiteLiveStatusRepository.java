package com.novatech.monitoring.repository;

import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.SiteLiveStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de site_live_status (estado actual de cada obra). */
@Repository
public class SiteLiveStatusRepository {

    private final JdbcTemplate jdbc;

    private static final RowMapper<SiteLiveStatus> MAPPER = (rs, n) -> new SiteLiveStatus(
            rs.getLong("site_id"),
            getDateTime(rs, "updated_at"),
            getDateTime(rs, "device_time"),
            getDouble(rs, "battery_percent"),
            getDouble(rs, "battery_voltage"),
            getEnum(rs, "battery_level", SiteLiveStatus.BatteryLevel.class),
            rs.getString("battery_trend"),
            getEnum(rs, "solar_status", Device.Status.class),
            getDouble(rs, "solar_rated_power"),
            getDouble(rs, "solar_generation"),
            getDouble(rs, "solar_energy_today"),
            getBool(rs, "low_generation"),
            getDouble(rs, "consumption"),
            getDouble(rs, "consumption_cameras"),
            getDouble(rs, "consumption_connectivity"),
            getDouble(rs, "consumption_control"),
            getDouble(rs, "estimated_autonomy"),
            getEnum(rs, "starlink_status", Device.Status.class),
            getDouble(rs, "starlink_latency"),
            getDouble(rs, "starlink_download"),
            getDouble(rs, "starlink_upload"),
            getDouble(rs, "starlink_packet_loss"),
            getDateTime(rs, "starlink_last_seen"),
            getEnum(rs, "cellular_status", Device.Status.class),
            getInteger(rs, "cellular_signal"),
            getDouble(rs, "cellular_latency"),
            getDouble(rs, "cellular_download"),
            getDouble(rs, "cellular_upload"),
            getDateTime(rs, "cellular_last_seen"),
            getEnum(rs, "active_connection", ConnectionType.class),
            getDateTime(rs, "last_history_at"));

    public SiteLiveStatusRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<SiteLiveStatus> find(long siteId) {
        return jdbc.query("SELECT * FROM site_live_status WHERE site_id = ?", MAPPER, siteId).stream().findFirst();
    }

    public List<SiteLiveStatus> findAll() {
        return jdbc.query("SELECT * FROM site_live_status", MAPPER);
    }

    /** Inserta o reemplaza la fila de la obra (hay una sola por obra). */
    public void save(SiteLiveStatus s) {
        jdbc.update("""
                        INSERT OR REPLACE INTO site_live_status (
                            site_id, updated_at, device_time, battery_percent, battery_voltage, battery_level,
                            battery_trend, solar_status, solar_rated_power, solar_generation, solar_energy_today,
                            low_generation, consumption, consumption_cameras, consumption_connectivity,
                            consumption_control, estimated_autonomy, starlink_status, starlink_latency,
                            starlink_download, starlink_upload, starlink_packet_loss, starlink_last_seen,
                            cellular_status, cellular_signal, cellular_latency, cellular_download, cellular_upload,
                            cellular_last_seen, active_connection, last_history_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                s.siteId(), ts(s.updatedAt()), ts(s.deviceTime()), s.batteryPercent(), s.batteryVoltage(),
                name(s.batteryLevel()), s.batteryTrend(), name(s.solarStatus()), s.solarRatedPower(),
                s.solarGeneration(), s.solarEnergyToday(), bool(s.lowGeneration()), s.consumption(),
                s.consumptionCameras(), s.consumptionConnectivity(), s.consumptionControl(), s.estimatedAutonomy(),
                name(s.starlinkStatus()), s.starlinkLatency(), s.starlinkDownload(), s.starlinkUpload(),
                s.starlinkPacketLoss(), ts(s.starlinkLastSeen()), name(s.cellularStatus()), s.cellularSignal(),
                s.cellularLatency(), s.cellularDownload(), s.cellularUpload(), ts(s.cellularLastSeen()),
                name(s.activeConnection()), ts(s.lastHistoryAt()));
    }
}

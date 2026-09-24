package com.novatech.monitoring.repository;

import com.novatech.monitoring.dto.DeviceDtos.DeviceView;
import com.novatech.monitoring.model.Device;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de la tabla devices. */
@Repository
public class DeviceRepository {

    private final JdbcTemplate jdbc;

    private static final RowMapper<Device> MAPPER = (rs, n) -> new Device(
            rs.getLong("id"),
            rs.getLong("site_id"),
            rs.getString("code"),
            rs.getString("name"),
            getEnum(rs, "type", Device.Type.class),
            getEnum(rs, "status", Device.Status.class),
            getBool(rs, "simulated"),
            getDateTime(rs, "last_seen"),
            getDateTime(rs, "created_at"));

    private static final RowMapper<DeviceView> VIEW_MAPPER = (rs, n) -> new DeviceView(
            rs.getLong("id"),
            rs.getLong("site_id"),
            rs.getString("site_code"),
            rs.getString("code"),
            rs.getString("name"),
            getEnum(rs, "type", Device.Type.class),
            getEnum(rs, "status", Device.Status.class),
            getBool(rs, "simulated"),
            getDateTime(rs, "last_seen"),
            rs.getString("position"),
            rs.getString("resolution"),
            rs.getString("scene"));

    public DeviceRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<Device> findAll() {
        return jdbc.query("SELECT * FROM devices ORDER BY site_id, id", MAPPER);
    }

    public List<Device> findBySite(long siteId) {
        return jdbc.query("SELECT * FROM devices WHERE site_id = ? ORDER BY id", MAPPER, siteId);
    }

    public Optional<Device> findById(long id) {
        return jdbc.query("SELECT * FROM devices WHERE id = ?", MAPPER, id).stream().findFirst();
    }

    public Optional<Device> findByCode(String code) {
        return jdbc.query("SELECT * FROM devices WHERE code = ?", MAPPER, code).stream().findFirst();
    }

    /** Inventario con datos de camara (si corresponde). siteId null = todas las obras. */
    public List<DeviceView> findViews(Long siteId) {
        StringBuilder sql = new StringBuilder("""
                SELECT d.*, s.code AS site_code, c.position, c.resolution, c.scene
                FROM devices d
                JOIN sites s ON s.id = d.site_id
                LEFT JOIN cameras c ON c.device_id = d.id
                """);
        List<Object> args = new ArrayList<>();
        if (siteId != null) {
            sql.append(" WHERE d.site_id = ?");
            args.add(siteId);
        }
        sql.append(" ORDER BY s.code, CASE d.type WHEN 'CAMERA' THEN 0 WHEN 'SOLAR_PANEL' THEN 1 "
                + "WHEN 'BATTERY' THEN 2 WHEN 'STARLINK' THEN 3 ELSE 4 END, d.code");
        return jdbc.query(sql.toString(), VIEW_MAPPER, args.toArray());
    }

    public long insert(long siteId, String code, String name, Device.Type type, Device.Status status,
                       boolean simulated, LocalDateTime lastSeen, LocalDateTime createdAt) {
        return jdbc.queryForObject(
                "INSERT INTO devices (site_id, code, name, type, status, simulated, last_seen, created_at) "
                        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                Long.class, siteId, code, name, type.name(), status.name(), bool(simulated), ts(lastSeen), ts(createdAt));
    }

    /** Cambia el estado. Si lastSeen es null se conserva la ultima comunicacion anterior. */
    public void updateStatus(long id, Device.Status status, LocalDateTime lastSeen) {
        jdbc.update("UPDATE devices SET status = ?, last_seen = COALESCE(?, last_seen) WHERE id = ?",
                status.name(), ts(lastSeen), id);
    }

    public void updateName(long id, String name) {
        jdbc.update("UPDATE devices SET name = ? WHERE id = ?", name, id);
    }

    public int countCameras(long siteId) {
        Integer total = jdbc.queryForObject(
                "SELECT COUNT(*) FROM devices WHERE site_id = ? AND type = 'CAMERA'", Integer.class, siteId);
        return total == null ? 0 : total;
    }

    /** Mayor numero usado en los codigos CAM-NNN (para asignar el siguiente). */
    public int maxCameraNumber() {
        Integer max = jdbc.queryForObject(
                "SELECT COALESCE(MAX(CAST(substr(code, 5) AS INTEGER)), 0) FROM devices WHERE code LIKE 'CAM-%'",
                Integer.class);
        return max == null ? 0 : max;
    }

    public boolean anySimulated() {
        Integer total = jdbc.queryForObject("SELECT COUNT(*) FROM devices WHERE simulated = 1", Integer.class);
        return total != null && total > 0;
    }
}

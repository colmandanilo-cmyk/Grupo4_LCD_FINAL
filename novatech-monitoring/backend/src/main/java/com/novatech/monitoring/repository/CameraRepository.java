package com.novatech.monitoring.repository;

import com.novatech.monitoring.dto.DeviceDtos.CameraView;
import com.novatech.monitoring.model.Camera;
import com.novatech.monitoring.model.Device;
import com.novatech.monitoring.model.EventType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de la tabla cameras. */
@Repository
public class CameraRepository {

    private final JdbcTemplate jdbc;

    private static final RowMapper<Camera> MAPPER = (rs, n) -> new Camera(
            rs.getLong("id"),
            rs.getLong("device_id"),
            rs.getString("position"),
            rs.getString("resolution"),
            rs.getInt("fps"),
            getBool(rs, "motion_detection"),
            getBool(rs, "recording"),
            rs.getInt("signal_percent"),
            getBool(rs, "motion_active"),
            getDateTime(rs, "last_motion_at"),
            rs.getString("scene"));

    private static final RowMapper<CameraView> VIEW_MAPPER = (rs, n) -> new CameraView(
            rs.getLong("device_id"),
            rs.getLong("site_id"),
            rs.getString("site_code"),
            rs.getString("site_name"),
            rs.getString("code"),
            rs.getString("name"),
            rs.getString("position"),
            rs.getString("resolution"),
            getEnum(rs, "status", Device.Status.class),
            rs.getInt("fps"),
            rs.getInt("signal_percent"),
            getBool(rs, "motion_detection"),
            getBool(rs, "recording"),
            getBool(rs, "motion_active"),
            getDateTime(rs, "last_motion_at"),
            getDateTime(rs, "last_seen"),
            rs.getString("scene"),
            getBool(rs, "simulated"),
            getBool(rs, "intrusion_active"),
            getEnum(rs, "last_event_type", EventType.class),
            getDateTime(rs, "last_event_at"),
            rs.getString("last_event_description"),
            getDateTime(rs, "device_time"),
            getDateTime(rs, "live_updated_at"),
            rs.getInt("speed"),
            getBool(rs, "running"));

    public CameraRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Camera> findByDeviceId(long deviceId) {
        return jdbc.query("SELECT * FROM cameras WHERE device_id = ?", MAPPER, deviceId).stream().findFirst();
    }

    public void insert(long deviceId, String position, String resolution, int fps, boolean motionDetection,
                       boolean recording, int signal, String scene) {
        jdbc.update("INSERT INTO cameras (device_id, position, resolution, fps, motion_detection, recording, "
                        + "signal_percent, motion_active, scene) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
                deviceId, position, resolution, fps, bool(motionDetection), bool(recording), signal, scene);
    }

    /** Datos en vivo que llegan con la telemetria. lastMotionAt null conserva el valor anterior. */
    public void updateLive(long deviceId, int fps, int signal, boolean motionActive, boolean recording,
                           LocalDateTime lastMotionAt) {
        jdbc.update("UPDATE cameras SET fps = ?, signal_percent = ?, motion_active = ?, recording = ?, "
                        + "last_motion_at = COALESCE(?, last_motion_at) WHERE device_id = ?",
                fps, signal, bool(motionActive), bool(recording), ts(lastMotionAt), deviceId);
    }

    public void markMotion(long deviceId, LocalDateTime when) {
        jdbc.update("UPDATE cameras SET motion_active = 1, last_motion_at = ? WHERE device_id = ?", ts(when), deviceId);
    }

    public void updateInfo(long deviceId, String position, String resolution, String scene) {
        jdbc.update("UPDATE cameras SET position = COALESCE(?, position), resolution = COALESCE(?, resolution), "
                + "scene = COALESCE(?, scene) WHERE device_id = ?", position, resolution, scene, deviceId);
    }

    /**
     * Camaras con todo lo que necesita la vista CCTV: estado, intrusion activa
     * (alerta de intrusion sin resolver), ultimo evento y reloj del equipo.
     */
    public List<CameraView> findViews(Long siteId) {
        StringBuilder sql = new StringBuilder("""
                SELECT d.id AS device_id, d.site_id, s.code AS site_code, s.name AS site_name, d.code, d.name,
                       c.position, c.resolution, d.status, c.fps, c.signal_percent, c.motion_detection, c.recording,
                       c.motion_active, c.last_motion_at, d.last_seen, c.scene, d.simulated,
                       EXISTS (SELECT 1 FROM alerts a WHERE a.device_id = d.id AND a.alert_type = 'INTRUSION'
                               AND a.status <> 'RESUELTA') AS intrusion_active,
                       le.event_type AS last_event_type, le.timestamp AS last_event_at,
                       le.description AS last_event_description,
                       l.device_time, l.updated_at AS live_updated_at,
                       COALESCE(ss.speed, 1) AS speed, COALESCE(ss.enabled, 0) AS running
                FROM devices d
                JOIN cameras c ON c.device_id = d.id
                JOIN sites s ON s.id = d.site_id
                LEFT JOIN events le ON le.id = (SELECT e.id FROM events e WHERE e.device_id = d.id
                                                ORDER BY e.timestamp DESC, e.id DESC LIMIT 1)
                LEFT JOIN site_live_status l ON l.site_id = d.site_id
                LEFT JOIN simulation_state ss ON ss.site_id = d.site_id
                WHERE d.type = 'CAMERA'
                """);
        List<Object> args = new ArrayList<>();
        if (siteId != null) {
            sql.append(" AND d.site_id = ?");
            args.add(siteId);
        }
        sql.append(" ORDER BY s.code, d.code");
        return jdbc.query(sql.toString(), VIEW_MAPPER, args.toArray());
    }
}

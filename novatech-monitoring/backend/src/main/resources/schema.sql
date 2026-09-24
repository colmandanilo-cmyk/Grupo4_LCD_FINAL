-- ============================================================
-- NOVA TECH - Estructura de la base de datos SQLite
-- Se ejecuta en cada arranque; IF NOT EXISTS evita recrear tablas.
-- Fechas: texto 'YYYY-MM-DD HH:MM:SS' en hora local.
-- Booleanos: INTEGER 0/1.
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL CHECK (role IN ('ADMINISTRADOR','SUPERVISOR','OPERADOR')),
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at      TEXT    NOT NULL,
    last_login_at   TEXT
);

CREATE TABLE IF NOT EXISTS sites (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    code                TEXT    NOT NULL UNIQUE,
    name                TEXT    NOT NULL,
    client              TEXT    NOT NULL,
    location            TEXT    NOT NULL,
    status              TEXT    NOT NULL DEFAULT 'ACTIVA' CHECK (status IN ('ACTIVA','MANTENIMIENTO','SIN_CONEXION')),
    installation_date   TEXT    NOT NULL,
    created_at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id     INTEGER NOT NULL REFERENCES sites(id),
    code        TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    type        TEXT    NOT NULL CHECK (type IN ('CAMERA','SOLAR_PANEL','BATTERY','STARLINK','CELLULAR_4G')),
    status      TEXT    NOT NULL DEFAULT 'ONLINE' CHECK (status IN ('ONLINE','OFFLINE','MANTENIMIENTO','FALLA')),
    simulated   INTEGER NOT NULL DEFAULT 1 CHECK (simulated IN (0,1)),
    last_seen   TEXT,
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_devices_site ON devices(site_id);

CREATE TABLE IF NOT EXISTS cameras (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           INTEGER NOT NULL UNIQUE REFERENCES devices(id),
    position            TEXT    NOT NULL,
    resolution          TEXT    NOT NULL DEFAULT '1920x1080',
    fps                 INTEGER NOT NULL DEFAULT 25,
    motion_detection    INTEGER NOT NULL DEFAULT 1 CHECK (motion_detection IN (0,1)),
    recording           INTEGER NOT NULL DEFAULT 1 CHECK (recording IN (0,1)),
    signal_percent      INTEGER NOT NULL DEFAULT 0,
    motion_active       INTEGER NOT NULL DEFAULT 0 CHECK (motion_active IN (0,1)),
    last_motion_at      TEXT,
    scene               TEXT    NOT NULL DEFAULT 'acceso'
);

-- Estado actual: una fila por obra, se actualiza con cada telemetria.
CREATE TABLE IF NOT EXISTS site_live_status (
    site_id                     INTEGER PRIMARY KEY REFERENCES sites(id),
    updated_at                  TEXT    NOT NULL,
    device_time                 TEXT,
    battery_percent             REAL,
    battery_voltage             REAL,
    battery_level               TEXT    NOT NULL DEFAULT 'NORMAL' CHECK (battery_level IN ('NORMAL','BAJA','CRITICA')),
    battery_trend               TEXT,
    solar_status                TEXT,
    solar_rated_power           REAL,
    solar_generation            REAL,
    solar_energy_today          REAL,
    low_generation              INTEGER NOT NULL DEFAULT 0,
    consumption                 REAL,
    consumption_cameras         REAL,
    consumption_connectivity    REAL,
    consumption_control         REAL,
    estimated_autonomy          REAL,
    starlink_status             TEXT,
    starlink_latency            REAL,
    starlink_download           REAL,
    starlink_upload             REAL,
    starlink_packet_loss        REAL,
    starlink_last_seen          TEXT,
    cellular_status             TEXT,
    cellular_signal             INTEGER,
    cellular_latency            REAL,
    cellular_download           REAL,
    cellular_upload             REAL,
    cellular_last_seen          TEXT,
    active_connection           TEXT    NOT NULL DEFAULT 'STARLINK' CHECK (active_connection IN ('STARLINK','CELLULAR_4G','NONE')),
    last_history_at             TEXT
);

CREATE TABLE IF NOT EXISTS energy_status (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id             INTEGER NOT NULL REFERENCES sites(id),
    timestamp           TEXT    NOT NULL,
    battery_percent     REAL    NOT NULL,
    battery_voltage     REAL    NOT NULL,
    solar_generation    REAL    NOT NULL,
    consumption         REAL    NOT NULL,
    estimated_autonomy  REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_energy_site_time ON energy_status(site_id, timestamp);

CREATE TABLE IF NOT EXISTS connectivity_status (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id                 INTEGER NOT NULL REFERENCES sites(id),
    timestamp               TEXT    NOT NULL,
    starlink_status         TEXT    NOT NULL,
    starlink_latency        REAL,
    starlink_download       REAL,
    starlink_upload         REAL,
    starlink_packet_loss    REAL,
    cellular_status         TEXT    NOT NULL,
    cellular_signal         INTEGER,
    cellular_latency        REAL,
    cellular_download       REAL,
    cellular_upload         REAL,
    active_connection       TEXT    NOT NULL CHECK (active_connection IN ('STARLINK','CELLULAR_4G','NONE'))
);
CREATE INDEX IF NOT EXISTS idx_connectivity_site_time ON connectivity_status(site_id, timestamp);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id     INTEGER NOT NULL REFERENCES sites(id),
    device_id   INTEGER REFERENCES devices(id),
    timestamp   TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    severity    TEXT    NOT NULL CHECK (severity IN ('INFO','BAJA','MEDIA','ALTA','CRITICA')),
    description TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_site_time ON events(site_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp);

CREATE TABLE IF NOT EXISTS alerts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id             INTEGER NOT NULL REFERENCES sites(id),
    device_id           INTEGER REFERENCES devices(id),
    event_id            INTEGER REFERENCES events(id),
    alert_type          TEXT    NOT NULL,
    created_at          TEXT    NOT NULL,
    severity            TEXT    NOT NULL CHECK (severity IN ('INFO','BAJA','MEDIA','ALTA','CRITICA')),
    status              TEXT    NOT NULL DEFAULT 'NUEVA' CHECK (status IN ('NUEVA','RECONOCIDA','EN_ATENCION','RESUELTA')),
    title               TEXT    NOT NULL,
    description         TEXT    NOT NULL,
    responsible_id      INTEGER REFERENCES users(id),
    acknowledged_by     INTEGER REFERENCES users(id),
    acknowledged_at     TEXT,
    resolved_by         INTEGER REFERENCES users(id),
    resolved_at         TEXT,
    resolution_note     TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_site_status ON alerts(site_id, status);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);

CREATE TABLE IF NOT EXISTS incidents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id         INTEGER NOT NULL REFERENCES sites(id),
    alert_id        INTEGER UNIQUE REFERENCES alerts(id),
    code            TEXT    NOT NULL UNIQUE,
    title           TEXT    NOT NULL,
    description     TEXT    NOT NULL,
    priority        TEXT    NOT NULL CHECK (priority IN ('BAJA','MEDIA','ALTA','CRITICA')),
    status          TEXT    NOT NULL DEFAULT 'ABIERTA' CHECK (status IN ('ABIERTA','EN_PROCESO','RESUELTA','CERRADA')),
    assigned_to     INTEGER REFERENCES users(id),
    created_by      INTEGER REFERENCES users(id),
    created_at      TEXT    NOT NULL,
    updated_at      TEXT,
    resolved_at     TEXT,
    closed_at       TEXT,
    observations    TEXT
);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_site ON incidents(site_id);

CREATE TABLE IF NOT EXISTS telemetry (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id     INTEGER NOT NULL REFERENCES sites(id),
    device_id   INTEGER NOT NULL REFERENCES devices(id),
    timestamp   TEXT    NOT NULL,
    metric      TEXT    NOT NULL,
    value       REAL    NOT NULL,
    unit        TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telemetry_device_metric_time ON telemetry(device_id, metric, timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_site_time ON telemetry(site_id, timestamp);

CREATE TABLE IF NOT EXISTS simulation_state (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id     INTEGER NOT NULL UNIQUE REFERENCES sites(id),
    enabled     INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    speed       INTEGER NOT NULL DEFAULT 1 CHECK (speed IN (1,5,20)),
    scenario    TEXT    NOT NULL DEFAULT 'NORMAL',
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_commands (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id     INTEGER REFERENCES sites(id),
    device_id   INTEGER REFERENCES devices(id),
    command     TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'PENDIENTE' CHECK (status IN ('PENDIENTE','ENVIADO','EJECUTADO','ERROR','EXPIRADO')),
    created_by  INTEGER REFERENCES users(id),
    created_at  TEXT    NOT NULL,
    sent_at     TEXT,
    executed_at TEXT,
    result      TEXT
);
CREATE INDEX IF NOT EXISTS idx_commands_status ON simulation_commands(status, created_at);

CREATE TABLE IF NOT EXISTS system_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    description TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    updated_by  INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id),
    action      TEXT    NOT NULL,
    entity      TEXT    NOT NULL,
    entity_id   INTEGER,
    details     TEXT,
    timestamp   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(timestamp);

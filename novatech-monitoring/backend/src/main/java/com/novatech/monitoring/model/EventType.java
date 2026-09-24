package com.novatech.monitoring.model;

/**
 * Tipos de evento (seccion 27 del enunciado, mas tres de la contingencia de conectividad).
 * La severidad y si generan alerta se deciden en MonitoringRules.
 */
public enum EventType {
    MOTION_DETECTED("Movimiento detectado"),
    INTRUSION_DETECTED("Intrusión detectada"),
    CAMERA_OFFLINE("Cámara desconectada"),
    CAMERA_RESTORED("Cámara recuperada"),
    BATTERY_LOW("Batería baja"),
    BATTERY_CRITICAL("Batería crítica"),
    STARLINK_DOWN("Starlink desconectado"),
    STARLINK_RESTORED("Starlink recuperado"),
    CELLULAR_ACTIVATED("4G activado"),
    CELLULAR_DOWN("4G desconectado"),
    CELLULAR_RESTORED("4G recuperado"),
    CONNECTIVITY_LOST("Obra sin conectividad"),
    LOW_SOLAR_GENERATION("Baja generación solar"),
    SOLAR_PANEL_FAILURE("Falla panel solar"),
    DEVICE_MAINTENANCE("Dispositivo en mantenimiento"),
    SYSTEM_RESTORED("Sistema restaurado");

    private final String label;

    EventType(String label) {
        this.label = label;
    }

    public String label() {
        return label;
    }
}

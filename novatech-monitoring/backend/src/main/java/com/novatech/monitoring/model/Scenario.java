package com.novatech.monitoring.model;

import java.util.Arrays;
import java.util.Optional;

/**
 * Ordenes que el Laboratorio de Simulacion envia al simulador Python.
 * "path" es el final de la URL: POST /api/simulation/{path}.
 */
public enum Scenario {
    RESTORE_NORMAL("restore-normal", "Operación normal", false),
    MOTION("motion", "Detectar movimiento", true),
    INTRUSION("intrusion", "Simular intrusión", true),
    CAMERA_FAILURE("camera-failure", "Desconectar cámara", true),
    CAMERA_RESTORE("camera-restore", "Recuperar cámara", true),
    STARLINK_FAILURE("starlink-failure", "Falla Starlink", false),
    STARLINK_RESTORE("starlink-restore", "Restaurar Starlink", false),
    NETWORK_FAILURE("network-failure", "Falla Starlink + 4G", false),
    LOW_BATTERY("low-battery", "Batería baja", false),
    CRITICAL_BATTERY("critical-battery", "Batería crítica", false),
    CLOUDY_DAY("cloudy-day", "Día nublado", false),
    SOLAR_FAILURE("solar-failure", "Falla panel solar", false),
    RESTORE_ENERGY("restore-energy", "Restaurar energía", false),
    RESET("reset", "Reiniciar simulación", false);

    private final String path;
    private final String label;
    private final boolean cameraScenario;

    Scenario(String path, String label, boolean cameraScenario) {
        this.path = path;
        this.label = label;
        this.cameraScenario = cameraScenario;
    }

    public String path() {
        return path;
    }

    public String label() {
        return label;
    }

    /** true si el escenario actua sobre una camara (se puede elegir cual). */
    public boolean cameraScenario() {
        return cameraScenario;
    }

    public static Optional<Scenario> fromPath(String path) {
        return Arrays.stream(values()).filter(s -> s.path.equals(path)).findFirst();
    }
}

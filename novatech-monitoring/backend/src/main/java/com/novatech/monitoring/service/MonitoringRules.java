package com.novatech.monitoring.service;

import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.EventType;
import com.novatech.monitoring.model.GeneralState;
import com.novatech.monitoring.model.Incident;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.model.SiteLiveStatus.BatteryLevel;

import java.time.Duration;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.Collection;
import java.util.Map;
import java.util.Set;

/**
 * REGLAS DE NEGOCIO DE NOVA TECH, TODAS EN UN SOLO LUGAR (seccion 18 del enunciado).
 *
 * Si se quiere cambiar como se calcula el estado general, que severidad tiene
 * cada evento, cuando una bateria es "baja" o como funciona la contingencia
 * Starlink -> 4G, se modifica esta clase. Los servicios solo la consultan.
 *
 * Los umbrales de bateria vienen de la pantalla Configuracion (ConfigService);
 * el resto son constantes documentadas aqui.
 */
public final class MonitoringRules {

    /** Margen para "salir" de un nivel de bateria y evitar alertas repetidas. */
    public static final int BATTERY_HYSTERESIS = 5;

    /** Horario laboral de las obras: una intrusion fuera de el es CRITICA. */
    public static final LocalTime WORK_START = LocalTime.of(7, 0);
    public static final LocalTime WORK_END = LocalTime.of(18, 0);

    /** Si una obra no envia datos en este tiempo, la interfaz muestra "Sin datos recientes". */
    public static final long STALE_DATA_SECONDS = 60;

    /** La fuente de datos se considera conectada si hablo con Java en este tiempo. */
    public static final long DATA_SOURCE_ONLINE_SECONDS = 15;

    /** Una orden del laboratorio que nadie recoge en este tiempo expira. */
    public static final long COMMAND_EXPIRY_SECONDS = 120;

    /** Una orden enviada que no se confirma en este tiempo se marca como ERROR. */
    public static final long COMMAND_CONFIRM_SECONDS = 60;

    /** Tiempo que se considera vigente la ultima deteccion de movimiento de una camara. */
    public static final long MOTION_VISIBLE_SECONDS = 40;

    /** Cantidad de camaras por obra (seccion 20). */
    public static final int MIN_CAMERAS = 2;
    public static final int MAX_CAMERAS = 4;

    /** Diferencia minima (W) entre generacion y consumo para decir que la bateria carga o descarga. */
    private static final double TREND_MARGIN_W = 5.0;

    private MonitoringRules() {
    }

    // ============================================================
    // 1. Estado general de una obra (seccion 18)
    // ============================================================

    /**
     * A partir de las severidades de las alertas NO resueltas:
     * - alguna CRITICA            -> ESTADO CRITICO
     * - alguna MEDIA o ALTA       -> ADVERTENCIA
     * - ninguna, o solo INFO/BAJA -> OPERACION NORMAL
     */
    public static GeneralState generalState(Collection<Severity> activeAlertSeverities) {
        boolean critical = activeAlertSeverities.stream().anyMatch(s -> s == Severity.CRITICA);
        if (critical) {
            return GeneralState.CRITICO;
        }
        boolean warning = activeAlertSeverities.stream().anyMatch(s -> s == Severity.MEDIA || s == Severity.ALTA);
        return warning ? GeneralState.ADVERTENCIA : GeneralState.NORMAL;
    }

    /** Estado de la plataforma: el peor entre todas las obras. */
    public static GeneralState worst(Collection<GeneralState> states) {
        return states.stream().max((a, b) -> Integer.compare(a.rank(), b.rank())).orElse(GeneralState.NORMAL);
    }

    // ============================================================
    // 2. Severidad de los eventos y de las alertas (secciones 28 y 29)
    // ============================================================

    private static final Map<EventType, Severity> EVENT_SEVERITY = Map.ofEntries(
            Map.entry(EventType.MOTION_DETECTED, Severity.INFO),
            Map.entry(EventType.INTRUSION_DETECTED, Severity.ALTA),
            Map.entry(EventType.CAMERA_OFFLINE, Severity.ALTA),
            Map.entry(EventType.CAMERA_RESTORED, Severity.INFO),
            Map.entry(EventType.BATTERY_LOW, Severity.MEDIA),
            Map.entry(EventType.BATTERY_CRITICAL, Severity.ALTA),
            Map.entry(EventType.STARLINK_DOWN, Severity.MEDIA),
            Map.entry(EventType.STARLINK_RESTORED, Severity.INFO),
            Map.entry(EventType.CELLULAR_ACTIVATED, Severity.BAJA),
            Map.entry(EventType.CELLULAR_DOWN, Severity.BAJA),
            Map.entry(EventType.CELLULAR_RESTORED, Severity.INFO),
            Map.entry(EventType.CONNECTIVITY_LOST, Severity.CRITICA),
            Map.entry(EventType.LOW_SOLAR_GENERATION, Severity.BAJA),
            Map.entry(EventType.SOLAR_PANEL_FAILURE, Severity.MEDIA),
            Map.entry(EventType.DEVICE_MAINTENANCE, Severity.INFO),
            Map.entry(EventType.SYSTEM_RESTORED, Severity.INFO));

    /** Severidad de un evento. La intrusion se calcula aparte con intrusionSeverity. */
    public static Severity eventSeverity(EventType type) {
        return EVENT_SEVERITY.getOrDefault(type, Severity.INFO);
    }

    /** Tipos de evento que un dispositivo puede informar directamente (el resto los detecta Java). */
    public static final Set<EventType> DEVICE_REPORTED_EVENTS =
            Set.of(EventType.MOTION_DETECTED, EventType.INTRUSION_DETECTED);

    /** Intrusion: ALTA en horario laboral, CRITICA fuera de el (hora del equipo). */
    public static Severity intrusionSeverity(LocalTime deviceTime) {
        boolean workHours = !deviceTime.isBefore(WORK_START) && deviceTime.isBefore(WORK_END);
        return workHours ? Severity.ALTA : Severity.CRITICA;
    }

    /** Severidad de cada tipo de alerta de condicion. */
    public static Severity alertSeverity(Alert.Type type) {
        return switch (type) {
            case CAMERA_OFFLINE, BATTERY_CRITICAL -> Severity.ALTA;
            case BATTERY_LOW, STARLINK, SOLAR_PANEL -> Severity.MEDIA;
            case CONNECTIVITY -> Severity.CRITICA;
            case INTRUSION -> Severity.ALTA;
        };
    }

    // ============================================================
    // 3. Nivel de bateria con histeresis (seccion 24)
    // ============================================================

    /**
     * Baja de nivel en cuanto cruza el umbral; sube solo cuando supera umbral + 5.
     * Ejemplo con 35/20: NORMAL->BAJA en 35 %, BAJA->NORMAL en 40 %,
     * ->CRITICA en 20 %, CRITICA->BAJA en 25 %.
     */
    public static BatteryLevel batteryLevel(BatteryLevel previous, double percent, int lowThreshold,
                                            int criticalThreshold) {
        BatteryLevel level = previous == null ? BatteryLevel.NORMAL : previous;
        if (percent <= criticalThreshold) {
            return BatteryLevel.CRITICA;
        }
        if (percent <= lowThreshold && level == BatteryLevel.NORMAL) {
            return BatteryLevel.BAJA;
        }
        if (level == BatteryLevel.CRITICA && percent >= criticalThreshold + BATTERY_HYSTERESIS) {
            level = BatteryLevel.BAJA;
        }
        if (level == BatteryLevel.BAJA && percent >= lowThreshold + BATTERY_HYSTERESIS) {
            level = BatteryLevel.NORMAL;
        }
        return level;
    }

    /** CARGANDO, DESCARGANDO o ESTABLE segun generacion y consumo. */
    public static String batteryTrend(double generationW, double consumptionW, double percent) {
        double balance = generationW - consumptionW;
        if (balance > TREND_MARGIN_W) {
            return percent >= 99.5 ? "CARGA COMPLETA" : "CARGANDO";
        }
        if (balance < -TREND_MARGIN_W) {
            return "DESCARGANDO";
        }
        return "ESTABLE";
    }

    // ============================================================
    // 4. Contingencia de conectividad (seccion 26)
    // ============================================================

    /**
     * Starlink en linea            -> STARLINK (conexion principal)
     * Starlink caido y 4G en linea -> CELLULAR_4G (respaldo)
     * Ambos caidos                 -> NONE (obra sin conectividad)
     */
    public static ConnectionType activeConnection(boolean starlinkOnline, boolean cellularOnline) {
        if (starlinkOnline) {
            return ConnectionType.STARLINK;
        }
        return cellularOnline ? ConnectionType.CELLULAR_4G : ConnectionType.NONE;
    }

    /** Condicion "Starlink caido con 4G disponible": alerta MEDIA. */
    public static boolean starlinkDegraded(boolean starlinkOnline, boolean cellularOnline) {
        return !starlinkOnline && cellularOnline;
    }

    /** Condicion "Starlink y 4G caidos": alerta CRITICA. */
    public static boolean connectivityLost(boolean starlinkOnline, boolean cellularOnline) {
        return !starlinkOnline && !cellularOnline;
    }

    // ============================================================
    // 5. Incidencias (seccion 31)
    // ============================================================

    private static final Map<Incident.Status, Set<Incident.Status>> INCIDENT_TRANSITIONS = Map.of(
            Incident.Status.ABIERTA, Set.of(Incident.Status.EN_PROCESO, Incident.Status.RESUELTA),
            Incident.Status.EN_PROCESO, Set.of(Incident.Status.RESUELTA),
            Incident.Status.RESUELTA, Set.of(Incident.Status.EN_PROCESO, Incident.Status.CERRADA),
            Incident.Status.CERRADA, Set.of());

    public static boolean incidentTransitionAllowed(Incident.Status from, Incident.Status to) {
        return INCIDENT_TRANSITIONS.getOrDefault(from, Set.of()).contains(to);
    }

    /** Prioridad sugerida para una incidencia creada desde una alerta. */
    public static Severity incidentPriorityFor(Severity alertSeverity) {
        return alertSeverity == Severity.INFO ? Severity.BAJA : alertSeverity;
    }

    // ============================================================
    // 6. Utilidades de tiempo
    // ============================================================

    /** true si el dato es mas viejo que el limite (o no existe). */
    public static boolean isOlderThan(LocalDateTime time, LocalDateTime now, long seconds) {
        return time == null || Duration.between(time, now).getSeconds() > seconds;
    }
}

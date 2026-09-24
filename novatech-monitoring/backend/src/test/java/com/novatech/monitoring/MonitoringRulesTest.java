package com.novatech.monitoring;

import com.novatech.monitoring.model.Alert;
import com.novatech.monitoring.model.ConnectionType;
import com.novatech.monitoring.model.GeneralState;
import com.novatech.monitoring.model.Incident;
import com.novatech.monitoring.model.Severity;
import com.novatech.monitoring.model.SiteLiveStatus.BatteryLevel;
import com.novatech.monitoring.service.MonitoringRules;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Reglas de negocio puras: no levantan Spring ni usan base de datos. */
class MonitoringRulesTest {

    private static final int LOW = 35;
    private static final int CRITICAL = 20;

    @Test
    @DisplayName("Estado general según las alertas activas")
    void generalState() {
        assertEquals(GeneralState.NORMAL, MonitoringRules.generalState(List.of()));
        assertEquals(GeneralState.NORMAL, MonitoringRules.generalState(List.of(Severity.INFO, Severity.BAJA)));
        assertEquals(GeneralState.ADVERTENCIA, MonitoringRules.generalState(List.of(Severity.MEDIA)));
        assertEquals(GeneralState.ADVERTENCIA, MonitoringRules.generalState(List.of(Severity.BAJA, Severity.ALTA)));
        assertEquals(GeneralState.CRITICO, MonitoringRules.generalState(List.of(Severity.MEDIA, Severity.CRITICA)));
    }

    @Test
    @DisplayName("El estado de la plataforma es el peor de todas las obras")
    void worstState() {
        assertEquals(GeneralState.CRITICO, MonitoringRules.worst(
                List.of(GeneralState.NORMAL, GeneralState.CRITICO, GeneralState.ADVERTENCIA)));
        assertEquals(GeneralState.NORMAL, MonitoringRules.worst(List.of()));
    }

    @Test
    @DisplayName("Intrusión: ALTA de 07:00 a 17:59, CRÍTICA fuera de ese horario")
    void intrusionSeverity() {
        assertEquals(Severity.CRITICA, MonitoringRules.intrusionSeverity(LocalTime.of(6, 59)));
        assertEquals(Severity.ALTA, MonitoringRules.intrusionSeverity(LocalTime.of(7, 0)));
        assertEquals(Severity.ALTA, MonitoringRules.intrusionSeverity(LocalTime.of(17, 59)));
        assertEquals(Severity.CRITICA, MonitoringRules.intrusionSeverity(LocalTime.of(18, 0)));
        assertEquals(Severity.CRITICA, MonitoringRules.intrusionSeverity(LocalTime.of(2, 30)));
    }

    @Test
    @DisplayName("Severidad de cada alerta de condición")
    void alertSeverities() {
        assertEquals(Severity.ALTA, MonitoringRules.alertSeverity(Alert.Type.CAMERA_OFFLINE));
        assertEquals(Severity.MEDIA, MonitoringRules.alertSeverity(Alert.Type.BATTERY_LOW));
        assertEquals(Severity.ALTA, MonitoringRules.alertSeverity(Alert.Type.BATTERY_CRITICAL));
        assertEquals(Severity.MEDIA, MonitoringRules.alertSeverity(Alert.Type.STARLINK));
        assertEquals(Severity.CRITICA, MonitoringRules.alertSeverity(Alert.Type.CONNECTIVITY));
        assertEquals(Severity.MEDIA, MonitoringRules.alertSeverity(Alert.Type.SOLAR_PANEL));
    }

    @Test
    @DisplayName("Batería: baja de nivel al cruzar el umbral")
    void batteryGoesDown() {
        assertEquals(BatteryLevel.NORMAL, MonitoringRules.batteryLevel(BatteryLevel.NORMAL, 36, LOW, CRITICAL));
        assertEquals(BatteryLevel.BAJA, MonitoringRules.batteryLevel(BatteryLevel.NORMAL, 35, LOW, CRITICAL));
        assertEquals(BatteryLevel.CRITICA, MonitoringRules.batteryLevel(BatteryLevel.BAJA, 20, LOW, CRITICAL));
        assertEquals(BatteryLevel.CRITICA, MonitoringRules.batteryLevel(BatteryLevel.NORMAL, 12, LOW, CRITICAL));
        assertEquals(BatteryLevel.NORMAL, MonitoringRules.batteryLevel(null, 80, LOW, CRITICAL));
    }

    @Test
    @DisplayName("Batería: histéresis de 5 puntos para subir de nivel")
    void batteryHysteresis() {
        assertEquals(BatteryLevel.CRITICA, MonitoringRules.batteryLevel(BatteryLevel.CRITICA, 24, LOW, CRITICAL));
        assertEquals(BatteryLevel.BAJA, MonitoringRules.batteryLevel(BatteryLevel.CRITICA, 25, LOW, CRITICAL));
        assertEquals(BatteryLevel.BAJA, MonitoringRules.batteryLevel(BatteryLevel.BAJA, 39, LOW, CRITICAL));
        assertEquals(BatteryLevel.NORMAL, MonitoringRules.batteryLevel(BatteryLevel.BAJA, 40, LOW, CRITICAL));
        assertEquals(BatteryLevel.NORMAL, MonitoringRules.batteryLevel(BatteryLevel.CRITICA, 90, LOW, CRITICAL));
    }

    @Test
    @DisplayName("Tendencia de la batería según generación y consumo")
    void batteryTrend() {
        assertEquals("CARGANDO", MonitoringRules.batteryTrend(400, 95, 60));
        assertEquals("CARGA COMPLETA", MonitoringRules.batteryTrend(400, 95, 100));
        assertEquals("DESCARGANDO", MonitoringRules.batteryTrend(0, 95, 60));
        assertEquals("ESTABLE", MonitoringRules.batteryTrend(97, 95, 60));
    }

    @Test
    @DisplayName("Tabla de contingencia de conectividad")
    void connectivityContingency() {
        assertEquals(ConnectionType.STARLINK, MonitoringRules.activeConnection(true, true));
        assertEquals(ConnectionType.STARLINK, MonitoringRules.activeConnection(true, false));
        assertEquals(ConnectionType.CELLULAR_4G, MonitoringRules.activeConnection(false, true));
        assertEquals(ConnectionType.NONE, MonitoringRules.activeConnection(false, false));

        assertTrue(MonitoringRules.starlinkDegraded(false, true));
        assertFalse(MonitoringRules.starlinkDegraded(true, false));
        assertTrue(MonitoringRules.connectivityLost(false, false));
        assertFalse(MonitoringRules.connectivityLost(false, true));
    }

    @Test
    @DisplayName("Transiciones permitidas de una incidencia")
    void incidentTransitions() {
        assertTrue(MonitoringRules.incidentTransitionAllowed(Incident.Status.ABIERTA, Incident.Status.EN_PROCESO));
        assertTrue(MonitoringRules.incidentTransitionAllowed(Incident.Status.ABIERTA, Incident.Status.RESUELTA));
        assertTrue(MonitoringRules.incidentTransitionAllowed(Incident.Status.EN_PROCESO, Incident.Status.RESUELTA));
        assertTrue(MonitoringRules.incidentTransitionAllowed(Incident.Status.RESUELTA, Incident.Status.EN_PROCESO));
        assertTrue(MonitoringRules.incidentTransitionAllowed(Incident.Status.RESUELTA, Incident.Status.CERRADA));

        assertFalse(MonitoringRules.incidentTransitionAllowed(Incident.Status.ABIERTA, Incident.Status.CERRADA));
        assertFalse(MonitoringRules.incidentTransitionAllowed(Incident.Status.EN_PROCESO, Incident.Status.ABIERTA));
        assertFalse(MonitoringRules.incidentTransitionAllowed(Incident.Status.CERRADA, Incident.Status.EN_PROCESO));
    }

    @Test
    @DisplayName("Prioridad sugerida de una incidencia creada desde una alerta")
    void incidentPriority() {
        assertEquals(Severity.CRITICA, MonitoringRules.incidentPriorityFor(Severity.CRITICA));
        assertEquals(Severity.BAJA, MonitoringRules.incidentPriorityFor(Severity.INFO));
    }

    @Test
    @DisplayName("Datos viejos: más antiguos que el límite o inexistentes")
    void staleData() {
        LocalDateTime now = LocalDateTime.of(2026, 9, 24, 12, 0, 0);
        assertFalse(MonitoringRules.isOlderThan(now.minusSeconds(60), now, 60));
        assertTrue(MonitoringRules.isOlderThan(now.minusSeconds(61), now, 60));
        assertTrue(MonitoringRules.isOlderThan(null, now, 60));
    }
}

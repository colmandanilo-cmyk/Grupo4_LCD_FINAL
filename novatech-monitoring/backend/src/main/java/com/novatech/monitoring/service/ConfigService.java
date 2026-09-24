package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.ConfigDtos.ConfigEntry;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.repository.ConfigRepository;
import com.novatech.monitoring.repository.SimulationRepository;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.security.AuthenticatedUser;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Parametros configurables del sistema (pantalla Configuracion, seccion 43).
 * Los valores se guardan en system_config y se mantienen en memoria para no
 * consultar la base en cada telemetria.
 */
@Service
public class ConfigService {

    public static final String BATTERY_LOW = "battery.low_threshold";
    public static final String BATTERY_CRITICAL = "battery.critical_threshold";
    public static final String UI_REFRESH = "ui.refresh_seconds";
    public static final String TELEMETRY_INTERVAL = "telemetry.interval_seconds";
    public static final String SIMULATION_ENABLED = "simulation.enabled";
    public static final String SIMULATION_SPEED = "simulation.default_speed";

    public static final Set<Integer> ALLOWED_SPEEDS = Set.of(1, 5, 20);

    private record Default(String value, String description) {
    }

    /** Valores por defecto y texto de ayuda de cada parametro. */
    private static final Map<String, Default> DEFAULTS = new LinkedHashMap<>();

    static {
        DEFAULTS.put(BATTERY_LOW, new Default("35", "Límite de batería baja (%). Genera alerta MEDIA."));
        DEFAULTS.put(BATTERY_CRITICAL, new Default("20", "Límite de batería crítica (%). Genera alerta ALTA."));
        DEFAULTS.put(UI_REFRESH, new Default("5", "Frecuencia de actualización de las pantallas (segundos)."));
        DEFAULTS.put(TELEMETRY_INTERVAL, new Default("60", "Frecuencia de registro del historial de telemetría (segundos)."));
        DEFAULTS.put(SIMULATION_ENABLED, new Default("true", "Simulación automática activada (true/false)."));
        DEFAULTS.put(SIMULATION_SPEED, new Default("1", "Velocidad predeterminada de la simulación (1, 5 o 20)."));
    }

    private final ConfigRepository repository;
    private final SimulationRepository simulationRepository;
    private final AuditService auditService;
    private final Map<String, String> cache = new ConcurrentHashMap<>();

    public ConfigService(ConfigRepository repository, SimulationRepository simulationRepository,
                         AuditService auditService) {
        this.repository = repository;
        this.simulationRepository = simulationRepository;
        this.auditService = auditService;
    }

    /** Crea los parametros que falten con su valor por defecto. */
    @Transactional
    public void ensureDefaults() {
        LocalDateTime now = SqlUtils.now();
        DEFAULTS.forEach((key, def) -> repository.insertIfMissing(key, def.value(), def.description(), now));
        reload();
    }

    public List<ConfigEntry> findAll() {
        return repository.findAll();
    }

    public int batteryLowThreshold() {
        return intValue(BATTERY_LOW);
    }

    public int batteryCriticalThreshold() {
        return intValue(BATTERY_CRITICAL);
    }

    public int refreshSeconds() {
        return intValue(UI_REFRESH);
    }

    public int telemetryIntervalSeconds() {
        return intValue(TELEMETRY_INTERVAL);
    }

    public boolean simulationEnabled() {
        return Boolean.parseBoolean(value(SIMULATION_ENABLED));
    }

    public int defaultSpeed() {
        return intValue(SIMULATION_SPEED);
    }

    /** Valida y guarda los parametros recibidos. Registra cada cambio en auditoria. */
    @Transactional
    public List<ConfigEntry> update(Map<String, String> values, AuthenticatedUser user) {
        Map<String, String> clean = new LinkedHashMap<>();
        values.forEach((key, raw) -> {
            if (!DEFAULTS.containsKey(key)) {
                throw ApiException.badRequest("Parámetro desconocido: " + key);
            }
            clean.put(key, validate(key, raw == null ? "" : raw.trim()));
        });

        int low = Integer.parseInt(clean.getOrDefault(BATTERY_LOW, value(BATTERY_LOW)));
        int critical = Integer.parseInt(clean.getOrDefault(BATTERY_CRITICAL, value(BATTERY_CRITICAL)));
        if (critical >= low) {
            throw ApiException.badRequest("El límite de batería crítica debe ser menor que el de batería baja");
        }

        LocalDateTime now = SqlUtils.now();
        clean.forEach((key, newValue) -> {
            String oldValue = value(key);
            if (!newValue.equals(oldValue)) {
                repository.updateValue(key, newValue, user.id(), now);
                auditService.log(user.id(), "CONFIGURACION_ACTUALIZADA", "CONFIG", null,
                        key + ": " + oldValue + " → " + newValue);
                if (SIMULATION_ENABLED.equals(key)) {
                    // Activar o desactivar la simulacion automatica se aplica de inmediato.
                    simulationRepository.setEnabledAll(Boolean.parseBoolean(newValue), now);
                }
            }
        });
        reload();
        return repository.findAll();
    }

    private String validate(String key, String raw) {
        switch (key) {
            case BATTERY_LOW -> checkRange(key, raw, 5, 90, "El límite de batería baja debe estar entre 5 y 90 %");
            case BATTERY_CRITICAL -> checkRange(key, raw, 1, 89, "El límite de batería crítica debe estar entre 1 y 89 %");
            case UI_REFRESH -> checkRange(key, raw, 2, 60, "La frecuencia de actualización debe estar entre 2 y 60 segundos");
            case TELEMETRY_INTERVAL -> checkRange(key, raw, 10, 600, "La frecuencia de telemetría debe estar entre 10 y 600 segundos");
            case SIMULATION_ENABLED -> {
                if (!raw.equalsIgnoreCase("true") && !raw.equalsIgnoreCase("false")) {
                    throw ApiException.badRequest("Simulación activada debe ser true o false");
                }
                return raw.toLowerCase();
            }
            case SIMULATION_SPEED -> {
                int speed = parse(raw, "La velocidad debe ser 1, 5 o 20");
                if (!ALLOWED_SPEEDS.contains(speed)) {
                    throw ApiException.badRequest("La velocidad debe ser 1, 5 o 20");
                }
            }
            default -> throw ApiException.badRequest("Parámetro desconocido: " + key);
        }
        return String.valueOf(Integer.parseInt(raw));
    }

    private static void checkRange(String key, String raw, int min, int max, String message) {
        int value = parse(raw, message);
        if (value < min || value > max) {
            throw ApiException.badRequest(message);
        }
    }

    private static int parse(String raw, String message) {
        try {
            return Integer.parseInt(raw);
        } catch (NumberFormatException e) {
            throw ApiException.badRequest(message);
        }
    }

    private String value(String key) {
        if (cache.isEmpty()) {
            reload();
        }
        String value = cache.get(key);
        return value != null ? value : DEFAULTS.get(key).value();
    }

    private int intValue(String key) {
        return Integer.parseInt(value(key));
    }

    private void reload() {
        repository.findAll().forEach(entry -> cache.put(entry.key(), entry.value()));
    }
}

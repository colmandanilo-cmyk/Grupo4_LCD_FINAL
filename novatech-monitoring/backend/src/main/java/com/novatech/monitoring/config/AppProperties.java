package com.novatech.monitoring.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.List;

/**
 * Propiedades propias del sistema, leidas de application.properties (prefijo "novatech.").
 */
@ConfigurationProperties(prefix = "novatech")
public record AppProperties(Db db, Security security, Ingest ingest, Cors cors, Retention retention) {

    /** Ruta del archivo SQLite. */
    public record Db(String path) {}

    /** Duracion del token de sesion en horas. */
    public record Security(int jwtExpirationHours) {}

    /** Clave que deben enviar los dispositivos en la cabecera X-Device-Key. */
    public record Ingest(String apiKey) {}

    /** Origenes que el navegador puede usar para llamar a la API. */
    public record Cors(List<String> allowedOrigins) {}

    /** Dias que se conservan la telemetria y el historial de energia/conectividad. */
    public record Retention(int telemetryDays, int historyDays) {}
}

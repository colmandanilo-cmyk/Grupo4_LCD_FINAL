package com.novatech.monitoring.config;

import com.zaxxer.hikari.HikariDataSource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.sql.DataSource;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Conexion a SQLite.
 *
 * - Crea la carpeta de la base si no existe (SQLite crea el archivo, pero no la carpeta).
 * - Usa UNA sola conexion: SQLite admite un escritor a la vez y asi se evita
 *   el error "database is locked" cuando escriben el simulador y los usuarios.
 * - foreign_keys=on: SQLite no valida claves foraneas si no se le pide.
 * - journal_mode=WAL: permite leer la base con otra herramienta mientras la app corre.
 * - busy_timeout: espera hasta 5 s si la base esta ocupada, en vez de fallar.
 */
@Configuration
public class DatabaseConfig {

    private static final Logger log = LoggerFactory.getLogger(DatabaseConfig.class);

    @Bean
    public DataSource dataSource(AppProperties properties) {
        Path dbFile = Path.of(properties.db().path()).toAbsolutePath().normalize();
        try {
            Files.createDirectories(dbFile.getParent());
        } catch (IOException e) {
            throw new UncheckedIOException("No se pudo crear la carpeta de la base de datos: " + dbFile.getParent(), e);
        }
        log.info("Base de datos SQLite: {}", dbFile);

        HikariDataSource dataSource = new HikariDataSource();
        dataSource.setDriverClassName("org.sqlite.JDBC");
        dataSource.setJdbcUrl("jdbc:sqlite:" + dbFile + "?foreign_keys=on&journal_mode=WAL&busy_timeout=5000");
        dataSource.setMaximumPoolSize(1);
        dataSource.setPoolName("novatech-sqlite");
        return dataSource;
    }
}

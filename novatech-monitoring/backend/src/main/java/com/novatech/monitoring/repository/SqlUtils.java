package com.novatech.monitoring.repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;

/**
 * Utilidades para leer y escribir en SQLite.
 *
 * Las fechas se guardan como texto 'yyyy-MM-dd HH:mm:ss' (hora local).
 * Asi se ordenan correctamente como texto y se leen facil al abrir la base.
 */
public final class SqlUtils {

    public static final DateTimeFormatter DB_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private SqlUtils() {
    }

    /** Hora actual sin fracciones de segundo. */
    public static LocalDateTime now() {
        return LocalDateTime.now().truncatedTo(ChronoUnit.SECONDS);
    }

    /** LocalDateTime -> texto para la base (null se mantiene null). */
    public static String ts(LocalDateTime value) {
        return value == null ? null : value.truncatedTo(ChronoUnit.SECONDS).format(DB_FORMAT);
    }

    public static String date(LocalDate value) {
        return value == null ? null : value.toString();
    }

    public static LocalDateTime getDateTime(ResultSet rs, String column) throws SQLException {
        String value = rs.getString(column);
        return value == null ? null : LocalDateTime.parse(value, DB_FORMAT);
    }

    public static LocalDate getDate(ResultSet rs, String column) throws SQLException {
        String value = rs.getString(column);
        return value == null ? null : LocalDate.parse(value);
    }

    public static Double getDouble(ResultSet rs, String column) throws SQLException {
        double value = rs.getDouble(column);
        return rs.wasNull() ? null : value;
    }

    public static Integer getInteger(ResultSet rs, String column) throws SQLException {
        int value = rs.getInt(column);
        return rs.wasNull() ? null : value;
    }

    public static Long getLong(ResultSet rs, String column) throws SQLException {
        long value = rs.getLong(column);
        return rs.wasNull() ? null : value;
    }

    public static boolean getBool(ResultSet rs, String column) throws SQLException {
        return rs.getInt(column) == 1;
    }

    public static <E extends Enum<E>> E getEnum(ResultSet rs, String column, Class<E> type) throws SQLException {
        String value = rs.getString(column);
        return value == null ? null : Enum.valueOf(type, value);
    }

    /** Nombre del enum para guardarlo (null se mantiene null). */
    public static String name(Enum<?> value) {
        return value == null ? null : value.name();
    }

    public static int bool(boolean value) {
        return value ? 1 : 0;
    }

    /** Tamano de pagina entre 1 y 200 (20 si no se indica). */
    public static int pageSize(Integer size) {
        if (size == null || size <= 0) {
            return 20;
        }
        return Math.min(size, 200);
    }

    public static int page(Integer page) {
        return page == null || page < 0 ? 0 : page;
    }

    /** Redondea a 2 decimales (para valores que se muestran en pantalla). */
    public static Double round2(Double value) {
        return value == null ? null : Math.round(value * 100.0) / 100.0;
    }
}

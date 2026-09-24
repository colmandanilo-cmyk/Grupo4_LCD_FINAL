package com.novatech.monitoring.security;

/**
 * Expresiones de permiso para @PreAuthorize.
 * Cada endpoint declara quien puede usarlo; asi la regla queda junto al codigo que protege.
 */
public final class Roles {

    /** Solo el administrador. */
    public static final String ADMIN = "hasRole('ADMINISTRADOR')";

    /** Administrador o supervisor. */
    public static final String ADMIN_O_SUPERVISOR = "hasAnyRole('ADMINISTRADOR','SUPERVISOR')";

    /** Cualquier usuario con sesion iniciada. */
    public static final String CUALQUIER_ROL = "hasAnyRole('ADMINISTRADOR','SUPERVISOR','OPERADOR')";

    /** Rol interno que reciben los dispositivos que envian la clave X-Device-Key. */
    public static final String DISPOSITIVO = "DISPOSITIVO";

    private Roles() {
    }
}

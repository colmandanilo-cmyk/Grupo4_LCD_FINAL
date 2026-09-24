package com.novatech.monitoring.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

import java.time.LocalDateTime;

/** Datos de entrada y salida de /api/auth. */
public final class AuthDtos {

    private AuthDtos() {
    }

    public record LoginRequest(
            @NotBlank(message = "Ingrese su correo") @Email(message = "El correo no es válido") String email,
            @NotBlank(message = "Ingrese su contraseña") String password) {
    }

    /** Parametros que la interfaz necesita conocer al iniciar sesion. */
    public record UiSettings(int refreshSeconds, int batteryLowThreshold, int batteryCriticalThreshold) {
    }

    public record LoginResponse(String token, LocalDateTime expiresAt, UserDtos.UserView user, UiSettings settings) {
    }

    public record MeResponse(UserDtos.UserView user, UiSettings settings) {
    }
}

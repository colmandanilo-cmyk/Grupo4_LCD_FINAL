package com.novatech.monitoring.dto;

import com.novatech.monitoring.model.Role;
import com.novatech.monitoring.model.User;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;

/** Datos de entrada y salida de /api/users. Nunca incluyen el hash de la contrasena. */
public final class UserDtos {

    private UserDtos() {
    }

    public record UserView(Long id, String name, String email, Role role, boolean active,
                           LocalDateTime createdAt, LocalDateTime lastLoginAt) {
        public static UserView of(User u) {
            return new UserView(u.id(), u.name(), u.email(), u.role(), u.active(), u.createdAt(), u.lastLoginAt());
        }
    }

    public record UserCreateRequest(
            @NotBlank(message = "El nombre es obligatorio") @Size(max = 100, message = "Máximo 100 caracteres") String name,
            @NotBlank(message = "El correo es obligatorio") @Email(message = "El correo no es válido") String email,
            @NotNull(message = "Seleccione un rol") Role role,
            @NotBlank(message = "La contraseña es obligatoria") String password) {
    }

    /** Todos los campos son opcionales: solo se cambia lo que llega. */
    public record UserUpdateRequest(
            @Size(min = 1, max = 100, message = "El nombre debe tener entre 1 y 100 caracteres") String name,
            @Email(message = "El correo no es válido") String email,
            Role role,
            Boolean active,
            String password) {
    }

    /** Usuario que puede elegirse como responsable de una incidencia. */
    public record AssignableUser(Long id, String name, Role role) {
    }
}

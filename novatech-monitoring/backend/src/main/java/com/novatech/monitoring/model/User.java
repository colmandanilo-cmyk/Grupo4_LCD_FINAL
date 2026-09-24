package com.novatech.monitoring.model;

import java.time.LocalDateTime;

/** Fila de la tabla users. La contrasena solo existe como hash BCrypt. */
public record User(
        Long id,
        String name,
        String email,
        String passwordHash,
        Role role,
        boolean active,
        LocalDateTime createdAt,
        LocalDateTime lastLoginAt) {
}

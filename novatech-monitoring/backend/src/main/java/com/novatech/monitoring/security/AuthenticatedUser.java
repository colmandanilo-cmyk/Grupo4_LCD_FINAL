package com.novatech.monitoring.security;

import com.novatech.monitoring.model.Role;

/**
 * Usuario de la peticion en curso. Los controladores lo reciben con
 * {@code @AuthenticationPrincipal AuthenticatedUser user}.
 */
public record AuthenticatedUser(Long id, String name, String email, Role role) {
}

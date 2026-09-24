package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.AuthDtos.LoginRequest;
import com.novatech.monitoring.dto.AuthDtos.LoginResponse;
import com.novatech.monitoring.dto.AuthDtos.MeResponse;
import com.novatech.monitoring.dto.AuthDtos.UiSettings;
import com.novatech.monitoring.dto.UserDtos.UserView;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.User;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.repository.UserRepository;
import com.novatech.monitoring.security.AuthenticatedUser;
import com.novatech.monitoring.security.JwtService;
import com.novatech.monitoring.security.LoginAttemptService;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Optional;

/** Inicio y cierre de sesion (secciones 11 y 42). */
@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final LoginAttemptService attempts;
    private final AuditService auditService;
    private final ConfigService configService;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtService jwtService,
                       LoginAttemptService attempts, AuditService auditService, ConfigService configService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
        this.attempts = attempts;
        this.auditService = auditService;
        this.configService = configService;
    }

    public LoginResponse login(LoginRequest request) {
        String email = request.email().trim();
        long minutes = attempts.minutesLocked(email);
        if (minutes > 0) {
            throw ApiException.tooManyRequests("Demasiados intentos fallidos. Intente nuevamente en " + minutes
                    + (minutes == 1 ? " minuto." : " minutos."));
        }

        Optional<User> found = userRepository.findByEmail(email);
        if (found.isEmpty() || !passwordEncoder.matches(request.password(), found.get().passwordHash())) {
            attempts.registerFailure(email);
            auditService.log(found.map(User::id).orElse(null), "LOGIN_FALLIDO", "SESSION", null,
                    "Intento fallido para " + email);
            // Mismo mensaje exista o no el correo, para no revelar que usuarios existen.
            throw ApiException.unauthorized("Correo o contraseña incorrectos");
        }
        User user = found.get();
        if (!user.active()) {
            auditService.log(user.id(), "LOGIN_FALLIDO", "SESSION", null, "Usuario desactivado: " + email);
            throw ApiException.forbidden("Su usuario está desactivado. Contacte al administrador.");
        }

        attempts.registerSuccess(email);
        LocalDateTime now = SqlUtils.now();
        userRepository.updateLastLogin(user.id(), now);
        auditService.log(user.id(), "LOGIN", "SESSION", user.id(), "Inicio de sesión de " + user.email());

        LocalDateTime expiresAt = jwtService.expirationFromNow();
        String token = jwtService.generate(user, expiresAt);
        User updated = userRepository.findById(user.id()).orElse(user);
        return new LoginResponse(token, expiresAt, UserView.of(updated), settings());
    }

    public MeResponse me(AuthenticatedUser principal) {
        User user = userRepository.findById(principal.id())
                .orElseThrow(() -> ApiException.unauthorized("Usuario no encontrado"));
        return new MeResponse(UserView.of(user), settings());
    }

    public void logout(AuthenticatedUser principal) {
        auditService.log(principal.id(), "LOGOUT", "SESSION", principal.id(), "Cierre de sesión de " + principal.email());
    }

    private UiSettings settings() {
        return new UiSettings(configService.refreshSeconds(), configService.batteryLowThreshold(),
                configService.batteryCriticalThreshold());
    }
}

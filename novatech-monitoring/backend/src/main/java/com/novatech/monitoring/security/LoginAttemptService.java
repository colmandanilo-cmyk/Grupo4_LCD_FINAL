package com.novatech.monitoring.security;

import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Proteccion basica contra fuerza bruta: tras 5 intentos fallidos seguidos
 * con el mismo correo, ese correo queda bloqueado 5 minutos. Se guarda en memoria.
 */
@Service
public class LoginAttemptService {

    public static final int MAX_ATTEMPTS = 5;
    public static final Duration LOCK_TIME = Duration.ofMinutes(5);

    private record Attempts(int failures, Instant lockedUntil) {
    }

    private final Map<String, Attempts> attempts = new ConcurrentHashMap<>();

    /** Minutos que faltan para desbloquear, o 0 si el correo no esta bloqueado. */
    public long minutesLocked(String email) {
        Attempts current = attempts.get(key(email));
        if (current == null || current.lockedUntil() == null) {
            return 0;
        }
        Duration left = Duration.between(Instant.now(), current.lockedUntil());
        if (left.isNegative() || left.isZero()) {
            attempts.remove(key(email));
            return 0;
        }
        return Math.max(1, (left.getSeconds() + 59) / 60);
    }

    public void registerFailure(String email) {
        attempts.compute(key(email), (k, current) -> {
            int failures = current == null ? 1 : current.failures() + 1;
            Instant lockedUntil = failures >= MAX_ATTEMPTS ? Instant.now().plus(LOCK_TIME) : null;
            return new Attempts(failures, lockedUntil);
        });
    }

    public void registerSuccess(String email) {
        attempts.remove(key(email));
    }

    private static String key(String email) {
        return email == null ? "" : email.trim().toLowerCase(Locale.ROOT);
    }
}

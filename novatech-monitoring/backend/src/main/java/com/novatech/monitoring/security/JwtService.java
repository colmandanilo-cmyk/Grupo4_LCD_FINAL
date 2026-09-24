package com.novatech.monitoring.security;

import com.novatech.monitoring.config.AppProperties;
import com.novatech.monitoring.model.User;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Base64;
import java.util.Date;
import java.util.Optional;

/**
 * Crea y valida los tokens JWT de sesion (firmados con HMAC-SHA256).
 *
 * El secreto de firma se genera al azar en el primer arranque y se guarda en
 * data/jwt-secret.key (junto a la base de datos, fuera de Git). Asi cada
 * instalacion tiene su propio secreto y los tokens sobreviven a un reinicio.
 */
@Service
public class JwtService {

    private static final Logger log = LoggerFactory.getLogger(JwtService.class);

    private final SecretKey key;
    private final int expirationHours;

    public JwtService(AppProperties properties) {
        this.expirationHours = properties.security().jwtExpirationHours();
        Path dataDir = Path.of(properties.db().path()).toAbsolutePath().normalize().getParent();
        this.key = Keys.hmacShaKeyFor(loadOrCreateSecret(dataDir.resolve("jwt-secret.key")));
    }

    /** Token con id, nombre, correo y rol del usuario. */
    public String generate(User user, LocalDateTime expiresAt) {
        Date now = new Date();
        return Jwts.builder()
                .subject(String.valueOf(user.id()))
                .claim("email", user.email())
                .claim("name", user.name())
                .claim("role", user.role().name())
                .issuedAt(now)
                .expiration(Date.from(expiresAt.atZone(ZoneId.systemDefault()).toInstant()))
                .signWith(key)
                .compact();
    }

    public LocalDateTime expirationFromNow() {
        return LocalDateTime.now().withNano(0).plusHours(expirationHours);
    }

    /** Devuelve el id de usuario si el token es valido y no vencio. */
    public Optional<Long> validate(String token) {
        try {
            Claims claims = Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
            return Optional.of(Long.parseLong(claims.getSubject()));
        } catch (JwtException | IllegalArgumentException e) {
            return Optional.empty();
        }
    }

    private static byte[] loadOrCreateSecret(Path file) {
        try {
            if (Files.exists(file)) {
                return Base64.getDecoder().decode(Files.readString(file).trim());
            }
            byte[] secret = new byte[32];
            new SecureRandom().nextBytes(secret);
            Files.createDirectories(file.getParent());
            Files.writeString(file, Base64.getEncoder().encodeToString(secret));
            log.info("Se generó un nuevo secreto para firmar tokens en {}", file);
            return secret;
        } catch (IOException e) {
            throw new UncheckedIOException("No se pudo leer o crear el secreto JWT en " + file, e);
        }
    }
}

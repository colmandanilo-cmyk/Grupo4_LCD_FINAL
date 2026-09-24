package com.novatech.monitoring.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;

/**
 * Autentica a los dispositivos (simulador hoy, equipos reales manana) en /api/ingest/**.
 * Deben enviar la cabecera X-Device-Key con la clave configurada.
 */
public class DeviceKeyFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-Device-Key";

    private final byte[] expectedKey;

    public DeviceKeyFilter(String apiKey) {
        this.expectedKey = apiKey.getBytes(StandardCharsets.UTF_8);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/api/ingest/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String key = request.getHeader(HEADER);
        // Comparacion en tiempo constante para no dar pistas sobre la clave.
        if (key != null && MessageDigest.isEqual(expectedKey, key.getBytes(StandardCharsets.UTF_8))) {
            var authentication = new UsernamePasswordAuthenticationToken("dispositivo", null,
                    List.of(new SimpleGrantedAuthority("ROLE_" + Roles.DISPOSITIVO)));
            SecurityContextHolder.getContext().setAuthentication(authentication);
        }
        chain.doFilter(request, response);
    }
}

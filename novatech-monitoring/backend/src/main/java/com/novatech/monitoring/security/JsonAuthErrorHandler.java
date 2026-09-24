package com.novatech.monitoring.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.novatech.monitoring.exception.GlobalExceptionHandler;
import com.novatech.monitoring.exception.GlobalExceptionHandler.ApiError;
import com.novatech.monitoring.repository.SqlUtils;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.access.AccessDeniedHandler;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/** Respuestas 401 (sin sesion) y 403 (sin permiso) en el mismo formato JSON que el resto de errores. */
public class JsonAuthErrorHandler implements AuthenticationEntryPoint, AccessDeniedHandler {

    private final ObjectMapper objectMapper;

    public JsonAuthErrorHandler(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response, AuthenticationException ex)
            throws IOException {
        String message = request.getRequestURI().startsWith("/api/ingest/")
                ? "Clave de dispositivo ausente o incorrecta (cabecera X-Device-Key)"
                : "Debe iniciar sesión. Su sesión no existe o expiró";
        write(response, request, HttpStatus.UNAUTHORIZED, message);
    }

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, AccessDeniedException ex)
            throws IOException {
        write(response, request, HttpStatus.FORBIDDEN, "Su rol no tiene permiso para realizar esta acción");
    }

    private void write(HttpServletResponse response, HttpServletRequest request, HttpStatus status, String message)
            throws IOException {
        ApiError body = new ApiError(SqlUtils.now(), status.value(), GlobalExceptionHandler.errorTitle(status), message,
                request.getRequestURI(), null);
        response.setStatus(status.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        objectMapper.writeValue(response.getOutputStream(), body);
    }
}

package com.novatech.monitoring.service;

import com.novatech.monitoring.dto.UserDtos.AssignableUser;
import com.novatech.monitoring.dto.UserDtos.UserCreateRequest;
import com.novatech.monitoring.dto.UserDtos.UserUpdateRequest;
import com.novatech.monitoring.dto.UserDtos.UserView;
import com.novatech.monitoring.exception.ApiException;
import com.novatech.monitoring.model.Role;
import com.novatech.monitoring.model.User;
import com.novatech.monitoring.repository.SqlUtils;
import com.novatech.monitoring.repository.UserRepository;
import com.novatech.monitoring.security.AuthenticatedUser;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Administracion de usuarios (solo administrador). */
@Service
public class UserService {

    private final UserRepository repository;
    private final PasswordEncoder passwordEncoder;
    private final AuditService auditService;

    public UserService(UserRepository repository, PasswordEncoder passwordEncoder, AuditService auditService) {
        this.repository = repository;
        this.passwordEncoder = passwordEncoder;
        this.auditService = auditService;
    }

    public List<UserView> findAll() {
        return repository.findAll().stream().map(UserView::of).toList();
    }

    public List<AssignableUser> assignable() {
        return repository.findAssignable();
    }

    @Transactional
    public UserView create(UserCreateRequest request, AuthenticatedUser admin) {
        String email = normalizeEmail(request.email());
        if (repository.findByEmail(email).isPresent()) {
            throw ApiException.conflict("Ya existe un usuario con el correo " + email);
        }
        checkPassword(request.password());
        long id = repository.insert(request.name().trim(), email, passwordEncoder.encode(request.password()),
                request.role(), true, SqlUtils.now());
        auditService.log(admin.id(), "USUARIO_CREADO", "USER", id, email + " (" + request.role() + ")");
        return UserView.of(get(id));
    }

    @Transactional
    public UserView update(long id, UserUpdateRequest request, AuthenticatedUser admin) {
        User user = get(id);
        String name = request.name() != null ? request.name().trim() : user.name();
        String email = request.email() != null ? normalizeEmail(request.email()) : user.email();
        Role role = request.role() != null ? request.role() : user.role();
        boolean active = request.active() != null ? request.active() : user.active();

        if (!email.equalsIgnoreCase(user.email())) {
            repository.findByEmail(email).filter(other -> !other.id().equals(id)).ifPresent(other -> {
                throw ApiException.conflict("Ya existe un usuario con el correo " + email);
            });
        }
        // Nunca puede quedar el sistema sin un administrador activo.
        boolean wasActiveAdmin = user.role() == Role.ADMINISTRADOR && user.active();
        boolean staysActiveAdmin = role == Role.ADMINISTRADOR && active;
        if (wasActiveAdmin && !staysActiveAdmin && repository.countActiveAdmins() <= 1) {
            throw ApiException.conflict("No se puede desactivar ni cambiar el rol del último administrador activo");
        }
        if (id == admin.id() && !active) {
            throw ApiException.conflict("No puede desactivar su propio usuario");
        }

        List<String> changes = new ArrayList<>();
        if (!name.equals(user.name())) changes.add("nombre");
        if (!email.equalsIgnoreCase(user.email())) changes.add("correo");
        if (role != user.role()) changes.add("rol " + user.role() + " → " + role);
        if (active != user.active()) changes.add(active ? "activado" : "desactivado");
        repository.update(id, name, email, role, active);
        if (request.password() != null && !request.password().isBlank()) {
            checkPassword(request.password());
            repository.updatePassword(id, passwordEncoder.encode(request.password()));
            changes.add("contraseña");
        }
        auditService.log(admin.id(), "USUARIO_ACTUALIZADO", "USER", id,
                email + (changes.isEmpty() ? " (sin cambios)" : ": " + String.join(", ", changes)));
        return UserView.of(get(id));
    }

    private User get(long id) {
        return repository.findById(id).orElseThrow(() -> ApiException.notFound("El usuario " + id + " no existe"));
    }

    private static String normalizeEmail(String email) {
        return email.trim().toLowerCase(Locale.ROOT);
    }

    /** Contrasena: minimo 8 caracteres, con al menos una letra y un numero. */
    private static void checkPassword(String password) {
        if (password == null || password.length() < 8
                || !password.matches(".*[A-Za-z].*") || !password.matches(".*\\d.*")) {
            throw ApiException.badRequest("La contraseña debe tener al menos 8 caracteres, con letras y números");
        }
    }
}

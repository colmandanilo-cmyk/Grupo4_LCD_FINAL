package com.novatech.monitoring.controller;

import com.novatech.monitoring.dto.UserDtos.AssignableUser;
import com.novatech.monitoring.dto.UserDtos.UserCreateRequest;
import com.novatech.monitoring.dto.UserDtos.UserUpdateRequest;
import com.novatech.monitoring.dto.UserDtos.UserView;
import com.novatech.monitoring.security.AuthenticatedUser;
import com.novatech.monitoring.security.Roles;
import com.novatech.monitoring.service.UserService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** /api/users: administracion de usuarios. */
@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    @PreAuthorize(Roles.ADMIN)
    public List<UserView> list() {
        return userService.findAll();
    }

    /** Usuarios activos para elegir responsable de una incidencia. */
    @GetMapping("/assignable")
    @PreAuthorize(Roles.ADMIN_O_SUPERVISOR)
    public List<AssignableUser> assignable() {
        return userService.assignable();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @PreAuthorize(Roles.ADMIN)
    public UserView create(@Valid @RequestBody UserCreateRequest request, @AuthenticationPrincipal AuthenticatedUser user) {
        return userService.create(request, user);
    }

    @PutMapping("/{id}")
    @PreAuthorize(Roles.ADMIN)
    public UserView update(@PathVariable long id, @Valid @RequestBody UserUpdateRequest request,
                           @AuthenticationPrincipal AuthenticatedUser user) {
        return userService.update(id, request, user);
    }
}

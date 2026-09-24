package com.novatech.monitoring.repository;

import com.novatech.monitoring.dto.UserDtos.AssignableUser;
import com.novatech.monitoring.model.Role;
import com.novatech.monitoring.model.User;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de la tabla users. */
@Repository
public class UserRepository {

    private final JdbcTemplate jdbc;

    private static final RowMapper<User> MAPPER = (rs, n) -> new User(
            rs.getLong("id"),
            rs.getString("name"),
            rs.getString("email"),
            rs.getString("password_hash"),
            getEnum(rs, "role", Role.class),
            getBool(rs, "active"),
            getDateTime(rs, "created_at"),
            getDateTime(rs, "last_login_at"));

    public UserRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<User> findById(long id) {
        return jdbc.query("SELECT * FROM users WHERE id = ?", MAPPER, id).stream().findFirst();
    }

    public Optional<User> findByEmail(String email) {
        return jdbc.query("SELECT * FROM users WHERE lower(email) = lower(?)", MAPPER, email).stream().findFirst();
    }

    public List<User> findAll() {
        return jdbc.query("SELECT * FROM users ORDER BY role, name", MAPPER);
    }

    public List<AssignableUser> findAssignable() {
        return jdbc.query("SELECT id, name, role FROM users WHERE active = 1 ORDER BY name",
                (rs, n) -> new AssignableUser(rs.getLong("id"), rs.getString("name"), getEnum(rs, "role", Role.class)));
    }

    public long count() {
        Long total = jdbc.queryForObject("SELECT COUNT(*) FROM users", Long.class);
        return total == null ? 0 : total;
    }

    public long countActiveAdmins() {
        Long total = jdbc.queryForObject(
                "SELECT COUNT(*) FROM users WHERE role = 'ADMINISTRADOR' AND active = 1", Long.class);
        return total == null ? 0 : total;
    }

    public long insert(String name, String email, String passwordHash, Role role, boolean active, LocalDateTime createdAt) {
        return jdbc.queryForObject(
                "INSERT INTO users (name, email, password_hash, role, active, created_at) VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
                Long.class, name, email, passwordHash, role.name(), bool(active), ts(createdAt));
    }

    public void update(long id, String name, String email, Role role, boolean active) {
        jdbc.update("UPDATE users SET name = ?, email = ?, role = ?, active = ? WHERE id = ?",
                name, email, role.name(), bool(active), id);
    }

    public void updatePassword(long id, String passwordHash) {
        jdbc.update("UPDATE users SET password_hash = ? WHERE id = ?", passwordHash, id);
    }

    public void updateLastLogin(long id, LocalDateTime when) {
        jdbc.update("UPDATE users SET last_login_at = ? WHERE id = ?", ts(when), id);
    }
}

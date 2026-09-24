package com.novatech.monitoring.repository;

import com.novatech.monitoring.model.Site;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static com.novatech.monitoring.repository.SqlUtils.*;

/** SQL de la tabla sites. */
@Repository
public class SiteRepository {

    private final JdbcTemplate jdbc;

    private static final RowMapper<Site> MAPPER = (rs, n) -> new Site(
            rs.getLong("id"),
            rs.getString("code"),
            rs.getString("name"),
            rs.getString("client"),
            rs.getString("location"),
            getEnum(rs, "status", Site.Status.class),
            getDate(rs, "installation_date"),
            getDateTime(rs, "created_at"));

    public SiteRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<Site> findAll() {
        return jdbc.query("SELECT * FROM sites ORDER BY code", MAPPER);
    }

    public Optional<Site> findById(long id) {
        return jdbc.query("SELECT * FROM sites WHERE id = ?", MAPPER, id).stream().findFirst();
    }

    public Optional<Site> findByCode(String code) {
        return jdbc.query("SELECT * FROM sites WHERE code = ?", MAPPER, code).stream().findFirst();
    }

    public long insert(String code, String name, String client, String location, Site.Status status,
                       LocalDate installationDate, LocalDateTime createdAt) {
        return jdbc.queryForObject(
                "INSERT INTO sites (code, name, client, location, status, installation_date, created_at) "
                        + "VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
                Long.class, code, name, client, location, status.name(), date(installationDate), ts(createdAt));
    }

    public void update(long id, String code, String name, String client, String location, Site.Status status,
                       LocalDate installationDate) {
        jdbc.update("UPDATE sites SET code = ?, name = ?, client = ?, location = ?, status = ?, installation_date = ? "
                        + "WHERE id = ?",
                code, name, client, location, status.name(), date(installationDate), id);
    }

    public void updateStatus(long id, Site.Status status) {
        jdbc.update("UPDATE sites SET status = ? WHERE id = ?", status.name(), id);
    }
}

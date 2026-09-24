package com.novatech.monitoring;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.security.servlet.UserDetailsServiceAutoConfiguration;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Punto de entrada del backend de NOVA TECH.
 *
 * Al arrancar: crea la base SQLite si no existe (schema.sql), carga los datos
 * iniciales si la base esta vacia (DataSeeder) y publica la API REST en
 * http://localhost:8080/api.
 *
 * Con --novatech.exit-after-init=true solo prepara la base y termina
 * (lo usan install.bat y reset_demo.bat).
 */
// Se excluye el usuario en memoria de Spring: los usuarios estan en la tabla users.
@SpringBootApplication(exclude = UserDetailsServiceAutoConfiguration.class)
@ConfigurationPropertiesScan
@EnableScheduling
public class NovatechApplication {

    public static void main(String[] args) {
        ConfigurableApplicationContext context = SpringApplication.run(NovatechApplication.class, args);
        boolean exitAfterInit = context.getEnvironment()
                .getProperty("novatech.exit-after-init", Boolean.class, false);
        if (exitAfterInit) {
            System.out.println("Base de datos lista. Finalizando (modo exit-after-init).");
            System.exit(SpringApplication.exit(context));
        }
    }
}

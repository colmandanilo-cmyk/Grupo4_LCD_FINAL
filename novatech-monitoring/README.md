# NOVA TECH – Sistema de Monitoreo y Vigilancia para Obras

Proyecto académico. Plataforma web para monitorear estaciones autónomas de vigilancia en obras de construcción: cámaras, energía solar, batería, conectividad Starlink con respaldo 4G, eventos, alertas e incidencias. Como no hay equipos físicos, un simulador en Python hace de dispositivos.

Arquitectura: React (interfaz) · Java con Spring Boot (API y lógica de negocio) · Python (simulador de dispositivos) · SQLite (base de datos).

Este proyecto es independiente del que ocupa la raíz del repositorio y vive completo dentro de esta carpeta.

## Estado

| Etapa | Contenido | Estado |
|---|---|---|
| 1 | Diseño y estructura | Completada: [docs/etapa-1-diseno.md](docs/etapa-1-diseno.md) |
| 2 | Backend Java | Completada: [backend/](backend/) |
| 3 | Simulador Python | Completada: [simulator/](simulator/) |
| 4 | Frontend React | Pendiente |
| 5 | Integración | Pendiente |
| 6 | Pruebas y corrección | Pendiente |
| 7 | Instalación, ejecución, reset y documentación | Pendiente |

## Probar el backend (Etapa 2)

Requiere Java 17 o superior. Desde la carpeta `backend/`:

```
mvnw.cmd -DskipTests package        (Windows)
./mvnw -DskipTests package          (Linux/macOS)
java -jar target/novatech-backend.jar
```

La API queda en http://localhost:8080/api (salud: http://localhost:8080/api/health). La primera vez crea `backend/data/novatech.db` con los datos iniciales. Usuarios: `admin@novatech.local` / `Admin123*`, `supervisor@novatech.local` / `Supervisor123*`, `operador@novatech.local` / `Operador123*`.

## Probar el simulador (Etapa 3)

Requiere Python 3.10 o superior y el backend en marcha. Desde la carpeta `simulator/`:

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt       (Windows)
.venv\Scripts\python main.py
```

En Linux/macOS: `.venv/bin/pip` y `.venv/bin/python`. Pruebas: `python -m unittest discover -s tests -t .`

En la Etapa 7 este archivo se reemplaza por el README completo: instalación en Windows, ejecución, usuarios de prueba, escenarios de simulación, limitaciones y evolución futura.

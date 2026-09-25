# Arquitectura de NOVA TECH

NOVA TECH es una plataforma web para vigilar obras de construcción que tienen una estación autónoma: cámaras, panel solar, batería, antena Starlink y un módem 4G de respaldo. Como el proyecto es académico y no hay equipos físicos, un simulador en Python hace de esos dispositivos. El resto del sistema funciona igual que funcionaría con equipos reales.

Todo corre en una sola computadora con Windows y no usa servicios en la nube, Docker ni colas de mensajes.

## Componentes

| Componente | Tecnología | Dirección | Función |
|---|---|---|---|
| Frontend | React 19 + JavaScript, servido por Vite | http://localhost:5173 | Interfaz del centro de monitoreo |
| Backend | Java 17 + Spring Boot 3.5 | http://localhost:8080/api | API REST, seguridad, reglas de negocio y acceso a datos |
| Simulador | Python 3.10+ con `requests` | Sin puerto: solo hace peticiones | Imita cámaras, panel solar, batería, Starlink y 4G |
| Base de datos | SQLite | `backend/data/novatech.db` | Un archivo que solo abre Java |

```mermaid
flowchart LR
    subgraph Navegador
        FE["Frontend React<br/>localhost:5173"]
    end
    subgraph Backend["Backend Java · Spring Boot · localhost:8080"]
        SEC["security/<br/>JWT, roles, clave de dispositivo"]
        CTRL["controller/<br/>API REST"]
        SVC["service/<br/>reglas de negocio"]
        REPO["repository/<br/>SQL con JdbcTemplate"]
    end
    DB[("SQLite<br/>novatech.db")]
    SIM["Simulador Python<br/>dispositivos virtuales"]
    FE -- "/api/* con JWT, polling 5 s" --> SEC
    SIM -- "/api/ingest/* con X-Device-Key" --> SEC
    SEC --> CTRL --> SVC --> REPO --> DB
```

## Flujo del usuario

La persona que monitorea solo usa el navegador. React nunca accede a la base de datos ni al simulador: todo lo pide a la API de Java.

```mermaid
flowchart TB
    U["Usuario"] --> R["React<br/>pantallas, gráficos, vista CCTV"]
    R -- "HTTP/JSON con token JWT" --> A["API Java<br/>controladores REST"]
    A --> S["Servicios Java<br/>reglas de negocio, alertas, reportes, auditoría"]
    S --> D[("SQLite<br/>novatech.db")]
```

## Flujo de los dispositivos simulados

El simulador ocupa el lugar de los equipos. Envía lecturas crudas (por ejemplo "Starlink fuera de línea" o "batería al 15 %") y Java decide qué significan: qué eventos registrar, qué alertas crear, qué conexión usar y en qué estado queda la obra.

```mermaid
flowchart TB
    P["Simulador Python<br/>cámaras, panel, batería, Starlink, 4G"] -- "POST /api/ingest/telemetry<br/>POST /api/ingest/events<br/>clave X-Device-Key" --> A["API Java"]
    A --> S["IngestService y MonitoringRules"]
    S --> D[("SQLite")]
    A -- "GET /api/ingest/sync<br/>órdenes del laboratorio, pausa y velocidad" --> P
```

## Arquitectura futura con equipos reales

El canal `/api/ingest/*` es el límite entre los dispositivos y el sistema. Para pasar a equipos reales basta con que el controlador de cada estación envíe el mismo JSON que hoy envía Python. El backend, la base de datos y la interfaz no cambian; la marca "DATOS SIMULADOS" desaparece sola porque sale de la columna `simulated` de cada dispositivo.

```mermaid
flowchart TB
    C["Cámaras físicas"] --> GW["Controlador de la estación"]
    PS["Panel solar"] --> GW
    B["Batería"] --> GW
    SL["Starlink"] --> GW
    G4["4G"] --> GW
    GW -- "mismo JSON de /api/ingest" --> A["API Java"]
    A --> N["Sistema NOVA TECH<br/>servicios, SQLite y React"]
```

| Capa | Hoy | Con equipos reales |
|---|---|---|
| Dispositivos | Objetos Python con valores simulados | Equipos instalados en la obra |
| Fuente de datos | El simulador llama a `/api/ingest/telemetry` y `/api/ingest/events` | El controlador de la estación llama a los mismos endpoints |
| Control | `/api/ingest/sync` entrega órdenes del laboratorio | El mismo endpoint entrega inventario y órdenes remotas; el laboratorio se retira |
| Gestión y presentación | Java, SQLite y React | Sin cambios |

## Backend Java por capas

| Paquete | Responsabilidad |
|---|---|
| `security/` | Token JWT de los usuarios, roles, clave `X-Device-Key` de los dispositivos, bloqueo temporal tras varios intentos fallidos |
| `controller/` | Endpoints REST, validación de datos de entrada y permisos con `@PreAuthorize` |
| `service/` | Lógica de negocio. `MonitoringRules` reúne las reglas: estado general, severidades, niveles de batería con histéresis, tabla de contingencia y transiciones de incidencias |
| `repository/` | Consultas SQL con `JdbcTemplate`, una clase por tabla |
| `model/` y `dto/` | Datos del dominio y formas de las respuestas |
| `config/` | Conexión a SQLite, propiedades y carga de datos iniciales (`DataSeeder`) |
| `exception/` | Convierte cualquier error en un JSON con mensaje en español |

## Ciclo normal de funcionamiento

```mermaid
sequenceDiagram
    participant P as Simulador Python
    participant J as Backend Java
    participant DB as SQLite
    participant R as React
    loop cada 2 s
        P->>J: GET /api/ingest/sync
        J-->>P: inventario, pausa y velocidad, órdenes pendientes
    end
    loop cada 5 s, por obra
        P->>J: POST /api/ingest/telemetry
        J->>DB: actualiza site_live_status
        J->>DB: agrega historial cada 60 s o si hubo cambios
        J-->>P: conexión activa y estado general
    end
    loop cada 5 s
        R->>J: GET /api/dashboard/summary (con JWT)
        J->>DB: consultas
        J-->>R: KPIs y datos de gráficos
    end
```

Una orden del laboratorio se refleja en pantalla en pocos segundos: hasta 2 s para que Python la recoja y hasta 5 s para el siguiente refresco del navegador.

## Inicio de sesión y permisos

```mermaid
sequenceDiagram
    actor U as Usuario
    participant R as React
    participant J as Java
    participant DB as SQLite
    U->>R: correo y contraseña
    R->>J: POST /api/auth/login
    J->>DB: busca el usuario por correo
    J->>J: BCrypt compara la contraseña con password_hash
    J->>DB: audit_log LOGIN o LOGIN_FALLIDO
    J-->>R: token JWT, nombre y rol
    R->>R: guarda el token y arma el menú según el rol
    R->>J: GET /api/... con Authorization Bearer
    J->>J: el filtro valida el token y @PreAuthorize el rol
    J-->>R: 200 con datos, o 401 / 403
```

| Rol | Puede |
|---|---|
| ADMINISTRADOR | Todo: obras, dispositivos, usuarios, configuración, laboratorio de simulación, auditoría, alertas, incidencias y reportes |
| SUPERVISOR | Consultar todo, reconocer y resolver alertas, gestionar incidencias y exportar reportes |
| OPERADOR | Consultar obras, cámaras, energía, conectividad y eventos, y reconocer alertas |

La interfaz oculta lo que cada rol no puede usar, pero el control real lo hace el backend: una llamada sin permiso recibe 403.

## Escenario del laboratorio: intrusión

```mermaid
sequenceDiagram
    autonumber
    actor A as Administrador
    participant R as React (Laboratorio)
    participant J as Java
    participant DB as SQLite
    participant P as Simulador Python
    A->>R: SIMULAR INTRUSIÓN en OBRA-001, CAM-002
    R->>J: POST /api/simulation/intrusion
    J->>DB: simulation_commands PENDIENTE y audit_log
    J-->>R: 202 orden registrada
    P->>J: GET /api/ingest/sync
    J->>DB: orden pasa a ENVIADO
    J-->>P: orden INTRUSION para CAM-002
    P->>P: CAM-002 con movimiento, arma el evento
    P->>J: POST /api/ingest/events (INTRUSION_DETECTED)
    J->>J: MonitoringRules da severidad por hora y confirma que genera alerta
    J->>DB: INSERT events y alerts (NUEVA)
    J-->>P: 201 con eventId y alertId
    P->>J: POST /api/ingest/commands/{id}/ack
    P->>J: POST /api/ingest/telemetry con motion = true
    R->>J: polling de estado, alertas y cámaras
    J-->>R: alerta nueva, estado ADVERTENCIA o CRÍTICO, cámara con ALERTA DE INTRUSIÓN
```

## Contingencia Starlink → 4G

```mermaid
sequenceDiagram
    autonumber
    participant P as Simulador Python
    participant J as Java (IngestService)
    participant DB as SQLite
    participant R as React
    P->>J: POST telemetry con starlink OFFLINE y cellular ONLINE
    J->>DB: lee el estado anterior
    J->>J: detecta el cambio ONLINE → OFFLINE
    J->>DB: evento STARLINK_DOWN "Conexión Starlink perdida"
    J->>J: la tabla de contingencia verifica el 4G y elige CELLULAR_4G
    J->>DB: evento CELLULAR_ACTIVATED "Activando respaldo 4G / Conexión restablecida mediante 4G"
    J->>DB: alerta MEDIA "Starlink caído, operando con 4G"
    J->>DB: active_connection = CELLULAR_4G e historial
    J-->>P: activeConnection = CELLULAR_4G
    P->>P: el consumo pasa a módem 4G activo
    R->>J: GET /api/connectivity/sites/1
    J-->>R: CONEXIÓN ACTIVA: 4G DE RESPALDO
```

```mermaid
stateDiagram-v2
    STARLINK --> CELLULAR_4G: Starlink cae y hay 4G
    CELLULAR_4G --> STARLINK: Starlink vuelve
    CELLULAR_4G --> NONE: el 4G también cae
    STARLINK --> NONE: caen ambos a la vez
    NONE --> CELLULAR_4G: vuelve solo el 4G
    NONE --> STARLINK: vuelve Starlink
```

## Seguridad

- Contraseñas guardadas con BCrypt; nunca en texto plano.
- Token JWT firmado con un secreto que se genera al instalar (`backend/data/jwt-secret.key`, fuera de Git) y vence a las 8 horas.
- Los dispositivos se autentican con la cabecera `X-Device-Key`, distinta del login de personas.
- El backend escucha solo en 127.0.0.1: no queda expuesto a la red local.
- Las acciones importantes quedan en la tabla `audit_log`.

## Decisiones principales

| Decisión | Motivo |
|---|---|
| Polling cada 5 segundos en lugar de WebSocket | Más simple y suficiente para un centro de monitoreo; el intervalo se cambia en Configuración |
| SQLite con una sola conexión y modo WAL | No requiere instalar un servidor y evita bloqueos de escritura |
| `JdbcTemplate` en lugar de JPA | Consultas SQL visibles y fáciles de seguir en un proyecto académico |
| El simulador no decide nada | Si Python eligiera la conexión o creara alertas, al cambiar a equipos reales habría que reescribir esa lógica |
| Vista CCTV con escenas ilustradas | No hay video real; las escenas, la hora y los indicadores muestran cómo se vería el monitoreo |

El detalle completo del diseño, con todas las tablas, endpoints y reglas, está en [etapa-1-diseno.md](etapa-1-diseno.md). El modelo de datos está en [database.md](database.md).

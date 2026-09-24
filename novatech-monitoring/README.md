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
| 4 | Frontend React | Completada: [frontend/](frontend/) |
| 5 | Integración | Completada: flujo de demostración de 30 pasos verificado |
| 6 | Pruebas y corrección | Completada: 47 pruebas JUnit, 25 del simulador y el recorrido de demostración |
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

## Probar el frontend (Etapa 4)

Requiere Node.js 20.19 o superior, con el backend en marcha (y, para ver datos en vivo, el simulador). Desde la carpeta `frontend/`:

```
npm install
npm run dev
```

La aplicación queda en http://localhost:5173. Las llamadas a `/api` se redirigen al backend en el puerto 8080, así que no hace falta configurar nada más. Se ingresa con cualquiera de los usuarios de arriba; el menú y los botones cambian según el rol.

## Probar todo junto (Etapa 5)

Con el backend, el simulador y el frontend en marcha, en ese orden, se puede seguir el escenario completo de demostración: iniciar sesión como administrador, entrar a OBRA-001, ejecutar SIMULAR INTRUSIÓN en el Laboratorio, reconocer la alerta, crear una incidencia y resolverla, provocar FALLA STARLINK para ver el paso a 4G, restaurar Starlink, ejecutar BATERÍA CRÍTICA y volver a OPERACIÓN NORMAL. Las órdenes del laboratorio tardan uno o dos segundos en reflejarse.

Si el simulador está apagado, la cabecera muestra "Fuente de datos: desconectada" y las órdenes del laboratorio esperan hasta 2 minutos antes de vencer. Si el backend se detiene, la interfaz muestra el error y se recupera sola cuando vuelve.

## Pruebas (Etapa 6)

En Windows, `run_tests.bat` ejecuta las pruebas del backend (JUnit) y del simulador (unittest) y muestra un resumen. Con el sistema en marcha, `run_tests.bat demo` además recorre por API los 30 pasos del escenario de demostración.

Por separado:

```
cd backend
mvnw.cmd test                                   (Windows; en Linux/macOS: ./mvnw test)

cd simulator
.venv\Scripts\python -m unittest discover -s tests -t .
.venv\Scripts\python tests\check_demo_flow.py    (con backend y simulador en marcha)
```

Las pruebas del backend cubren inicio de sesión, permisos por rol, consulta de obras, eventos y alertas, intrusión, falla de Starlink y cambio a 4G, batería baja y crítica, y el ciclo de alertas e incidencias. Usan una base de datos propia en `backend/target/test-data/`, así que no alteran los datos de la demostración.

En la Etapa 7 este archivo se reemplaza por el README completo: instalación en Windows, ejecución, usuarios de prueba, escenarios de simulación, limitaciones y evolución futura.

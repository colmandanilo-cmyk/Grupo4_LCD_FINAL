# Guía de demostración

Guion para presentar NOVA TECH en unos 15 minutos. Sigue los 30 pasos del escenario de la sección 56 del enunciado y dice qué hacer en cada pantalla y qué debería verse.

## Antes de empezar

1. Ejecutar `reset_demo.bat` el mismo día de la presentación. Así las cuatro obras arrancan en OPERACIÓN NORMAL y los gráficos muestran 24 horas de historial recién generado. Al final pregunta si se inicia la aplicación: responder S.
2. Si la aplicación ya estaba instalada y los datos están limpios, alcanza con `start_app.bat`.
3. Esperar a que se abra el navegador en http://localhost:5173. Deben quedar abiertas tres ventanas: "NOVA TECH - Backend", "NOVA TECH - Simulador" y "NOVA TECH - Frontend". No cerrarlas durante la demostración.
4. Opcional, para confirmar que todo responde: `run_tests.bat demo` recorre los mismos 30 pasos por API en menos de un minuto. Si se usa, conviene ejecutarlo antes de `reset_demo.bat`, porque deja registradas alertas e incidencias de prueba.

Una orden del laboratorio tarda entre 1 y 2 segundos en ejecutarse y la pantalla se actualiza cada 5 segundos. Si algo no aparece de inmediato, esperar un momento antes de repetir la acción.

## Escenario completo (sección 56)

### Ingreso y vista general

| Paso | Qué hacer | Qué se ve |
|---|---|---|
| 1. Ejecutar la aplicación | `start_app.bat` (o `reset_demo.bat` y responder S) | Pantalla de inicio de sesión de NOVA TECH |
| 2. Iniciar sesión como administrador | Correo `admin@novatech.local`, contraseña `Admin123*`, INICIAR SESIÓN. También se puede desplegar "Cuentas de demostración" y elegir la cuenta | Dashboard; arriba a la derecha, "Administrador del Sistema" |
| 3. Ver cuatro obras | Menú Obras | OBRA-001 a OBRA-004 con cliente, ubicación, estado, batería y conexión |
| 4. Ver dashboard completo | Menú Dashboard | Indicadores (obras, cámaras 12/12, disponibilidad, alertas, batería, conectividad), gráficos de cámaras, alertas de 24 horas, batería por obra y conectividad, tabla de obras y últimas alertas |
| 5. Todas las obras comienzan normales | Mirar la columna Estado general y la cabecera | OPERACIÓN NORMAL en las cuatro obras y en la cabecera |

### Centro de control de OBRA-001

| Paso | Qué hacer | Qué se ve |
|---|---|---|
| 6. Entrar a OBRA-001 | Obras, clic en la fila de OBRA-001 | "CENTRO DE CONTROL – EDIFICIO EMPRESARIAL SAN ISIDRO" y el indicador de estado general |
| 7. Visualizar cámaras | Pestaña Cámaras | Cuatro cámaras con hora, señal, FPS y marca REC. De noche las escenas pasan a visión infrarroja. Clic en una cámara abre el detalle |
| 8. Visualizar batería | Pestaña Energía | Panel solar, batería con porcentaje y autonomía, consumo por componente y los gráficos de nivel de batería y generación contra consumo |
| 9. Visualizar Starlink | Pestaña Comunicaciones | "CONEXIÓN ACTIVA: STARLINK", datos de Starlink y del 4G en espera, y latencia de 24 horas |

### Intrusión, alerta e incidencia

| Paso | Qué hacer | Qué se ve |
|---|---|---|
| 10. Abrir el Laboratorio de Simulación | Menú Simulador | Escenarios agrupados, control de simulación y "Simulador conectado" |
| 11. Ejecutar SIMULAR INTRUSIÓN | Obra a simular: OBRA-001. Cámara: Acceso principal. Botón SIMULAR INTRUSIÓN | Aviso "SIMULAR INTRUSIÓN enviado al simulador"; la orden aparece en la Bitácora de órdenes |
| 12. Python genera evento | Mirar la bitácora y la ventana del simulador | La orden pasa a EJECUTADO; la consola del simulador informa la intrusión |
| 13. Java recibe evento | Panel "Eventos recientes de la obra", a la derecha | "Intrusión detectada en Acceso principal…" |
| 14. Java genera alerta | Esperar unos segundos | Aviso emergente de alerta nueva y contador rojo junto a Alertas en el menú |
| 15. SQLite almacena información | Explicar: el evento y la alerta ya están en la base; se puede recargar la página y siguen ahí | La información persiste |
| 16. React muestra la alerta | Menú Alertas | Alerta "Intrusión detectada – Acceso principal", severidad ALTA (07:00 a 17:59) o CRÍTICA (fuera de ese horario), estado NUEVA |
| 17. Cambia el estado general | Mirar la cabecera | ADVERTENCIA si la alerta es ALTA, ESTADO CRÍTICO si es CRÍTICA |
| 18. Usuario reconoce alerta | Botón Reconocer | Estado RECONOCIDA, con usuario y hora |
| 19. Usuario crea incidencia | Botón Crear incidencia. Completar título y descripción, elegir responsable, Crear incidencia | Aviso "Incidencia creada" con su código INC-AAAA-NNNN; la alerta pasa a EN ATENCIÓN |
| 20. Usuario resuelve incidencia | Menú Incidencias, clic en la incidencia. Pasar a EN PROCESO y luego Marcar como RESUELTA. Se puede escribir una observación antes de cada cambio | La incidencia queda RESUELTA y su alerta también; el estado general vuelve a OPERACIÓN NORMAL. Con Cerrar incidencia pasa a CERRADA |

### Contingencia Starlink → 4G

| Paso | Qué hacer | Qué se ve |
|---|---|---|
| 21. Ejecutar FALLA STARLINK | Simulador, obra OBRA-001, FALLA STARLINK | Orden en la bitácora |
| 22. Python coloca Starlink offline | Esperar a que la orden pase a EJECUTADO | La consola del simulador informa Starlink fuera de línea |
| 23. Java detecta el cambio | Eventos recientes de la obra | "CONEXIÓN STARLINK PERDIDA" |
| 24. Sistema activa 4G | Eventos recientes | "ACTIVANDO RESPALDO 4G. CONEXIÓN RESTABLECIDA MEDIANTE 4G" y alerta MEDIA |
| 25. React muestra 4G DE RESPALDO | Obras, OBRA-001, pestaña Comunicaciones | Banner "CONEXIÓN ACTIVA: 4G DE RESPALDO", Starlink OFFLINE y 4G EN USO. En el dashboard, la obra muestra 4G DE RESPALDO y el estado ADVERTENCIA |
| 26. Restaurar Starlink | Simulador, RESTAURAR STARLINK | Orden ejecutada |
| 27. Sistema vuelve a conexión principal | Pestaña Comunicaciones | "CONEXIÓN ACTIVA: STARLINK"; la alerta de Starlink se resuelve sola |

### Batería crítica y cierre

| Paso | Qué hacer | Qué se ve |
|---|---|---|
| 28. Ejecutar BATERÍA CRÍTICA | Simulador, BATERÍA CRÍTICA | La batería de la obra baja a cerca de 15 % |
| 29. Generar alerta | Menú Alertas o pestaña Energía de la obra | Alerta "Batería crítica" de severidad ALTA; la obra en ADVERTENCIA |
| 30. Restaurar operación normal | Simulador, OPERACIÓN NORMAL | Todos los sistemas de la obra se restauran, las alertas de condición se resuelven solas y la cabecera vuelve a OPERACIÓN NORMAL |

## Escenarios adicionales

| Escenario | Qué muestra |
|---|---|
| DETECTAR MOVIMIENTO | Evento informativo sin alerta; la cámara muestra MOVIMIENTO DETECTADO durante 30 segundos |
| DESCONECTAR CÁMARA y RECUPERAR CÁMARA | Cámara SIN SEÑAL, alerta ALTA y cámaras 11/12 en el dashboard; al recuperarla, la alerta se resuelve sola |
| FALLA STARLINK + 4G | Obra sin conectividad, estado SIN CONEXIÓN y alerta CRÍTICA |
| BATERÍA BAJA | Batería cerca de 30 % y alerta MEDIA |
| DÍA NUBLADO | Generación solar reducida; evento informativo sin alerta |
| FALLA PANEL SOLAR | Generación en 0 W y alerta MEDIA |
| RESTAURAR ENERGÍA | Panel y batería vuelven a la normalidad |
| Velocidad x20 | El reloj de la estación avanza 20 veces más rápido: en pocos minutos se ve el ciclo solar y cómo la batería carga de día y se descarga de noche |
| Pausar y Reanudar | Detiene y reanuda la simulación automática de las obras |
| Reiniciar | Devuelve la simulación al estado normal sin borrar el historial |

## Roles

Para mostrar los permisos, cerrar sesión con Salir y entrar con otra cuenta:

- `supervisor@novatech.local` / `Supervisor123*`: ve Alertas, Incidencias y Reportes, pero no Simulador, Usuarios, Configuración ni Auditoría.
- `operador@novatech.local` / `Operador123*`: consulta y reconoce alertas; no resuelve alertas, no ve Incidencias ni Reportes.

Si alguien escribe a mano la dirección de una pantalla que no le corresponde, aparece "Acceso denegado".

## Otras pantallas para mostrar

- Reportes: disponibilidad, alertas, energía, conectividad e incidencias por período (24 horas, 7 días, 30 días o personalizado), con exportación a CSV e impresión o guardado en PDF desde el navegador.
- Auditoría: cada acción de la demostración queda registrada con usuario, fecha y detalle.
- Configuración: umbrales de batería, frecuencia de actualización y de registro de telemetría, y opciones de simulación.

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| La cabecera dice "Fuente de datos: desconectada" | La ventana del simulador se cerró. Ejecutar `stop_app.bat` y luego `start_app.bat` |
| La pantalla dice "No se pudo conectar con el servidor" | El backend se detuvo. Revisar su ventana; `stop_app.bat` y `start_app.bat` lo resuelven. La interfaz se recupera sola cuando vuelve |
| Una obra quedó en un estado raro después de varias pruebas | Simulador, OPERACIÓN NORMAL. Si persiste, `reset_demo.bat` |
| Los gráficos de 24 horas están casi vacíos | La base se creó días atrás y la aplicación estuvo apagada. `reset_demo.bat` genera historial nuevo |
| "El puerto 8080 ya está en uso" al iniciar | La aplicación ya estaba abierta: `stop_app.bat` y volver a iniciar |

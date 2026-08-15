# Radar de Oportunidades en Compras Públicas

De la demanda histórica del Estado a un llamado concreto con sus requisitos.

Curso: Lenguaje de Ciencia de Datos II (4364) · CIBERTEC · Grupo 4

---

## Qué resuelve

Un proveedor que quiere venderle al Estado peruano no puede responder hoy tres
preguntas, aunque toda la información sea pública:

| Pregunta | Pantalla | Fuentes |
|---|---|---|
| ¿Dónde me conviene competir? | Radar de oportunidad | 1 + 2 + 5 |
| ¿Qué está abierto ahora? | Monitor de llamados vigentes | 3 |
| ¿Qué necesito para postular? | Ficha de formalidades | 3 + 4 |

## Fuentes de datos

**1 · OCDS / SEACE (OECE) — demanda histórica y adjudicados.**
Descarga masiva anual `.jsonl.gz` (un proceso por línea JSON). Aporta montos,
procesos, entidades, categorías CUBSO y el RUC **adjudicatario** de cada award.
Licencia CC BY 4.0.

**2 · Ficha Única del Proveedor (OECE) — habilitados.**
Endpoint REST por RUC: `https://eap.oece.gob.pe/perfilprov-bus/1.0/ficha/{RUC}`.
Devuelve el estado real del proveedor en el RNP: `esHabilitado`,
`esAptoContratar` y los capítulos vigentes (`lscIdTipRegVig`). Reemplaza el
proxy por coincidencia de texto anterior: la habilitación deja de estimarse y
pasa a leerse del registro oficial.

**3 · API de releases del OECE — llamados vigentes.**
Endpoint REST `…/api/v1/releasesAfter`, paginación por cursor. Documentado en
el portal del OECE y usado por el colector oficial de la Open Contracting
Partnership. Aporta qué está convocado **hoy**, con cronograma y documentos.

**4 · Catálogo de formalidades — requisitos.**
Dataset curado a partir de la Ley N.º 32069 y su Reglamento (D.S. 009-2025-EF),
con la base legal citada en cada requisito. En `normativa/`.

**5 · Diccionario CUBSO — puente código → capítulo RNP.**
Cada categoría CUBSO pertenece a un capítulo (bienes / servicios / consultor /
ejecutor de obras). Es lo que permite cruzar adjudicados (nivel CUBSO fino) con
habilitados (nivel capítulo). Se lee del Excel oficial del OECE o, por defecto,
se deriva del tipo de objeto observado en OCDS.

## Densidad de oferta: tres planos

La oferta se mide en tres planos, cada uno con su grano y su lectura:

| Plano | Qué dice | Grano |
|---|---|---|
| **Adjudicados** (F1) | quién **ya ganó** en la categoría | categoría CUBSO |
| **Competencia vigente** (F1 × F2) | de esos, cuántos **siguen habilitados** hoy | categoría CUBSO |
| **Habilitados** (F2) | cuán poblada está la puerta de entrada al sector | capítulo RNP |

La variable que ordena el radar es la **competencia vigente**. Es el cruce por
RUC del detalle OCDS contra la Ficha Única del Proveedor, y contesta lo que
ninguna de las dos fuentes contesta sola: de los que ganaron en esta categoría,
cuántos siguen en condiciones de volver a competir.

Cuando vale cero con ganadores históricos mayores que cero, la categoría quedó
**sin adjudicatario vigente**: el rubro tiene demanda y nadie en carrera. Son
852 categorías por S/ 1 440 millones de demanda acumulada, y van a un panel
aparte (`reports/diagnostico_mercados_desiertos_*.csv`) ordenado por demanda.

### Un ratio que se descartó al medirlo

La versión anterior resumía el contraste en un cociente de saturación:
`adjudicados_categoria / habilitados_capitulo`. Se descartó porque divide dos
universos que no son comparables: el numerador se cuenta por categoría CUBSO
(más de treinta mil) y el denominador por capítulo RNP (cuatro). El cociente
quedaba en el orden de 0.0001 para todo el catálogo, con un máximo observado de
0.1774, y no ordenaba nada. Las dos columnas que lo componían siguen
publicadas, de modo que el ratio se puede reconstruir y auditar; lo que no se
hace es presentarlo como señal.

### Piso de mercado

Sin un piso, el índice premia mercados vacíos por diminutos: una categoría
donde el Estado gastó S/ 44 000 en dos años no tiene competencia porque no vale
la pena competir ahí. El criterio principal es la **recurrencia** (al menos 2
procesos) y no el monto, porque la mediana de procesos por categoría es
exactamente 1: ese filtro separa mercados de compras aisladas. El piso
monetario (20 UIT acumuladas) es secundario y descarta lo residual.

De las 30 705 categorías, 12 386 quedan aptas para el ranking. Las demás **no
se borran**: se marcan con `apto_para_ranking = False` y la Data App filtra por
la bandera en su vista por defecto, con opción de desactivarla.

## Trazabilidad: logs y reportes separados

La revisión de la T1 observó que el log grababa datos y resultados. Se corrigió
separando físicamente las dos responsabilidades:

- **`logs/`** — solo eventos: inicio/fin de etapa, duración, estado, código
  HTTP, reintentos, archivos escritos.
- **`reports/`** — todos los números: métricas de calidad, conteos, coberturas
  y tablas de resultados (JSON + CSV).

La separación no depende de la disciplina del programador: el logger instala un
filtro (`FiltroTrazabilidad` en `utils.py`) que **rechaza** cualquier intento
de escribir un DataFrame, Series, ndarray o texto multilínea, y deja constancia
del bloqueo.

## Ejecución

### Automática (recomendada)

Un solo comando corre las siete etapas en el orden correcto:

```bash
python pipeline.py --semanal        # actualización completa
python pipeline.py --diario         # solo lo urgente (convocatorias + maestro)
python pipeline.py --semanal --demo # ensayo sin red
```

El proyecto está preparado para **actualizarse solo todos los días** mediante
el Programador de tareas de Windows o `cron` en un servidor. Dos frecuencias,
según el ritmo real de cada fuente: **diaria** para las convocatorias vigentes
(tienen fecha de cierre) y el año OCDS en curso; **semanal** para la demanda
histórica, la habilitación de proveedores y el diccionario CUBSO. El
orquestador limpia solo los logs de más de 30 días, así que el disco no crece
sin límite. Ver `INSTRUCCIONES_AUTOMATIZACION.md` y `crontab.txt`.

### Manual (etapa por etapa)

```bash
pip install -r requirements.txt

python ingesta_ocds.py               # F1: demanda + adjudicados
python diccionario_cubso.py          # F5: puente CUBSO → capítulo
python ficha_proveedores.py          # F2: habilitación real por RUC (caché)
python consulta_proveedores.py       # densidad: adjudicados + competencia vigente
python monitor_convocatorias.py      # F3: llamados vigentes
python formalidades.py               # F4: requisitos por convocatoria
python calidad.py                    # métricas de calidad de las cinco fuentes
python diagnostico.py                # calidad + validación + maestro transformado
streamlit run app.py                 # Data App (3 pantallas)
```

Todos los módulos de ingesta aceptan `--demo` para correr sin conexión con
datos sintéticos deterministas que respetan la estructura real de las fuentes.

### Sobre la ficha de proveedores (caché incremental)

El detalle OCDS tiene ~30 000 RUC adjudicatarios únicos. A una petición por RUC
con pausa de cortesía, descargar todo de una vez toma horas. Por eso la ficha
usa un **caché incremental reanudable**: cada consulta se guarda y las corridas
siguientes solo piden los RUC que faltan.

```bash
python ficha_proveedores.py --limite 500    # primeras 500 faltantes
python ficha_proveedores.py --limite 0      # todas las faltantes
python ficha_proveedores.py --rucs 10714515590   # RUC puntuales
```

## Mapeo de capítulos RNP: confirmado

El endpoint de la ficha entrega los capítulos como IDs (`"4 1 2"`), y durante
un tiempo el mapeo ID → nombre fue una hipótesis a la espera de la respuesta
del endpoint `grupos`. Quedó confirmado por una vía distinta y mejor: la
columna "Tipo de ítem" del Excel oficial del CUBSO trae la correspondencia
escrita, y coincide con la hipótesis que se venía usando.

| ID | Capítulo | Etiqueta en el proyecto |
|---|---|---|
| 1 | BIENES | `BIENES` |
| 2 | SERVICIOS | `SERVICIOS` |
| 3 | OBRAS | `EJECUTOR_DE_OBRAS` |
| 4 | CONSULTORÍAS DE OBRAS | `CONSULTOR_DE_OBRAS` |

La constante vive en `ficha_proveedores.py` (`CAPITULOS_RNP`) y las hojas del
Excel se mapean en `diccionario_cubso.py` (`HOJAS_OFICIALES`).

## Diccionario CUBSO: oficial más derivado

`diccionario_cubso.py` construye el puente categoría → capítulo de dos formas
que se complementan.

El **Excel oficial** del CUBSO trae una hoja por capítulo, así que la
clasificación no se infiere: viene dada por la estructura del catálogo. Es la
única vía para separar ejecución de obra de consultoría de obra, distinción
que el OCDS no hace (su `mainProcurementCategory` solo distingue goods,
services y works) y que en el RNP son capítulos con requisitos distintos.

El **modo derivado** infiere el capítulo desde el propio detalle OCDS. Cubre
las categorías cuya descripción no calza literal con el título del catálogo
(abreviaturas, lotes, variantes de redacción), que el catálogo oficial dejaría
sin clasificar.

Por defecto se usan los dos: oficial donde la descripción coincide, derivado
donde no. La columna `origen` deja ver cuál alimentó cada fila, de modo que la
precisión del cruce sea un dato del reporte y no una estimación. Si el Excel
está en `normativa/cubso_oficial.xlsx`, el módulo lo detecta sin necesidad de
banderas, para que la corrida automática del pipeline también se beneficie.

```bash
python diccionario_cubso.py                  # detecta el Excel si está presente
python diccionario_cubso.py --solo-oficial   # sin completar con lo derivado
```

El Excel se descarga desde gob.pe/oece, sección "Publicaciones del SEACE",
opción "Documentos de orientación (SEACE)", filtrando por CUBSO. Pesa unos
34 MB descomprimido y su lectura toma cerca de dos minutos, razón por la cual
el diccionario es una etapa semanal y no diaria.

## Estructura

```
radar-oportunidades/
├── pipeline.py                # orquestador: corre todo en orden (--diario/--semanal)
├── config.py                  # rutas, endpoints y parámetros
├── utils.py                   # logger con filtro anti-datos, cronómetro, reportes, limpieza
├── ingesta_ocds.py            # F1: demanda + adjudicados
├── ficha_proveedores.py       # F2: habilitación real por RUC (caché incremental)
├── diccionario_cubso.py       # F5: puente CUBSO → capítulo RNP (Excel oficial + derivado)
├── consulta_proveedores.py    # densidad: adjudicados + competencia vigente
├── monitor_convocatorias.py   # F3: llamados vigentes
├── formalidades.py            # F4: ficha de requisitos por convocatoria
├── calidad.py                 # seis métricas de calidad de datos (T3)
├── transformacion.py          # enriquecimiento, binning y escalado (T4)
├── validacion.py              # esquemas Pandera y reglas de negocio (T4)
├── diagnostico.py             # orquesta calidad → validación → integración → transformación
├── wrangling_radar_oportunidades.ipynb   # notebook de wrangling sobre los datos del proyecto
├── app.py                     # Data App en Streamlit (3 pantallas)
├── ejecutar_diario.bat        # lo dispara el Programador de tareas (Windows)
├── ejecutar_semanal.bat       #   idem, actualización completa
├── crontab.txt                # diseño de despliegue en servidor (Linux)
├── INSTRUCCIONES_AUTOMATIZACION.md
├── normativa/
│   └── formalidades_catalogo.json
├── data/{raw,processed,checkpoints}/
├── logs/                      # trazabilidad (sin datos)
└── reports/                   # métricas y resultados (JSON + CSV)
```

## Transformación y gobernanza de datos

La etapa de transformación está separada en tres módulos que `diagnostico.py`
encadena en orden. El orden importa: se mide antes de validar, y se valida
antes y después de transformar.

**`calidad.py` — mide.** Las seis métricas del Tema 3 aplicadas a las cinco
fuentes: completitud, unicidad, validez, consistencia, exactitud y actualidad.
Nunca rechaza una fila; devuelve porcentajes que se comparan entre corridas
para detectar si una fuente se degradó. La métrica de actualidad es la que más
riesgo cubre en este proyecto: el pipeline puede correr sin un solo error y
estar publicando datos de hace un año porque la fuente dejó de replicarse.

**`transformacion.py` — enriquece, discretiza y escala.** Variables derivadas
del propio dataset (incluida la estacionalidad, que sale de la columna `fecha`
del OCDS y antes se descartaba al agregar); binning con `pd.cut` sobre cortes
anclados en la UIT y `pd.qcut` sobre cuartiles empíricos; y el índice de
oportunidad, que combina demanda (55 %) y espacio de mercado (45 %) en un
potencial y lo multiplica por la accesibilidad del ticket, en una escala de 0 a
100. La accesibilidad multiplica y no suma: un mercado enorme al que una MYPE
no puede entrar no es una oportunidad grande, es una oportunidad nula.

Sobre el escalado hay una decisión que conviene poder defender: se usa Min-Max
sobre `log1p(demanda)`, no Z-Score. La demanda por categoría CUBSO tiene cola
muy larga, así que el Min-Max crudo le da 1.0 a la mayor y aplasta al resto
contra el cero (en la corrida de referencia, el 97 % de las categorías queda
por debajo de 0.05). El Z-Score aguanta mejor la cola pero devuelve valores
negativos y sin cota, que no se interpretan en un tablero. El logaritmo previo
comprime la cola y deja el resultado acotado en [0,1]. El Z-Score igual se
calcula, como variable de diagnóstico para marcar categorías atípicas. Las tres
alternativas se comparan con números en el reporte de cada corrida.

**`validacion.py` — decide.** Esquemas Pandera por dataset (tipos, nulabilidad,
unicidad, rangos) más reglas de coherencia entre columnas que ningún esquema
por columna puede ver. Corre en modo `lazy` para juntar todos los fallos en una
pasada. El pipeline se detiene solo si el porcentaje de filas rechazadas supera
la tolerancia, porque una fuente pública con 0,3 % de registros mal formados es
normal y abortar por eso sería frágil.

### Vectorización

Ningún módulo de la ruta de datos itera fila por fila: no hay un `iterrows()`,
un `itertuples()` ni un `apply(axis=1)` en todo el pipeline. Las métricas de
calidad son máscaras booleanas sobre columnas completas, las agregaciones son
`groupby`, y las asignaciones condicionales usan `np.where` o indexación por
máscara. El notebook incluye una auditoría que lo comprueba sobre el código
fuente, más un benchmark que mide el costo de hacerlo mal.

Los bucles que quedan son de otra naturaleza: `optimizar_memoria()` recorre
columnas (unas veinte iteraciones sobre metadatos, no cientos de miles sobre
datos); la ingesta recorre líneas del `.jsonl.gz`, que es lectura por streaming
y es justamente la técnica de chunking; y los módulos de red recorren páginas
de API, donde el costo lo domina la latencia HTTP.

### Validaciones en el log

La separación logs / reports no significa que el log calle sobre las
validaciones. Significa que registra **qué se comprobó y cómo salió**, que es un
evento, y no **qué valor concreto falló**, que es un dato y va al CSV de
`reports/`. Un log que solo dijera "validación OK" no permitiría distinguir si
pasó porque los datos estaban bien o porque el esquema no comprobaba nada, así
que `validacion.py` registra primero las reglas de cada columna y después el
resultado, con una línea por regla incumplida:

```
REGLAS     | dataset=maestro_oportunidades | columna=indice_oportunidad | tipo=float64 | nullable=False | checks=in_range
VALIDACION | dataset=maestro_oportunidades | estado=CON_FALLOS | reglas_fallidas=4 | filas_afectadas=4 | pct=2.40
VALIDACION | dataset=maestro_oportunidades | columna=banda_competencia | regla=isin([...]) | casos=1
NEGOCIO    | regla=ticket_promedio_coherente | violaciones=0 | estado=OK
CALIDAD    | dataset=ocds_procesos | metrica=completitud | global=98.72% | columnas_incompletas=3
```

### Notebook de wrangling

`wrangling_radar_oportunidades.ipynb` documenta la etapa completa sobre los
datos del proyecto. Importa las funciones de los módulos en lugar de
reescribirlas: si el código estuviera duplicado, cualquier corrección en el
pipeline dejaría al notebook mintiendo. Donde hace falta ver la lógica, la
celda la muestra con `inspect.getsource()`.

## Limitaciones declaradas

- La habilitación se lee de la Ficha Única del Proveedor (dato real del RNP), a
  nivel de capítulo, que es el nivel al que el RNP habilita.
- Los adjudicados son proveedores que ganaron al menos una vez; no incluyen a
  quienes participaron sin ganar.
- La competencia vigente solo cubre las categorías cuyos adjudicatarios tienen
  RUC de once dígitos. Consorcios y personas naturales bajo otro formato no
  cruzan contra el padrón y se etiquetan "Competencia no determinada", no como
  mercado vacío.
- **Desfase de publicación del monitor.** La API de releases del OECE no
  publica los procedimientos en tiempo real. Al cierre de esta entrega los
  releases más recientes correspondían a junio de 2026, mientras el buscador
  del SEACE ya mostraba procesos de julio. El monitor refleja el estado de la
  API, no el del SEACE, y eso se declara en la ficha metodológica de la app.
- La categoría CUBSO de una convocatoria se toma del primer ítem clasificado.
- La ficha de formalidades es orientativa: los requisitos exigibles son los de
  las bases integradas de cada procedimiento.

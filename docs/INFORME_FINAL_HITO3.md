# Informe final — Hito 3

**Proyecto:** Pipeline ETL y dashboard de indicadores EPH · Aglomerado 18 (Santiago del Estero - La Banda)
**Entidad:** Dirección General de Estadística y Censos (DGEyC) — Santiago del Estero
**Equipo:** Achaval María José · Cabaña Emilio · Constantinidi Leandro · Gomez Cinthia · Pinto Villegas Eduardo
**Cátedra:** Práctica Profesionalizante II · ITSE 2026
**Versión del pipeline:** 3.0.0 · **Fecha:** julio de 2026
**Dashboard:** <https://pipeline-eph-dgeyc-sde.streamlit.app/>
**Repositorio:** <https://github.com/Emvcab/Pipeline-EPH-DGEyC>

---

## 1. Introducción

El proyecto automatiza el procesamiento de los microdatos públicos de la Encuesta Permanente de Hogares (EPH) del INDEC para el Aglomerado 18, que reúne a las ciudades de Santiago del Estero y La Banda. A partir de los archivos que el INDEC publica cada trimestre, el sistema descarga, valida, integra y calcula indicadores del mercado laboral, mantiene un histórico acumulado de 12 períodos (2023T1 a 2025T4) y los presenta en un dashboard pensado para usuarios no técnicos de la DGEyC.

El producto tiene dos componentes: el pipeline (`src/pipeline.py`), que produce los archivos de datos con sus metadatos y controles, y el dashboard (`notebooks/app.py`), que muestra únicamente resultados que superaron la validación.

## 2. Problema institucional abordado

Cada publicación trimestral del INDEC obliga a repetir una secuencia de tareas: descargar los archivos comprimidos, identificar las bases de personas y hogares, filtrar el aglomerado local, aplicar el ponderador muestral y calcular las tasas e ingresos. Hecho a mano, ese proceso insume horas, depende de quién lo ejecuta y no deja registro de qué controles se aplicaron.

El pipeline reduce esa carga operativa y agrega lo que el proceso manual no tenía: validaciones previas a la publicación de resultados, trazabilidad de cada corrida, metadatos que documentan cada archivo exportado y un registro del estado de cada período. No reemplaza los procedimientos internos de la Dirección; ordena y documenta el tratamiento de la información pública.

## 3. Qué se había presentado en el Hito 2

El Hito 2 entregó el pipeline ETL en su versión 2.0: descarga automática desde el sitio del INDEC, filtrado del Aglomerado 18, cálculo de tasas e ingresos ponderados por `PONDERA`, histórico acumulado, suite inicial de tests y documentación técnica. La entidad recibió el repositorio y lo evaluó.

Entre el Hito 2 y el cierre actual se sumaron dos versiones intermedias que respondieron de forma directa a la devolución: la 2.1.0 incorporó metadatos automáticos para cada CSV y la 2.2.0 agregó el calendario de publicaciones y la validación de esquema contra cambios del INDEC.

## 4. Devolución recibida de la entidad

La DGEyC valoró el diseño del pipeline y su documentación, y consideró cumplido el objetivo técnico. A la vez dejó recomendaciones concretas, que resumimos así:

1. Adaptar el producto a usuarios no técnicos.
2. Acompañar cada archivo exportado con metadatos que lo hagan usable por terceros.
3. Incorporar un calendario asociado a las publicaciones del INDEC, con auditoría y disponibilización de cada nuevo reporte.
4. Prever contingencias ante cambios de nombres, variables, formatos o fallas de extracción, advirtiendo el error antes de que llegue al usuario final.
5. Documentar estados por período y diferenciar la importancia de cada carga (Load).
6. Reconocer cuellos de botella, métricas de ejecución y posibilidades de extensión con nuevas variables.
7. Mantener contacto con el área operativa de EPH y otros usuarios institucionales.

## 5. Mejoras realizadas para el Hito 3 (versión 3.0.0)

**Indicadores comparables con las publicaciones oficiales.** Las tasas principales se calculan ahora sobre la población total, que es el denominador que usa el INDEC en sus informes técnicos: `tasa_actividad_oficial`, `tasa_empleo_oficial`, `tasa_desocupacion` y su complemento `proporcion_inactiva_total`. Las tasas calculadas sobre la población de 10 años y más se conservan con nombres explícitos (`tasa_actividad_10_mas`, `tasa_empleo_10_mas`, `tasa_inactividad_10_mas`). La migración renombra las columnas históricas sin cambiar su significado en silencio: ningún valor previo se altera, solo queda identificado por lo que siempre fue.

**Ciclo de estados por período.** Cada trimestre atraviesa un ciclo registrado en `estado_periodos.csv`: `PENDIENTE`, `DESCARGADO`, `PROCESADO`, `EN_REVISION`, `VALIDADO`, `FALLIDO` o `PUBLICADO`, con fecha esperada de publicación, fecha de detección, cantidad de intentos y un mensaje entendible del último control.

**Controles críticos previos a la publicación.** Antes de promover resultados se verifica: presencia del Aglomerado 18 en ambas bases, población expandida positiva, ausencia de períodos duplicados, tasas dentro del rango 0-100, complementariedad entre actividad y proporción inactiva, desocupación calculable, cantidad mínima razonable de filas, existencia de todos los archivos con sus metadatos y coherencia del indicador de informalidad con la disponibilidad de la variable `EMPLEO`. El resultado queda en `validacion_publicacion_<periodo>.json`.

**Carga transaccional.** Las salidas se construyen en una carpeta temporal y se promueven solo si superan todos los controles. Si un período falla, queda marcado `FALLIDO` con su mensaje y no se reemplaza ni el histórico ni el snapshot vigente. La descarga también es atómica: un archivo parcial o corrupto se descarta en lugar de quedar bloqueando corridas futuras.

**Robustez de extracción.** Se valida el estado HTTP, que el ZIP no esté vacío y sea un ZIP real, se controlan las rutas internas al descomprimir, se identifican las bases individual y hogar por nombre con búsqueda recursiva, y la lectura prueba cuatro combinaciones de separador y codificación. La validación de esquema distingue faltantes críticos (detienen el proceso antes de generar resultados) de faltantes opcionales (se informan y se continúa).

**Metadatos completos y manifiesto.** Cada salida se acompaña de un `.meta.json` y el conjunto queda descripto en `manifest_salidas.json` (ver sección 8).

**Dashboard institucional.** Cinco secciones orientadas a la lectura no técnica, con advertencias metodológicas visibles y descarga de datos, metadatos y guías (ver sección 6).

**Snapshot agregado para la nube.** `data_snapshot/` contiene solo información agregada y validada: histórico, indicadores por período, control de calidad agregado, estados, validaciones, manifiesto y documentación. No incluye ZIP, microdatos individuales ni bases unidas. Se actualiza con el comando `--publicar-snapshot`, que se niega a publicar si el último período no está validado y conserva el snapshot anterior ante cualquier falla.

**Pruebas.** La suite creció a **50 tests**, que verifican fórmulas, migración de nombres, rangos, metadatos, manifiesto, bloqueo de publicación, conservación del snapshot y rutas relativas. Escriben solo en directorios temporales. Resultado de la validación final: 50 aprobados.

## 6. Dashboard publicado y finalidad

El dashboard está publicado en <https://pipeline-eph-dgeyc-sde.streamlit.app/> y también puede ejecutarse localmente. Su finalidad es que una persona sin formación técnica pueda responder tres preguntas: cuál es la situación del mercado laboral del aglomerado en el último trimestre validado, cómo evolucionó desde 2023 y qué confiabilidad tiene el dato que está mirando.

Secciones:

| Sección | Contenido |
|---|---|
| Resumen ejecutivo | Último período validado, estado de validación, fecha de actualización, tasas principales, muestra y población expandida, informalidad |
| Evolución laboral | Series de actividad y empleo oficiales, desocupación, proporción inactiva e informalidad |
| Ingresos | Ingreso promedio ponderado, mediano y no respuesta de ingresos, con advertencia de nominalidad |
| Calidad y auditoría | Estados por período, calidad de variables, cambios de esquema y controles lógicos, con metadatos descargables |
| Documentación y descargas | Histórico, indicadores, estado de períodos, metadatos, manifiesto, diccionario de datos, guía de uso y metodología |

El tablero solo muestra períodos con estado `VALIDADO` o `PUBLICADO`. Usa los resultados locales si su último período está validado; en caso contrario recurre al snapshot agregado del repositorio, y lo indica en pantalla.

## 7. Validaciones aplicadas

En orden de ejecución:

1. **Descarga**: estado HTTP verificado, ZIP no vacío y estructuralmente válido; los archivos parciales se descartan.
2. **Extracción**: control de rutas internas del ZIP e identificación explícita de las bases individual y hogar.
3. **Lectura**: cuatro combinaciones de separador y codificación, con verificación de columnas mínimas.
4. **Esquema**: columnas obligatorias y opcionales por base; un faltante crítico detiene el período antes de generar resultados y queda registrado en `validacion_esquema_<periodo>.json`.
5. **Publicación**: los nueve controles críticos descriptos en la sección 5, registrados en `validacion_publicacion_<periodo>.json`.
6. **Snapshot**: rechazo de históricos vacíos, duplicados o con tasas fuera de rango; conservación del snapshot anterior si algo falla.
7. **Suite automatizada**: 50 tests sobre fórmulas, controles y publicación.

## 8. Metadatos y manifiesto de salidas

Cada archivo exportado tiene un `nombre_archivo.meta.json` con: descripción y clasificación de la carga, fuente y organismo productor, URL de origen del trimestre, aglomerado, período, fecha y hora de generación, versión del pipeline, cantidad de filas y columnas, definición de cada variable, tipos de datos, unidades, fórmulas de los indicadores, filtros aplicados, ponderador utilizado, conteo de nulos, códigos especiales, advertencias metodológicas, marca de ingresos nominales, estado de validación, última ejecución exitosa, archivo de origen, identificador de ejecución y hash SHA-256 para verificar integridad.

`manifest_salidas.json` relaciona cada salida con su clasificación, su período, su estado de validación y su archivo de metadatos:

| Salida | Clasificación |
|---|---|
| `historico_SDE.csv` | Crítica |
| `indicadores_SDE_<periodo>.csv` | Analítica |
| `base_unida_SDE_<periodo>.csv` (solo local) | Analítica |
| `calidad_datos_SDE_<periodo>.csv` · `calidad_snapshot_SDE.csv` | Calidad |
| `validacion_esquema_<periodo>.json` · `validacion_publicacion_<periodo>.json` · `estado_periodos.csv` | Auditoría |
| Registros de `logs/` | Operativa |
| Manifiesto y documentación (`.md`) | Disponibilización |

## 9. Advertencias metodológicas

- **Ingresos nominales.** Todos los valores monetarios están en pesos argentinos corrientes, sin deflactar. No representan variaciones de poder adquisitivo; cualquier comparación real exige descontar la inflación del período.
- **Informalidad no disponible en 2023T1, 2023T2 y 2023T3.** La variable `EMPLEO`, necesaria para estimarla, existe en los microdatos públicos desde 2023T4. En los tres primeros trimestres el indicador se presenta como no disponible.
- **Sin imputación de faltantes.** Los valores ausentes y los códigos especiales (-9, -8, -7) se cuentan y se informan; no se imputan ni se reemplazan por cero.
- **Alcance territorial.** El Aglomerado 18 representa de manera conjunta a Santiago del Estero y La Banda. Los microdatos públicos no permiten desagregar por ciudad.
- **Carácter de los resultados.** Los indicadores se calculan a partir de microdatos públicos del INDEC mediante el ponderador `PONDERA`. No constituyen una nueva estadística oficial provincial ni sustituyen procedimientos institucionales.
- **Dos familias de tasas.** Las tasas "oficiales" usan la población total como denominador y son las comparables con los informes técnicos del INDEC; las tasas "10_mas" usan la población de 10 años y más y sirven para análisis específicos. Para el 4T2025, por ejemplo, la actividad oficial es 41,23% y la específica de 10 años y más es 46,06%. Ambas conviven en el histórico con nombres explícitos.
- **Indicadores operativos de campo.** Los microdatos públicos solo incluyen entrevistas realizadas, de modo que la tasa de no respuesta de hogares observada no mide el rechazo real de campo. Ese tipo de indicador requiere bases internas de la DGEyC y una definición institucional previa.
- **Documento antecedente.** El reporte ejecutivo en PDF elaborado antes de esta versión (`Reporte_Ejecutivo_EPH_SDE_4T2025.pdf`) se conserva solo como antecedente: usa la denominación anterior de las tasas y cifras de una corrida previa, y no es el documento vigente. Las referencias actuales son este informe y [METODOLOGIA.md](METODOLOGIA.md); por eso el dashboard no lo ofrece entre sus descargas.

## 10. Por qué no se implementó Machine Learning productivo

El Hito 3 se resuelve con el dashboard institucional: era la necesidad expresada por la entidad (adaptar el producto a usuarios no técnicos y asegurar la calidad de lo que se publica) y es lo que este cierre entrega validado.

Machine Learning queda como línea futura por dos razones verificables:

1. **No hay una necesidad institucional concreta definida.** Ninguna de las recomendaciones de la devolución requiere un modelo predictivo; piden metadatos, calendario, contingencias, estados y comunicación no técnica. Definir un problema que justifique un modelo exige las reuniones con el área operativa que el propio roadmap propone.
2. **No hay una variable objetivo robusta.** El candidato natural, la no respuesta de ingresos, suma menos de 150 casos positivos en los tres años relevados, alrededor del 2% de los ocupados de la muestra. Con ese volumen y desbalance, un modelo produciría conclusiones frágiles que no corresponde presentar como producto institucional.

Si en el futuro la Dirección define un problema concreto, hay líneas exploratorias razonables: caracterización de la informalidad a nivel persona (la clase es frecuente y la muestra lo permite), análisis descriptivo de la no respuesta de ingresos con técnicas estadísticas clásicas, o reglas de detección de anomalías sobre los indicadores agregados, que en parte ya están implementadas como controles de publicación. Cualquiera de ellas exigirá tratamiento del ponderador, validación temporal y revisión metodológica antes de usarse.

## 11. Conclusión

El cierre del Hito 3 entrega un sistema que descarga, valida y publica indicadores del mercado laboral del Aglomerado 18 con trazabilidad completa: cada archivo sale acompañado de metadatos, cada período tiene un estado registrado, y ningún resultado llega al dashboard sin pasar los controles críticos. Las siete recomendaciones de la devolución institucional quedaron incorporadas o documentadas: metadatos y manifiesto, calendario y estados, contingencias con bloqueo de publicación, clasificación de cargas, dashboard para usuarios no técnicos, y advertencias metodológicas explícitas en datos y pantalla.

Quedan como trabajo futuro las métricas de rendimiento por etapa, los indicadores operativos de campo (condicionados a bases internas de la entidad), la deflactación de ingresos y la eventual línea analítica avanzada, cuando exista un problema institucional que la justifique. El detalle operativo está en [MANUAL_TECNICO_PIPELINE.md](MANUAL_TECNICO_PIPELINE.md), la guía de lectura del tablero en [MANUAL_USUARIO_DASHBOARD.md](MANUAL_USUARIO_DASHBOARD.md) y las definiciones de cálculo en [METODOLOGIA.md](METODOLOGIA.md).

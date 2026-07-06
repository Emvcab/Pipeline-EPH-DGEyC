# Diccionario de Datos

> Descripción completa de los archivos que produce el pipeline ETL

**Proyecto:** Pipeline ETL — EPH Santiago del Estero
**Fuente:** Microdatos públicos del INDEC — Encuesta Permanente de Hogares
**Aglomerado:** 18 (Santiago del Estero — La Banda)

---

## Estructura general de salida

El pipeline genera **3 carpetas** y **4 tipos de archivos**:

```
Pipeline_EPH_DGEyC/
├── data/        Microdatos crudos del INDEC (ZIPs descargados)
├── results/     Archivos procesados → SE USAN PARA REPORTES
└── logs/        Registros de cada corrida (para diagnóstico)
```

### Resumen de archivos en `results/`

| Archivo | Cantidad | Frecuencia |
|---|---|---|
| `historico_SDE.csv` | 1 (acumulado) | Se actualiza con cada corrida |
| `indicadores_SDE_<periodo>.csv` | 1 por trimestre | Una vez por trimestre procesado |
| `calidad_datos_SDE_<periodo>.csv` | 1 por trimestre | Una vez por trimestre procesado |
| `base_unida_SDE_<periodo>.csv` | 1 por trimestre | Una vez por trimestre procesado |

Con 12 trimestres procesados (2023-2025) se generan **37 archivos** en total (1 histórico + 12×3).

---

## 1. `historico_SDE.csv` — Archivo principal

**Estructura:** 1 fila por trimestre × ~30 columnas
**Codificación:** UTF-8
**Separador:** coma (,)
**Tamaño aproximado:** 12 filas con todos los trimestres procesados

Este es el archivo más importante. Contiene todos los indicadores calculados para todos los trimestres procesados, listo para cargar en dashboards, enviar a otras instituciones o usar en informes.

### Columnas

#### Identificación (4 columnas)

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `anio` | int | Año del trimestre | `2025` |
| `trimestre` | int | Número de trimestre (1 a 4) | `4` |
| `periodo` | str | Período en formato AÑOTtrim | `"2025T4"` |
| `aglomerado` | int | Código del aglomerado (siempre 18) | `18` |

#### Muestra (2 columnas)

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `n_personas_muestra` | int | Personas relevadas en la muestra del aglomerado | `1411` |
| `n_hogares_muestra` | int | Hogares relevados en la muestra del aglomerado | `415` |

#### Población expandida (6 columnas)

Estos valores son la población **real estimada** que representa la muestra, aplicando los ponderadores oficiales del INDEC.

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `poblacion_expandida_total` | int | Población total representada por la muestra | `420976` |
| `poblacion_expandida_mayor10` | int | Población de 10 años o más representada | `376817` |
| `pea_expandida` | int | Población Económicamente Activa (ocupados + desocupados) | `173558` |
| `ocupados_expandidos` | int | Personas ocupadas representadas | `172461` |
| `desocupados_expandidos` | int | Personas desocupadas representadas | `1097` |
| `inactivos_expandidos` | int | Personas inactivas representadas | `203259` |

#### Tasas del mercado laboral (5 columnas)

Todas en porcentaje (0-100), con dos decimales.

| Columna | Tipo | Descripción | Fórmula | Ejemplo |
|---|---|---|---|---|
| `tasa_actividad` | float | % de personas ≥10 años que trabajan o buscan trabajo | PEA / Población ≥10 × 100 | `46.06` |
| `tasa_empleo` | float | % de personas ≥10 años que efectivamente trabajan | Ocupados / Población ≥10 × 100 | `45.77` |
| `tasa_desocupacion` | float | % de la PEA que busca trabajo y no encuentra | Desocupados / PEA × 100 | `0.63` |
| `tasa_inactividad` | float | % de personas ≥10 años que no trabajan ni buscan | Inactivos / Población ≥10 × 100 | `53.94` |
| `tasa_informalidad` | float / null | % de ocupados sin aportes ni registro | Ocupados con EMPLEO=2 / Ocupados con EMPLEO válido × 100 | `55.21` |

> ⚠️ **Importante:** `tasa_informalidad` es `null` en los trimestres 1T2023, 2T2023 y 3T2023 porque la variable `EMPLEO` no existía en los microdatos del INDEC antes del 4T2023.

#### Ingresos (6 columnas)

Valores en pesos argentinos nominales (sin deflactar). El INDEC los actualiza trimestre a trimestre.

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `ingreso_promedio_observado` | float | Promedio simple del ingreso de ocupación principal (sin ponderar) | `752462` |
| `ingreso_mediano_observado` | float | Mediana del ingreso de ocupación principal | `700000` |
| `ingreso_promedio_ponderado_observado` | float | Promedio ponderado por PONDERA — **valor metodológicamente correcto** | `789090` |
| `n_ocupados_con_ingreso_valido` | int | Cantidad de ocupados que declararon ingreso > 0 | `589` |
| `n_ocupados_sin_respuesta_ingreso` | int | Cantidad de ocupados con P21 = -9 (no respondió) | `11` |
| `tasa_no_respuesta_ingresos_ocupados` | float | % de ocupados que no respondieron su ingreso | `1.83` |

#### Operativos del relevamiento (2 columnas)

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `hogares_encuestados` | int | Hogares con entrevista efectivamente completada (REALIZADA=1) | `415` |
| `tasa_no_respuesta_hogar` | float | % de hogares que no completaron la entrevista | `0.0` |

> ⚠️ **Nota:** En los microdatos públicos del INDEC, todos los hogares tienen `REALIZADA = 1` porque solo se publican los relevamientos efectivos. La tasa de rechazo real requiere datos internos de la DGEyC.

#### Trazabilidad (2 columnas)

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `fecha_procesamiento` | str | Fecha y hora exacta del procesamiento | `"2026-06-26 14:38:21"` |
| `fuente` | str | Fuente de los datos | `"INDEC - EPH microdatos públicos"` |

---

## 2. `indicadores_SDE_<periodo>.csv`

**Estructura:** 1 fila × las mismas columnas que `historico_SDE.csv`
**Ejemplo de nombre:** `indicadores_SDE_2025T4.csv`

Contiene los mismos indicadores que el histórico, pero solo del trimestre específico. Sirve para:
- Entregas individuales por trimestre
- Anexos de informes puntuales
- Verificar el cálculo de un período específico

Las columnas son **idénticas** a las del histórico.

---

## 3. `calidad_datos_SDE_<periodo>.csv`

**Estructura:** 6 filas × 6 columnas
**Ejemplo de nombre:** `calidad_datos_SDE_2025T4.csv`

Reporta la calidad de cada variable clave del trimestre. Permite detectar problemas en los datos del INDEC sin tener que abrirlos manualmente.

### Columnas

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `columna` | str | Nombre de la variable evaluada | `"P21"` |
| `nulos` | int | Cantidad de valores nulos / vacíos | `0` |
| `codigo_-9_no_resp` | int | Cantidad de valores con código -9 (no respondió) | `11` |
| `codigo_-8` | int | Cantidad de valores con código -8 (no sabe) | `0` |
| `codigo_-7` | int | Cantidad de valores con código -7 (otro código especial) | `0` |
| `validos` | int | Cantidad de valores numéricos válidos | `589` |

### Variables que se evalúan

Las 6 variables clave del análisis: `ESTADO`, `EMPLEO`, `P21`, `PONDERA`, `CH04`, `CH06`.

---

## 4. `base_unida_SDE_<periodo>.csv`

**Estructura:** ~1.400 filas × ~330 columnas
**Ejemplo de nombre:** `base_unida_SDE_2025T4.csv`

Contiene los **microdatos individuales** del trimestre (1 fila por persona) con los **datos del hogar** correspondiente agregados como columnas adicionales. La unión se hace mediante las claves `CODUSU + NRO_HOGAR`.

Sirve para análisis avanzados a nivel persona — por ejemplo, estudiar quiénes no respondieron sus ingresos cruzando con características del hogar (vivienda, servicios, etc.).

### Columnas

Combina **todas las columnas de la base individual del INDEC** (~235) con **todas las de la base hogar** (~98), eliminando duplicados de claves. Las columnas del hogar que tienen el mismo nombre que las individuales aparecen con sufijo `_hog`.

Para el detalle completo de las variables de cada base, consultar el **manual de diseño de registros del INDEC** que acompaña cada trimestre.

---

## Notas sobre valores nulos

El pipeline **no imputa valores faltantes** — esa es una decisión metodológica deliberada del análisis exploratorio. Los nulos aparecen en estas situaciones:

| Situación | Cuándo aparece | Acción del pipeline |
|---|---|---|
| `tasa_informalidad` nula | Trimestres anteriores a 4T2023 | Se reporta como nulo (la variable EMPLEO no existía) |
| Código `-9` en P21 | Ocupado que se negó a declarar ingreso | Se cuenta en `n_ocupados_sin_respuesta_ingreso` |
| Códigos `-8`, `-7` | Casos especiales del INDEC | Se cuentan en `calidad_datos_SDE_*.csv` |
| Valores no numéricos en columnas numéricas | Formato variable del INDEC | Se convierten a nulo con `pd.to_numeric(errors='coerce')` |

---

## Cómo usar estos archivos

### Para reportes oficiales
Usar `historico_SDE.csv` — abre directo en Excel, LibreOffice o cualquier herramienta de visualización.

### Para auditoría
Cruzar `calidad_datos_SDE_<periodo>.csv` con los valores del histórico para validar que los cálculos son coherentes con la calidad de los datos.

### Para análisis estadístico avanzado
Cargar `base_unida_SDE_<periodo>.csv` en Python/R y analizar a nivel de persona u hogar.

### Para envío a INDEC nacional o gobierno provincial
El histórico tiene formato CSV estándar, abrible en cualquier software. Se puede convertir a Excel con `pd.read_csv()` y `.to_excel()`.

---

## Versión del diccionario

| Versión | Fecha | Notas |
|---|---|---|
| 1.0 | 2026-06-26 | Versión inicial del diccionario |

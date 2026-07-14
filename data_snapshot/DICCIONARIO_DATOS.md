# Diccionario de datos

**Fuente:** Encuesta Permanente de Hogares — microdatos públicos del INDEC
**Ámbito:** Aglomerado 18 — Santiago del Estero - La Banda
**Ponderador:** `PONDERA`

## Histórico e indicadores trimestrales

`historico_SDE.csv` contiene una fila por período validado. `indicadores_SDE_<periodo>.csv` contiene la misma estructura para un único trimestre.

| Variable | Tipo | Definición / fórmula | Unidad |
|---|---|---|---|
| `anio` | entero | Año del relevamiento | año |
| `trimestre` | entero | Trimestre 1 a 4 | trimestre |
| `periodo` | texto | Formato `AAAATn` | período |
| `aglomerado` | entero | Código 18 | código |
| `n_personas_muestra` | entero | Personas observadas | personas de muestra |
| `n_hogares_muestra` | entero | Hogares observados | hogares de muestra |
| `poblacion_expandida_total` | entero | Suma de `PONDERA` de todas las personas del aglomerado | personas expandidas |
| `poblacion_expandida_mayor10` | entero | Suma de `PONDERA` con `CH06 >= 10` | personas expandidas |
| `pea_expandida` | entero | Suma de `PONDERA` con `ESTADO` 1 o 2 | personas expandidas |
| `ocupados_expandidos` | entero | Suma de `PONDERA` con `ESTADO = 1` | personas expandidas |
| `desocupados_expandidos` | entero | Suma de `PONDERA` con `ESTADO = 2` | personas expandidas |
| `inactivos_expandidos` | entero | Suma de `PONDERA` con `ESTADO = 3` | personas expandidas |
| `tasa_actividad_oficial` | decimal | PEA expandida / población total expandida × 100 | porcentaje |
| `tasa_empleo_oficial` | decimal | ocupados expandidos / población total expandida × 100 | porcentaje |
| `tasa_desocupacion` | decimal | desocupados expandidos / PEA expandida × 100 | porcentaje |
| `proporcion_inactiva_total` | decimal | 100 - `tasa_actividad_oficial` | porcentaje |
| `tasa_actividad_10_mas` | decimal | PEA expandida / población de 10 años y más expandida × 100 | porcentaje |
| `tasa_empleo_10_mas` | decimal | ocupados expandidos / población de 10 años y más expandida × 100 | porcentaje |
| `tasa_inactividad_10_mas` | decimal | inactivos expandidos / población de 10 años y más expandida × 100 | porcentaje |
| `tasa_informalidad` | decimal o nulo | EMPLEO=2 ponderado / EMPLEO válido 1 o 2 ponderado × 100 | porcentaje |
| `ingreso_promedio_observado` | decimal o nulo | Promedio simple de `P21 > 0` entre ocupados | pesos nominales |
| `ingreso_mediano_observado` | decimal o nulo | Mediana de `P21 > 0` entre ocupados | pesos nominales |
| `ingreso_promedio_ponderado_observado` | decimal o nulo | suma(`P21 × PONDERA`) / suma(`PONDERA`) con `P21 > 0` | pesos nominales |
| `n_ocupados_con_ingreso_valido` | entero | Ocupados de muestra con `P21 > 0` y ponderador válido | personas de muestra |
| `n_ocupados_sin_respuesta_ingreso` | entero | Ocupados de muestra con `P21 = -9` | personas de muestra |
| `tasa_no_respuesta_ingresos_ocupados` | decimal | casos `P21 = -9` / ocupados de muestra × 100 | porcentaje |
| `hogares_encuestados` | entero | Registros de hogar con `REALIZADA = 1` | hogares publicados |
| `tasa_no_respuesta_hogar` | decimal | `REALIZADA = 0` / hogares publicados × 100 | porcentaje observado |
| `fecha_procesamiento` | texto | Fecha y hora de cálculo | fecha-hora |
| `fuente` | texto | Identificación del origen | texto |

`proporcion_inactiva_total` es un indicador complementario. Incluye por complemento a toda la población fuera de la PEA y no debe confundirse con `tasa_inactividad_10_mas`.

### Migración de nombres

| Nombre anterior | Nombre actual | Motivo |
|---|---|---|
| `tasa_actividad` | `tasa_actividad_10_mas` | El denominador anterior era población de 10 años y más |
| `tasa_empleo` | `tasa_empleo_10_mas` | El denominador anterior era población de 10 años y más |
| `tasa_inactividad` | `tasa_inactividad_10_mas` | El denominador anterior era población de 10 años y más |

## Calidad de datos

`calidad_datos_SDE_<periodo>.csv` informa por variable: `columna`, `nulos`, `codigo_-9_no_resp`, `codigo_-8`, `codigo_-7`, `validos` y `variable_disponible`. Cuando una variable no existe, sus conteos permanecen nulos. No se reemplazan por cero.

`calidad_snapshot_SDE.csv` contiene controles lógicos agregados cuando el dashboard funciona sin microdatos: población positiva, tasas en rango, complementariedad, duplicados y disponibilidad de informalidad. No reemplaza los conteos detallados del ETL.

## Estado de períodos

`estado_periodos.csv` contiene `periodo`, `fecha_esperada`, `fecha_deteccion`, `fecha_procesamiento_estado`, `intentos`, `estado`, `mensaje` y `ultima_actualizacion`.

Estados: `PENDIENTE`, `DESCARGADO`, `PROCESADO`, `EN_REVISION`, `VALIDADO`, `FALLIDO` y `PUBLICADO`.

## Metadatos

Todo CSV se acompaña por un archivo homónimo `.meta.json`. Incluye nombre, descripción, clasificación, fuente, organismo productor, URL, aglomerado, período, fecha, versión, dimensiones, variables, definiciones, tipos, unidades, fórmulas, filtros, ponderador, nulos, códigos especiales, advertencias, indicador de ingresos nominales, estado, última ejecución exitosa, archivo de origen, identificador de ejecución y SHA-256.

## Reglas de faltantes y alcance

- No se imputan faltantes.
- No se reemplazan faltantes por cero.
- En `2023T1`, `2023T2` y `2023T3`, la variable necesaria para estimar informalidad no está disponible. Por ese motivo, `tasa_informalidad` se presenta como no disponible y no se realiza imputación ni se reemplazan faltantes por cero.
- Los ingresos son nominales y requieren deflactación para comparaciones reales.
- El Aglomerado 18 no permite separar Santiago Capital de La Banda.
- `REALIZADA` en los microdatos públicos no permite medir por sí sola el rechazo de campo.

# Arquitectura técnica del pipeline

> Decisiones de diseño y organización interna del código

---

## Filosofía de diseño

El pipeline está construido siguiendo el principio **menos es más** (KISS - Keep It Simple, Stupid). Optamos deliberadamente por **un archivo único bien organizado** en lugar de modularización en múltiples archivos.

### ¿Por qué archivo único?

| Criterio | Archivo único | Modular |
|---|---|---|
| Tamaño del proyecto (~400 líneas) | ✅ Apropiado | ❌ Ingeniería excesiva |
| Mantenibilidad por usuario no-developer | ✅ Lee de arriba abajo | ❌ Salta entre archivos |
| Portabilidad | ✅ Un archivo se comparte fácil | ❌ Estructura compleja |
| Cantidad de desarrolladores activos | ✅ 1-4 personas | ❌ Equipo grande |

La modularización tendría sentido si superáramos las ~1000 líneas o si varios equipos tocaran el código en paralelo. No es nuestro caso.

---

## Modelo ETL clásico

El pipeline sigue el patrón **Extract → Transform → Load** con un paso adicional de **Report**:

```
        ┌─────────────────────────────────────────┐
        │              EXTRACCIÓN                  │
        │   descargar_zip() → extraer_zip() →     │
        │         leer_archivo_eph()               │
        └─────────────┬───────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────────────────┐
        │            TRANSFORMACIÓN                │
        │  filtrar_sde() → calcular_indicadores() │
        │  reporte_calidad() → unir_bases()       │
        └─────────────┬───────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────────────────┐
        │                CARGA                     │
        │           guardar_trimestre()            │
        └─────────────┬───────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────────────────┐
        │               REPORTE                    │
        │   imprimir_resumen() + archivo .log      │
        └─────────────────────────────────────────┘
```

---

## Organización interna del código

El archivo `pipeline.py` está dividido en **8 secciones** delimitadas por comentarios visuales:

| # | Sección | Líneas aprox. | Responsabilidad |
|---|---|---|---|
| 1 | CONFIGURACIÓN | ~15 | Constantes globales |
| 2 | LOGGING | ~20 | Configuración de logs |
| 3 | EXTRACCIÓN | ~80 | Descarga, descompresión, lectura |
| 4 | TRANSFORMACIÓN | ~120 | Cálculo de indicadores |
| 5 | CALIDAD/UNIÓN | ~30 | Reportes auxiliares |
| 6 | CARGA | ~40 | Guardado de archivos |
| 7 | ORQUESTACIÓN | ~60 | Coordinación del flujo |
| 8 | ENTRADA | ~40 | CLI con argparse |

---

## Decisiones técnicas clave

### Lectura robusta de archivos

El INDEC ocasionalmente varía el separador y la codificación entre trimestres. En lugar de asumir un único formato, probamos **4 combinaciones** hasta encontrar la correcta:

```python
LECTURAS = [
    {"sep": ";", "encoding": "utf-8"},
    {"sep": ";", "encoding": "latin1"},
    {"sep": ",", "encoding": "utf-8"},
    {"sep": ",", "encoding": "latin1"},
]
```

### Manejo de variables ausentes

La variable `EMPLEO` no existe antes del 4T2023. En lugar de fallar con `KeyError`, verificamos su existencia y devolvemos `None` para la tasa de informalidad en esos trimestres:

```python
if "EMPLEO" in ocupados.columns:
    # calcular
else:
    tasa_inf = None
```

### División por cero segura

Implementamos una función auxiliar `porcentaje()` que maneja el caso de denominador cero devolviendo `None` en lugar de lanzar excepción.

### Histórico sin duplicados

Al actualizar el histórico, si el período ya existe lo eliminamos antes de agregar la nueva versión. Esto permite reprocesar un trimestre sin generar duplicados.

```python
hist = hist[hist["periodo"] != periodo]
hist = pd.concat([hist, df_ind], ignore_index=True)
```

### Búsqueda recursiva en ZIPs

Algunos ZIPs del INDEC anidan los archivos en subcarpetas. Usamos `Path.rglob()` para encontrarlos sin importar la profundidad:

```python
ind = next((p for p in destino.rglob("*.txt") if "individual" in p.name.lower()), None)
```

---

## Logging estructurado

Reemplazamos `print` por logging profesional con dos handlers simultáneos:

1. **Consola** — para feedback inmediato durante la ejecución
2. **Archivo** — para trazabilidad y diagnóstico posterior

Cada corrida genera un archivo `logs/pipeline_YYYYMMDD_HHMMSS.log` independiente.

---

## Manejo de errores

Cada función maneja sus excepciones específicas:

- `requests.RequestException` → fallo de descarga
- `zipfile.BadZipFile` → ZIP corrupto
- `UnicodeDecodeError, pd.errors.ParserError` → formato de archivo no esperado
- `Exception` genérica solo en el orquestador, con `log.exception()` para capturar el stack trace completo

---

## Convenciones de código

- **Type hints** completos en firma de funciones
- **Docstrings** en una línea concisa para cada función
- **Constantes** en `MAYUSCULAS_CON_GUION_BAJO`
- **Funciones** en `minusculas_con_guion_bajo` (snake_case)
- **Líneas** no exceden 100 caracteres
- **Imports** organizados: stdlib → terceros → locales

---

## Extensibilidad

Para agregar un nuevo indicador, basta con:

1. Calcular el valor en `calcular_indicadores()`
2. Agregarlo al diccionario que devuelve la función
3. (Opcional) Agregarlo al resumen impreso en `imprimir_resumen()`

La nueva columna aparece automáticamente en `historico_SDE.csv` sin tocar nada más.

Para agregar un nuevo año al procesamiento masivo, solo se modifica la constante `ANIOS` en la sección de configuración.

---

## Testing

La suite de tests en `tests/test_pipeline.py` valida:

- Funciones puras (cálculo de porcentaje, manejo de divisiones por cero)
- Lógica de filtrado por aglomerado
- Estructura del diccionario de indicadores

No se testea la descarga ni la lectura de archivos reales (eso requiere infraestructura del INDEC).

# Manual técnico del pipeline

**Versión del pipeline:** 3.0.0 · **Python:** 3.10 o superior
**Repositorio:** <https://github.com/Emvcab/Pipeline-EPH-DGEyC>

Este manual describe la operación técnica del sistema: instalación, ejecución, salidas, validaciones, manejo de fallas y actualización del snapshot. Reemplaza como referencia vigente al manual anterior en formato Word, que describe la estructura de carpetas de una versión previa. Las definiciones de cálculo están en [METODOLOGIA.md](METODOLOGIA.md) y el detalle de columnas en [DICCIONARIO_DATOS.md](DICCIONARIO_DATOS.md).

---

## 1. Estructura del repositorio

```text
Pipeline-EPH-DGEyC/
├── src/pipeline.py            Pipeline ETL, validaciones, estados y publicación
├── notebooks/app.py           Dashboard Streamlit
├── notebooks/eda_eph_sde.py   Análisis exploratorio complementario
├── tests/test_pipeline.py     Suite automatizada (50 tests)
├── requirements.txt           Dependencias
├── data/                      ZIP y TXT descargados (excluidos de Git)
├── results/                   Salidas locales del pipeline (excluidas de Git)
├── logs/                      Un archivo de registro por corrida (excluidos de Git)
├── data_snapshot/             Agregados validados, versionados para Streamlit Cloud
└── docs/                      Documentación del proyecto
```

`data/`, `results/` y `logs/` se crean solos al ejecutar. Lo único versionado con datos es `data_snapshot/`, que contiene exclusivamente agregados validados: histórico, indicadores por período, calidad agregada, estados, validaciones, manifiesto y guías. Nunca microdatos individuales.

## 2. Instalación

```bash
git clone https://github.com/Emvcab/Pipeline-EPH-DGEyC.git
cd Pipeline-EPH-DGEyC
python -m venv .venv
```

Activar el entorno e instalar dependencias.

En Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

En Linux o macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 3. Ejecución del pipeline

Siempre desde la raíz del repositorio:

```bash
# Un trimestre puntual
python src/pipeline.py --anio 2025 --trimestre 4

# Un año completo
python src/pipeline.py --anio 2024

# Todo el período configurado (2023-2025)
python src/pipeline.py --todos

# Volver a descargar un ZIP ya existente
python src/pipeline.py --anio 2025 --trimestre 4 --forzar

# Calendario de publicaciones del INDEC y estado de cada período
python src/pipeline.py --calendario

# Actualizar data_snapshot/ con el último resultado validado
python src/pipeline.py --publicar-snapshot
```

Cada corrida escribe un registro con marca de tiempo en `logs/`. Para incorporar un año nuevo al modo `--todos`, agregarlo a la constante `ANIOS` al inicio de `src/pipeline.py`.

## 4. Tests

```bash
python -m pytest tests -q
```

Resultado esperado: **50 passed**. Las pruebas escriben únicamente en directorios temporales del sistema; no tocan `data/`, `results/` ni `data_snapshot/`. Cubren fórmulas e indicadores, migración de nombres de tasas, rangos, metadatos y manifiesto, bloqueo de publicación ante controles fallidos, conservación del snapshot y rutas relativas.

## 5. Dashboard local

```bash
python -m streamlit run notebooks/app.py
```

Se abre en el navegador (por defecto en el puerto 8501). Selección de fuente de datos: si `results/` tiene un histórico cuyo último período figura `VALIDADO` o `PUBLICADO` en `estado_periodos.csv`, usa esos resultados; si no, usa `data_snapshot/`; si ninguna fuente está validada, lo informa y no muestra indicadores. En Streamlit Cloud, el archivo principal configurado es `notebooks/app.py`.

## 6. Archivos que genera

Por cada trimestre procesado quedan en `results/`:

| Archivo | Contenido | Clasificación |
|---|---|---|
| `indicadores_SDE_<periodo>.csv` | Fila única con los indicadores del trimestre | Analítica |
| `calidad_datos_SDE_<periodo>.csv` | Nulos y códigos especiales (-9, -8, -7) por variable clave | Calidad |
| `base_unida_SDE_<periodo>.csv` | Microdatos individual + hogar unidos por `CODUSU` y `NRO_HOGAR`; nunca se publica en el snapshot | Analítica |
| `validacion_esquema_<periodo>.json` | Columnas obligatorias y opcionales presentes o faltantes | Auditoría |
| `validacion_publicacion_<periodo>.json` | Resultado de los controles críticos | Auditoría |
| `historico_SDE.csv` | Histórico acumulado, un registro por trimestre, sin duplicados | Crítica |
| `estado_periodos.csv` | Ciclo de estados de cada período | Auditoría |
| `manifest_salidas.json` | Inventario de salidas con clasificación y metadatos asociados | Disponibilización |

Cada salida tiene su `nombre_archivo.meta.json` con descripción, clasificación, fuente, período, estructura, definiciones, unidades, fórmulas, filtros, ponderador, nulos, advertencias, estado de validación y hash SHA-256.

## 7. Validaciones que aplica

1. **Descarga**: verificación del estado HTTP; el contenido baja a un archivo temporal `.part` que solo se promueve si no está vacío y es un ZIP válido.
2. **Extracción**: control de rutas internas del comprimido (se rechazan rutas fuera del destino) e identificación de las bases individual y hogar; si falta una, el período no continúa.
3. **Lectura**: cuatro combinaciones de separador y codificación; se exige que `AGLOMERADO` exista como columna y que haya una cantidad mínima de columnas.
4. **Esquema**: contra listas de columnas obligatorias y opcionales por base. Faltante obligatorio: nivel `critico`, el período se detiene antes de calcular. Faltante opcional (caso típico: `EMPLEO` antes de 2023T4): nivel `advertencia`, se continúa y el indicador afectado queda nulo.
5. **Publicación** (controles críticos, todos deben cumplirse): Aglomerado 18 presente en ambas bases; población expandida positiva; histórico sin períodos duplicados; todas las tasas entre 0 y 100; actividad oficial más proporción inactiva igual a 100 (tolerancia 0,02); desocupación calculable cuando hay PEA; mínimos de 100 personas y 30 hogares en muestra; todos los archivos y metadatos generados y no vacíos; informalidad nula cuando `EMPLEO` no está disponible.
6. **Snapshot**: antes de publicar se rechazan históricos vacíos, con duplicados o con tasas fuera de rango.

## 8. Manejo de errores y contingencias

El principio general: ningún resultado se promueve sin validación, y una falla nunca destruye lo último válido.

| Situación | Comportamiento |
|---|---|
| URL inexistente o falla de conexión | Error registrado, período `FALLIDO`, el resto del lote continúa |
| Descarga interrumpida | El `.part` se descarta; no queda un ZIP corrupto bloqueando la próxima corrida |
| ZIP vacío o inválido | Se detecta antes de extraer; período `FALLIDO` |
| Cambio de nombre de archivos internos | Si no se identifican individual y hogar, el período se detiene con mensaje claro |
| Cambio de separador o codificación | Se prueban los cuatro formatos conocidos antes de declarar la falla |
| Columna obligatoria faltante | Detención previa al cálculo, detalle en `validacion_esquema_<periodo>.json` |
| Aglomerado 18 ausente | Detención con error explícito |
| Valores fuera de rango o inconsistentes | La validación de publicación marca el período `FALLIDO` y no promueve archivos |
| Falla al escribir salidas | Construcción en carpeta temporal con respaldo y reversión: el histórico y el snapshot previos quedan intactos |
| Último período no validado | `--publicar-snapshot` se niega y conserva el snapshot anterior |

Diagnóstico ante una falla, en orden: 1) mensaje de `estado_periodos.csv`; 2) último archivo de `logs/`; 3) `validacion_esquema_<periodo>.json` y `validacion_publicacion_<periodo>.json`; 4) corregir y reprocesar el trimestre; 5) confirmar que el estado quedó `VALIDADO`.

## 9. Actualización del snapshot ante un nuevo trimestre

Cuando el INDEC publica un trimestre nuevo (el cronograma aproximado se consulta con `--calendario`):

1. Procesarlo: `python src/pipeline.py --anio <año> --trimestre <n>`.
2. Verificar en `results/estado_periodos.csv` que el período quedó `VALIDADO` y revisar `validacion_publicacion_<periodo>.json`.
3. Revisar los indicadores generados (`indicadores_SDE_<periodo>.csv` y su `.meta.json`).
4. Ejecutar `python src/pipeline.py --publicar-snapshot`. El comando reconstruye `data_snapshot/` desde el histórico validado (histórico, indicadores por período, calidad agregada, estados, validaciones, guías y manifiesto), excluye microdatos y, si algo falla a mitad de camino, deja el snapshot anterior tal como estaba.
5. Revisar el diff de `data_snapshot/`, confirmar los cambios en Git y subirlos a la rama que usa el despliegue. Streamlit Cloud reconstruye la aplicación automáticamente al recibir el push; no hay que publicar nada a mano.

Si el trimestre pertenece a un año nuevo, antes del paso 1 agregar el año a `ANIOS` en `src/pipeline.py` (y acompañarlo de una corrida de tests).

## 10. Cómo incorporar un nuevo indicador

Procedimiento para agregar un indicador al pipeline sin romper la coherencia entre datos, metadatos y documentación. No requiere reestructurar el sistema; sí requiere completar todos los pasos, porque un indicador sin metadata o sin pruebas queda fuera del estándar del proyecto.

1. **Definir el indicador antes de tocar el código**: objetivo, población de referencia (por ejemplo, ocupados, población total, hogares) y denominador exacto. Dejar la definición escrita; las ambigüedades de denominador son la fuente de error más costosa.
2. **Incorporar el cálculo en `calcular_indicadores()`** (`src/pipeline.py`), siguiendo el patrón existente: subpoblaciones con conversión numérica explícita, suma de `PONDERA` para expandir y la función `porcentaje()` para tasas, que ya maneja denominadores no positivos.
3. **Registrar el nombre en los diccionarios del módulo**: descripción en `DICCIONARIO_COLUMNAS`, fórmula en `FORMULAS_INDICADORES` y unidad en `UNIDADES`. Con eso, la metadata del CSV documenta el indicador de forma automática.
4. **Definir el tratamiento de nulos y de variables opcionales**: si la variable de origen puede faltar en algunos trimestres, el indicador debe quedar nulo en esos períodos (como hace `tasa_informalidad` con `EMPLEO`), nunca imputarse ni reemplazarse por cero. Si corresponde, sumar la variable de origen al esquema opcional.
5. **Agregar pruebas automatizadas** en `tests/test_pipeline.py`: el valor esperado con datos de ejemplo, el caso de variable ausente y el rango válido. Si el indicador es una tasa, incorporarlo a los controles de rango de la validación de publicación.
6. **Verificar que el indicador llegue al CSV y a su metadata**: aparece solo en las salidas al regenerar; confirmar que el `.meta.json` lo describa con definición, fórmula y unidad (paso 3 mediante).
7. **Regenerar manifiesto y snapshot**: reprocesar los períodos afectados y ejecutar `--publicar-snapshot` tras la validación, para que histórico, indicadores por período, metadatos y hashes queden coherentes.
8. **Sumarlo al dashboard solo si tiene utilidad institucional**: el tablero muestra un conjunto reducido a propósito. Un indicador de control interno puede vivir en el CSV y la metadata sin ocupar pantalla.
9. **Documentar limitaciones metodológicas**: actualizar `METODOLOGIA.md` y `DICCIONARIO_DATOS.md`, incluyendo desde qué período existe el dato, advertencias de interpretación y, si aplica, la nota de nominalidad.

## 11. Notas operativas

- Las rutas del código son relativas a la raíz del repositorio; el sistema funciona en Windows, Linux y macOS sin ajustes.
- El dashboard no descarga datos del INDEC ni escribe registros: solo lee archivos ya validados.
- `requirements.txt` incluye lo necesario para pipeline, tests, análisis y dashboard. En un despliegue, conviene revisar periódicamente la compatibilidad de la versión de Streamlit instalada por la plataforma.
- El repositorio incluye una configuración de contenedor de desarrollo (`.devcontainer/`) que instala dependencias y levanta el dashboard, útil para GitHub Codespaces.

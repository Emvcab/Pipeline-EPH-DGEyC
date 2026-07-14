# Pipeline EPH — Santiago del Estero

Sistema para descargar, integrar, validar y calcular indicadores trimestrales a partir de microdatos públicos de la Encuesta Permanente de Hogares (EPH) del INDEC para el **Aglomerado 18 — Santiago del Estero - La Banda**.

El snapshot validado cubre **12 períodos**, desde `2023T1` hasta `2025T4`.

**Entregado a:** Dirección General de Estadística y Censos (DGEyC) — Santiago del Estero
**Desarrollado por:** Práctica Profesionalizante II · ITSE 2026
**Grupo:** Achaval María José · Cabaña Emilio · Constantinidi Leandro · Gomez Cinthia · Pinto Villegas Eduardo

## Alcance

El proyecto automatiza las tareas necesarias para descargar, integrar, validar y calcular indicadores trimestrales a partir de microdatos públicos. Aplica `PONDERA`, conserva valores faltantes, produce metadatos y bloquea resultados que no superan los controles críticos.

El Hito 3 se presenta mediante un dashboard institucional para usuarios no técnicos. Machine Learning podrá evaluarse en una etapa posterior, una vez definido un problema institucional concreto, con datos suficientes y validación metodológica.

El Aglomerado 18 representa conjuntamente Santiago del Estero y La Banda. Los microdatos públicos no permiten separar ambas ciudades ni evaluar encuestadores o personal de carga.

## Indicadores

Indicadores principales:

- `tasa_actividad_oficial` = PEA expandida / población total expandida × 100.
- `tasa_empleo_oficial` = ocupados expandidos / población total expandida × 100.
- `tasa_desocupacion` = desocupados expandidos / PEA expandida × 100.
- `proporcion_inactiva_total` = 100 - tasa de actividad oficial. Es complementaria.

Indicadores específicos de población de 10 años y más:

- `tasa_actividad_10_mas`.
- `tasa_empleo_10_mas`.
- `tasa_inactividad_10_mas`.

Los nombres anteriores `tasa_actividad`, `tasa_empleo` y `tasa_inactividad` correspondían al denominador de 10 años y más. La migración los renombra explícitamente y no cambia su significado en silencio.

Los ingresos son nominales. No representan directamente variaciones del poder adquisitivo y requieren deflactación para comparaciones reales. En `2023T1`, `2023T2` y `2023T3`, la variable necesaria para estimar informalidad no está disponible. Por ese motivo, el indicador se presenta como no disponible y no se realiza imputación ni se reemplazan faltantes por cero.

## Estructura

```text
Pipeline-EPH-DGEyC/
├── src/pipeline.py                 Pipeline, validaciones y publicación segura
├── notebooks/app.py               Dashboard Streamlit
├── notebooks/eda_eph_sde.py       Análisis técnico complementario
├── tests/test_pipeline.py          Suite automatizada
├── data/                           ZIP y TXT locales, excluidos de Git
├── results/                        Salidas locales, excluidas de Git
├── data_snapshot/                  Agregados validados para Streamlit Cloud
├── logs/                           Registro operativo local
└── docs/
    ├── DICCIONARIO_DATOS.md
    ├── METODOLOGIA.md
    ├── GUIA_USO.md
    └── ARQUITECTURA.md
```

`data_snapshot/` contiene sólo histórico e indicadores agregados, control de calidad agregado, estados, validaciones, metadatos, manifiesto y documentación. No contiene ZIP, microdatos individuales ni bases unidas.

## Instalación

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Linux o macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Ejecución

```bash
# Un trimestre
python src/pipeline.py --anio 2025 --trimestre 4

# Un año
python src/pipeline.py --anio 2025

# Período configurado completo
python src/pipeline.py --todos

# Calendario y estado de períodos
python src/pipeline.py --calendario

# Volver a descargar un ZIP
python src/pipeline.py --anio 2025 --trimestre 4 --forzar
```

Para actualizar localmente el snapshot sólo después de una validación exitosa:

```bash
python src/pipeline.py --publicar-snapshot
```

Este comando no despliega la aplicación en Streamlit Cloud. Sólo prepara los archivos agregados que deben revisarse antes de versionarlos.

## Salidas, metadatos y manifiesto

Cada CSV exportado queda acompañado por `nombre_archivo.meta.json`.

| Salida | Clasificación |
|---|---|
| `historico_SDE.csv` | Crítica |
| `indicadores_SDE_<periodo>.csv` | Analítica |
| `calidad_datos_SDE_<periodo>.csv` | Calidad |
| `validacion_esquema_<periodo>.json` | Auditoría |
| `validacion_publicacion_<periodo>.json` | Auditoría |
| `estado_periodos.csv` | Auditoría |
| logs | Operativa |
| gráficos | Visualización |
| `manifest_salidas.json` y snapshot | Disponibilización |

Los metadatos documentan fuente, período, estructura, variables, tipos, unidades, fórmulas, filtros, nulos, códigos especiales, ponderador, advertencias, estado de validación, hash e identificador de ejecución. `results/manifest_salidas.json` relaciona cada salida con su metadata.

## Control previo a publicación

Estados posibles: `PENDIENTE`, `DESCARGADO`, `PROCESADO`, `EN_REVISION`, `VALIDADO`, `FALLIDO` y `PUBLICADO`.

Antes de promover un período se comprueban descarga y ZIP, archivos individual y hogar, esquema obligatorio, Aglomerado 18, población total positiva, duplicados, rango de tasas, complementariedad actividad-inactividad, desocupación calculable, filas razonables, archivos y metadatos, y disponibilidad de informalidad.

Las salidas se construyen en una carpeta temporal. Ante una falla crítica, el período queda `FALLIDO`, se registra un mensaje entendible y no se reemplaza el histórico ni el snapshot vigente.

## Dashboard

Ejecución exacta desde la raíz:

```bash
python -m streamlit run notebooks/app.py
```

La aplicación tiene cinco secciones: resumen ejecutivo, evolución laboral, ingresos, calidad y auditoría, y documentación y descargas. Usa `results/` únicamente si el último período es `VALIDADO` o `PUBLICADO`; en caso contrario conserva el último `data_snapshot/` validado. Funciona sin conexión a los ZIP del INDEC.

Para Streamlit Cloud, configurar como archivo principal:

```text
notebooks/app.py
```

## Tests

```bash
python -m pytest tests -q
```

Las pruebas escriben sólo en directorios temporales y verifican fórmulas, migración de nombres, rangos, metadatos, manifiesto, bloqueo de publicación, conservación del snapshot, carga agregada y rutas relativas.

Resultado de la validación final: **50 tests aprobados**.

## Devolución institucional y mejoras incorporadas

- Dashboard reducido y adaptado a usuarios no técnicos.
- Metadatos automáticos para cada salida tabular.
- Clasificación de cargas y manifiesto general.
- Control previo a publicación y estados por período.
- Calendario, contingencia y conservación del último resultado validado.
- Snapshot agregado para ejecución independiente del ETL.
- Arquitectura ampliable mediante funciones documentadas y salidas trazables.

## Limitaciones y reporte anterior

- Los indicadores se calculan a partir de microdatos públicos y no sustituyen procedimientos institucionales confirmados.
- Los indicadores operativos de campo requieren bases internas y definiciones institucionales.
- El archivo `docs/Reporte_Ejecutivo_EPH_SDE_4T2025.pdf` se conserva como antecedente, pero no se ofrece en el dashboard: utiliza los nombres y denominadores anteriores y contiene una línea futura que ya no representa el alcance del Hito 3. No existe una fuente editable equivalente en el repositorio.

## Fuente

Encuesta Permanente de Hogares — Instituto Nacional de Estadística y Censos (INDEC), República Argentina: <https://www.indec.gob.ar>.

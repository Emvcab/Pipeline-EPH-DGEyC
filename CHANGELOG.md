# Historial de cambios

## 3.0.0 — 2026-07-13

- Separación entre tasas principales sobre población total y tasas específicas de 10 años y más.
- Migración explícita de nombres históricos sin cambio silencioso de denominador.
- Metadatos completos, manifiesto general y clasificación de cargas.
- Estados por período, controles críticos y promoción transaccional.
- Snapshot agregado para Streamlit, con conservación del anterior ante fallas.
- Dashboard institucional en cinco secciones, sin afirmaciones predictivas.
- Documentación metodológica y pruebas ampliadas.

Todos los cambios relevantes del proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado [Semantic Versioning](https://semver.org/lang/es/).


## [2.2.0] — 2026-06-30

### Agregado
- **Calendario de publicaciones INDEC** — flag `--calendario` muestra cronograma esperado vs estado real (procesado / esperando / futuro)
- **Validación automática de esquema** — el pipeline verifica que las columnas esperadas estén presentes antes de procesar. Si el INDEC cambia algo crítico, el pipeline avisa antes de generar resultados
- Archivo `validacion_esquema_<periodo>.json` por trimestre con resultado de la validación
- Constantes `ESQUEMA_OBLIGATORIO_INDIVIDUAL`, `ESQUEMA_OBLIGATORIO_HOGAR`, `ESQUEMA_OPCIONAL_INDIVIDUAL`
- 7 tests nuevos (total: 31 tests pasando)

### Motivación
Implementación de sugerencia recibida en devolución institucional de la DGEyC:
> "Debería incluirse un calendario, ya que el pipeline se activa con cada nueva
> publicación y debería considerarse la contingencia, auditoría y disponibilización
> del nuevo reporte, o fallas en la extracción."

---
---

## [2.1.0] — 2026-06-30

### Agregado
- **Sistema de metadatos automáticos** — cada archivo CSV generado por el pipeline ahora se acompaña de un archivo `.meta.json` con información completa para su uso (versión del pipeline, fecha de generación, fuente, esquema de columnas con tipos y descripciones, hash de integridad SHA-256)
- Función `generar_metadatos()` con diccionario embebido de las ~30 columnas del histórico
- Función `calcular_hash()` para verificación de integridad
- Constante `PIPELINE_VERSION` para trazabilidad de versiones
- 7 tests nuevos para el sistema de metadatos (total: 24 tests)

### Cambiado
- `guardar_trimestre()` ahora genera 4 CSV + 4 JSON por trimestre procesado
- Docstring del pipeline actualizado con la nueva estructura de salidas

### Motivación
Implementación de sugerencia recibida en devolución institucional de la DGEyC:
> "Los csv o xlsx que se exporten del pipeline o las Loads deben estar acompañadas
> de metadatos para ser usables."

---


## [2.0.0] — 2026-06-26

### Cambiado
- **Refactorización profesional completa del pipeline**, reduciendo de 1.434 a 411 líneas (-71%) sin pérdida de funcionalidad técnica
- Adopción de estándares profesionales: `type hints` completos, `docstrings`, logging estructurado, manejo explícito de errores
- Centralización de constantes en sección de configuración al inicio del archivo
- Reemplazo de `os.path` por `pathlib.Path` para manejo de rutas
- Reorganización del proyecto en estructura de carpetas profesional (`src/`, `docs/`, `tests/`, `data/`, `results/`, `logs/`)

### Agregado
- `README.md` con instrucciones de instalación y uso
- `requirements.txt` con dependencias pinned
- `.gitignore` profesional
- `CHANGELOG.md` (este archivo)
- `LICENSE`
- Suite de tests básicos en `tests/`
- Documentación de arquitectura en `docs/ARQUITECTURA.md`

### Eliminado
- Funciones de diagnóstico geográfico (información movida a documentación)
- Inventario de columnas por trimestre (uso único, no aporta valor continuo)
- Variables descriptivas decodificadas innecesarias para cálculos
- Múltiples archivos redundantes de salida
- Prints duplicados con logs

---

## [1.5.0] — 2026-06-07

### Agregado
- Lectura robusta probando 4 combinaciones de separador/codificación
- Cálculo de ingreso promedio ponderado
- Reporte de calidad de datos por trimestre
- Base unida individuo-hogar por `CODUSU + NRO_HOGAR`
- Tasa de inactividad
- Sistema de logs con timestamp en carpeta `logs/`
- Flag `--forzar` para re-descargar ZIPs existentes

### Cambiado
- Migración a `pathlib.Path` en lugar de strings para rutas
- Logging básico reemplaza algunos prints

---

## [1.0.0] — 2026-05-18

### Agregado
- Versión inicial del pipeline (Hito 1)
- Descarga automatizada desde el FTP del INDEC
- Filtrado por aglomerado 18 (Santiago del Estero — La Banda)
- Cálculo de tasas: actividad, empleo, desocupación, informalidad
- Cálculo de ingreso promedio simple y mediana
- Tres modos de ejecución: trimestre, año completo, todos los trimestres
- Histórico acumulado en `historico_SDE.csv`

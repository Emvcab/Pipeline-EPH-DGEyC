# Arquitectura técnica

## Flujo

```text
Descarga temporal → ZIP válido → lectura y esquema → filtro Aglomerado 18
        → cálculo ponderado → staging de salidas → controles críticos
        → VALIDADO: promoción atómica a results/
        → FALLIDO: conservar histórico y snapshot anteriores
```

El pipeline se mantiene en `src/pipeline.py` para facilitar su lectura operativa. Las funciones aceptan directorios alternativos en los puntos que se prueban, lo que evita escribir en resultados reales durante los tests.

## Decisiones metodológicas

- Las tasas principales de actividad y empleo usan población total expandida.
- La desocupación usa PEA expandida.
- La proporción inactiva total se define como complemento de actividad oficial.
- Las tasas de 10 años y más tienen nombres específicos.
- `PONDERA` se aplica a estimaciones poblacionales, informalidad e ingreso promedio ponderado.
- Los faltantes no se imputan ni se sustituyen por cero.
- Los ingresos son nominales.

`migrar_historico()` renombra las columnas históricas ambiguas y vuelve a calcular las tasas principales desde sus componentes expandidos. La operación es explícita e idempotente.

## Transacción de publicación

`guardar_trimestre()` crea indicadores, calidad, histórico candidato y metadatos en una carpeta temporal. `validar_publicacion()` controla Aglomerado 18, población positiva, duplicados, rango de tasas, complementariedad, desocupación calculable, filas razonables, archivos, metadatos e informalidad no disponible.

Sólo una candidatura válida se promueve a `results/`. Si falla una escritura durante la promoción, se restauran los archivos previos.

## Trazabilidad

`estado_periodos.csv` registra `PENDIENTE`, `DESCARGADO`, `PROCESADO`, `EN_REVISION`, `VALIDADO`, `FALLIDO` o `PUBLICADO`.

Los metadatos se generan automáticamente para cada CSV y salida de auditoría. `manifest_salidas.json` permite descubrir archivos, clasificación, período, validación, metadata y fecha de generación.

## Snapshot

`preparar_snapshot_desde_historico()` construye en staging un paquete agregado con histórico, indicadores trimestrales, estados, validaciones de esquema, documentación y manifiesto. No copia `base_unida`, ZIP ni microdatos. El directorio vigente se reemplaza sólo cuando el nuevo snapshot completo es válido.

`publicar_snapshot_validado()` exige que el último período de `results/` esté `VALIDADO` o `PUBLICADO`. Es una preparación local; el despliegue de Streamlit Cloud es una acción externa y separada.

## Dashboard y escalabilidad

`notebooks/app.py` usa rutas relativas. Prioriza `results/` sólo si el último período está validado; de lo contrario usa `data_snapshot/`. Los gráficos se construyen desde CSV agregados.

Las cargas se distinguen como Crítica, Analítica, Calidad, Auditoría, Operativa, Visualización y Disponibilización. En una etapa posterior pueden agregarse métricas por etapa sin modificar las fórmulas públicas.

## Cuellos de botella y límites actuales

- **Dependencia del INDEC.** El pipeline necesita que el INDEC publique el trimestre y sostenga la URL y el empaquetado actuales. Si la publicación se demora o cambia de ubicación, no hay dato nuevo que procesar y el período queda `PENDIENTE`.
- **Cambios de formato de origen.** Nombres de archivos, variables, codificación o separadores pueden cambiar entre trimestres. La lectura prueba cuatro combinaciones conocidas y la validación de esquema detiene el proceso ante faltantes críticos, pero un cambio profundo exige actualizar los esquemas esperados en el código.
- **Descarga y lectura completas antes del filtrado.** Cada corrida baja el ZIP nacional y carga la base completa en memoria antes de filtrar el Aglomerado 18. La descarga depende de la red y es la etapa más lenta; la lectura carga cientos de columnas de todos los aglomerados para conservar unas 1.500 filas locales.
- **Crecimiento en memoria y tiempo.** El consumo escala con el tamaño de las bases nacionales y con la cantidad de períodos o variables que se agreguen. Con 12 trimestres el procesamiento local demora segundos por período una vez descargados los ZIP; el histórico agregado, en cambio, crece una fila por trimestre y no compromete recursos.
- **Publicación con revisión humana.** La actualización del snapshot es una decisión deliberada (`--publicar-snapshot` tras revisar el estado `VALIDADO`), no un proceso automático. Es un límite aceptado: prioriza la revisión institucional sobre la inmediatez.
- **Regeneración tras cambios.** Cualquier cambio de fórmulas, columnas o períodos exige regenerar snapshot y manifiesto para que datos, metadatos y hashes vuelvan a ser coherentes.

Estas limitaciones están controladas de manera parcial por las validaciones de esquema y de publicación, la construcción en staging, los estados por período y el rollback que conserva el último resultado válido. Controlan el efecto de una falla, no su causa: la disponibilidad y el formato del origen siguen fuera del alcance del sistema.

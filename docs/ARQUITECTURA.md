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

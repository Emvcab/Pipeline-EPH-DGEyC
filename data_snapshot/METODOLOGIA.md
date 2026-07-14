# Metodología de indicadores

## Universo y ponderación

El procesamiento filtra `AGLOMERADO = 18` y usa `PONDERA` para transformar observaciones de muestra en estimaciones poblacionales. No se imputan faltantes ni se convierten en cero.

## Indicadores principales

```text
tasa_actividad_oficial = PEA expandida / población total expandida × 100
tasa_empleo_oficial = ocupados expandidos / población total expandida × 100
tasa_desocupacion = desocupados expandidos / PEA expandida × 100
proporcion_inactiva_total = 100 - tasa_actividad_oficial
```

La proporción inactiva total es complementaria. No equivale a la tasa específica de inactividad de 10 años y más.

## Indicadores de 10 años y más

```text
tasa_actividad_10_mas = PEA expandida / población de 10 años y más expandida × 100
tasa_empleo_10_mas = ocupados expandidos / población de 10 años y más expandida × 100
tasa_inactividad_10_mas = inactivos expandidos / población de 10 años y más expandida × 100
```

## Informalidad e ingresos

Informalidad: ocupados ponderados con `EMPLEO = 2` / ocupados ponderados con `EMPLEO` en `{1, 2}` × 100. En `2023T1`, `2023T2` y `2023T3`, la variable necesaria para estimar informalidad no está disponible. Por ese motivo, el indicador se presenta como no disponible y no se realiza imputación ni se reemplazan faltantes por cero.

Para ingresos se consideran ocupados con `P21 > 0`. El promedio ponderado es suma(`P21 × PONDERA`) / suma(`PONDERA`). Todos los valores monetarios son pesos argentinos nominales y requieren deflactación para estudiar poder adquisitivo.

## Limitaciones

- El Aglomerado 18 reúne Santiago del Estero y La Banda sin desagregación pública entre ciudades.
- Los microdatos públicos no permiten evaluar encuestadores ni personal de carga.
- Los resultados calculados no sustituyen procedimientos institucionales confirmados.
- Machine Learning podrá evaluarse en una etapa posterior, una vez definido un problema institucional concreto, con datos suficientes y validación metodológica.

## Antecedente documental

`Reporte_Ejecutivo_EPH_SDE_4T2025.pdf` conserva cifras y textos producidos con la denominación anterior de tasas y una línea predictiva descartada para este hito. No existe en el repositorio una fuente editable equivalente. El archivo se conserva sin alteraciones y no se ofrece desde el dashboard.

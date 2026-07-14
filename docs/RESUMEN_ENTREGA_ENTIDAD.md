# Resumen de entrega — DGEyC Santiago del Estero

**Proyecto:** Pipeline ETL y dashboard de indicadores EPH · Aglomerado 18 (Santiago del Estero - La Banda)
**Equipo:** Grupo 3 · Práctica Profesionalizante II · ITSE 2026
**Fecha:** julio de 2026 · **Versión:** 3.0.0

**Dashboard:** <https://pipeline-eph-dgeyc-sde.streamlit.app/>
**Repositorio:** <https://github.com/Emvcab/Pipeline-EPH-DGEyC>

---

## Qué se incorporó de la devolución

La devolución recibida tras la entrega anterior orientó todo el trabajo de esta etapa. Punto por punto:

| Observación de la Dirección | Cómo se resolvió | Estado |
|---|---|---|
| Los CSV exportados deben ir acompañados de metadatos para ser usables | Cada salida tiene su `.meta.json` con fuente, período, definiciones, unidades, fórmulas, filtros, ponderador, advertencias, estado de validación y hash de integridad. `manifest_salidas.json` inventaría todo el conjunto | Resuelto |
| Calendario asociado a las publicaciones del INDEC, con contingencia, auditoría y disponibilización | Comando `--calendario`, ciclo de estados por período (`PENDIENTE` a `VALIDADO`/`FALLIDO`/`PUBLICADO`) persistido en `estado_periodos.csv` y visible en el dashboard | Resuelto |
| Advertir el error antes de que sea publicado o lo note el usuario final | Validación de esquema frente a cambios del INDEC y nueve controles críticos previos a la publicación; un período que falla no reemplaza el histórico ni el snapshot vigente | Resuelto |
| Diferenciar la importancia y finalidad de cada Load | Clasificación de cada salida (Crítica, Analítica, Calidad, Auditoría, Operativa, Disponibilización) en metadatos y manifiesto | Resuelto |
| Ajustar el producto a una audiencia no técnica | Dashboard de cinco secciones con advertencias en pantalla, manual de usuario y guías descargables desde el propio tablero | Resuelto |
| Cuellos de botella, métricas de ejecución y construcción de nuevas variables | Documentado como línea de trabajo; los registros por corrida ya permiten estimar duraciones, pero falta la medición sistemática por etapa | Mejora futura |
| Contacto con el área operativa de EPH y otros usuarios | Propuesta de reuniones mantenida en el roadmap; los indicadores operativos de campo requieren bases internas de la Dirección | Mejora futura |

Además, las tasas principales ahora se calculan sobre la población total, el mismo denominador de los informes técnicos del INDEC, lo que permite el cotejo directo con las publicaciones oficiales. Las tasas sobre población de 10 años y más se conservan identificadas con nombres explícitos.

## Qué queda como mejora futura

- Métricas de rendimiento por etapa del pipeline (descarga, lectura, cálculo, guardado).
- Indicadores operativos del relevamiento, sujetos a la disponibilidad de bases internas y a definiciones de la Dirección.
- Series de ingresos deflactadas.
- Análisis avanzados (por ejemplo, modelos sobre informalidad o no respuesta de ingresos) solo si se define un problema institucional concreto con datos suficientes; no se incluyó ningún componente predictivo en esta entrega.

## Verificación de esta entrega

- 12 períodos procesados y validados (2023T1 a 2025T4); último período validado: 2025T4.
- 50 pruebas automatizadas aprobadas.
- Todos los indicadores publicados superaron los controles de rango, consistencia y completitud.
- Las 30 salidas del snapshot cuentan con su archivo de metadatos y su hash de integridad verificado, inventariadas en `manifest_salidas.json`.
- El snapshot publicado contiene únicamente agregados; no incluye microdatos individuales.
- Los indicadores se calculan a partir de microdatos públicos del INDEC y no constituyen una nueva estadística oficial provincial.

## Archivos entregables

1. Repositorio completo con el pipeline (`src/pipeline.py`) y el dashboard (`notebooks/app.py`).
2. Dashboard publicado en línea (enlace arriba).
3. `data_snapshot/`: histórico validado, indicadores por trimestre, estados, validaciones, manifiesto y metadatos.
4. Documentación en `docs/`: informe final del hito, manual de usuario del dashboard, manual técnico, metodología, diccionario de datos, guía de uso y arquitectura.

Quedamos a disposición para revisar la entrega, relevar nuevas necesidades y coordinar las reuniones propuestas con el área operativa.

Grupo 3 — Práctica Profesionalizante II · ITSE 2026
Achaval María José · Cabaña Emilio · Constantinidi Leandro · Gomez Cinthia · Pinto Villegas Eduardo

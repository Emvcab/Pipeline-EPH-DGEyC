# Guion de exposición — Cierre del Hito 3

**Duración total:** 10 minutos (4 oradores) · **Proyecto:** Pipeline EPH · Aglomerado 18
**Material en pantalla:** dashboard publicado + repositorio. Sin diapositivas obligatorias.

Preparación previa (responsable: orador 3):

- Abrir el dashboard 10 minutos antes; si la plataforma lo puso en pausa, reactivarlo para que cargue rápido durante la demo.
- Tener de respaldo el dashboard corriendo en una computadora local (`python -m streamlit run notebooks/app.py`) por si falla la conexión.
- Dejar abierto en otra pestaña un archivo `.meta.json` del repositorio para mostrarlo sin buscarlo en vivo.

---

## Orador 1 — Problema y devolución recibida (2 minutos)

**En pantalla:** portada del repositorio en GitHub.

- Presentar al grupo y al proyecto en una frase: "Automatizamos el procesamiento trimestral de los microdatos públicos de la EPH del INDEC para el aglomerado Santiago del Estero - La Banda, en colaboración con la Dirección General de Estadística y Censos".
- El problema: cada trimestre, obtener indicadores locales implicaba descargar archivos, filtrar el aglomerado, aplicar el ponderador y calcular tasas a mano. Horas de trabajo repetitivo, sin registro de controles ni trazabilidad.
- Qué había al cierre del hito anterior: un pipeline funcional que ya descargaba, filtraba y calculaba, con pruebas y documentación.
- La devolución de la entidad valoró el diseño y marcó el rumbo de esta etapa: metadatos en cada archivo exportado, calendario y contingencias, advertir errores antes de publicar, y adaptar el producto a usuarios no técnicos.
- Cierre del bloque: "Esta etapa consistió en convertir ese pipeline en un sistema confiable de punta a punta. Lo que sigue muestra cómo".

**Idea fuerza:** la entidad no pidió más indicadores; pidió confiabilidad y usabilidad.

## Orador 2 — Mejoras técnicas: validaciones, estados y metadatos (2 min 30 s)

**En pantalla:** un `.meta.json` del repositorio; luego `estado_periodos.csv`.

- Tasas comparables: "Las tasas principales ahora se calculan sobre población total, el mismo denominador que usa el INDEC en sus informes. Las tasas sobre población de 10 años y más siguen disponibles, con nombre explícito. Nada se recalculó en silencio: cada columna dice lo que es".
- Ciclo de estados: cada trimestre pasa por pendiente, descargado, procesado, en revisión y validado o fallido. Todo queda registrado con fecha, intentos y un mensaje entendible.
- Controles previos a publicar: aglomerado presente, población positiva, tasas entre 0 y 100, consistencia actividad-inactividad, mínimos de muestra, archivos completos. "Si un control crítico falla, el período queda marcado como fallido y no pisa ni el histórico ni lo que ve el dashboard. El error se advierte antes de publicarse, que era exactamente el pedido".
- Metadatos: mostrar el `.meta.json` 15 segundos. "Cada CSV sale con su ficha: fuente, período, definición de cada variable, unidades, fórmulas, filtros, ponderador, advertencias y un código de integridad. Y un manifiesto general inventaría todas las salidas con su clasificación: crítica, analítica, calidad, auditoría".
- Respaldo: 50 pruebas automatizadas aprobadas.

**Idea fuerza:** ningún dato llega a publicarse sin pasar controles, y ningún archivo viaja sin su ficha.

## Orador 3 — Demo del dashboard (3 minutos)

**En pantalla:** el dashboard publicado. Recorrido pausado, sin apuro.

1. **Encabezado** (20 s): fuente EPH-INDEC, aglomerado, y la aclaración de que los indicadores no constituyen una nueva estadística oficial provincial.
2. **Resumen ejecutivo** (50 s): último período validado, estado y fecha de actualización. Leer dos números en voz alta, por ejemplo: "Al cuarto trimestre de 2025, la tasa de actividad oficial fue 41,2% y la desocupación 0,6%". Señalar la advertencia territorial.
3. **Evolución laboral** (30 s): la serie 2023-2025; mencionar que la informalidad arranca en 2023T4 porque antes el INDEC no publicaba la variable, y que el tablero lo aclara en vez de rellenar.
4. **Ingresos** (30 s): mostrar la advertencia de valores nominales antes que los montos. "El tablero avisa primero cómo leer y después muestra el número".
5. **Calidad y auditoría** (50 s): la parte menos vistosa y más importante. Tabla de estados por período, selector de un trimestre, validaciones lógicas en verde. "Cualquier persona puede auditar qué controles pasó el dato que está mirando".
6. **Documentación y descargas** (20 s): histórico, metadatos, manifiesto, diccionario, metodología. "El dato se va acompañado de su documentación".

**Idea fuerza:** el tablero no solo muestra indicadores; muestra cuánto confiar en ellos.

## Orador 4 — Límites, entregables y próximos pasos (2 min 30 s)

**En pantalla:** sección de advertencias metodológicas del informe final (`docs/INFORME_FINAL_HITO3.md`).

- Límites metodológicos, dichos sin vueltas (60 s):
  - Ingresos nominales; sin deflactar no se puede hablar de poder adquisitivo.
  - Informalidad no disponible en los tres primeros trimestres de 2023; se informa, no se imputa.
  - No se imputan datos faltantes en ningún indicador.
  - El aglomerado se analiza completo: no hay desagregación pública entre Santiago y La Banda.
  - Los resultados no constituyen una estadística oficial provincial ni miden el trabajo de campo.
- Sobre Machine Learning (40 s): "Evaluamos incorporar un componente predictivo y decidimos no hacerlo en este hito. No hay todavía una necesidad institucional concreta que lo justifique, y la variable candidata, la no respuesta de ingresos, tiene menos de 150 casos en tres años: cualquier modelo sobre esa base daría conclusiones frágiles. El hito se cubre con el dashboard validado; lo predictivo queda como línea futura, condicionada a definir el problema con la entidad".
- Entregables (30 s): repositorio con pipeline y dashboard, aplicación publicada, snapshot validado con metadatos y manifiesto, informe final, manuales de usuario y técnico, metodología y diccionario de datos.
- Cierre (20 s): "El sistema queda operativo y documentado para que la Dirección lo use cada trimestre: se procesa el período nuevo, se revisa que quede validado y se publica el snapshot. Los próximos pasos naturales son las reuniones con el área operativa y las métricas de rendimiento por etapa. Gracias".

**Idea fuerza:** decir lo que el producto no hace es parte del producto.

---

## Preguntas probables y respuestas breves

- **¿Por qué las tasas difieren de las que ya habían mostrado antes?** Antes publicábamos tasas sobre población de 10 años y más. Ahora las principales usan población total, como los informes del INDEC, y las anteriores siguen disponibles con nombre explícito. Es un cambio de denominación transparente, no una corrección de datos.
- **¿Qué pasa si el INDEC cambia el formato de sus archivos?** La validación de esquema lo detecta antes de calcular: el período queda fallido con el detalle registrado, y el histórico y el tablero conservan la última versión válida.
- **¿El tablero se actualiza solo?** La actualización es deliberada: se procesa el trimestre, se revisa que esté validado y recién entonces se publica el snapshot. Preferimos un paso de revisión humana a una publicación automática.
- **¿Pueden medir el desempeño de los encuestadores?** No con microdatos públicos: solo contienen entrevistas realizadas. Eso requiere bases internas de la Dirección y una definición institucional previa.

## Reparto de tiempos

| Bloque | Orador | Tiempo |
|---|---|---|
| Problema y devolución | 1 | 2:00 |
| Validaciones, estados y metadatos | 2 | 2:30 |
| Demo del dashboard | 3 | 3:00 |
| Límites, entregables y cierre | 4 | 2:30 |
| **Total** | | **10:00** |

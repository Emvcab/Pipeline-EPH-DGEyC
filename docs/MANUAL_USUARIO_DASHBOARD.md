# Manual de usuario del dashboard

**Tablero:** Mercado laboral en Santiago del Estero - La Banda
**Dirección:** <https://pipeline-eph-dgeyc-sde.streamlit.app/>
**Fuente de los datos:** Encuesta Permanente de Hogares (EPH) — INDEC · Aglomerado 18

Este manual está pensado para personas que van a consultar el tablero sin conocimientos de programación ni de estadística avanzada.

---

## 1. Cómo ingresar

1. Abrí un navegador (Chrome, Edge o Firefox) y entrá a la dirección del tablero.
2. No hace falta usuario, contraseña ni instalar nada.
3. Si el tablero estuvo un tiempo sin visitas, la plataforma lo pone en pausa. En ese caso vas a ver una pantalla de espera o un botón para reactivarlo: tocalo y esperá alrededor de un minuto mientras vuelve a cargar.
4. Al abrirse vas a ver el título, la fuente de los datos y una franja que indica qué información está mostrando:
   - "El tablero está usando el snapshot agregado y validado": está mostrando la copia de datos validados incluida en el repositorio. Es el modo normal de la versión en línea.
   - "El tablero está usando resultados locales validados": aparece cuando alguien lo ejecuta en su propia computadora después de correr el pipeline.

Debajo del título hay una aclaración fija que conviene leer una vez: los datos son producidos por el INDEC y los indicadores los calcula este sistema; no constituyen una nueva estadística oficial provincial.

## 2. Qué muestra cada pestaña

### Resumen ejecutivo

Es la foto del último trimestre validado. Muestra:

- **Último período validado**, **estado de validación** y **fecha de actualización**.
- Las cuatro tasas principales: actividad oficial, empleo oficial, desocupación y proporción inactiva total.
- **Personas y hogares en muestra** (cuántos se encuestaron) y **población total expandida** (a cuánta gente representan esas encuestas).
- La **tasa de informalidad**. Si el período no tiene la variable necesaria, vas a ver "No disponible" y un aviso que lo explica.
- Una advertencia territorial: los datos describen el aglomerado completo, sin separar Santiago Capital de La Banda.

### Evolución laboral

Gráficos de línea con la trayectoria 2023-2025: actividad y empleo oficiales juntos, desocupación por separado, proporción inactiva e informalidad. La informalidad arranca en 2023T4 porque antes el INDEC no publicaba la variable que permite calcularla; el propio gráfico lo aclara.

### Ingresos

Ingreso promedio ponderado, ingreso mediano y porcentaje de personas ocupadas que no declararon su ingreso, con la serie completa. Toda la pestaña está encabezada por una advertencia: los montos son nominales (pesos corrientes de cada trimestre).

### Calidad y auditoría

Es la pestaña para responder "¿qué tan confiable es este dato?". Contiene:

- Cuántos períodos están validados y cuántos tienen advertencias.
- La tabla de **estado de períodos**: cada trimestre con su fecha esperada de publicación, su estado y un mensaje del último control.
- Un selector de **período a auditar**, que despliega la muestra del trimestre, el detalle de variables con valores faltantes y códigos especiales, los cambios de esquema detectados frente a los archivos del INDEC y una tabla de **validaciones lógicas** (por ejemplo, que todas las tasas estén entre 0 y 100).
- Un botón para descargar los metadatos de ese período.

### Documentación y descargas

Botones para bajar el histórico completo, los indicadores y el reporte de calidad del último período, el estado de períodos, los metadatos del histórico, el manifiesto de salidas, la validación de esquema y tres guías: diccionario de datos, guía de uso y metodología.

## 3. Cómo interpretar los indicadores

| Indicador | Qué mide | Cómo leerlo |
|---|---|---|
| Tasa de actividad oficial | Personas que trabajan o buscan trabajo, sobre la población total | Es la medida comparable con los informes del INDEC |
| Tasa de empleo oficial | Personas ocupadas sobre la población total | Sube o baja junto con la actividad; conviene mirarlas juntas |
| Tasa de desocupación | Personas que buscan trabajo y no encuentran, sobre la población activa | En este aglomerado es baja; leela junto con la informalidad |
| Proporción inactiva total | 100 menos la tasa de actividad oficial | Es el complemento de la actividad, no un indicador independiente |
| Tasa de informalidad | Ocupados sin registro sobre ocupados con dato de registro | Disponible desde 2023T4; en el aglomerado ronda valores altos |
| Ingreso promedio ponderado | Ingreso de la ocupación principal, ponderado para representar a la población | Está en pesos corrientes: no compares montos de distintos años sin ajustar por inflación |
| No respuesta de ingresos | Ocupados que no declararon cuánto ganan | Es un indicador de calidad del dato, no del mercado laboral |

Dos aclaraciones que evitan errores frecuentes:

- **Una desocupación baja no significa pleno empleo.** En economías con informalidad alta, muchas personas que no consiguen empleo formal aparecen ocupadas en trabajos sin registro. Por eso el tablero muestra ambos indicadores.
- **"Población expandida" no es un censo.** Es la estimación de a cuánta gente representa la muestra al aplicar el ponderador oficial del INDEC.

Si en algún análisis externo encontrás tasas distintas para el mismo trimestre, revisá el denominador: este tablero usa la población total (criterio de los informes del INDEC) para las tasas principales, y publica aparte las tasas calculadas sobre la población de 10 años y más, identificadas con el sufijo "10_mas".

## 4. Cómo descargar archivos

1. Entrá a la pestaña **Documentación y descargas** (o usá el botón de metadatos dentro de Calidad y auditoría).
2. Tocá el botón del archivo que necesites. El navegador lo guarda en tu carpeta de descargas.
3. Los archivos `.csv` se abren con Excel, LibreOffice o cualquier planilla. Están codificados en UTF-8 y separados por coma.
4. Los archivos `.meta.json` y el manifiesto son de texto: se pueden abrir con cualquier editor (por ejemplo, el Bloc de notas) o con el navegador.
5. Si un botón aparece como "no disponible para esta fuente", ese archivo no forma parte del modo en que está funcionando el tablero (por ejemplo, los microdatos unidos nunca se publican en la versión en línea).

## 5. Cómo leer advertencias y metadatos

Las advertencias aparecen en recuadros de color dentro de cada pestaña. Las tres que vas a ver seguido: ingresos nominales, informalidad no disponible en los primeros trimestres de 2023 y alcance territorial del aglomerado.

Cada archivo descargable tiene un compañero `.meta.json` que responde las preguntas básicas antes de usar el dato: qué contiene el archivo y para qué sirve, de dónde salió (organismo, operativo y dirección de descarga del INDEC), a qué período corresponde, cuántas filas y columnas tiene, qué significa cada variable, en qué unidad está, con qué fórmula se calculó, qué filtros se aplicaron, cuántos valores faltantes hay, qué advertencias corresponden, en qué estado de validación está y un código de integridad (hash) que permite comprobar que el archivo no se alteró.

Regla práctica: si vas a reenviar un CSV, reenviá también su `.meta.json`. Ese par es lo que hace interpretable el dato para quien lo recibe.

## 6. Qué no debe interpretarse a partir de este tablero

- **Relaciones de causa y efecto.** El tablero describe la evolución de los indicadores; no explica por qué suben o bajan ni permite atribuir causas.
- **Una nueva estadística oficial.** Los cálculos se hacen sobre microdatos públicos del INDEC con metodología documentada, pero el resultado no es una publicación oficial de la provincia ni del INDEC.
- **Datos separados de Santiago Capital y La Banda.** El Aglomerado 18 es una sola unidad estadística; no existe desagregación pública por ciudad.
- **Desempeño de encuestadores o de carga de datos.** Los microdatos públicos solo contienen entrevistas realizadas; no informan rechazos ni trabajo de campo.
- **Poder adquisitivo.** Los ingresos son nominales; una suba en pesos no implica una mejora real.

Ante cualquier duda sobre definiciones o fórmulas, el documento de referencia es [METODOLOGIA.md](METODOLOGIA.md), descargable desde el propio tablero.

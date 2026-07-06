# Pipeline ETL — EPH Santiago del Estero

> Sistema automatizado de procesamiento de microdatos de la Encuesta Permanente de Hogares (EPH) del INDEC para el aglomerado **Santiago del Estero — La Banda** (código 18).

**Entregado a:** Dirección General de Estadística y Censos (DGEyC) — Santiago del Estero
**Desarrollado por:** Práctica Profesionalizante II · ITSE 2026
**Grupo:** Achaval María José · Cabaña Emilio · Constantinidi Leandro · Gomez Cinthia · Pinto Villegas Eduardo

---

## Qué hace

Descarga automáticamente los microdatos públicos del INDEC, filtra el aglomerado de Santiago del Estero, aplica las fórmulas oficiales de la metodología EPH ponderadas por `PONDERA` y genera indicadores del mercado laboral e indicadores operativos del relevamiento. Mantiene un histórico acumulado actualizable trimestre a trimestre.

Reemplaza el procesamiento manual trimestral que requería abrir varios archivos, traducir códigos numéricos y calcular tablas a mano — reduciendo horas de trabajo a unos pocos minutos.

---

## Estructura del proyecto

```
Pipeline_EPH_DGEyC/
├── README.md                  Este archivo
├── requirements.txt           Dependencias de Python
├── CHANGELOG.md               Historial de versiones
├── LICENSE                    Licencia
├── .gitignore                 Archivos excluidos del repositorio
│
├── src/
│   └── pipeline.py            Pipeline ETL principal
│
├── docs/
│   ├── Manual_Pipeline_EPH.docx   Manual técnico completo
│   └── ARQUITECTURA.md            Decisiones de diseño
│
├── tests/
│   └── test_pipeline.py       Tests automatizados (17 verificaciones)
│
├── data/                      Microdatos descargados (se llena al ejecutar)
├── results/                   Indicadores y reportes generados
└── logs/                      Registros de cada corrida
```

---

## Requisitos

- **Python 3.10 o superior**
- **Conexión a internet** (para descargar los ZIPs del INDEC)
- Sistema operativo: Windows, macOS o Linux

---

## Instalación

```bash
# 1. Ubicarse en la carpeta del proyecto
cd Pipeline_EPH_DGEyC

# 2. (Opcional) Crear un entorno virtual
python -m venv venv
venv\Scripts\activate          # En Windows
source venv/bin/activate       # En macOS/Linux

# 3. Instalar las dependencias
pip install -r requirements.txt
```

---

## Uso

### Procesar un trimestre específico
```bash
python src/pipeline.py --anio 2025 --trimestre 4
```

### Procesar un año completo
```bash
python src/pipeline.py --anio 2024
```

### Procesar todo el período 2023-2025
```bash
python src/pipeline.py --todos
```

### Re-descargar un trimestre existente
```bash
python src/pipeline.py --anio 2025 --trimestre 4 --forzar
```

---

## Archivos generados

Al ejecutar el pipeline, en `results/` aparecen:

| Archivo | Descripción |
|---|---|
| `historico_SDE.csv` | Base histórica acumulada — el archivo principal |
| `indicadores_SDE_<periodo>.csv` | Indicadores del trimestre puntual |
| `calidad_datos_SDE_<periodo>.csv` | Reporte de nulos y códigos especiales |
| `base_unida_SDE_<periodo>.csv` | Microdatos individual + hogar unidos |

Además, cada corrida genera un archivo `.log` en `logs/` con el detalle del procesamiento.

---

## Indicadores calculados

### Mercado laboral
- Tasa de actividad
- Tasa de empleo
- Tasa de desocupación
- Tasa de inactividad
- Tasa de informalidad (disponible desde 4T2023)
- Ingreso promedio ponderado, simple y mediano

### Operativos del relevamiento
- Hogares en muestra y encuestados
- Personas en muestra
- Población expandida total y por subgrupos (PEA, ocupados, etc.)
- Tasa de no respuesta de ingresos

---

## Verificación con tests

Para verificar que el pipeline funciona correctamente:

```bash
python -m pytest tests/
```

Resultado esperado:
```
============== 17 passed in ~1s ==============
```

---

## Documentación adicional

- **Manual técnico completo:** `docs/Manual_Pipeline_EPH.docx`
- **Decisiones de arquitectura:** `docs/ARQUITECTURA.md`

---

## Soporte y contacto

Para consultas técnicas o mantenimiento del pipeline, contactarse con el grupo de PP2 — ITSE 2026.

---

## Fuente de datos

Microdatos públicos de la Encuesta Permanente de Hogares (EPH) del Instituto Nacional de Estadística y Censos (INDEC) de la República Argentina.

- Sitio oficial: https://www.indec.gob.ar

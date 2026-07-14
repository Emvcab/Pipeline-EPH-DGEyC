# Guía de uso

## Procesar

Desde la raíz del repositorio:

```bash
python src/pipeline.py --anio 2025 --trimestre 4
python src/pipeline.py --calendario
```

Revisar `results/estado_periodos.csv`, `validacion_publicacion_<periodo>.json`, los CSV y sus `.meta.json`. Un período `FALLIDO` no reemplaza el histórico vigente.

## Preparar el snapshot

Sólo después de revisar un período `VALIDADO`:

```bash
python src/pipeline.py --publicar-snapshot
```

El comando excluye microdatos y no despliega la aplicación en la nube.

## Abrir el dashboard

```bash
python -m streamlit run notebooks/app.py
```

Si `results/` no tiene un último período validado, la aplicación usa `data_snapshot/` y muestra una explicación.

## Ante una falla

1. Leer el mensaje de `estado_periodos.csv`.
2. Revisar el último archivo de `logs/`.
3. Consultar la validación de esquema.
4. Corregir sin borrar el histórico ni el snapshot válidos.
5. Reprocesar y comprobar estado `VALIDADO`.

Los indicadores operativos de campo requieren bases internas. No deben inferirse de los microdatos públicos.

## Validación final

El snapshot validado cubre **12 períodos**, desde `2023T1` hasta `2025T4`.
La implementación fue verificada con `python -m pytest tests -q`: **50 tests aprobados**.

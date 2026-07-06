"""
Dashboard EPH — Santiago del Estero (Aglomerado 18)
====================================================
Práctica Profesionalizante II · ITSE 2026
Grupo: Achaval · Cabaña · Constantinidi · Gomez · Pinto Villegas

Tablero interactivo para explorar los resultados del pipeline ETL.
Lee los archivos generados en la carpeta results/ — no necesita
ejecutar el pipeline ni depender de módulos externos.

Uso:
    python -m streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

# ─── Configuración de la página ─────────────────────────────────────────────
st.set_page_config(
    page_title="EPH Santiago del Estero",
    page_icon="📊",
    layout="wide",
)

# Rutas — el dashboard lee lo que produjo el pipeline
RAIZ = Path(__file__).resolve().parent
DIR_RESULTADOS = RAIZ / "results"
DIR_GRAFICOS = RAIZ / "notebooks"  # donde el EDA guarda los PNG


# ─── Funciones auxiliares ───────────────────────────────────────────────────
def leer_csv(nombre: str) -> pd.DataFrame | None:
    """Lee un CSV de results/ si existe."""
    ruta = DIR_RESULTADOS / nombre
    if ruta.exists():
        return pd.read_csv(ruta)
    return None


def leer_metadatos(nombre_csv: str) -> dict | None:
    """Lee el .meta.json asociado a un CSV."""
    ruta = DIR_RESULTADOS / nombre_csv.replace(".csv", ".meta.json")
    if ruta.exists():
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return None


def mostrar_grafico(nombre: str, titulo: str) -> None:
    """Muestra un PNG del EDA si existe."""
    for carpeta in [DIR_GRAFICOS, RAIZ, RAIZ / "graficos_eda"]:
        ruta = carpeta / nombre
        if ruta.exists():
            st.image(str(ruta), caption=titulo, use_container_width=True)
            return
    st.info(f"El gráfico «{titulo}» todavía no fue generado. "
            f"Ejecutá el notebook del EDA para producirlo.")


def boton_descarga(nombre: str, etiqueta: str) -> None:
    """Botón para descargar un archivo de results/."""
    ruta = DIR_RESULTADOS / nombre
    if ruta.exists():
        with open(ruta, "rb") as f:
            st.download_button(etiqueta, f, file_name=nombre, key=nombre)
    else:
        st.caption(f"— {nombre} (no disponible)")


# ─── Encabezado ─────────────────────────────────────────────────────────────
st.title("Mercado Laboral en Santiago del Estero")
st.caption("Encuesta Permanente de Hogares · Aglomerado 18 (Santiago del Estero — La Banda) · INDEC")

# Cargar histórico
df = leer_csv("historico_SDE.csv")

if df is None:
    st.warning(
        "No se encontró el archivo **results/historico_SDE.csv**.\n\n"
        "Ejecutá primero el pipeline:\n"
        "```\npython src/pipeline.py --todos\n```"
    )
    st.stop()

df = df.sort_values(["anio", "trimestre"]).reset_index(drop=True)
ultimo = df.iloc[-1]

# ─── Pestañas ───────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Resumen",
    "📊 Análisis",
    "✓ Calidad y validación",
    "💡 Hallazgos",
    "⬇ Descargas",
])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — RESUMEN
# ═══════════════════════════════════════════════════════════════════════════
with tab1:
    st.header(f"Indicadores clave · {ultimo['periodo']}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Tasa de actividad", f"{ultimo['tasa_actividad']:.2f}%")
    c2.metric("Tasa de empleo", f"{ultimo['tasa_empleo']:.2f}%")
    c3.metric("Tasa de desocupación", f"{ultimo['tasa_desocupacion']:.2f}%")

    c4, c5, c6 = st.columns(3)
    c4.metric("Tasa de inactividad", f"{ultimo['tasa_inactividad']:.2f}%")
    if pd.notna(ultimo.get("tasa_informalidad")):
        c5.metric("Informalidad laboral", f"{ultimo['tasa_informalidad']:.2f}%")
    else:
        c5.metric("Informalidad laboral", "s/d")
    ingreso = ultimo.get("ingreso_promedio_ponderado_observado")
    if pd.notna(ingreso):
        c6.metric("Ingreso promedio", f"${ingreso:,.0f}")

    st.divider()

    # Muestra y población
    c7, c8, c9 = st.columns(3)
    c7.metric("Personas en muestra", f"{int(ultimo['n_personas_muestra']):,}")
    c8.metric("Hogares en muestra", f"{int(ultimo['n_hogares_muestra']):,}")
    c9.metric("Población representada", f"{int(ultimo['poblacion_expandida_total']):,}")

    st.divider()

    # Evolución rápida
    st.subheader("Evolución del mercado laboral")
    cols_linea = [c for c in ["tasa_actividad", "tasa_empleo", "tasa_inactividad"]
                  if c in df.columns]
    st.line_chart(df.set_index("periodo")[cols_linea])

    with st.expander("Ver base histórica completa"):
        st.dataframe(df, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — ANÁLISIS (EDA)
# ═══════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Análisis exploratorio")
    st.caption("Cuatro visualizaciones clave de la evolución del mercado laboral.")

    graficos = [
        ("eda_1_mercado_laboral.png", "1 · Serie de tiempo del mercado laboral"),
        ("eda_2_informalidad.png", "2 · Informalidad laboral"),
        ("eda_3_ingresos_no_respuesta.png", "3 · Ingresos y no respuesta"),
        ("eda_4_interanual.png", "4 · Comparación interanual"),
    ]

    for i in range(0, len(graficos), 2):
        col_a, col_b = st.columns(2)
        with col_a:
            mostrar_grafico(*graficos[i])
        if i + 1 < len(graficos):
            with col_b:
                mostrar_grafico(*graficos[i + 1])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — CALIDAD Y VALIDACIÓN
# ═══════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Calidad de datos y validación de esquema")

    # Selector de trimestre
    periodos = df["periodo"].tolist()
    periodo_sel = st.selectbox("Seleccioná un trimestre", periodos, index=len(periodos) - 1)

    col_izq, col_der = st.columns(2)

    # Calidad de datos
    with col_izq:
        st.subheader("Calidad de datos")
        calidad = leer_csv(f"calidad_datos_SDE_{periodo_sel}.csv")
        if calidad is not None:
            st.dataframe(calidad, use_container_width=True)
            st.caption("Conteo de nulos y códigos especiales por variable clave.")
        else:
            st.info("Reporte de calidad no disponible para este trimestre.")

    # Validación de esquema
    with col_der:
        st.subheader("Validación de esquema")
        ruta_val = DIR_RESULTADOS / f"validacion_esquema_{periodo_sel}.json"
        if ruta_val.exists():
            with open(ruta_val, encoding="utf-8") as f:
                val = json.load(f)
            for base in ["individual", "hogar"]:
                if base in val:
                    nivel = val[base]["nivel"]
                    icono = {"ok": "✅", "advertencia": "⚠️", "critico": "❌"}.get(nivel, "•")
                    st.write(f"{icono} **Base {base}:** {nivel}")
                    if val[base].get("opcionales_faltantes"):
                        st.caption(f"Opcionales faltantes: {val[base]['opcionales_faltantes']}")
        else:
            st.info("Validación de esquema no disponible para este trimestre.")

    st.divider()

    # Metadatos del histórico
    st.subheader("Metadatos del histórico")
    meta = leer_metadatos("historico_SDE.csv")
    if meta:
        c1, c2, c3 = st.columns(3)
        c1.metric("Versión pipeline", meta.get("version_pipeline", "s/d"))
        c2.metric("Filas", meta["estructura"]["n_filas"])
        c3.metric("Columnas", meta["estructura"]["n_columnas"])
        st.caption(f"Generado: {meta.get('fecha_generacion', 's/d')} · "
                   f"Hash: {meta['integridad']['hash_sha256_truncado']}")
        with st.expander("Ver diccionario de columnas"):
            esquema_df = pd.DataFrame(meta["esquema"])
            st.dataframe(esquema_df, use_container_width=True)
    else:
        st.info("Metadatos no disponibles. Regenerá el histórico con el pipeline v2.1+")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 4 — HALLAZGOS
# ═══════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("Principales hallazgos")

    primer = df.iloc[0]

    def variacion(col):
        vi, vf = primer[col], ultimo[col]
        if pd.isna(vi) or pd.isna(vf):
            return None
        delta = vf - vi
        return vi, vf, delta

    # Hallazgo 1
    v = variacion("tasa_actividad")
    if v:
        st.subheader("1 · La participación laboral cae de forma sostenida")
        st.write(f"La tasa de actividad pasó de **{v[0]:.1f}%** en {primer['periodo']} "
                 f"a **{v[1]:.1f}%** en {ultimo['periodo']} "
                 f"({'▼' if v[2] < 0 else '▲'} {abs(v[2]):.1f} puntos porcentuales). "
                 f"Cada vez menos personas participan del mercado laboral.")

    # Hallazgo 2
    st.subheader("2 · La desocupación es estructuralmente baja")
    st.write(f"La desocupación cerró en **{ultimo['tasa_desocupacion']:.2f}%**. "
             f"Debe leerse junto a la alta informalidad: no refleja pleno empleo, "
             f"sino que la economía informal absorbe a quienes no encuentran empleo formal.")

    # Hallazgo 3
    inf = df[df["tasa_informalidad"].notna()]
    if len(inf) > 0:
        st.subheader("3 · La informalidad es persistente y elevada")
        st.write(f"Promedio del período: **{inf['tasa_informalidad'].mean():.1f}%**. "
                 f"Más de la mitad de los ocupados trabaja sin registro en todos "
                 f"los trimestres con datos disponibles (desde 4T2023).")

    # Hallazgo 4
    v = variacion("tasa_no_respuesta_ingresos_ocupados")
    if v:
        st.subheader("4 · La no respuesta de ingresos creció en 2025")
        st.write(f"Pasó de **{v[0]:.1f}%** a **{v[1]:.1f}%**. "
                 f"Este fenómeno —posiblemente vinculado al contexto inflacionario— "
                 f"es el objeto de estudio del modelo predictivo del Hito 3.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 5 — DESCARGAS
# ═══════════════════════════════════════════════════════════════════════════
with tab5:
    st.header("Descargar archivos generados")

    st.subheader("Archivo principal")
    boton_descarga("historico_SDE.csv", "⬇ Descargar histórico completo (CSV)")

    st.divider()
    st.subheader("Por trimestre")
    periodos = df["periodo"].tolist()
    periodo_dl = st.selectbox("Trimestre", periodos, index=len(periodos) - 1, key="dl")
    col1, col2, col3 = st.columns(3)
    with col1:
        boton_descarga(f"indicadores_SDE_{periodo_dl}.csv", "Indicadores")
    with col2:
        boton_descarga(f"calidad_datos_SDE_{periodo_dl}.csv", "Calidad")
    with col3:
        boton_descarga(f"base_unida_SDE_{periodo_dl}.csv", "Base unida")

    st.divider()

    # Nota sobre indicadores operativos futuros
    with st.expander("ℹ️ Sobre los indicadores operativos del relevamiento"):
        st.markdown("""
        Los microdatos públicos del INDEC permiten calcular los indicadores del
        mercado laboral, pero **no incluyen la tasa de rechazo** ni el desempeño
        operativo de los encuestadores.

        Para incorporar esos indicadores se requiere el cruce con los **registros
        internos de la DGEyC** (estado real de cada entrevista, motivo de no respuesta,
        identificación de encuestadores). El pipeline ya está preparado para
        incorporarlos cuando esos datos estén disponibles.
        """)

# ─── Pie ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Práctica Profesionalizante II · ITSE 2026 · "
    "Achaval · Cabaña · Constantinidi · Gomez · Pinto Villegas · "
    "Fuente: microdatos EPH-INDEC"
)

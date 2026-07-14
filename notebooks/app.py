"""Dashboard institucional de indicadores EPH para el aglomerado 18."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="EPH · Santiago del Estero - La Banda",
    page_icon="📊",
    layout="wide",
)

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from pipeline import normalizar_estado, normalizar_periodo


DIR_RESULTADOS = RAIZ / "results"
DIR_SNAPSHOT = RAIZ / "data_snapshot"
DIR_DOCS = RAIZ / "docs"
ESTADOS_VALIDOS = {"VALIDADO", "PUBLICADO"}


def leer_json(ruta: Path) -> dict | None:
    """Lee JSON sin interrumpir el dashboard si falta o está dañado."""
    try:
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


def leer_csv(ruta: Path) -> pd.DataFrame | None:
    """Lee CSV con un resultado comprensible ante archivos ausentes o inválidos."""
    try:
        return pd.read_csv(ruta) if ruta.exists() else None
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return None


def directorio_publicable(directorio: Path) -> bool:
    """Acepta un directorio sólo si su último período está validado."""
    historico = leer_csv(directorio / "historico_SDE.csv")
    estados = leer_csv(directorio / "estado_periodos.csv")
    if historico is None or historico.empty or estados is None or estados.empty:
        return False
    periodos_historico = historico["periodo"].map(normalizar_periodo)
    periodos_estado = estados["periodo"].map(normalizar_periodo)
    estados_normalizados = estados["estado"].map(normalizar_estado)
    if periodos_historico.isna().any() or periodos_estado.isna().any():
        return False
    ultimo_indice = historico.sort_values(["anio", "trimestre"]).index[-1]
    ultimo = periodos_historico.loc[ultimo_indice]
    fila = estados[periodos_estado == ultimo]
    if fila.empty:
        return False
    return estados_normalizados.loc[fila.index[-1]] in ESTADOS_VALIDOS


def seleccionar_fuente() -> tuple[Path | None, bool, str]:
    """Prioriza resultados locales validados y conserva el snapshot como contingencia."""
    if directorio_publicable(DIR_RESULTADOS):
        return DIR_RESULTADOS, False, "Resultados locales validados"
    if directorio_publicable(DIR_SNAPSHOT):
        return DIR_SNAPSHOT, True, "Snapshot agregado validado"
    return None, False, "Sin datos validados"


def formato_numero(valor: object, decimales: int = 0, prefijo: str = "") -> str:
    """Formatea métricas y evita mostrar errores cuando el dato no existe."""
    if valor is None or pd.isna(valor):
        return "No disponible"
    return f"{prefijo}{float(valor):,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formato_tasa(valor: object) -> str:
    return "No disponible" if valor is None or pd.isna(valor) else f"{float(valor):.2f}%"


def boton_descarga(ruta: Path, etiqueta: str, clave: str) -> None:
    """Ofrece un archivo existente o explica claramente su ausencia."""
    if ruta.exists() and ruta.is_file():
        st.download_button(
            etiqueta,
            data=ruta.read_bytes(),
            file_name=ruta.name,
            key=clave,
        )
    else:
        st.caption(f"{ruta.name}: no disponible para esta fuente.")


DIR_ACTIVO, USANDO_SNAPSHOT, DESCRIPCION_FUENTE = seleccionar_fuente()

st.title("Mercado laboral en Santiago del Estero - La Banda")
st.markdown("**Fuente:** Encuesta Permanente de Hogares — INDEC.")
st.markdown("**Alcance territorial:** Aglomerado 18 — Santiago del Estero - La Banda.")
st.caption(
    "Los datos públicos son producidos por el INDEC. Los indicadores son calculados por "
    "este pipeline mediante PONDERA; no constituyen una nueva estadística oficial provincial."
)

if DIR_ACTIVO is None:
    st.error(
        "No hay un histórico acompañado por estados de validación. Se conserva cualquier "
        "archivo existente, pero no se lo muestra hasta que supere los controles críticos."
    )
    st.stop()

if USANDO_SNAPSHOT:
    st.info(
        "El tablero está usando el snapshot agregado y validado. No necesita ZIP ni "
        "microdatos individuales para funcionar."
    )
else:
    st.success("El tablero está usando resultados locales validados.")

historico = leer_csv(DIR_ACTIVO / "historico_SDE.csv")
estados = leer_csv(DIR_ACTIVO / "estado_periodos.csv")
meta_historico = leer_json(DIR_ACTIVO / "historico_SDE.meta.json") or {}

if historico is None or historico.empty or estados is None:
    st.error("Los archivos validados no pudieron leerse. Se requiere revisar el snapshot.")
    st.stop()

historico["periodo"] = historico["periodo"].map(normalizar_periodo)
estados["periodo"] = estados["periodo"].map(normalizar_periodo)
estados["estado"] = estados["estado"].map(normalizar_estado)
if historico["periodo"].isna().any() or estados["periodo"].isna().any():
    st.error("Hay períodos fuera del formato canónico YYYYTx en los archivos del dashboard.")
    st.stop()

periodos_validos = set(
    estados.loc[estados["estado"].isin(ESTADOS_VALIDOS), "periodo"]
)
df = historico[historico["periodo"].isin(periodos_validos)].copy()
df = df.sort_values(["anio", "trimestre"]).reset_index(drop=True)
if df.empty:
    st.error("No hay períodos con estado VALIDADO o PUBLICADO.")
    st.stop()

ultimo = df.iloc[-1]
periodo_ultimo = str(ultimo["periodo"])
estado_ultimo = estados.loc[estados["periodo"].astype(str) == periodo_ultimo].iloc[-1]

tab_resumen, tab_evolucion, tab_ingresos, tab_calidad, tab_documentacion = st.tabs([
    "Resumen ejecutivo",
    "Evolución laboral",
    "Ingresos",
    "Calidad y auditoría",
    "Documentación y descargas",
])


with tab_resumen:
    st.header("Resumen ejecutivo")
    a, b, c = st.columns(3)
    a.metric("Último período validado", periodo_ultimo)
    b.metric("Estado de validación", str(estado_ultimo["estado"]))
    b.caption(str(estado_ultimo.get("mensaje", "Sin mensaje adicional")))
    c.metric(
        "Fecha de actualización",
        str(meta_historico.get("ultima_ejecucion_exitosa")
            or meta_historico.get("fecha_hora_generacion") or "No disponible"),
    )

    st.subheader("Indicadores principales")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tasa de actividad oficial", formato_tasa(ultimo.get("tasa_actividad_oficial")))
    c2.metric("Tasa de empleo oficial", formato_tasa(ultimo.get("tasa_empleo_oficial")))
    c3.metric("Tasa de desocupación", formato_tasa(ultimo.get("tasa_desocupacion")))
    c4.metric("Proporción inactiva total", formato_tasa(ultimo.get("proporcion_inactiva_total")))
    st.caption(
        "La proporción inactiva total es complementaria: 100 menos la tasa de actividad oficial."
    )

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Personas en muestra", formato_numero(ultimo.get("n_personas_muestra")))
    c6.metric("Hogares en muestra", formato_numero(ultimo.get("n_hogares_muestra")))
    c7.metric("Población total expandida", formato_numero(ultimo.get("poblacion_expandida_total")))
    c8.metric("Tasa de informalidad", formato_tasa(ultimo.get("tasa_informalidad")))
    if pd.isna(ultimo.get("tasa_informalidad")):
        st.warning("La informalidad no está disponible porque la variable EMPLEO no existe en ese período.")
    st.info(
        "Advertencia territorial: los microdatos públicos identifican el aglomerado conjunto y "
        "no permiten separar Santiago Capital de La Banda."
    )


with tab_evolucion:
    st.header("Evolución laboral")
    st.subheader("Actividad y empleo oficiales")
    columnas_conjuntas = [
        col for col in ["tasa_actividad_oficial", "tasa_empleo_oficial"] if col in df.columns
    ]
    if columnas_conjuntas:
        st.line_chart(df.set_index("periodo")[columnas_conjuntas])
    else:
        st.info("Las tasas oficiales todavía no están disponibles.")

    izquierda, derecha = st.columns(2)
    with izquierda:
        st.subheader("Desocupación")
        if "tasa_desocupacion" in df.columns:
            st.line_chart(df.set_index("periodo")[["tasa_desocupacion"]])
        else:
            st.info("La tasa de desocupación no está disponible.")
    with derecha:
        st.subheader("Proporción inactiva total")
        if "proporcion_inactiva_total" in df.columns:
            st.line_chart(df.set_index("periodo")[["proporcion_inactiva_total"]])
        else:
            st.info("El indicador complementario no está disponible.")

    st.subheader("Informalidad")
    informalidad = df[["periodo", "tasa_informalidad"]].dropna() if "tasa_informalidad" in df else pd.DataFrame()
    if len(informalidad) >= 2:
        st.line_chart(informalidad.set_index("periodo"))
    else:
        st.info("No hay suficientes períodos con EMPLEO disponible para mostrar una evolución.")
    st.caption(
        "En 2023T1, 2023T2 y 2023T3, la variable necesaria para estimar informalidad "
        "no está disponible. Por ese motivo, el indicador se presenta como no disponible "
        "y no se realiza imputación ni se reemplazan faltantes por cero."
    )


with tab_ingresos:
    st.header("Ingresos nominales")
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Ingreso promedio ponderado",
        formato_numero(ultimo.get("ingreso_promedio_ponderado_observado"), prefijo="$"),
    )
    c2.metric(
        "Ingreso mediano",
        formato_numero(ultimo.get("ingreso_mediano_observado"), prefijo="$"),
    )
    c3.metric(
        "No respuesta de ingresos",
        formato_tasa(ultimo.get("tasa_no_respuesta_ingresos_ocupados")),
    )
    st.warning(
        "Los ingresos son nominales y no representan directamente variaciones del poder "
        "adquisitivo. Para comparaciones reales se requiere deflactación."
    )
    columnas_ingresos = [
        col for col in [
            "ingreso_promedio_ponderado_observado", "ingreso_mediano_observado"
        ] if col in df.columns
    ]
    if columnas_ingresos:
        st.line_chart(df.set_index("periodo")[columnas_ingresos])
    else:
        st.info("No hay una serie de ingresos disponible.")


with tab_calidad:
    st.header("Calidad y auditoría")
    validados = int(estados["estado"].isin(ESTADOS_VALIDOS).sum())
    advertencias = 0
    for periodo in df["periodo"].astype(str):
        esquema_periodo = leer_json(DIR_ACTIVO / f"validacion_esquema_{periodo}.json") or {}
        if any(
            resultado.get("nivel") == "advertencia"
            for resultado in esquema_periodo.values()
            if isinstance(resultado, dict)
        ):
            advertencias += 1
    c1, c2, c3 = st.columns(3)
    c1.metric("Períodos validados", validados)
    c2.metric("Períodos con advertencias", advertencias)
    c3.metric("Última ejecución", str(estado_ultimo["estado"]))

    st.subheader("Estado de períodos")
    st.dataframe(estados, width="stretch", hide_index=True)

    periodo_seleccionado = st.selectbox(
        "Período a auditar", df["periodo"].astype(str).tolist(), index=len(df) - 1
    )
    fila_periodo = df[df["periodo"].astype(str) == periodo_seleccionado].iloc[-1]
    r1, r2, r3 = st.columns(3)
    r1.metric("Personas en muestra", formato_numero(fila_periodo.get("n_personas_muestra")))
    r2.metric("Hogares en muestra", formato_numero(fila_periodo.get("n_hogares_muestra")))
    r3.metric(
        "Población expandida", formato_numero(fila_periodo.get("poblacion_expandida_total"))
    )
    izquierda, derecha = st.columns(2)
    with izquierda:
        st.subheader("Variables, nulos y códigos especiales")
        calidad = leer_csv(DIR_ACTIVO / f"calidad_datos_SDE_{periodo_seleccionado}.csv")
        if calidad is not None and not calidad.empty:
            st.dataframe(calidad, width="stretch", hide_index=True)
        else:
            calidad_agregada = leer_csv(DIR_ACTIVO / "calidad_snapshot_SDE.csv")
            if calidad_agregada is not None:
                fila_calidad = calidad_agregada[
                    calidad_agregada["periodo"].astype(str) == periodo_seleccionado
                ]
                st.dataframe(fila_calidad, width="stretch", hide_index=True)
                st.caption(
                    "Control agregado del snapshot. Los conteos de nulos y códigos especiales por "
                    "variable requieren regenerar el período desde los microdatos."
                )
            else:
                st.info("No hay un reporte de calidad disponible para este período.")
    with derecha:
        st.subheader("Cambios de esquema")
        esquema = leer_json(DIR_ACTIVO / f"validacion_esquema_{periodo_seleccionado}.json")
        if esquema:
            for base in ["individual", "hogar"]:
                resultado = esquema.get(base, {})
                st.write(f"**Base {base}:** {resultado.get('nivel', 'sin estado')}")
                faltantes = resultado.get("obligatorias_faltantes", [])
                opcionales = resultado.get("opcionales_faltantes", [])
                st.caption(
                    f"Obligatorias faltantes: {faltantes or 'ninguna'} · "
                    f"Opcionales faltantes: {opcionales or 'ninguna'}"
                )
        else:
            st.info("No hay validación de esquema disponible para este período.")

    st.subheader("Validaciones lógicas")
    validacion_publicacion = leer_json(
        DIR_ACTIVO / f"validacion_publicacion_{periodo_seleccionado}.json"
    )
    if validacion_publicacion and validacion_publicacion.get("controles"):
        st.dataframe(
            pd.DataFrame(validacion_publicacion["controles"]),
            width="stretch",
            hide_index=True,
        )
    else:
        fila = df[df["periodo"].astype(str) == periodo_seleccionado].iloc[-1]
        chequeos = pd.DataFrame([
            {"control": "población total positiva", "cumple": fila["poblacion_expandida_total"] > 0},
            {"control": "tasas oficiales entre 0 y 100", "cumple": all(
                0 <= float(fila[col]) <= 100
                for col in ["tasa_actividad_oficial", "tasa_empleo_oficial", "tasa_desocupacion"]
            )},
            {"control": "actividad + proporción inactiva = 100", "cumple": abs(
                float(fila["tasa_actividad_oficial"])
                + float(fila["proporcion_inactiva_total"]) - 100
            ) <= 0.02},
        ])
        st.dataframe(chequeos, width="stretch", hide_index=True)

    boton_descarga(
        DIR_ACTIVO / f"indicadores_SDE_{periodo_seleccionado}.meta.json",
        "Descargar metadatos del período",
        f"meta_auditoria_{periodo_seleccionado}",
    )


with tab_documentacion:
    st.header("Documentación y descargas")
    st.caption(f"Fuente activa: {DESCRIPCION_FUENTE}.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Datos agregados")
        boton_descarga(DIR_ACTIVO / "historico_SDE.csv", "Descargar histórico", "dl_hist")
        boton_descarga(
            DIR_ACTIVO / f"indicadores_SDE_{periodo_ultimo}.csv",
            f"Descargar indicadores {periodo_ultimo}",
            "dl_ind",
        )
        boton_descarga(
            DIR_ACTIVO / f"calidad_datos_SDE_{periodo_ultimo}.csv",
            f"Descargar calidad {periodo_ultimo}",
            "dl_cal",
        )
        boton_descarga(DIR_ACTIVO / "estado_periodos.csv", "Descargar estado de períodos", "dl_estado")
    with c2:
        st.subheader("Metadatos y manifiesto")
        boton_descarga(
            DIR_ACTIVO / "historico_SDE.meta.json",
            "Descargar metadatos del histórico",
            "dl_meta_hist",
        )
        boton_descarga(
            DIR_ACTIVO / "manifest_salidas.json",
            "Descargar manifiesto de salidas",
            "dl_manifest",
        )
        boton_descarga(
            DIR_ACTIVO / f"validacion_esquema_{periodo_ultimo}.json",
            "Descargar validación de esquema",
            "dl_esquema",
        )

    st.subheader("Guías")
    for nombre, etiqueta in [
        ("DICCIONARIO_DATOS.md", "Diccionario de datos"),
        ("GUIA_USO.md", "Guía de uso"),
        ("METODOLOGIA.md", "Metodología"),
    ]:
        ruta = DIR_ACTIVO / nombre
        if not ruta.exists():
            ruta = DIR_DOCS / nombre
        boton_descarga(ruta, f"Descargar {etiqueta}", f"doc_{nombre}")

    st.info(
        "Los posibles indicadores operativos futuros requieren bases internas y una "
        "definición institucional previa. No se derivan de los microdatos públicos."
    )


st.divider()
st.caption(
    "Práctica Profesionalizante II · ITSE 2026 · "
    "Achaval · Cabaña · Constantinidi · Gomez · Pinto Villegas"
)

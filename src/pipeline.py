"""
Pipeline ETL — Microdatos EPH · DGEyC Santiago del Estero
==========================================================
Práctica Profesionalizante II · ITSE 2026
Grupo: Achaval · Cabaña · Constantinidi · Gomez · Pinto Villegas

Descarga, procesa y consolida los microdatos de la Encuesta Permanente de
Hogares del INDEC para el aglomerado Santiago del Estero — La Banda (18).

Uso:
    python pipeline.py --anio 2025 --trimestre 4
    python pipeline.py --anio 2024
    python pipeline.py --todos
    python pipeline.py --anio 2025 --trimestre 4 --forzar
    python pipeline.py --calendario

Salidas (carpeta results/):
    historico_SDE.csv                      Base histórica acumulada
    historico_SDE.meta.json                Metadatos del histórico
    indicadores_SDE_<periodo>.csv          Indicadores del trimestre
    indicadores_SDE_<periodo>.meta.json    Metadatos de los indicadores
    calidad_datos_SDE_<periodo>.csv        Reporte de nulos y códigos especiales
    calidad_datos_SDE_<periodo>.meta.json  Metadatos del reporte de calidad
    base_unida_SDE_<periodo>.csv           Individual + hogar unidas por CODUSU
    base_unida_SDE_<periodo>.meta.json     Metadatos de la base unida
    validacion_esquema_<periodo>.json      Validación de esquema vs INDEC
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests


# ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────
PIPELINE_VERSION = "2.2.0"
AGLOMERADO_SDE = 18
URL_BASE       = "https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/"
ANIOS          = [2023, 2024, 2025]
TRIMESTRES     = [1, 2, 3, 4]

# Rutas relativas al directorio raíz del proyecto (un nivel arriba de src/)
RAIZ           = Path(__file__).resolve().parent.parent
DIR_DATOS      = RAIZ / "data"
DIR_RESULTADOS = RAIZ / "results"
DIR_LOGS       = RAIZ / "logs"

# Combinaciones a probar al leer los .txt (el INDEC varía entre trimestres)
LECTURAS = [
    {"sep": ";", "encoding": "utf-8"},
    {"sep": ";", "encoding": "latin1"},
    {"sep": ",", "encoding": "utf-8"},
    {"sep": ",", "encoding": "latin1"},
]

# Calendario de publicaciones INDEC — el INDEC publica cada trimestre
# aproximadamente 3 meses después del cierre. Formato: (mes, año_relativo).
# Ejemplo: T1 se publica en junio del mismo año, T4 se publica en marzo del año siguiente.
MES_PUBLICACION_INDEC = {
    1: ("Junio",      0),   # T1 → junio del mismo año
    2: ("Septiembre", 0),   # T2 → septiembre del mismo año
    3: ("Diciembre",  0),   # T3 → diciembre del mismo año
    4: ("Marzo",      1),   # T4 → marzo del año siguiente
}

# Esquema esperado de la EPH — variables obligatorias para que el pipeline funcione
# Si alguna falta, el INDEC cambió algo crítico y hay que revisar el código.
ESQUEMA_OBLIGATORIO_INDIVIDUAL = ["AGLOMERADO", "PONDERA", "ESTADO", "P21", "CH04", "CH06", "CODUSU", "NRO_HOGAR"]
ESQUEMA_OBLIGATORIO_HOGAR      = ["AGLOMERADO", "REALIZADA", "CODUSU", "NRO_HOGAR"]
# Variables opcionales — si faltan se reporta pero el pipeline sigue
ESQUEMA_OPCIONAL_INDIVIDUAL    = ["EMPLEO"]  # desde 4T2023


# ─── LOGGING ────────────────────────────────────────────────────────────────
def configurar_logging() -> logging.Logger:
    """Configura logger con salida simultánea a consola y archivo."""
    DIR_LOGS.mkdir(exist_ok=True)
    archivo = DIR_LOGS / f"pipeline_{datetime.now():%Y%m%d_%H%M%S}.log"

    logger = logging.getLogger("pipeline_eph")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(archivo, encoding="utf-8"); fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout); ch.setFormatter(fmt)
    logger.addHandler(fh); logger.addHandler(ch)
    return logger


log = configurar_logging()


# ─── EXTRACCIÓN ─────────────────────────────────────────────────────────────
def descargar_zip(anio: int, trimestre: int, forzar: bool = False) -> Optional[Path]:
    """Descarga el ZIP del trimestre desde el FTP del INDEC."""
    DIR_DATOS.mkdir(exist_ok=True)
    nombre = f"EPH_usu_{trimestre}_Trim_{anio}_txt.zip"
    ruta = DIR_DATOS / nombre

    if ruta.exists() and not forzar:
        log.info(f"  Ya existe: {nombre} (se reutiliza)")
        return ruta

    url = URL_BASE + nombre
    log.info(f"  Descargando {nombre}...")
    try:
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(ruta, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        log.info(f"  Descargado ({ruta.stat().st_size/1024:.0f} KB)")
        return ruta
    except requests.RequestException as e:
        log.error(f"  Error de descarga: {e}")
        return None


def extraer_zip(ruta_zip: Path, anio: int, trimestre: int) -> tuple[Optional[Path], Optional[Path]]:
    """Descomprime el ZIP y devuelve rutas a los archivos individual y hogar."""
    destino = DIR_DATOS / f"t{trimestre}_{anio}"
    destino.mkdir(exist_ok=True)

    try:
        with zipfile.ZipFile(ruta_zip) as z:
            z.extractall(destino)
    except zipfile.BadZipFile:
        log.error(f"  ZIP corrupto: {ruta_zip.name}")
        return None, None

    # Búsqueda recursiva (algunos ZIPs anidan los archivos)
    ind = next((p for p in destino.rglob("*.txt") if "individual" in p.name.lower()), None)
    hog = next((p for p in destino.rglob("*.txt") if "hogar" in p.name.lower()), None)

    if not ind or not hog:
        log.error("  No se encontraron los archivos individual/hogar")
    return ind, hog


def leer_archivo_eph(ruta: Path) -> Optional[pd.DataFrame]:
    """Lee un .txt de la EPH probando varias combinaciones de separador/codificación.

    Valida que AGLOMERADO esté como columna real (no concatenada con otras),
    requiriendo un mínimo razonable de columnas para descartar lecturas inválidas.
    """
    for opciones in LECTURAS:
        try:
            df = pd.read_csv(ruta, low_memory=False, **opciones)
            # Una lectura válida tiene AGLOMERADO como columna y al menos 30 columnas
            # (los archivos EPH reales tienen 98+ en hogar y 235+ en individual)
            if "AGLOMERADO" in df.columns and len(df.columns) >= 30:
                return df
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    log.error(f"  No se pudo leer {ruta.name} con ningún formato conocido")
    return None


# ─── TRANSFORMACIÓN ─────────────────────────────────────────────────────────
def filtrar_sde(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra el aglomerado 18 (Santiago del Estero — La Banda)."""
    return df[df["AGLOMERADO"] == AGLOMERADO_SDE].copy().reset_index(drop=True)


def cargar_y_filtrar(ruta_ind: Path, ruta_hog: Path,
                      anio: int, trimestre: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carga ambas bases, valida el esquema, y las filtra por el aglomerado SDE."""
    df_ind = leer_archivo_eph(ruta_ind)
    df_hog = leer_archivo_eph(ruta_hog)
    if df_ind is None or df_hog is None:
        raise RuntimeError("No se pudieron leer las bases EPH del trimestre.")

    # Validación de esquema — detecta cambios del INDEC antes de procesar
    val_ind = validar_esquema(df_ind, ESQUEMA_OBLIGATORIO_INDIVIDUAL,
                                ESQUEMA_OPCIONAL_INDIVIDUAL, "individual", anio, trimestre)
    val_hog = validar_esquema(df_hog, ESQUEMA_OBLIGATORIO_HOGAR,
                                [], "hogar", anio, trimestre)

    # Guardar reporte combinado
    DIR_RESULTADOS.mkdir(exist_ok=True)
    ruta_val = DIR_RESULTADOS / f"validacion_esquema_{anio}T{trimestre}.json"
    with open(ruta_val, "w", encoding="utf-8") as f:
        json.dump({"individual": val_ind, "hogar": val_hog}, f, ensure_ascii=False, indent=2)

    # Si falta algo obligatorio, abortamos
    if val_ind["nivel"] == "critico" or val_hog["nivel"] == "critico":
        raise RuntimeError(
            f"Esquema crítico: faltan variables obligatorias en {anio}T{trimestre}. "
            f"Revisar {ruta_val.name} para detalles."
        )

    sde_ind = filtrar_sde(df_ind)
    sde_hog = filtrar_sde(df_hog)

    log.info(f"  Individual: {len(df_ind):,} totales -> {len(sde_ind):,} en SDE")
    log.info(f"  Hogar:      {len(df_hog):,} totales -> {len(sde_hog):,} en SDE")
    return sde_ind, sde_hog


def porcentaje(num: float, den: float, decimales: int = 2) -> Optional[float]:
    """Calcula porcentaje con manejo seguro de división por cero."""
    return round(num / den * 100, decimales) if den > 0 else None


def calcular_indicadores(sde_ind: pd.DataFrame, sde_hog: pd.DataFrame,
                          anio: int, trimestre: int) -> dict:
    """Calcula los indicadores del mercado laboral y operativos del trimestre."""

    # Subpoblaciones según criterio oficial INDEC
    mayores10 = sde_ind[sde_ind["ESTADO"].isin([1, 2, 3])]
    pea       = sde_ind[sde_ind["ESTADO"].isin([1, 2])]
    ocupados  = sde_ind[sde_ind["ESTADO"] == 1]
    desocup   = sde_ind[sde_ind["ESTADO"] == 2]
    inactivos = sde_ind[sde_ind["ESTADO"] == 3]

    # Pesos expandidos
    p_pob   = sde_ind["PONDERA"].sum()
    p_may10 = mayores10["PONDERA"].sum()
    p_pea   = pea["PONDERA"].sum()
    p_ocup  = ocupados["PONDERA"].sum()
    p_des   = desocup["PONDERA"].sum()
    p_inact = inactivos["PONDERA"].sum()

    # Informalidad (EMPLEO existe desde 4T2023 en adelante)
    tasa_inf = None
    if "EMPLEO" in ocupados.columns:
        ocup_val = ocupados[ocupados["EMPLEO"].isin([1, 2])]
        if len(ocup_val) > 0:
            informales = ocup_val[ocup_val["EMPLEO"] == 2]["PONDERA"].sum()
            tasa_inf = porcentaje(informales, ocup_val["PONDERA"].sum())

    # Ingreso de la ocupación principal (P21) — convertir a numérico una sola vez
    ocupados = ocupados.copy()
    ocupados["P21"] = pd.to_numeric(ocupados["P21"], errors="coerce")
    ocupados["PONDERA"] = pd.to_numeric(ocupados["PONDERA"], errors="coerce")

    ingresos_validos = ocupados[ocupados["P21"] > 0]
    nr_ingresos = int((ocupados["P21"] == -9).sum())

    ingreso_simple   = round(ingresos_validos["P21"].mean(), 0) if len(ingresos_validos) else None
    ingreso_mediano  = round(ingresos_validos["P21"].median(), 0) if len(ingresos_validos) else None
    ingreso_ponderado = None
    if len(ingresos_validos) > 0:
        peso_ing = ingresos_validos["PONDERA"].sum()
        if peso_ing > 0:
            ingreso_ponderado = round(
                (ingresos_validos["P21"] * ingresos_validos["PONDERA"]).sum() / peso_ing, 0
            )

    return {
        # Identificación
        "anio":              anio,
        "trimestre":         trimestre,
        "periodo":           f"{anio}T{trimestre}",
        "aglomerado":        AGLOMERADO_SDE,
        # Muestra
        "n_personas_muestra": len(sde_ind),
        "n_hogares_muestra":  len(sde_hog),
        # Población expandida
        "poblacion_expandida_total":    int(p_pob),
        "poblacion_expandida_mayor10":  int(p_may10),
        "pea_expandida":                int(p_pea),
        "ocupados_expandidos":          int(p_ocup),
        "desocupados_expandidos":       int(p_des),
        "inactivos_expandidos":         int(p_inact),
        # Tasas mercado laboral
        "tasa_actividad":     porcentaje(p_pea,   p_may10),
        "tasa_empleo":        porcentaje(p_ocup,  p_may10),
        "tasa_desocupacion":  porcentaje(p_des,   p_pea),
        "tasa_inactividad":   porcentaje(p_inact, p_may10),
        "tasa_informalidad":  tasa_inf,
        # Ingresos
        "ingreso_promedio_observado":           ingreso_simple,
        "ingreso_mediano_observado":            ingreso_mediano,
        "ingreso_promedio_ponderado_observado": ingreso_ponderado,
        "n_ocupados_con_ingreso_valido":        len(ingresos_validos),
        "n_ocupados_sin_respuesta_ingreso":     nr_ingresos,
        "tasa_no_respuesta_ingresos_ocupados":  porcentaje(nr_ingresos, len(ocupados)) if len(ocupados) else None,
        # Operativos
        "hogares_encuestados":      int((sde_hog["REALIZADA"] == 1).sum()),
        "tasa_no_respuesta_hogar":  porcentaje((sde_hog["REALIZADA"] == 0).sum(), len(sde_hog)),
        # Trazabilidad
        "fecha_procesamiento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fuente":              "INDEC - EPH microdatos públicos",
    }


def reporte_calidad(df: pd.DataFrame, columnas_clave: list[str]) -> pd.DataFrame:
    """Cuenta nulos y códigos especiales (-9, -8, -7) por columna clave."""
    filas = []
    for col in columnas_clave:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        filas.append({
            "columna":           col,
            "nulos":             int(s.isna().sum()),
            "codigo_-9_no_resp": int((s == -9).sum()),
            "codigo_-8":         int((s == -8).sum()),
            "codigo_-7":         int((s == -7).sum()),
            "validos":           int((s.notna() & ~s.isin([-9, -8, -7])).sum()),
        })
    return pd.DataFrame(filas)


def unir_bases(sde_ind: pd.DataFrame, sde_hog: pd.DataFrame) -> pd.DataFrame:
    """Une individual + hogar por CODUSU + NRO_HOGAR (clave estándar EPH)."""
    claves = ["CODUSU", "NRO_HOGAR"]
    if not all(c in sde_ind.columns and c in sde_hog.columns for c in claves):
        log.warning("  No se encontraron claves CODUSU/NRO_HOGAR — se omite unión")
        return pd.DataFrame()
    return sde_ind.merge(sde_hog, on=claves, how="left", suffixes=("", "_hog"))


# ─── METADATOS ──────────────────────────────────────────────────────────────
# Diccionario de columnas del histórico — usado para embeber en metadatos
DICCIONARIO_COLUMNAS = {
    "anio": "Año del trimestre relevado",
    "trimestre": "Número de trimestre (1 a 4)",
    "periodo": "Período en formato AAAATtrim",
    "aglomerado": "Código del aglomerado urbano EPH (18 = SDE - La Banda)",
    "n_personas_muestra": "Personas relevadas en la muestra del aglomerado",
    "n_hogares_muestra": "Hogares relevados en la muestra del aglomerado",
    "poblacion_expandida_total": "Población total estimada (suma de PONDERA)",
    "poblacion_expandida_mayor10": "Población de 10 años o más estimada",
    "pea_expandida": "Población Económicamente Activa estimada",
    "ocupados_expandidos": "Personas ocupadas estimadas",
    "desocupados_expandidos": "Personas desocupadas estimadas",
    "inactivos_expandidos": "Personas inactivas estimadas",
    "tasa_actividad": "Tasa de actividad (PEA / Pob ≥10) × 100",
    "tasa_empleo": "Tasa de empleo (Ocupados / Pob ≥10) × 100",
    "tasa_desocupacion": "Tasa de desocupación (Desocupados / PEA) × 100",
    "tasa_inactividad": "Tasa de inactividad (Inactivos / Pob ≥10) × 100",
    "tasa_informalidad": "% de ocupados sin registro (null antes de 4T2023)",
    "ingreso_promedio_observado": "Promedio simple del ingreso ocupación principal",
    "ingreso_mediano_observado": "Mediana del ingreso ocupación principal",
    "ingreso_promedio_ponderado_observado": "Ingreso promedio ponderado por PONDERA",
    "n_ocupados_con_ingreso_valido": "Cantidad de ocupados con P21 > 0",
    "n_ocupados_sin_respuesta_ingreso": "Cantidad de ocupados con P21 = -9",
    "tasa_no_respuesta_ingresos_ocupados": "% de ocupados que no respondieron ingreso",
    "hogares_encuestados": "Hogares con REALIZADA = 1",
    "tasa_no_respuesta_hogar": "% de hogares con REALIZADA = 0",
    "fecha_procesamiento": "Fecha y hora del procesamiento",
    "fuente": "Fuente de los datos",
}


def calcular_hash(ruta: Path) -> str:
    """Calcula el SHA-256 de un archivo (8 primeros caracteres)."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def generar_metadatos(
    ruta_csv: Path,
    df: pd.DataFrame,
    descripcion: str,
    anio: Optional[int] = None,
    trimestre: Optional[int] = None,
) -> dict:
    """Genera el diccionario de metadatos para un archivo CSV."""
    # Esquema de columnas con tipo y descripción
    esquema = []
    for col in df.columns:
        esquema.append({
            "nombre": col,
            "tipo": str(df[col].dtype),
            "descripcion": DICCIONARIO_COLUMNAS.get(col, "(sin descripción)"),
            "nulos": int(df[col].isna().sum()),
        })

    # URL específica del trimestre si aplica
    fuente_url = URL_BASE
    if anio and trimestre:
        fuente_url += f"EPH_usu_{trimestre}_Trim_{anio}_txt.zip"

    return {
        "archivo": ruta_csv.name,
        "descripcion": descripcion,
        "version_pipeline": PIPELINE_VERSION,
        "fecha_generacion": datetime.now().isoformat(),
        "fuente": {
            "organismo": "INDEC",
            "operativo": "Encuesta Permanente de Hogares (EPH)",
            "url": fuente_url,
            "aglomerado_codigo": AGLOMERADO_SDE,
            "aglomerado_nombre": "Santiago del Estero - La Banda",
        },
        "periodo": {
            "anio": anio,
            "trimestre": trimestre,
        } if anio and trimestre else None,
        "estructura": {
            "n_filas": len(df),
            "n_columnas": len(df.columns),
            "encoding": "utf-8",
            "separador": ",",
        },
        "integridad": {
            "hash_sha256_truncado": calcular_hash(ruta_csv),
        },
        "esquema": esquema,
        "notas": [
            "tasa_informalidad es null en trimestres anteriores al 4T2023.",
            "Valores monetarios en pesos argentinos nominales (no deflactados).",
            "El pipeline no imputa valores faltantes.",
        ],
    }


def guardar_metadatos(ruta_csv: Path, metadatos: dict) -> None:
    """Guarda el archivo .meta.json junto al CSV."""
    ruta_json = ruta_csv.with_suffix(".meta.json")
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(metadatos, f, ensure_ascii=False, indent=2)


# ─── CALENDARIO Y VALIDACIÓN DE ESQUEMA ─────────────────────────────────────
def fecha_publicacion_esperada(anio: int, trimestre: int) -> tuple[str, int]:
    """Devuelve (mes_nombre, año) en que el INDEC debería publicar ese trimestre."""
    mes_nombre, offset_anio = MES_PUBLICACION_INDEC[trimestre]
    return mes_nombre, anio + offset_anio


def estado_trimestre(anio: int, trimestre: int) -> str:
    """Determina el estado de un trimestre: procesado, esperando, futuro."""
    ruta_indicadores = DIR_RESULTADOS / f"indicadores_SDE_{anio}T{trimestre}.csv"
    if ruta_indicadores.exists():
        return "procesado"

    mes_nombre, anio_pub = fecha_publicacion_esperada(anio, trimestre)
    mes_num = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
               "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}[mes_nombre]
    hoy = datetime.now()
    if (anio_pub, mes_num) <= (hoy.year, hoy.month):
        return "esperando"  # ya debería estar publicado pero no procesado
    return "futuro"


def mostrar_calendario() -> None:
    """Imprime el calendario completo de publicaciones EPH-INDEC."""
    iconos = {"procesado": "✓", "esperando": "⏳", "futuro": "○"}
    descripciones = {
        "procesado": "Publicado y procesado",
        "esperando": "Esperando publicación o procesamiento",
        "futuro":    "Aún no publicado",
    }

    log.info("\n" + "═" * 65)
    log.info("  CALENDARIO DE PUBLICACIONES EPH-INDEC · Aglomerado 18")
    log.info("═" * 65)
    log.info(f"  {'Trimestre':<12} {'Publicación esperada':<25} {'Estado':<25}")
    log.info("  " + "─" * 62)

    for anio in ANIOS + [max(ANIOS) + 1]:  # incluir un año extra futuro
        for trim in TRIMESTRES:
            mes, anio_pub = fecha_publicacion_esperada(anio, trim)
            est = estado_trimestre(anio, trim)
            log.info(f"  {anio}T{trim:<10} {mes} {anio_pub:<19} {iconos[est]} {descripciones[est]}")

    log.info("═" * 65 + "\n")


def validar_esquema(df: pd.DataFrame, esquema_obligatorio: list[str],
                     esquema_opcional: list[str], base: str,
                     anio: int, trimestre: int) -> dict:
    """Compara las columnas reales del archivo con el esquema esperado.

    Detecta:
    - Columnas obligatorias faltantes (CRÍTICO — el pipeline puede fallar)
    - Columnas opcionales faltantes (esperable en algunos trimestres)
    - Columnas nuevas (puede indicar cambios del INDEC)
    """
    columnas_reales = set(df.columns)
    obligatorias = set(esquema_obligatorio)
    opcionales = set(esquema_opcional)

    faltantes_obligatorias = sorted(obligatorias - columnas_reales)
    faltantes_opcionales = sorted(opcionales - columnas_reales)
    presentes = sorted(obligatorias & columnas_reales)

    nivel = "ok"
    if faltantes_obligatorias:
        nivel = "critico"
    elif faltantes_opcionales:
        nivel = "advertencia"

    resultado = {
        "periodo": f"{anio}T{trimestre}",
        "base": base,
        "nivel": nivel,
        "n_columnas_totales": len(columnas_reales),
        "obligatorias_presentes": presentes,
        "obligatorias_faltantes": faltantes_obligatorias,
        "opcionales_faltantes": faltantes_opcionales,
        "fecha_validacion": datetime.now().isoformat(),
    }

    if nivel == "critico":
        log.error(f"  ✗ Esquema crítico en base {base}: faltan {faltantes_obligatorias}")
    elif nivel == "advertencia":
        log.warning(f"  ⚠ Esquema con advertencia en base {base}: faltan opcionales {faltantes_opcionales}")
    else:
        log.info(f"  ✓ Esquema OK en base {base}: todas las variables obligatorias presentes")

    return resultado


# ─── CARGA ──────────────────────────────────────────────────────────────────
def guardar_trimestre(ind: dict, sde_ind: pd.DataFrame, sde_hog: pd.DataFrame) -> None:
    """Guarda los archivos del trimestre, sus metadatos, y actualiza el histórico."""
    DIR_RESULTADOS.mkdir(exist_ok=True)
    periodo = ind["periodo"]
    anio, trim = ind["anio"], ind["trimestre"]

    # 1. Indicadores del trimestre + metadatos
    df_ind = pd.DataFrame([ind])
    ruta_ind = DIR_RESULTADOS / f"indicadores_SDE_{periodo}.csv"
    df_ind.to_csv(ruta_ind, index=False)
    guardar_metadatos(ruta_ind, generar_metadatos(
        ruta_ind, df_ind,
        f"Indicadores calculados del trimestre {periodo} para el aglomerado SDE.",
        anio, trim,
    ))

    # 2. Reporte de calidad + metadatos
    reporte = reporte_calidad(sde_ind, ["ESTADO", "EMPLEO", "P21", "PONDERA", "CH04", "CH06"])
    ruta_cal = DIR_RESULTADOS / f"calidad_datos_SDE_{periodo}.csv"
    reporte.to_csv(ruta_cal, index=False)
    guardar_metadatos(ruta_cal, generar_metadatos(
        ruta_cal, reporte,
        f"Reporte de calidad de variables clave del trimestre {periodo}.",
        anio, trim,
    ))

    # 3. Base unida individual-hogar + metadatos
    base = unir_bases(sde_ind, sde_hog)
    if not base.empty:
        ruta_base = DIR_RESULTADOS / f"base_unida_SDE_{periodo}.csv"
        base.to_csv(ruta_base, index=False)
        guardar_metadatos(ruta_base, generar_metadatos(
            ruta_base, base,
            f"Microdatos individuo + hogar unidos por CODUSU + NRO_HOGAR ({periodo}).",
            anio, trim,
        ))

    # 4. Histórico acumulado (reemplaza el período si ya existe)
    ruta_hist = DIR_RESULTADOS / "historico_SDE.csv"
    if ruta_hist.exists():
        hist = pd.read_csv(ruta_hist)
        hist = hist[hist["periodo"] != periodo]
        hist = pd.concat([hist, df_ind], ignore_index=True)
    else:
        hist = df_ind
    hist = hist.sort_values(["anio", "trimestre"]).reset_index(drop=True)
    hist.to_csv(ruta_hist, index=False)
    guardar_metadatos(ruta_hist, generar_metadatos(
        ruta_hist, hist,
        "Base histórica acumulada con todos los trimestres procesados.",
    ))

    log.info(f"  Guardado: 4 CSV + 4 metadatos JSON ({periodo})")
    log.info(f"  Histórico actualizado: {len(hist)} trimestres acumulados")


# ─── REPORTE EN CONSOLA ─────────────────────────────────────────────────────
def imprimir_resumen(ind: dict) -> None:
    """Resumen formateado de los indicadores del trimestre."""
    sep = "─" * 52
    log.info(f"\n  {sep}")
    log.info(f"  INDICADORES — SDE · {ind['periodo']}")
    log.info(f"  {sep}")
    log.info(f"  Muestra:              {ind['n_personas_muestra']:,} personas · {ind['n_hogares_muestra']:,} hogares")
    log.info(f"  Población expandida:  {ind['poblacion_expandida_total']:,}")
    log.info(f"  {sep}")
    log.info(f"  Tasa de actividad:    {ind['tasa_actividad']}%")
    log.info(f"  Tasa de empleo:       {ind['tasa_empleo']}%")
    log.info(f"  Tasa de desocupación: {ind['tasa_desocupacion']}%")
    log.info(f"  Tasa de inactividad:  {ind['tasa_inactividad']}%")
    log.info(f"  Informalidad:         {ind['tasa_informalidad']}%")
    log.info(f"  No resp. ingresos:    {ind['tasa_no_respuesta_ingresos_ocupados']}%")
    if ind["ingreso_promedio_ponderado_observado"]:
        log.info(f"  Ingreso prom. pond.:  ${ind['ingreso_promedio_ponderado_observado']:,.0f}")
    log.info(f"  {sep}")
    log.info(f"  Hogares encuestados:  {ind['hogares_encuestados']}")
    log.info(f"  {sep}\n")


# ─── ORQUESTACIÓN ───────────────────────────────────────────────────────────
def procesar_trimestre(anio: int, trimestre: int, forzar: bool = False) -> Optional[dict]:
    """Ejecuta el pipeline completo para un trimestre."""
    log.info(f"\n{'='*55}")
    log.info(f"  PIPELINE EPH — {anio} T{trimestre}")
    log.info(f"{'='*55}")

    try:
        log.info("\n[1/4] Extracción — descargando del INDEC...")
        ruta_zip = descargar_zip(anio, trimestre, forzar)
        if not ruta_zip:
            return None

        ruta_ind, ruta_hog = extraer_zip(ruta_zip, anio, trimestre)
        if not ruta_ind or not ruta_hog:
            return None

        log.info("\n[2/4] Transformación — cargando y filtrando...")
        sde_ind, sde_hog = cargar_y_filtrar(ruta_ind, ruta_hog, anio, trimestre)

        log.info("\n[3/4] Calculando indicadores con ponderadores...")
        indicadores = calcular_indicadores(sde_ind, sde_hog, anio, trimestre)
        imprimir_resumen(indicadores)

        log.info("[4/4] Guardando resultados...")
        guardar_trimestre(indicadores, sde_ind, sde_hog)

        log.info(f"\n  {anio}T{trimestre} procesado correctamente\n")
        return indicadores

    except Exception as e:
        log.exception(f"  Error procesando {anio}T{trimestre}: {e}")
        return None


def procesar_lote(anios: list[int], trimestres: list[int], forzar: bool = False) -> list[dict]:
    """Procesa todos los pares año/trimestre indicados."""
    resultados = []
    total = len(anios) * len(trimestres)
    log.info(f"\nPipeline multi-trimestre — {total} trimestres a procesar")

    for anio in anios:
        for trimestre in trimestres:
            res = procesar_trimestre(anio, trimestre, forzar)
            if res:
                resultados.append(res)

    log.info(f"\n{'='*55}")
    log.info(f"  Pipeline completado: {len(resultados)}/{total} trimestres")
    log.info(f"  Histórico: {DIR_RESULTADOS/'historico_SDE.csv'}")
    log.info(f"{'='*55}\n")
    return resultados


# ─── ENTRADA ────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline ETL — Microdatos EPH · DGEyC Santiago del Estero",
        epilog="Ejemplos:\n"
               "  python pipeline.py --anio 2025 --trimestre 4\n"
               "  python pipeline.py --anio 2024\n"
               "  python pipeline.py --todos\n"
               "  python pipeline.py --anio 2025 --trimestre 4 --forzar\n"
               "  python pipeline.py --calendario",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--anio",       type=int, help="Año a procesar (ej: 2025)")
    parser.add_argument("--trimestre",  type=int, choices=[1, 2, 3, 4], help="Trimestre 1-4")
    parser.add_argument("--todos",      action="store_true", help="Procesar 2023-2025 completo")
    parser.add_argument("--forzar",     action="store_true", help="Re-descargar aunque el ZIP exista")
    parser.add_argument("--calendario", action="store_true", help="Mostrar calendario de publicaciones INDEC")
    args = parser.parse_args()

    if args.calendario:
        mostrar_calendario()
    elif args.todos:
        procesar_lote(ANIOS, TRIMESTRES, args.forzar)
    elif args.anio and args.trimestre:
        procesar_trimestre(args.anio, args.trimestre, args.forzar)
    elif args.anio:
        procesar_lote([args.anio], TRIMESTRES, args.forzar)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

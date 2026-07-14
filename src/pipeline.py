"""
Pipeline ETL — Microdatos EPH · DGEyC Santiago del Estero
==========================================================
Práctica Profesionalizante II · ITSE 2026
Grupo: Achaval · Cabaña · Constantinidi · Gomez · Pinto Villegas

Descarga, procesa, valida y consolida microdatos públicos de la Encuesta
Permanente de Hogares del INDEC para el aglomerado 18, Santiago del Estero -
La Banda. Las salidas se publican en ``results/`` sólo si superan los controles
críticos. El snapshot para Streamlit se actualiza mediante una acción explícita.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

try:
    import requests
except ImportError:  # permite validar snapshots agregados sin dependencias de red
    requests = None  # type: ignore[assignment]


# ─── CONFIGURACIÓN ──────────────────────────────────────────────────────────
PIPELINE_VERSION = "3.0.0"
AGLOMERADO_SDE = 18
AGLOMERADO_NOMBRE = "Santiago del Estero - La Banda"
URL_BASE = "https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/"
ANIOS = [2023, 2024, 2025]
TRIMESTRES = [1, 2, 3, 4]
ESTADOS_PERMITIDOS = {
    "PENDIENTE", "DESCARGADO", "PROCESADO", "EN_REVISION",
    "VALIDADO", "FALLIDO", "PUBLICADO",
}
ESTADOS_VISIBLES_DASHBOARD = {"VALIDADO", "PUBLICADO"}

RAIZ = Path(__file__).resolve().parent.parent
DIR_DATOS = RAIZ / "data"
DIR_RESULTADOS = RAIZ / "results"
DIR_LOGS = RAIZ / "logs"
DIR_SNAPSHOT = RAIZ / "data_snapshot"

LECTURAS = [
    {"sep": ";", "encoding": "utf-8"},
    {"sep": ";", "encoding": "latin1"},
    {"sep": ",", "encoding": "utf-8"},
    {"sep": ",", "encoding": "latin1"},
]

MES_PUBLICACION_INDEC = {
    1: ("Junio", 0),
    2: ("Septiembre", 0),
    3: ("Diciembre", 0),
    4: ("Marzo", 1),
}

ESQUEMA_OBLIGATORIO_INDIVIDUAL = [
    "AGLOMERADO", "PONDERA", "ESTADO", "P21", "CH04", "CH06",
    "CODUSU", "NRO_HOGAR",
]
ESQUEMA_OBLIGATORIO_HOGAR = ["AGLOMERADO", "REALIZADA", "CODUSU", "NRO_HOGAR"]
ESQUEMA_OPCIONAL_INDIVIDUAL = ["EMPLEO"]

TASAS_PRINCIPALES = [
    "tasa_actividad_oficial",
    "tasa_empleo_oficial",
    "tasa_desocupacion",
    "proporcion_inactiva_total",
]
TASAS_10_MAS = [
    "tasa_actividad_10_mas",
    "tasa_empleo_10_mas",
    "tasa_inactividad_10_mas",
]

FORMULAS_INDICADORES = {
    "tasa_actividad_oficial": "PEA expandida / población total expandida × 100",
    "tasa_empleo_oficial": "ocupados expandidos / población total expandida × 100",
    "tasa_desocupacion": "desocupados expandidos / PEA expandida × 100",
    "proporcion_inactiva_total": "100 - tasa_actividad_oficial",
    "tasa_actividad_10_mas": "PEA expandida / población de 10 años y más expandida × 100",
    "tasa_empleo_10_mas": "ocupados expandidos / población de 10 años y más expandida × 100",
    "tasa_inactividad_10_mas": "inactivos expandidos / población de 10 años y más expandida × 100",
    "tasa_informalidad": (
        "ocupados expandidos con EMPLEO=2 / ocupados expandidos con EMPLEO en {1,2} × 100"
    ),
    "ingreso_promedio_ponderado_observado": (
        "suma(P21 × PONDERA) / suma(PONDERA), para ocupados con P21 > 0"
    ),
    "tasa_no_respuesta_ingresos_ocupados": (
        "ocupados de muestra con P21=-9 / ocupados de muestra × 100"
    ),
}

DICCIONARIO_COLUMNAS = {
    "anio": "Año del trimestre relevado",
    "trimestre": "Número de trimestre (1 a 4)",
    "periodo": "Período en formato AAAATn",
    "aglomerado": "Código del aglomerado urbano EPH",
    "n_personas_muestra": "Personas de la muestra del aglomerado",
    "n_hogares_muestra": "Hogares de la muestra del aglomerado",
    "poblacion_expandida_total": "Población total expandida mediante PONDERA",
    "poblacion_expandida_mayor10": "Población de 10 años y más expandida mediante PONDERA",
    "pea_expandida": "Población Económicamente Activa expandida",
    "ocupados_expandidos": "Personas ocupadas expandidas",
    "desocupados_expandidos": "Personas desocupadas expandidas",
    "inactivos_expandidos": "Personas inactivas de 10 años y más expandidas",
    "tasa_actividad_oficial": "Tasa de actividad principal sobre población total",
    "tasa_empleo_oficial": "Tasa de empleo principal sobre población total",
    "tasa_desocupacion": "Tasa de desocupación sobre la PEA",
    "proporcion_inactiva_total": (
        "Indicador complementario: población fuera de la PEA sobre población total"
    ),
    "tasa_actividad_10_mas": "Tasa específica de actividad de la población de 10 años y más",
    "tasa_empleo_10_mas": "Tasa específica de empleo de la población de 10 años y más",
    "tasa_inactividad_10_mas": "Tasa específica de inactividad de la población de 10 años y más",
    "tasa_informalidad": "Proporción de ocupados sin registro; nula si EMPLEO no está disponible",
    "ingreso_promedio_observado": "Promedio simple del ingreso nominal de la ocupación principal",
    "ingreso_mediano_observado": "Mediana del ingreso nominal de la ocupación principal",
    "ingreso_promedio_ponderado_observado": (
        "Promedio ponderado del ingreso nominal de la ocupación principal"
    ),
    "n_ocupados_con_ingreso_valido": "Ocupados de muestra con P21 mayor que cero",
    "n_ocupados_sin_respuesta_ingreso": "Ocupados de muestra con P21 igual a -9",
    "tasa_no_respuesta_ingresos_ocupados": "No respuesta de ingreso entre ocupados de muestra",
    "hogares_encuestados": "Hogares publicados con REALIZADA igual a 1",
    "tasa_no_respuesta_hogar": (
        "Proporción observada con REALIZADA igual a 0; no equivale a rechazo de campo"
    ),
    "fecha_procesamiento": "Fecha y hora de procesamiento",
    "fuente": "Fuente de los datos",
    "columna": "Variable evaluada",
    "nulos": "Cantidad de valores nulos",
    "codigo_-9_no_resp": "Cantidad con código especial -9",
    "codigo_-8": "Cantidad con código especial -8",
    "codigo_-7": "Cantidad con código especial -7",
    "validos": "Cantidad de valores válidos",
    "fecha_esperada": "Mes y año esperados de publicación",
    "fecha_deteccion": "Primera fecha en que se detectó el período",
    "fecha_procesamiento_estado": "Fecha de procesamiento registrada en el control",
    "intentos": "Cantidad de intentos de procesamiento",
    "estado": "Estado del período dentro del ciclo de publicación",
    "mensaje": "Resultado comprensible del último control",
    "ultima_actualizacion": "Fecha y hora de la última actualización del estado",
    "poblacion_total_positiva": "Indica si la población expandida es mayor que cero",
    "tasas_en_rango": "Indica si las tasas disponibles están entre 0 y 100",
    "actividad_inactividad_consistente": "Indica si actividad oficial más proporción inactiva suma 100",
    "periodo_duplicado": "Indica si el período aparece duplicado en el histórico",
    "estado_informalidad": "Disponibilidad del indicador de informalidad",
    "observacion": "Explicación del control agregado",
}

UNIDADES = {
    **{col: "porcentaje" for col in TASAS_PRINCIPALES + TASAS_10_MAS},
    "tasa_informalidad": "porcentaje",
    "tasa_no_respuesta_ingresos_ocupados": "porcentaje",
    "tasa_no_respuesta_hogar": "porcentaje",
    "ingreso_promedio_observado": "pesos argentinos nominales",
    "ingreso_mediano_observado": "pesos argentinos nominales",
    "ingreso_promedio_ponderado_observado": "pesos argentinos nominales",
}


# ─── LOGGING ────────────────────────────────────────────────────────────────
log = logging.getLogger("pipeline_eph")
log.addHandler(logging.NullHandler())


def configurar_logging(directorio: Path = DIR_LOGS) -> logging.Logger:
    """Configura logging de consola y archivo sin escribir durante los imports."""
    directorio.mkdir(parents=True, exist_ok=True)
    archivo = directorio / f"pipeline_{datetime.now():%Y%m%d_%H%M%S}.log"
    logger = logging.getLogger("pipeline_eph")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formato = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    archivo_handler = logging.FileHandler(archivo, encoding="utf-8")
    archivo_handler.setFormatter(formato)
    consola_handler = logging.StreamHandler(sys.stdout)
    consola_handler.setFormatter(formato)
    logger.addHandler(archivo_handler)
    logger.addHandler(consola_handler)
    return logger


# ─── UTILIDADES ─────────────────────────────────────────────────────────────
def ahora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def calcular_hash(ruta: Path) -> str:
    """Calcula el SHA-256 completo de un archivo."""
    h = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(8192), b""):
            h.update(bloque)
    return h.hexdigest()


def porcentaje(num: float, den: float, decimales: int = 2) -> Optional[float]:
    """Calcula un porcentaje y devuelve None si el denominador no es positivo."""
    if den is None or pd.isna(den) or den <= 0 or num is None or pd.isna(num):
        return None
    return round(float(num) / float(den) * 100, decimales)


def normalizar_periodo(valor: object) -> Optional[str]:
    """Convierte variantes legibles de período al formato canónico ``YYYYTx``."""
    if valor is None or pd.isna(valor):
        return None
    texto = str(valor).strip().upper()
    coincidencia = re.fullmatch(r"(\d{4})\s*[-_/]?\s*T\s*([1-4])(?:\.0)?", texto)
    if coincidencia is None:
        return None
    return f"{coincidencia.group(1)}T{coincidencia.group(2)}"


def normalizar_estado(valor: object) -> Optional[str]:
    """Normaliza estado ignorando espacios y diferencias de mayúsculas."""
    if valor is None or pd.isna(valor):
        return None
    texto = str(valor).strip().upper()
    return texto or None


def _suma_ponderada(df: pd.DataFrame) -> float:
    """Suma ponderadores válidos sin imputar faltantes."""
    pesos = pd.to_numeric(df["PONDERA"], errors="coerce")
    valor = pesos.sum(min_count=1)
    return 0.0 if pd.isna(valor) else float(valor)


def clasificar_salida(nombre: str) -> str:
    """Asigna la clasificación institucional de una salida por su nombre."""
    nombre = nombre.lower()
    if nombre.startswith("historico_sde"):
        return "Crítica"
    if nombre.startswith("indicadores_sde"):
        return "Analítica"
    if nombre.startswith("calidad_datos_sde"):
        return "Calidad"
    if nombre.startswith("validacion") or nombre.startswith("estado_periodos"):
        return "Auditoría"
    if nombre.endswith(".log"):
        return "Operativa"
    if nombre.endswith((".png", ".jpg", ".jpeg", ".svg")):
        return "Visualización"
    if nombre.startswith("manifest") or nombre.endswith((".md", ".docx", ".pdf")):
        return "Disponibilización"
    return "Analítica"


def fecha_publicacion_esperada(anio: int, trimestre: int) -> tuple[str, int]:
    """Devuelve el mes y año aproximados de publicación del trimestre."""
    mes, desplazamiento = MES_PUBLICACION_INDEC[trimestre]
    return mes, anio + desplazamiento


def estado_trimestre(anio: int, trimestre: int, directorio: Path = DIR_RESULTADOS) -> str:
    """Consulta el estado persistido o estima si el período todavía es futuro."""
    ruta = directorio / "estado_periodos.csv"
    periodo = f"{anio}T{trimestre}"
    if ruta.exists():
        estados = pd.read_csv(ruta)
        fila = estados[estados["periodo"] == periodo]
        if not fila.empty:
            return str(fila.iloc[-1]["estado"])
    mes, anio_publicacion = fecha_publicacion_esperada(anio, trimestre)
    mes_numero = {
        "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5,
        "Junio": 6, "Julio": 7, "Agosto": 8, "Septiembre": 9,
        "Octubre": 10, "Noviembre": 11, "Diciembre": 12,
    }[mes]
    hoy = datetime.now()
    return "PENDIENTE" if (anio_publicacion, mes_numero) <= (hoy.year, hoy.month) else "FUTURO"


def mostrar_calendario(directorio: Path = DIR_RESULTADOS) -> None:
    """Muestra calendario y estados del ciclo de cada período."""
    log.info("\nCALENDARIO DE PUBLICACIONES EPH-INDEC · AGLOMERADO 18")
    for anio in ANIOS + [max(ANIOS) + 1]:
        for trimestre in TRIMESTRES:
            mes, anio_publicacion = fecha_publicacion_esperada(anio, trimestre)
            estado = estado_trimestre(anio, trimestre, directorio)
            log.info(f"  {anio}T{trimestre}: {mes} {anio_publicacion} · {estado}")


# ─── EXTRACCIÓN ─────────────────────────────────────────────────────────────
def descargar_zip(anio: int, trimestre: int, forzar: bool = False) -> Optional[Path]:
    """Descarga un ZIP a un archivo temporal y sólo lo promueve si no está vacío."""
    DIR_DATOS.mkdir(parents=True, exist_ok=True)
    nombre = f"EPH_usu_{trimestre}_Trim_{anio}_txt.zip"
    ruta = DIR_DATOS / nombre
    if ruta.exists() and ruta.stat().st_size > 0 and not forzar:
        log.info(f"  Se reutiliza {nombre}")
        return ruta

    if requests is None:
        log.error("  La dependencia requests no está instalada; no se puede descargar el ZIP.")
        return None

    temporal = ruta.with_suffix(ruta.suffix + ".part")
    try:
        respuesta = requests.get(URL_BASE + nombre, timeout=60, stream=True)
        respuesta.raise_for_status()
        with temporal.open("wb") as archivo:
            for bloque in respuesta.iter_content(8192):
                if bloque:
                    archivo.write(bloque)
        if not temporal.exists() or temporal.stat().st_size == 0:
            raise RuntimeError("La descarga produjo un ZIP vacío.")
        if not zipfile.is_zipfile(temporal):
            raise RuntimeError("El archivo descargado no es un ZIP válido.")
        temporal.replace(ruta)
        return ruta
    except (requests.RequestException, OSError, RuntimeError) as error:
        temporal.unlink(missing_ok=True)
        log.error(f"  Error de descarga: {error}")
        return None


def extraer_zip(
    ruta_zip: Path, anio: int, trimestre: int
) -> tuple[Optional[Path], Optional[Path]]:
    """Extrae el ZIP e identifica de forma explícita las bases individual y hogar."""
    if not ruta_zip.exists() or ruta_zip.stat().st_size == 0:
        log.error("  ZIP inexistente o vacío")
        return None, None
    destino = DIR_DATOS / f"t{trimestre}_{anio}"
    if destino.exists():
        individual_existente = next(
            (ruta for ruta in destino.rglob("*.txt") if "individual" in ruta.name.lower()), None
        )
        hogar_existente = next(
            (ruta for ruta in destino.rglob("*.txt") if "hogar" in ruta.name.lower()), None
        )
        if individual_existente is not None and hogar_existente is not None:
            return individual_existente, hogar_existente
    staging = Path(tempfile.mkdtemp(prefix=f".extraer_{anio}T{trimestre}_", dir=DIR_DATOS))
    try:
        with zipfile.ZipFile(ruta_zip) as archivo:
            raiz_staging = staging.resolve()
            for miembro in archivo.infolist():
                objetivo = (staging / miembro.filename).resolve()
                if not objetivo.is_relative_to(raiz_staging):
                    raise RuntimeError("El ZIP contiene una ruta de extracción insegura.")
                archivo.extract(miembro, staging)
    except (zipfile.BadZipFile, OSError, RuntimeError) as error:
        shutil.rmtree(staging, ignore_errors=True)
        log.error(f"  ZIP inválido: {error}")
        return None, None
    individual = next(
        (ruta for ruta in staging.rglob("*.txt") if "individual" in ruta.name.lower()), None
    )
    hogar = next((ruta for ruta in staging.rglob("*.txt") if "hogar" in ruta.name.lower()), None)
    if individual is None or hogar is None:
        shutil.rmtree(staging, ignore_errors=True)
        log.error("  No se identificaron ambos archivos: individual y hogar")
        return None, None
    respaldo = destino.with_name(f"{destino.name}_respaldo_{datetime.now():%Y%m%d_%H%M%S}")
    if destino.exists():
        destino.replace(respaldo)
    try:
        staging.replace(destino)
    except OSError:
        if respaldo.exists() and not destino.exists():
            respaldo.replace(destino)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    individual = next(
        (ruta for ruta in destino.rglob("*.txt") if "individual" in ruta.name.lower()), None
    )
    hogar = next((ruta for ruta in destino.rglob("*.txt") if "hogar" in ruta.name.lower()), None)
    return individual, hogar


def leer_archivo_eph(ruta: Path) -> Optional[pd.DataFrame]:
    """Lee una base EPH probando los formatos conocidos."""
    for opciones in LECTURAS:
        try:
            df = pd.read_csv(ruta, low_memory=False, **opciones)
            if "AGLOMERADO" in df.columns and len(df.columns) >= 30:
                return df
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    log.error(f"  No se pudo leer {ruta.name}")
    return None


# ─── TRANSFORMACIÓN ────────────────────────────────────────────────────────
def filtrar_sde(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra el aglomerado 18 sin modificar el DataFrame de origen."""
    if "AGLOMERADO" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    aglomerado = pd.to_numeric(df["AGLOMERADO"], errors="coerce")
    return df[aglomerado == AGLOMERADO_SDE].copy().reset_index(drop=True)


def validar_esquema(
    df: pd.DataFrame,
    esquema_obligatorio: list[str],
    esquema_opcional: list[str],
    base: str,
    anio: int,
    trimestre: int,
) -> dict:
    """Compara columnas reales con el esquema requerido."""
    columnas = set(df.columns)
    obligatorias = set(esquema_obligatorio)
    opcionales = set(esquema_opcional)
    faltantes_obligatorias = sorted(obligatorias - columnas)
    faltantes_opcionales = sorted(opcionales - columnas)
    nivel = "critico" if faltantes_obligatorias else (
        "advertencia" if faltantes_opcionales else "ok"
    )
    return {
        "periodo": f"{anio}T{trimestre}",
        "base": base,
        "nivel": nivel,
        "n_columnas_totales": len(columnas),
        "obligatorias_presentes": sorted(obligatorias & columnas),
        "obligatorias_faltantes": faltantes_obligatorias,
        "opcionales_faltantes": faltantes_opcionales,
        "fecha_validacion": ahora_iso(),
    }


def cargar_y_filtrar(
    ruta_ind: Path,
    ruta_hog: Path,
    anio: int,
    trimestre: int,
    directorio_resultados: Path = DIR_RESULTADOS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carga, valida y filtra ambas bases; conserva el reporte de auditoría."""
    df_ind = leer_archivo_eph(ruta_ind)
    df_hog = leer_archivo_eph(ruta_hog)
    if df_ind is None or df_hog is None:
        raise RuntimeError("No se pudieron leer las bases EPH del trimestre.")
    val_ind = validar_esquema(
        df_ind, ESQUEMA_OBLIGATORIO_INDIVIDUAL,
        ESQUEMA_OPCIONAL_INDIVIDUAL, "individual", anio, trimestre,
    )
    val_hog = validar_esquema(
        df_hog, ESQUEMA_OBLIGATORIO_HOGAR, [], "hogar", anio, trimestre,
    )
    directorio_resultados.mkdir(parents=True, exist_ok=True)
    ruta_validacion = directorio_resultados / f"validacion_esquema_{anio}T{trimestre}.json"
    ruta_validacion.write_text(
        json.dumps({"individual": val_ind, "hogar": val_hog}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    guardar_metadatos_genericos(
        ruta_validacion,
        f"Validación de esquema de las bases individual y hogar para {anio}T{trimestre}.",
        "Auditoría",
        periodo=f"{anio}T{trimestre}",
        anio=anio,
        trimestre=trimestre,
        estado_validacion="EN_REVISION",
        archivo_origen=f"{ruta_ind.name}; {ruta_hog.name}",
    )
    if val_ind["nivel"] == "critico" or val_hog["nivel"] == "critico":
        raise RuntimeError(
            f"Faltan columnas obligatorias en {anio}T{trimestre}; revisar {ruta_validacion.name}."
        )
    sde_ind = filtrar_sde(df_ind)
    sde_hog = filtrar_sde(df_hog)
    if sde_ind.empty or sde_hog.empty:
        raise RuntimeError("El aglomerado 18 no está presente en ambas bases.")
    return sde_ind, sde_hog


def calcular_indicadores(
    sde_ind: pd.DataFrame, sde_hog: pd.DataFrame, anio: int, trimestre: int
) -> dict:
    """Calcula indicadores ponderados sin imputar valores faltantes."""
    estado = pd.to_numeric(sde_ind["ESTADO"], errors="coerce")
    edad = pd.to_numeric(sde_ind["CH06"], errors="coerce")
    mayores10 = sde_ind[edad >= 10]
    pea = sde_ind[estado.isin([1, 2])]
    ocupados = sde_ind[estado == 1].copy()
    desocupados = sde_ind[estado == 2]
    inactivos = sde_ind[estado == 3]

    p_pob = _suma_ponderada(sde_ind)
    p_may10 = _suma_ponderada(mayores10)
    p_pea = _suma_ponderada(pea)
    p_ocup = _suma_ponderada(ocupados)
    p_des = _suma_ponderada(desocupados)
    p_inact = _suma_ponderada(inactivos)

    actividad_oficial = porcentaje(p_pea, p_pob)
    empleo_oficial = porcentaje(p_ocup, p_pob)
    proporcion_inactiva = (
        round(100 - actividad_oficial, 2) if actividad_oficial is not None else None
    )

    tasa_informalidad = None
    if "EMPLEO" in ocupados.columns:
        empleo = pd.to_numeric(ocupados["EMPLEO"], errors="coerce")
        ocupados_validos = ocupados[empleo.isin([1, 2])]
        empleo_valido = empleo[empleo.isin([1, 2])]
        if not ocupados_validos.empty:
            informales = ocupados_validos[empleo_valido == 2]
            tasa_informalidad = porcentaje(
                _suma_ponderada(informales), _suma_ponderada(ocupados_validos)
            )

    ocupados["P21"] = pd.to_numeric(ocupados["P21"], errors="coerce")
    ocupados["PONDERA"] = pd.to_numeric(ocupados["PONDERA"], errors="coerce")
    ingresos_validos = ocupados[(ocupados["P21"] > 0) & (ocupados["PONDERA"] > 0)]
    no_respuesta_ingresos = int((ocupados["P21"] == -9).sum())
    ingreso_simple = (
        round(float(ingresos_validos["P21"].mean()), 0) if not ingresos_validos.empty else None
    )
    ingreso_mediano = (
        round(float(ingresos_validos["P21"].median()), 0) if not ingresos_validos.empty else None
    )
    ingreso_ponderado = None
    if not ingresos_validos.empty:
        suma_pesos = ingresos_validos["PONDERA"].sum(min_count=1)
        if pd.notna(suma_pesos) and suma_pesos > 0:
            ingreso_ponderado = round(
                float((ingresos_validos["P21"] * ingresos_validos["PONDERA"]).sum())
                / float(suma_pesos),
                0,
            )

    realizada = pd.to_numeric(sde_hog["REALIZADA"], errors="coerce")
    return {
        "anio": anio,
        "trimestre": trimestre,
        "periodo": f"{anio}T{trimestre}",
        "aglomerado": AGLOMERADO_SDE,
        "n_personas_muestra": len(sde_ind),
        "n_hogares_muestra": len(sde_hog),
        "poblacion_expandida_total": int(p_pob),
        "poblacion_expandida_mayor10": int(p_may10),
        "pea_expandida": int(p_pea),
        "ocupados_expandidos": int(p_ocup),
        "desocupados_expandidos": int(p_des),
        "inactivos_expandidos": int(p_inact),
        "tasa_actividad_oficial": actividad_oficial,
        "tasa_empleo_oficial": empleo_oficial,
        "tasa_desocupacion": porcentaje(p_des, p_pea),
        "proporcion_inactiva_total": proporcion_inactiva,
        "tasa_actividad_10_mas": porcentaje(p_pea, p_may10),
        "tasa_empleo_10_mas": porcentaje(p_ocup, p_may10),
        "tasa_inactividad_10_mas": porcentaje(p_inact, p_may10),
        "tasa_informalidad": tasa_informalidad,
        "ingreso_promedio_observado": ingreso_simple,
        "ingreso_mediano_observado": ingreso_mediano,
        "ingreso_promedio_ponderado_observado": ingreso_ponderado,
        "n_ocupados_con_ingreso_valido": len(ingresos_validos),
        "n_ocupados_sin_respuesta_ingreso": no_respuesta_ingresos,
        "tasa_no_respuesta_ingresos_ocupados": porcentaje(
            no_respuesta_ingresos, len(ocupados)
        ),
        "hogares_encuestados": int((realizada == 1).sum()),
        "tasa_no_respuesta_hogar": porcentaje(int((realizada == 0).sum()), len(sde_hog)),
        "fecha_procesamiento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fuente": "Encuesta Permanente de Hogares - INDEC (microdatos públicos)",
    }


def migrar_historico(df: pd.DataFrame) -> pd.DataFrame:
    """Migra nombres ambiguos y calcula indicadores principales sin alterar su significado."""
    hist = df.copy()
    if "periodo" not in hist.columns:
        raise ValueError("No se puede migrar el histórico; falta la columna periodo.")
    hist["periodo"] = hist["periodo"].map(normalizar_periodo)
    if hist["periodo"].isna().any():
        raise ValueError("El histórico contiene períodos fuera del formato YYYYTx.")
    migraciones = {
        "tasa_actividad": "tasa_actividad_10_mas",
        "tasa_empleo": "tasa_empleo_10_mas",
        "tasa_inactividad": "tasa_inactividad_10_mas",
    }
    for anterior, nuevo in migraciones.items():
        if nuevo not in hist.columns and anterior in hist.columns:
            hist = hist.rename(columns={anterior: nuevo})
        elif anterior in hist.columns:
            hist = hist.drop(columns=[anterior])
    requeridas = {
        "pea_expandida", "ocupados_expandidos", "desocupados_expandidos",
        "poblacion_expandida_total", "poblacion_expandida_mayor10", "inactivos_expandidos",
    }
    if not requeridas.issubset(hist.columns):
        faltantes = sorted(requeridas - set(hist.columns))
        raise ValueError(f"No se puede migrar el histórico; faltan columnas: {faltantes}")
    hist["tasa_actividad_oficial"] = hist.apply(
        lambda fila: porcentaje(fila["pea_expandida"], fila["poblacion_expandida_total"]), axis=1
    )
    hist["tasa_empleo_oficial"] = hist.apply(
        lambda fila: porcentaje(fila["ocupados_expandidos"], fila["poblacion_expandida_total"]), axis=1
    )
    hist["tasa_desocupacion"] = hist.apply(
        lambda fila: porcentaje(fila["desocupados_expandidos"], fila["pea_expandida"]), axis=1
    )
    hist["proporcion_inactiva_total"] = hist["tasa_actividad_oficial"].apply(
        lambda valor: round(100 - valor, 2) if pd.notna(valor) else None
    )
    if "tasa_actividad_10_mas" not in hist.columns:
        hist["tasa_actividad_10_mas"] = hist.apply(
            lambda f: porcentaje(f["pea_expandida"], f["poblacion_expandida_mayor10"]), axis=1
        )
    if "tasa_empleo_10_mas" not in hist.columns:
        hist["tasa_empleo_10_mas"] = hist.apply(
            lambda f: porcentaje(f["ocupados_expandidos"], f["poblacion_expandida_mayor10"]), axis=1
        )
    if "tasa_inactividad_10_mas" not in hist.columns:
        hist["tasa_inactividad_10_mas"] = hist.apply(
            lambda f: porcentaje(f["inactivos_expandidos"], f["poblacion_expandida_mayor10"]), axis=1
        )
    columnas_prioritarias = [
        "anio", "trimestre", "periodo", "aglomerado", "n_personas_muestra",
        "n_hogares_muestra", "poblacion_expandida_total", "poblacion_expandida_mayor10",
        "pea_expandida", "ocupados_expandidos", "desocupados_expandidos",
        "inactivos_expandidos", "tasa_actividad_oficial", "tasa_empleo_oficial",
        "tasa_desocupacion", "proporcion_inactiva_total", "tasa_actividad_10_mas",
        "tasa_empleo_10_mas", "tasa_inactividad_10_mas", "tasa_informalidad",
    ]
    restantes = [col for col in hist.columns if col not in columnas_prioritarias]
    return hist[[col for col in columnas_prioritarias if col in hist.columns] + restantes]


def reporte_calidad(df: pd.DataFrame, columnas_clave: list[str]) -> pd.DataFrame:
    """Cuenta nulos y códigos especiales sin reemplazarlos por cero."""
    filas = []
    for columna in columnas_clave:
        if columna not in df.columns:
            filas.append({
                "columna": columna,
                "nulos": None,
                "codigo_-9_no_resp": None,
                "codigo_-8": None,
                "codigo_-7": None,
                "validos": None,
                "variable_disponible": False,
            })
            continue
        serie = pd.to_numeric(df[columna], errors="coerce")
        filas.append({
            "columna": columna,
            "nulos": int(serie.isna().sum()),
            "codigo_-9_no_resp": int((serie == -9).sum()),
            "codigo_-8": int((serie == -8).sum()),
            "codigo_-7": int((serie == -7).sum()),
            "validos": int((serie.notna() & ~serie.isin([-9, -8, -7])).sum()),
            "variable_disponible": True,
        })
    return pd.DataFrame(filas)


def unir_bases(sde_ind: pd.DataFrame, sde_hog: pd.DataFrame) -> pd.DataFrame:
    """Une individuo y hogar por la clave compuesta estándar de la EPH."""
    claves = ["CODUSU", "NRO_HOGAR"]
    if not all(c in sde_ind.columns and c in sde_hog.columns for c in claves):
        return pd.DataFrame()
    return sde_ind.merge(sde_hog, on=claves, how="left", suffixes=("", "_hog"))


# ─── METADATOS Y MANIFIESTO ────────────────────────────────────────────────
def generar_metadatos(
    ruta_csv: Path,
    df: pd.DataFrame,
    descripcion: str,
    anio: Optional[int] = None,
    trimestre: Optional[int] = None,
    clasificacion_load: Optional[str] = None,
    estado_validacion: str = "EN_REVISION",
    archivo_origen: Optional[str] = None,
    ultima_ejecucion_exitosa: Optional[str] = None,
) -> dict:
    """Genera metadatos autosuficientes para un CSV exportado."""
    if not ruta_csv.exists():
        raise FileNotFoundError(ruta_csv)
    periodo = f"{anio}T{trimestre}" if anio is not None and trimestre is not None else None
    fecha = ahora_iso()
    hash_archivo = calcular_hash(ruta_csv)
    variables = list(df.columns)
    advertencias = [
        "No se imputan valores faltantes ni se reemplazan por cero.",
        "Los ingresos se expresan en pesos argentinos nominales y no están deflactados.",
        "La informalidad permanece nula cuando EMPLEO no está disponible.",
        "proporcion_inactiva_total es un indicador complementario de la tasa de actividad oficial.",
        "El aglomerado 18 no permite separar Santiago Capital de La Banda.",
    ]
    return {
        "nombre_archivo": ruta_csv.name,
        "descripcion": descripcion,
        "clasificacion_load": clasificacion_load or clasificar_salida(ruta_csv.name),
        "fuente": "Encuesta Permanente de Hogares - microdatos públicos",
        "organismo_productor": "Instituto Nacional de Estadística y Censos (INDEC)",
        "url_origen": (
            URL_BASE + f"EPH_usu_{trimestre}_Trim_{anio}_txt.zip"
            if periodo else URL_BASE
        ),
        "aglomerado_codigo": AGLOMERADO_SDE,
        "aglomerado_nombre": AGLOMERADO_NOMBRE,
        "periodo": periodo,
        "anio": anio,
        "trimestre": trimestre,
        "fecha_hora_generacion": fecha,
        "version_pipeline": PIPELINE_VERSION,
        "filas": int(len(df)),
        "columnas": int(len(variables)),
        "variables": variables,
        "definicion_variables": {
            col: DICCIONARIO_COLUMNAS.get(col, "Variable documentada por su nombre de origen")
            for col in variables
        },
        "tipos_de_datos": {col: str(df[col].dtype) for col in variables},
        "unidades": {col: UNIDADES.get(col, "conteo, código o texto") for col in variables},
        "formulas": {col: FORMULAS_INDICADORES[col] for col in variables if col in FORMULAS_INDICADORES},
        "filtros_aplicados": [
            "AGLOMERADO = 18",
            "P21 > 0 para estadísticas de ingresos",
            "PONDERA válida y positiva para promedios ponderados de ingresos",
        ],
        "ponderador": "PONDERA",
        "cantidad_nulos": {col: int(df[col].isna().sum()) for col in variables},
        "codigos_especiales": {"-9": "no respuesta", "-8": "no sabe", "-7": "otro especial"},
        "advertencias_metodologicas": advertencias,
        "ingresos_nominales": any("ingreso" in col for col in variables),
        "estado_validacion": estado_validacion,
        "ultima_ejecucion_exitosa": ultima_ejecucion_exitosa,
        "archivo_origen": archivo_origen,
        "identificador_ejecucion": hashlib.sha256(
            f"{ruta_csv.name}|{fecha}|{hash_archivo}".encode("utf-8")
        ).hexdigest()[:16],
        "hash_sha256": hash_archivo,
    }


def guardar_metadatos(ruta_salida: Path, metadatos: dict) -> Path:
    """Guarda ``nombre.meta.json`` junto al archivo de salida."""
    ruta_meta = ruta_salida.with_suffix(".meta.json")
    ruta_meta.write_text(json.dumps(metadatos, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta_meta


def guardar_metadatos_genericos(
    ruta: Path,
    descripcion: str,
    clasificacion: str,
    periodo: Optional[str] = None,
    anio: Optional[int] = None,
    trimestre: Optional[int] = None,
    estado_validacion: str = "EN_REVISION",
    archivo_origen: Optional[str] = None,
) -> Path:
    """Genera metadatos mínimos y trazables para salidas no tabulares."""
    fecha = ahora_iso()
    hash_archivo = calcular_hash(ruta)
    meta = {
        "nombre_archivo": ruta.name,
        "descripcion": descripcion,
        "clasificacion_load": clasificacion,
        "fuente": "Encuesta Permanente de Hogares - microdatos públicos",
        "organismo_productor": "Instituto Nacional de Estadística y Censos (INDEC)",
        "url_origen": URL_BASE,
        "aglomerado_codigo": AGLOMERADO_SDE,
        "aglomerado_nombre": AGLOMERADO_NOMBRE,
        "periodo": periodo,
        "anio": anio,
        "trimestre": trimestre,
        "fecha_hora_generacion": fecha,
        "version_pipeline": PIPELINE_VERSION,
        "estado_validacion": estado_validacion,
        "ultima_ejecucion_exitosa": fecha if estado_validacion in ESTADOS_VISIBLES_DASHBOARD else None,
        "archivo_origen": archivo_origen,
        "identificador_ejecucion": hashlib.sha256(
            f"{ruta.name}|{fecha}|{hash_archivo}".encode("utf-8")
        ).hexdigest()[:16],
        "hash_sha256": hash_archivo,
        "advertencias_metodologicas": [
            "El aglomerado 18 no permite separar Santiago Capital de La Banda."
        ],
        "ingresos_nominales": False,
    }
    return guardar_metadatos(ruta, meta)


def generar_manifiesto(directorio: Path = DIR_RESULTADOS) -> dict:
    """Genera el manifiesto general de salidas y su asociación con metadatos."""
    directorio.mkdir(parents=True, exist_ok=True)
    salidas = []
    for ruta in sorted(directorio.rglob("*")):
        if not ruta.is_file() or ruta.name.endswith(".meta.json"):
            continue
        if ruta.name in {"manifest_salidas.json"} or ruta.name.startswith(".staging"):
            continue
        ruta_meta = ruta.with_suffix(".meta.json")
        meta: dict[str, Any] = {}
        if ruta_meta.exists():
            try:
                meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        periodo = meta.get("periodo")
        if not periodo and "periodo" in ruta.name.lower():
            periodo = None
        salidas.append({
            "nombre_archivo": ruta.name,
            "ruta_relativa": ruta.relative_to(directorio).as_posix(),
            "clasificacion_load": meta.get("clasificacion_load", clasificar_salida(ruta.name)),
            "periodo": periodo,
            "estado_validacion": meta.get("estado_validacion", "PENDIENTE"),
            "archivo_metadatos": (
                ruta_meta.relative_to(directorio).as_posix() if ruta_meta.exists() else None
            ),
            "fecha_generacion": meta.get("fecha_hora_generacion"),
        })
    if directorio.resolve() == DIR_RESULTADOS.resolve() and DIR_LOGS.exists():
        for ruta in sorted(DIR_LOGS.glob("*.log")):
            salidas.append({
                "nombre_archivo": ruta.name,
                "ruta_relativa": f"../logs/{ruta.name}",
                "clasificacion_load": "Operativa",
                "periodo": None,
                "estado_validacion": "PENDIENTE",
                "archivo_metadatos": None,
                "fecha_generacion": datetime.fromtimestamp(ruta.stat().st_mtime).isoformat(
                    timespec="seconds"
                ),
            })
    manifiesto = {
        "version_pipeline": PIPELINE_VERSION,
        "fecha_hora_generacion": ahora_iso(),
        "aglomerado_codigo": AGLOMERADO_SDE,
        "aglomerado_nombre": AGLOMERADO_NOMBRE,
        "cantidad_salidas": len(salidas),
        "salidas": salidas,
    }
    ruta = directorio / "manifest_salidas.json"
    ruta.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
    guardar_metadatos_genericos(
        ruta, "Manifiesto general de salidas del pipeline.", "Disponibilización",
        estado_validacion="VALIDADO",
    )
    return manifiesto


# ─── ESTADOS Y VALIDACIÓN PREVIA ────────────────────────────────────────────
def actualizar_estado_periodo(
    periodo: str,
    estado: str,
    mensaje: str,
    directorio: Path = DIR_RESULTADOS,
    incrementar_intento: bool = False,
) -> pd.DataFrame:
    """Actualiza el control de períodos mediante escritura atómica."""
    periodo_normalizado = normalizar_periodo(periodo)
    estado_normalizado = normalizar_estado(estado)
    if periodo_normalizado is None:
        raise ValueError(f"Período no válido: {periodo}")
    if estado_normalizado not in ESTADOS_PERMITIDOS:
        raise ValueError(f"Estado no permitido: {estado}")
    periodo = periodo_normalizado
    estado = estado_normalizado
    anio = int(periodo[:4])
    trimestre = int(periodo[-1])
    mes, anio_publicacion = fecha_publicacion_esperada(anio, trimestre)
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / "estado_periodos.csv"
    columnas = [
        "periodo", "fecha_esperada", "fecha_deteccion", "fecha_procesamiento_estado",
        "intentos", "estado", "mensaje", "ultima_actualizacion",
    ]
    estados = pd.read_csv(ruta) if ruta.exists() else pd.DataFrame(columns=columnas)
    if not estados.empty:
        estados["periodo"] = estados["periodo"].map(normalizar_periodo)
        estados["estado"] = estados["estado"].map(normalizar_estado)
        if estados["periodo"].isna().any():
            raise ValueError("estado_periodos.csv contiene períodos fuera del formato YYYYTx.")
    existente = estados[estados["periodo"] == periodo]
    fecha_deteccion = (
        str(existente.iloc[-1]["fecha_deteccion"]) if not existente.empty else ahora_iso()
    )
    intentos = int(existente.iloc[-1]["intentos"]) if not existente.empty else 0
    if incrementar_intento:
        intentos += 1
    fecha_procesamiento_estado = ahora_iso() if estado in {
        "PROCESADO", "EN_REVISION", "VALIDADO", "FALLIDO", "PUBLICADO"
    } else None
    nueva = pd.DataFrame([{
        "periodo": periodo,
        "fecha_esperada": f"{mes} {anio_publicacion}",
        "fecha_deteccion": fecha_deteccion,
        "fecha_procesamiento_estado": fecha_procesamiento_estado,
        "intentos": intentos,
        "estado": estado,
        "mensaje": mensaje,
        "ultima_actualizacion": ahora_iso(),
    }])
    estados = estados[estados["periodo"] != periodo]
    estados = pd.concat([estados, nueva], ignore_index=True).sort_values("periodo")
    temporal = ruta.with_suffix(".csv.tmp")
    estados.to_csv(temporal, index=False)
    temporal.replace(ruta)
    meta = generar_metadatos(
        ruta, estados, "Estado del ciclo de procesamiento y validación por período.",
        clasificacion_load="Auditoría",
        estado_validacion="VALIDADO",
        ultima_ejecucion_exitosa=(ahora_iso() if estado in ESTADOS_VISIBLES_DASHBOARD else None),
    )
    guardar_metadatos(ruta, meta)
    return estados


def _control(nombre: str, cumple: bool, detalle: str, critico: bool = True) -> dict:
    return {"control": nombre, "cumple": bool(cumple), "critico": critico, "detalle": detalle}


def validar_publicacion(
    indicadores: dict,
    historico: pd.DataFrame,
    sde_ind: pd.DataFrame,
    sde_hog: pd.DataFrame,
    rutas_requeridas: list[Path],
    minimo_personas: int = 100,
    minimo_hogares: int = 30,
) -> dict:
    """Ejecuta controles críticos antes de promover una nueva salida."""
    periodo = indicadores["periodo"]
    tasas = TASAS_PRINCIPALES + TASAS_10_MAS + ["tasa_informalidad"]
    valores_tasas = [indicadores.get(tasa) for tasa in tasas]
    tasas_en_rango = all(
        valor is None or pd.isna(valor) or 0 <= float(valor) <= 100 for valor in valores_tasas
    )
    actividad = indicadores.get("tasa_actividad_oficial")
    inactiva = indicadores.get("proporcion_inactiva_total")
    complemento = (
        actividad is not None and inactiva is not None
        and abs(float(actividad) + float(inactiva) - 100) <= 0.02
    )
    pea = indicadores.get("pea_expandida", 0)
    desempleo_calculable = pea <= 0 or indicadores.get("tasa_desocupacion") is not None
    empleo_disponible = "EMPLEO" in sde_ind.columns
    informalidad_correcta = empleo_disponible or pd.isna(indicadores.get("tasa_informalidad"))
    aglomerado_ind = (
        "AGLOMERADO" in sde_ind.columns
        and AGLOMERADO_SDE in pd.to_numeric(sde_ind["AGLOMERADO"], errors="coerce").values
    )
    aglomerado_hog = (
        "AGLOMERADO" in sde_hog.columns
        and AGLOMERADO_SDE in pd.to_numeric(sde_hog["AGLOMERADO"], errors="coerce").values
    )
    controles = [
        _control("aglomerado_18_presente", aglomerado_ind and aglomerado_hog,
                 "Aglomerado 18 presente en bases individual y hogar."),
        _control("poblacion_total_positiva", indicadores.get("poblacion_expandida_total", 0) > 0,
                 "La población total expandida debe ser mayor que cero."),
        _control("periodos_sin_duplicados", not historico["periodo"].duplicated().any(),
                 "El histórico no debe contener períodos duplicados."),
        _control("tasas_entre_0_y_100", tasas_en_rango,
                 "Todas las tasas calculadas deben estar entre 0 y 100."),
        _control("actividad_mas_inactividad_total", complemento,
                 "Actividad oficial + proporción inactiva total debe ser aproximadamente 100."),
        _control("desocupacion_calculable", desempleo_calculable,
                 "Con PEA positiva, la tasa de desocupación debe ser calculable."),
        _control("filas_razonables", len(sde_ind) >= minimo_personas and len(sde_hog) >= minimo_hogares,
                 f"Mínimos: {minimo_personas} personas y {minimo_hogares} hogares."),
        _control("archivos_generados", all(ruta.exists() and ruta.stat().st_size > 0 for ruta in rutas_requeridas),
                 "Todos los CSV y metadatos requeridos deben existir y no estar vacíos."),
        _control("informalidad_no_disponible", informalidad_correcta,
                 "Si EMPLEO no existe, la informalidad debe permanecer nula."),
    ]
    errores = [c["detalle"] for c in controles if c["critico"] and not c["cumple"]]
    return {
        "periodo": periodo,
        "fecha_validacion": ahora_iso(),
        "estado": "VALIDADO" if not errores else "FALLIDO",
        "es_valida": not errores,
        "controles": controles,
        "errores": errores,
    }


def _promover_archivos(staging: Path, destino: Path) -> None:
    """Promueve archivos con respaldo temporal y rollback ante error."""
    destino.mkdir(parents=True, exist_ok=True)
    respaldo = staging / ".respaldo"
    respaldo.mkdir()
    promovidos: list[Path] = []
    respaldados: list[tuple[Path, Path]] = []
    archivos = [ruta for ruta in staging.iterdir() if ruta.is_file()]
    try:
        for origen in archivos:
            final = destino / origen.name
            if final.exists():
                copia = respaldo / final.name
                final.replace(copia)
                respaldados.append((copia, final))
            origen.replace(final)
            promovidos.append(final)
    except OSError:
        for final in promovidos:
            final.unlink(missing_ok=True)
        for copia, final in respaldados:
            copia.replace(final)
        raise


# ─── CARGA TRANSACCIONAL ───────────────────────────────────────────────────
def guardar_trimestre(
    indicadores: dict,
    sde_ind: pd.DataFrame,
    sde_hog: pd.DataFrame,
    directorio: Path = DIR_RESULTADOS,
    minimo_personas: int = 100,
    minimo_hogares: int = 30,
) -> dict:
    """Construye salidas en staging y las promueve sólo si quedan validadas."""
    directorio.mkdir(parents=True, exist_ok=True)
    periodo = indicadores["periodo"]
    anio, trimestre = indicadores["anio"], indicadores["trimestre"]
    staging = Path(tempfile.mkdtemp(prefix=f".staging_{periodo}_", dir=directorio.parent))
    try:
        df_indicadores = pd.DataFrame([indicadores])
        ruta_indicadores = staging / f"indicadores_SDE_{periodo}.csv"
        df_indicadores.to_csv(ruta_indicadores, index=False)
        ruta_meta_ind = guardar_metadatos(
            ruta_indicadores,
            generar_metadatos(
                ruta_indicadores, df_indicadores,
                f"Indicadores agregados del período {periodo}.",
                anio, trimestre, "Analítica", "EN_REVISION",
                archivo_origen=f"EPH_usu_{trimestre}_Trim_{anio}_txt.zip",
            ),
        )

        calidad = reporte_calidad(
            sde_ind, ["ESTADO", "EMPLEO", "P21", "PONDERA", "CH04", "CH06"]
        )
        ruta_calidad = staging / f"calidad_datos_SDE_{periodo}.csv"
        calidad.to_csv(ruta_calidad, index=False)
        ruta_meta_calidad = guardar_metadatos(
            ruta_calidad,
            generar_metadatos(
                ruta_calidad, calidad,
                f"Calidad de variables clave del período {periodo}.",
                anio, trimestre, "Calidad", "EN_REVISION",
                archivo_origen=f"EPH_usu_{trimestre}_Trim_{anio}_txt.zip",
            ),
        )

        base_unida = unir_bases(sde_ind, sde_hog)
        if not base_unida.empty:
            ruta_base = staging / f"base_unida_SDE_{periodo}.csv"
            base_unida.to_csv(ruta_base, index=False)
            guardar_metadatos(
                ruta_base,
                generar_metadatos(
                    ruta_base, base_unida,
                    f"Microdatos individual-hogar unidos para {periodo}; no se incluyen en el snapshot.",
                    anio, trimestre, "Analítica", "EN_REVISION",
                    archivo_origen=f"EPH_usu_{trimestre}_Trim_{anio}_txt.zip",
                ),
            )

        ruta_historico_actual = directorio / "historico_SDE.csv"
        if ruta_historico_actual.exists():
            historico = migrar_historico(pd.read_csv(ruta_historico_actual))
            historico = historico[historico["periodo"] != periodo]
            historico = pd.concat([historico, df_indicadores], ignore_index=True)
        else:
            historico = df_indicadores
        historico = migrar_historico(historico).sort_values(["anio", "trimestre"]).reset_index(drop=True)
        ruta_historico = staging / "historico_SDE.csv"
        historico.to_csv(ruta_historico, index=False)
        ruta_meta_historico = guardar_metadatos(
            ruta_historico,
            generar_metadatos(
                ruta_historico, historico,
                "Histórico validado de indicadores agregados por trimestre.",
                clasificacion_load="Crítica", estado_validacion="EN_REVISION",
                ultima_ejecucion_exitosa=ahora_iso(),
            ),
        )

        requeridos = [
            ruta_indicadores, ruta_meta_ind, ruta_calidad, ruta_meta_calidad,
            ruta_historico, ruta_meta_historico,
        ]
        validacion = validar_publicacion(
            indicadores, historico, sde_ind, sde_hog, requeridos,
            minimo_personas=minimo_personas, minimo_hogares=minimo_hogares,
        )
        ruta_validacion = staging / f"validacion_publicacion_{periodo}.json"
        ruta_validacion.write_text(json.dumps(validacion, ensure_ascii=False, indent=2), encoding="utf-8")
        guardar_metadatos_genericos(
            ruta_validacion, f"Controles previos a publicación para {periodo}.", "Auditoría",
            periodo, anio, trimestre, validacion["estado"],
            archivo_origen=f"indicadores_SDE_{periodo}.csv",
        )
        if not validacion["es_valida"]:
            for ruta_auditoria in [ruta_validacion, ruta_validacion.with_suffix(".meta.json")]:
                destino_auditoria = directorio / ruta_auditoria.name
                shutil.copy2(ruta_auditoria, destino_auditoria)
            actualizar_estado_periodo(
                periodo, "FALLIDO", "; ".join(validacion["errores"]), directorio
            )
            generar_manifiesto(directorio)
            return validacion

        fecha_exitosa = ahora_iso()
        for ruta_meta in staging.glob("*.meta.json"):
            meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
            meta["estado_validacion"] = "VALIDADO"
            meta["ultima_ejecucion_exitosa"] = fecha_exitosa
            ruta_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        _promover_archivos(staging, directorio)
        actualizar_estado_periodo(
            periodo, "VALIDADO", "Período aprobado por todos los controles críticos.", directorio
        )
        ruta_meta_esquema = directorio / f"validacion_esquema_{periodo}.meta.json"
        if ruta_meta_esquema.exists():
            meta_esquema = json.loads(ruta_meta_esquema.read_text(encoding="utf-8"))
            meta_esquema["estado_validacion"] = "VALIDADO"
            meta_esquema["ultima_ejecucion_exitosa"] = fecha_exitosa
            ruta_meta_esquema.write_text(
                json.dumps(meta_esquema, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        generar_manifiesto(directorio)
        return validacion
    except Exception as error:
        validacion = {
            "periodo": periodo,
            "fecha_validacion": ahora_iso(),
            "estado": "FALLIDO",
            "es_valida": False,
            "controles": [],
            "errores": [f"No se pudo preparar la salida candidata: {error}"],
        }
        actualizar_estado_periodo(periodo, "FALLIDO", validacion["errores"][0], directorio)
        generar_manifiesto(directorio)
        return validacion
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def preparar_snapshot_desde_historico(
    ruta_historico: Path,
    destino: Path = DIR_SNAPSHOT,
    validaciones_existentes: Optional[Path] = None,
) -> dict:
    """Reconstruye un snapshot agregado en staging y conserva el anterior ante fallas."""
    historico = migrar_historico(pd.read_csv(ruta_historico))
    if historico.empty or historico["periodo"].duplicated().any():
        raise ValueError("El histórico del snapshot está vacío o tiene períodos duplicados.")
    tasas = [col for col in TASAS_PRINCIPALES + TASAS_10_MAS if col in historico.columns]
    if any(((historico[col] < 0) | (historico[col] > 100)).any() for col in tasas):
        raise ValueError("El histórico contiene tasas fuera del rango 0-100.")

    padre = destino.parent
    staging = Path(tempfile.mkdtemp(prefix=".snapshot_staging_", dir=padre))
    respaldo = padre / f".{destino.name}_respaldo_temporal"
    try:
        ruta_hist = staging / "historico_SDE.csv"
        historico.to_csv(ruta_hist, index=False)
        guardar_metadatos(
            ruta_hist,
            generar_metadatos(
                ruta_hist, historico,
                "Snapshot validado del histórico agregado para el dashboard.",
                clasificacion_load="Crítica", estado_validacion="VALIDADO",
                ultima_ejecucion_exitosa=ahora_iso(),
                archivo_origen=ruta_historico.name,
            ),
        )
        calidad_snapshot = []
        duplicados = set(
            historico.loc[historico["periodo"].duplicated(keep=False), "periodo"].astype(str)
        )
        for _, fila in historico.iterrows():
            valores_tasas = [fila.get(col) for col in TASAS_PRINCIPALES + TASAS_10_MAS]
            tasas_en_rango = all(
                pd.isna(valor) or 0 <= float(valor) <= 100 for valor in valores_tasas
            )
            complemento = abs(
                float(fila["tasa_actividad_oficial"])
                + float(fila["proporcion_inactiva_total"]) - 100
            ) <= 0.02
            informalidad = fila.get("tasa_informalidad")
            calidad_snapshot.append({
                "periodo": str(fila["periodo"]),
                "poblacion_total_positiva": bool(fila["poblacion_expandida_total"] > 0),
                "tasas_en_rango": tasas_en_rango,
                "actividad_inactividad_consistente": complemento,
                "periodo_duplicado": str(fila["periodo"]) in duplicados,
                "estado_informalidad": (
                    "NO_DISPONIBLE" if pd.isna(informalidad) else "DISPONIBLE"
                ),
                "observacion": (
                    "Control agregado; los conteos de nulos por variable requieren microdatos."
                ),
            })
        df_calidad_snapshot = pd.DataFrame(calidad_snapshot)
        ruta_calidad_snapshot = staging / "calidad_snapshot_SDE.csv"
        df_calidad_snapshot.to_csv(ruta_calidad_snapshot, index=False)
        guardar_metadatos(
            ruta_calidad_snapshot,
            generar_metadatos(
                ruta_calidad_snapshot, df_calidad_snapshot,
                "Controles de calidad agregados del snapshot; no reemplazan el reporte de microdatos.",
                clasificacion_load="Calidad", estado_validacion="VALIDADO",
                ultima_ejecucion_exitosa=ahora_iso(), archivo_origen=ruta_historico.name,
            ),
        )
        for _, fila in historico.iterrows():
            periodo = str(fila["periodo"])
            anio, trimestre = int(fila["anio"]), int(fila["trimestre"])
            df_periodo = pd.DataFrame([fila])
            ruta_ind = staging / f"indicadores_SDE_{periodo}.csv"
            df_periodo.to_csv(ruta_ind, index=False)
            guardar_metadatos(
                ruta_ind,
                generar_metadatos(
                    ruta_ind, df_periodo, f"Indicadores agregados validados de {periodo}.",
                    anio, trimestre, "Analítica", "VALIDADO", ruta_historico.name, ahora_iso(),
                ),
            )

        estados = []
        for _, fila in historico.iterrows():
            anio, trimestre, periodo = int(fila["anio"]), int(fila["trimestre"]), str(fila["periodo"])
            mes, anio_pub = fecha_publicacion_esperada(anio, trimestre)
            fecha_proc = str(fila.get("fecha_procesamiento", ""))
            estados.append({
                "periodo": periodo,
                "fecha_esperada": f"{mes} {anio_pub}",
                "fecha_deteccion": fecha_proc,
                "fecha_procesamiento_estado": fecha_proc,
                "intentos": 1,
                "estado": "VALIDADO",
                "mensaje": "Período disponible en el snapshot validado.",
                "ultima_actualizacion": ahora_iso(),
            })
        df_estados = pd.DataFrame(estados)
        ruta_estados = staging / "estado_periodos.csv"
        df_estados.to_csv(ruta_estados, index=False)
        guardar_metadatos(
            ruta_estados,
            generar_metadatos(
                ruta_estados, df_estados, "Estado de los períodos incluidos en el snapshot.",
                clasificacion_load="Auditoría", estado_validacion="VALIDADO",
                ultima_ejecucion_exitosa=ahora_iso(), archivo_origen=ruta_historico.name,
            ),
        )

        origen_validaciones = validaciones_existentes or destino
        if origen_validaciones.exists():
            for ruta in origen_validaciones.glob("validacion_esquema_*.json"):
                if ruta.name.endswith(".meta.json"):
                    continue
                copia = staging / ruta.name
                shutil.copy2(ruta, copia)
                periodo = ruta.stem.replace("validacion_esquema_", "")
                guardar_metadatos_genericos(
                    copia, f"Validación de esquema conservada para {periodo}.", "Auditoría",
                    periodo=periodo, anio=int(periodo[:4]), trimestre=int(periodo[-1]),
                    estado_validacion="VALIDADO", archivo_origen=ruta.name,
                )

        for documento in ["DICCIONARIO_DATOS.md", "GUIA_USO.md", "METODOLOGIA.md"]:
            origen = RAIZ / "docs" / documento
            if origen.exists():
                copia = staging / documento
                shutil.copy2(origen, copia)
                guardar_metadatos_genericos(
                    copia, f"Documento de apoyo para el dashboard: {documento}.",
                    "Disponibilización", estado_validacion="VALIDADO", archivo_origen=documento,
                )
        generar_manifiesto(staging)

        if respaldo.exists():
            shutil.rmtree(respaldo)
        if destino.exists():
            destino.replace(respaldo)
        try:
            staging.replace(destino)
        except OSError:
            if respaldo.exists() and not destino.exists():
                respaldo.replace(destino)
            raise
        shutil.rmtree(respaldo, ignore_errors=True)
        return json.loads((destino / "manifest_salidas.json").read_text(encoding="utf-8"))
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def publicar_snapshot_validado(
    origen: Path = DIR_RESULTADOS, destino: Path = DIR_SNAPSHOT
) -> dict:
    """Publica sólo salidas agregadas si el último período está validado."""
    ruta_hist = origen / "historico_SDE.csv"
    ruta_estados = origen / "estado_periodos.csv"
    if not ruta_hist.exists() or not ruta_estados.exists():
        raise RuntimeError("Faltan histórico o estados validados en results/.")
    estados = pd.read_csv(ruta_estados)
    historico = pd.read_csv(ruta_hist)
    ultimo = str(historico.sort_values(["anio", "trimestre"]).iloc[-1]["periodo"])
    estado = estados.loc[estados["periodo"] == ultimo, "estado"]
    if estado.empty or estado.iloc[-1] not in ESTADOS_VISIBLES_DASHBOARD:
        raise RuntimeError("El último período no está validado; se conserva el snapshot anterior.")
    manifiesto = preparar_snapshot_desde_historico(ruta_hist, destino, origen)
    actualizar_estado_periodo(
        ultimo, "PUBLICADO", "Snapshot agregado actualizado localmente.", origen
    )
    generar_manifiesto(origen)
    return manifiesto


# ─── ORQUESTACIÓN ───────────────────────────────────────────────────────────
def imprimir_resumen(indicadores: dict) -> None:
    log.info(f"  Período: {indicadores['periodo']}")
    log.info(f"  Actividad oficial: {indicadores['tasa_actividad_oficial']}%")
    log.info(f"  Empleo oficial: {indicadores['tasa_empleo_oficial']}%")
    log.info(f"  Desocupación: {indicadores['tasa_desocupacion']}%")
    log.info(f"  Proporción inactiva total: {indicadores['proporcion_inactiva_total']}%")


def procesar_trimestre(anio: int, trimestre: int, forzar: bool = False) -> Optional[dict]:
    """Ejecuta el ciclo completo y registra el estado comprensible del período."""
    periodo = f"{anio}T{trimestre}"
    actualizar_estado_periodo(
        periodo, "PENDIENTE", "Procesamiento iniciado.", DIR_RESULTADOS, incrementar_intento=True
    )
    try:
        ruta_zip = descargar_zip(anio, trimestre, forzar)
        if ruta_zip is None:
            raise RuntimeError("No se completó la descarga del ZIP.")
        actualizar_estado_periodo(periodo, "DESCARGADO", "ZIP descargado y no vacío.")
        ruta_ind, ruta_hog = extraer_zip(ruta_zip, anio, trimestre)
        if ruta_ind is None or ruta_hog is None:
            raise RuntimeError("No se identificaron las bases individual y hogar.")
        sde_ind, sde_hog = cargar_y_filtrar(ruta_ind, ruta_hog, anio, trimestre)
        indicadores = calcular_indicadores(sde_ind, sde_hog, anio, trimestre)
        actualizar_estado_periodo(periodo, "PROCESADO", "Indicadores calculados con PONDERA.")
        actualizar_estado_periodo(periodo, "EN_REVISION", "Controles críticos en ejecución.")
        validacion = guardar_trimestre(indicadores, sde_ind, sde_hog)
        if not validacion["es_valida"]:
            log.error(f"  {periodo} FALLIDO: {'; '.join(validacion['errores'])}")
            return None
        imprimir_resumen(indicadores)
        return indicadores
    except Exception as error:
        log.exception(f"  Error procesando {periodo}: {error}")
        actualizar_estado_periodo(periodo, "FALLIDO", str(error))
        generar_manifiesto(DIR_RESULTADOS)
        return None


def procesar_lote(anios: list[int], trimestres: list[int], forzar: bool = False) -> list[dict]:
    resultados = []
    for anio in anios:
        for trimestre in trimestres:
            resultado = procesar_trimestre(anio, trimestre, forzar)
            if resultado:
                resultados.append(resultado)
    return resultados


def main() -> None:
    global log
    log = configurar_logging()
    parser = argparse.ArgumentParser(description="Pipeline ETL y validación de microdatos EPH")
    parser.add_argument("--anio", type=int)
    parser.add_argument("--trimestre", type=int, choices=TRIMESTRES)
    parser.add_argument("--todos", action="store_true")
    parser.add_argument("--forzar", action="store_true")
    parser.add_argument("--calendario", action="store_true")
    parser.add_argument(
        "--publicar-snapshot", action="store_true",
        help="Actualiza data_snapshot sólo con el último resultado validado.",
    )
    args = parser.parse_args()
    if args.publicar_snapshot:
        publicar_snapshot_validado()
    elif args.calendario:
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

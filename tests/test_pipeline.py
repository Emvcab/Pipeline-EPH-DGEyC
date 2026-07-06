"""
Tests básicos del pipeline ETL.

Ejecutar desde la raíz del proyecto:
    python -m pytest tests/
    python -m pytest tests/ -v        # modo verboso
"""

import sys
from pathlib import Path

# Permite importar desde src/ sin instalar el paquete
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd
import pytest

from pipeline import (
    porcentaje,
    filtrar_sde,
    calcular_indicadores,
    reporte_calidad,
    unir_bases,
    generar_metadatos,
    calcular_hash,
    fecha_publicacion_esperada,
    validar_esquema,
    DICCIONARIO_COLUMNAS,
    PIPELINE_VERSION,
    AGLOMERADO_SDE,
    ESQUEMA_OBLIGATORIO_INDIVIDUAL,
    ESQUEMA_OBLIGATORIO_HOGAR,
    ESQUEMA_OPCIONAL_INDIVIDUAL,
)


# ─── Función porcentaje ─────────────────────────────────────────────────────

class TestPorcentaje:
    """Tests para la función auxiliar porcentaje()."""

    def test_calculo_basico(self):
        assert porcentaje(50, 100) == 50.0

    def test_dos_decimales(self):
        assert porcentaje(1, 3) == 33.33

    def test_division_por_cero_devuelve_none(self):
        assert porcentaje(10, 0) is None

    def test_numerador_cero(self):
        assert porcentaje(0, 100) == 0.0

    def test_decimales_personalizables(self):
        assert porcentaje(1, 3, decimales=4) == 33.3333


# ─── Función filtrar_sde ────────────────────────────────────────────────────

class TestFiltrarSDE:
    """Tests para el filtrado por aglomerado."""

    def test_filtra_solo_aglomerado_18(self):
        df = pd.DataFrame({
            "AGLOMERADO": [18, 18, 7, 9, 18],
            "valor": [1, 2, 3, 4, 5],
        })
        resultado = filtrar_sde(df)
        assert len(resultado) == 3
        assert all(resultado["AGLOMERADO"] == AGLOMERADO_SDE)

    def test_dataframe_vacio_si_no_hay_sde(self):
        df = pd.DataFrame({"AGLOMERADO": [7, 9, 12], "valor": [1, 2, 3]})
        resultado = filtrar_sde(df)
        assert len(resultado) == 0


# ─── Función calcular_indicadores ────────────────────────────────────────────

@pytest.fixture
def datos_individuales_mock():
    """Mock de la base individual con 6 personas en Santiago del Estero."""
    return pd.DataFrame({
        "AGLOMERADO": [18] * 6,
        "PONDERA":    [100, 150, 200, 100, 150, 100],
        "ESTADO":     [1, 1, 2, 3, 3, 4],   # 2 ocupados, 1 desocup, 2 inactivos, 1 menor
        "EMPLEO":     [1, 2, 0, 0, 0, 0],   # 1 registrado, 1 no registrado
        "P21":        [500000, 700000, 0, 0, 0, 0],
        "CH04":       [1, 2, 1, 2, 1, 2],
        "CH06":       [35, 42, 28, 65, 50, 8],
    })


@pytest.fixture
def datos_hogar_mock():
    """Mock de la base hogar con 3 hogares en Santiago del Estero."""
    return pd.DataFrame({
        "AGLOMERADO": [18, 18, 18],
        "REALIZADA":  [1, 1, 0],
        "CODUSU":     ["A001", "A002", "A003"],
        "NRO_HOGAR":  [1, 1, 1],
    })


class TestCalcularIndicadores:
    """Tests del cálculo de indicadores con datos controlados."""

    def test_devuelve_diccionario(self, datos_individuales_mock, datos_hogar_mock):
        resultado = calcular_indicadores(datos_individuales_mock, datos_hogar_mock, 2025, 4)
        assert isinstance(resultado, dict)

    def test_contiene_claves_obligatorias(self, datos_individuales_mock, datos_hogar_mock):
        resultado = calcular_indicadores(datos_individuales_mock, datos_hogar_mock, 2025, 4)
        claves = [
            "anio", "trimestre", "periodo", "aglomerado",
            "tasa_actividad", "tasa_empleo", "tasa_desocupacion",
            "tasa_inactividad", "tasa_informalidad",
            "ingreso_promedio_ponderado_observado",
            "hogares_encuestados",
        ]
        for clave in claves:
            assert clave in resultado, f"Falta la clave: {clave}"

    def test_periodo_formato_correcto(self, datos_individuales_mock, datos_hogar_mock):
        resultado = calcular_indicadores(datos_individuales_mock, datos_hogar_mock, 2025, 4)
        assert resultado["periodo"] == "2025T4"
        assert resultado["anio"] == 2025
        assert resultado["trimestre"] == 4

    def test_tasas_son_porcentajes_validos(self, datos_individuales_mock, datos_hogar_mock):
        resultado = calcular_indicadores(datos_individuales_mock, datos_hogar_mock, 2025, 4)
        for tasa in ["tasa_actividad", "tasa_empleo", "tasa_desocupacion", "tasa_inactividad"]:
            valor = resultado[tasa]
            assert valor is None or 0 <= valor <= 100, f"{tasa} fuera de rango: {valor}"

    def test_hogares_encuestados_cuenta_realizada_1(self, datos_individuales_mock, datos_hogar_mock):
        resultado = calcular_indicadores(datos_individuales_mock, datos_hogar_mock, 2025, 4)
        # En el mock hay 2 hogares con REALIZADA=1
        assert resultado["hogares_encuestados"] == 2

    def test_aglomerado_correcto(self, datos_individuales_mock, datos_hogar_mock):
        resultado = calcular_indicadores(datos_individuales_mock, datos_hogar_mock, 2025, 4)
        assert resultado["aglomerado"] == AGLOMERADO_SDE


# ─── Función reporte_calidad ─────────────────────────────────────────────────

class TestReporteCalidad:
    """Tests del reporte de calidad de datos."""

    def test_cuenta_codigos_especiales(self):
        df = pd.DataFrame({
            "P21": [1000, 2000, -9, -9, -8, 5000, None],
        })
        resultado = reporte_calidad(df, ["P21"])
        fila = resultado.iloc[0]
        assert fila["codigo_-9_no_resp"] == 2
        assert fila["codigo_-8"] == 1
        assert fila["nulos"] == 1
        assert fila["validos"] == 3  # 1000, 2000, 5000

    def test_columna_inexistente_no_genera_error(self):
        df = pd.DataFrame({"P21": [100, 200]})
        resultado = reporte_calidad(df, ["P21", "COLUMNA_FANTASMA"])
        # Solo debe haber una fila (P21)
        assert len(resultado) == 1


# ─── Función unir_bases ──────────────────────────────────────────────────────

class TestUnirBases:
    """Tests de la unión individual + hogar."""

    def test_une_correctamente_por_codusu_y_nro_hogar(self):
        ind = pd.DataFrame({
            "CODUSU": ["A001", "A001", "A002"],
            "NRO_HOGAR": [1, 1, 1],
            "edad": [30, 35, 40],
        })
        hog = pd.DataFrame({
            "CODUSU": ["A001", "A002"],
            "NRO_HOGAR": [1, 1],
            "vivienda_tipo": ["casa", "departamento"],
        })
        resultado = unir_bases(ind, hog)
        assert len(resultado) == 3
        assert "vivienda_tipo" in resultado.columns

    def test_sin_claves_devuelve_vacio(self):
        ind = pd.DataFrame({"edad": [30]})
        hog = pd.DataFrame({"tipo": ["casa"]})
        resultado = unir_bases(ind, hog)
        assert resultado.empty


# ─── Función generar_metadatos ──────────────────────────────────────────────

class TestMetadatos:
    """Tests del sistema de metadatos."""

    def test_genera_diccionario_con_claves_obligatorias(self, tmp_path):
        df = pd.DataFrame({"periodo": ["2025T4"], "tasa_actividad": [46.06]})
        ruta_csv = tmp_path / "test.csv"
        df.to_csv(ruta_csv, index=False)
        meta = generar_metadatos(ruta_csv, df, "Test", 2025, 4)

        for clave in ["archivo", "version_pipeline", "fecha_generacion",
                      "fuente", "estructura", "integridad", "esquema"]:
            assert clave in meta, f"Falta la clave: {clave}"

    def test_incluye_version_del_pipeline(self, tmp_path):
        df = pd.DataFrame({"x": [1, 2, 3]})
        ruta_csv = tmp_path / "test.csv"
        df.to_csv(ruta_csv, index=False)
        meta = generar_metadatos(ruta_csv, df, "Test")
        assert meta["version_pipeline"] == PIPELINE_VERSION

    def test_esquema_describe_columnas_conocidas(self, tmp_path):
        df = pd.DataFrame({"tasa_actividad": [46.06], "tasa_empleo": [45.77]})
        ruta_csv = tmp_path / "test.csv"
        df.to_csv(ruta_csv, index=False)
        meta = generar_metadatos(ruta_csv, df, "Test")
        descripciones = {c["nombre"]: c["descripcion"] for c in meta["esquema"]}
        # Las columnas conocidas tienen descripción del diccionario
        assert "Tasa de actividad" in descripciones["tasa_actividad"]
        assert "Tasa de empleo" in descripciones["tasa_empleo"]

    def test_estructura_reporta_filas_y_columnas(self, tmp_path):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        ruta_csv = tmp_path / "test.csv"
        df.to_csv(ruta_csv, index=False)
        meta = generar_metadatos(ruta_csv, df, "Test")
        assert meta["estructura"]["n_filas"] == 3
        assert meta["estructura"]["n_columnas"] == 2

    def test_periodo_se_incluye_cuando_se_indica(self, tmp_path):
        df = pd.DataFrame({"x": [1]})
        ruta_csv = tmp_path / "test.csv"
        df.to_csv(ruta_csv, index=False)
        meta = generar_metadatos(ruta_csv, df, "Test", 2025, 4)
        assert meta["periodo"] == {"anio": 2025, "trimestre": 4}

    def test_diccionario_de_columnas_no_esta_vacio(self):
        assert len(DICCIONARIO_COLUMNAS) > 20

    def test_hash_es_consistente(self, tmp_path):
        ruta = tmp_path / "test.csv"
        ruta.write_text("a,b\n1,2\n3,4\n")
        h1 = calcular_hash(ruta)
        h2 = calcular_hash(ruta)
        assert h1 == h2
        assert len(h1) == 16  # truncado a 16 caracteres


# ─── Calendario y validación de esquema ─────────────────────────────────────

class TestCalendario:
    """Tests del calendario de publicaciones INDEC."""

    def test_t1_se_publica_en_junio_del_mismo_anio(self):
        mes, anio = fecha_publicacion_esperada(2025, 1)
        assert mes == "Junio"
        assert anio == 2025

    def test_t4_se_publica_en_marzo_del_anio_siguiente(self):
        mes, anio = fecha_publicacion_esperada(2025, 4)
        assert mes == "Marzo"
        assert anio == 2026

    def test_t3_se_publica_en_diciembre_del_mismo_anio(self):
        mes, anio = fecha_publicacion_esperada(2024, 3)
        assert mes == "Diciembre"
        assert anio == 2024


class TestValidacionEsquema:
    """Tests del sistema de validación de esquema vs INDEC."""

    def test_esquema_completo_devuelve_nivel_ok(self):
        df = pd.DataFrame(columns=ESQUEMA_OBLIGATORIO_INDIVIDUAL + ESQUEMA_OPCIONAL_INDIVIDUAL)
        result = validar_esquema(df, ESQUEMA_OBLIGATORIO_INDIVIDUAL,
                                  ESQUEMA_OPCIONAL_INDIVIDUAL, "individual", 2025, 4)
        assert result["nivel"] == "ok"
        assert result["obligatorias_faltantes"] == []

    def test_falta_obligatoria_devuelve_critico(self):
        # Falta P21 (obligatoria)
        cols = [c for c in ESQUEMA_OBLIGATORIO_INDIVIDUAL if c != "P21"]
        df = pd.DataFrame(columns=cols)
        result = validar_esquema(df, ESQUEMA_OBLIGATORIO_INDIVIDUAL,
                                  ESQUEMA_OPCIONAL_INDIVIDUAL, "individual", 2025, 4)
        assert result["nivel"] == "critico"
        assert "P21" in result["obligatorias_faltantes"]

    def test_falta_opcional_devuelve_advertencia(self):
        # Solo faltan opcionales (caso típico: EMPLEO en 1T2023)
        df = pd.DataFrame(columns=ESQUEMA_OBLIGATORIO_INDIVIDUAL)  # sin EMPLEO
        result = validar_esquema(df, ESQUEMA_OBLIGATORIO_INDIVIDUAL,
                                  ESQUEMA_OPCIONAL_INDIVIDUAL, "individual", 2023, 1)
        assert result["nivel"] == "advertencia"
        assert "EMPLEO" in result["opcionales_faltantes"]

    def test_resultado_incluye_metadata_de_validacion(self):
        df = pd.DataFrame(columns=ESQUEMA_OBLIGATORIO_HOGAR)
        result = validar_esquema(df, ESQUEMA_OBLIGATORIO_HOGAR,
                                  [], "hogar", 2025, 4)
        assert result["periodo"] == "2025T4"
        assert result["base"] == "hogar"
        assert "fecha_validacion" in result

"""Pruebas del pipeline, las salidas validadas y el snapshot agregado."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from pipeline import (  # noqa: E402
    AGLOMERADO_SDE,
    DICCIONARIO_COLUMNAS,
    ESQUEMA_OBLIGATORIO_HOGAR,
    ESQUEMA_OBLIGATORIO_INDIVIDUAL,
    ESQUEMA_OPCIONAL_INDIVIDUAL,
    PIPELINE_VERSION,
    actualizar_estado_periodo,
    calcular_hash,
    calcular_indicadores,
    clasificar_salida,
    fecha_publicacion_esperada,
    filtrar_sde,
    generar_manifiesto,
    generar_metadatos,
    guardar_metadatos,
    guardar_trimestre,
    migrar_historico,
    normalizar_estado,
    normalizar_periodo,
    porcentaje,
    preparar_snapshot_desde_historico,
    publicar_snapshot_validado,
    reporte_calidad,
    unir_bases,
    validar_esquema,
    validar_publicacion,
)
import pipeline as pipeline_module  # noqa: E402


@pytest.fixture
def datos_individuales_mock() -> pd.DataFrame:
    return pd.DataFrame({
        "AGLOMERADO": [18] * 6,
        "PONDERA": [100, 150, 200, 100, 150, 100],
        "ESTADO": [1, 1, 2, 3, 3, 4],
        "EMPLEO": [1, 2, 0, 0, 0, 0],
        "P21": [500000, 700000, 0, 0, 0, 0],
        "CH04": [1, 2, 1, 2, 1, 2],
        "CH06": [35, 42, 28, 65, 50, 8],
        "CODUSU": ["A", "A", "B", "C", "D", "E"],
        "NRO_HOGAR": [1, 1, 1, 1, 1, 1],
    })


@pytest.fixture
def datos_hogar_mock() -> pd.DataFrame:
    return pd.DataFrame({
        "AGLOMERADO": [18, 18, 18, 18, 18],
        "REALIZADA": [1, 1, 0, 1, 1],
        "CODUSU": ["A", "B", "C", "D", "E"],
        "NRO_HOGAR": [1, 1, 1, 1, 1],
    })


@pytest.fixture
def indicadores_mock(datos_individuales_mock, datos_hogar_mock) -> dict:
    return calcular_indicadores(datos_individuales_mock, datos_hogar_mock, 2025, 4)


class TestPorcentaje:
    def test_calculo(self):
        assert porcentaje(50, 100) == 50.0

    def test_precision(self):
        assert porcentaje(1, 3, 4) == 33.3333

    @pytest.mark.parametrize("denominador", [0, -1, None])
    def test_denominador_no_positivo(self, denominador):
        assert porcentaje(10, denominador) is None


class TestIndicadores:
    def test_actividad_oficial_usa_poblacion_total(self, indicadores_mock):
        assert indicadores_mock["tasa_actividad_oficial"] == 56.25

    def test_empleo_oficial_usa_poblacion_total(self, indicadores_mock):
        assert indicadores_mock["tasa_empleo_oficial"] == 31.25

    def test_desocupacion_usa_pea(self, indicadores_mock):
        assert indicadores_mock["tasa_desocupacion"] == 44.44

    def test_proporcion_inactiva_es_complementaria(self, indicadores_mock):
        assert indicadores_mock["proporcion_inactiva_total"] == 43.75
        assert indicadores_mock["tasa_actividad_oficial"] + indicadores_mock["proporcion_inactiva_total"] == 100

    def test_tasas_10_mas_con_nombres_especificos(self, indicadores_mock):
        assert indicadores_mock["tasa_actividad_10_mas"] == 64.29
        assert indicadores_mock["tasa_empleo_10_mas"] == 35.71
        assert indicadores_mock["tasa_inactividad_10_mas"] == 35.71

    def test_no_conserva_nombres_ambiguos(self, indicadores_mock):
        assert "tasa_actividad" not in indicadores_mock
        assert "tasa_empleo" not in indicadores_mock
        assert "tasa_inactividad" not in indicadores_mock

    def test_tasas_en_rango(self, indicadores_mock):
        tasas = [clave for clave in indicadores_mock if clave.startswith("tasa_")]
        for tasa in tasas:
            valor = indicadores_mock[tasa]
            assert valor is None or 0 <= valor <= 100

    def test_poblacion_total_positiva(self, indicadores_mock):
        assert indicadores_mock["poblacion_expandida_total"] == 800
        assert indicadores_mock["poblacion_expandida_total"] > 0

    def test_aglomerado_18(self, indicadores_mock):
        assert indicadores_mock["aglomerado"] == AGLOMERADO_SDE

    def test_ingreso_ponderado_nominal(self, indicadores_mock):
        assert indicadores_mock["ingreso_promedio_ponderado_observado"] == 620000

    def test_informalidad_ponderada(self, indicadores_mock):
        assert indicadores_mock["tasa_informalidad"] == 60.0

    def test_informalidad_nula_si_empleo_no_disponible(
        self, datos_individuales_mock, datos_hogar_mock
    ):
        sin_empleo = datos_individuales_mock.drop(columns=["EMPLEO"])
        resultado = calcular_indicadores(sin_empleo, datos_hogar_mock, 2023, 1)
        assert resultado["tasa_informalidad"] is None

    def test_no_imputa_pondera_faltante(self, datos_individuales_mock, datos_hogar_mock):
        datos = datos_individuales_mock.copy()
        datos.loc[0, "PONDERA"] = None
        resultado = calcular_indicadores(datos, datos_hogar_mock, 2025, 4)
        assert resultado["poblacion_expandida_total"] == 700


class TestMigracionHistorico:
    def test_migra_columnas_sin_cambiar_semantica(self):
        anterior = pd.DataFrame([{
            "anio": 2025, "trimestre": 4, "periodo": " 2025t4 ", "aglomerado": 18,
            "poblacion_expandida_total": 1000, "poblacion_expandida_mayor10": 800,
            "pea_expandida": 400, "ocupados_expandidos": 350,
            "desocupados_expandidos": 50, "inactivos_expandidos": 400,
            "tasa_actividad": 50.0, "tasa_empleo": 43.75, "tasa_inactividad": 50.0,
        }])
        nuevo = migrar_historico(anterior)
        assert nuevo.loc[0, "tasa_actividad_10_mas"] == 50.0
        assert nuevo.loc[0, "tasa_actividad_oficial"] == 40.0
        assert nuevo.loc[0, "proporcion_inactiva_total"] == 60.0
        assert nuevo.loc[0, "periodo"] == "2025T4"
        assert normalizar_periodo("2025-T4") == "2025T4"
        assert normalizar_estado(" validado ") == "VALIDADO"

    def test_migracion_idempotente(self):
        base = pd.DataFrame([{
            "periodo": "2025T4", "poblacion_expandida_total": 1000,
            "poblacion_expandida_mayor10": 800, "pea_expandida": 400,
            "ocupados_expandidos": 350, "desocupados_expandidos": 50,
            "inactivos_expandidos": 400,
        }])
        una = migrar_historico(base)
        dos = migrar_historico(una)
        pd.testing.assert_frame_equal(una, dos)


class TestCalidadYUnion:
    def test_filtrar_sde(self):
        df = pd.DataFrame({"AGLOMERADO": [18, 7, 18], "x": [1, 2, 3]})
        resultado = filtrar_sde(df)
        assert resultado["x"].tolist() == [1, 3]

    def test_reporte_conserva_variable_no_disponible(self):
        resultado = reporte_calidad(pd.DataFrame({"P21": [1, -9, None]}), ["P21", "EMPLEO"])
        empleo = resultado[resultado["columna"] == "EMPLEO"].iloc[0]
        assert not empleo["variable_disponible"]
        assert pd.isna(empleo["nulos"])

    def test_reporte_cuenta_especiales(self):
        fila = reporte_calidad(pd.DataFrame({"P21": [1, -9, -8, -7, None]}), ["P21"]).iloc[0]
        assert fila["codigo_-9_no_resp"] == 1
        assert fila["codigo_-8"] == 1
        assert fila["codigo_-7"] == 1
        assert fila["nulos"] == 1

    def test_union_por_clave_compuesta(self, datos_individuales_mock, datos_hogar_mock):
        resultado = unir_bases(datos_individuales_mock, datos_hogar_mock)
        assert len(resultado) == len(datos_individuales_mock)
        assert "REALIZADA" in resultado.columns


class TestExtraccionSegura:
    def test_zip_sin_bases_no_se_promueve(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pipeline_module, "DIR_DATOS", tmp_path / "data")
        pipeline_module.DIR_DATOS.mkdir()
        ruta = tmp_path / "vacio.zip"
        with zipfile.ZipFile(ruta, "w") as archivo:
            archivo.writestr("README.txt", "sin bases")
        individual, hogar = pipeline_module.extraer_zip(ruta, 2025, 4)
        assert individual is None and hogar is None
        assert not (pipeline_module.DIR_DATOS / "t4_2025").exists()

    def test_zip_con_ruta_insegura_se_rechaza(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pipeline_module, "DIR_DATOS", tmp_path / "data")
        pipeline_module.DIR_DATOS.mkdir()
        ruta = tmp_path / "inseguro.zip"
        with zipfile.ZipFile(ruta, "w") as archivo:
            archivo.writestr("../individual.txt", "contenido")
            archivo.writestr("hogar.txt", "contenido")
        individual, hogar = pipeline_module.extraer_zip(ruta, 2025, 4)
        assert individual is None and hogar is None
        assert not (tmp_path / "individual.txt").exists()


class TestMetadatos:
    def test_incluye_campos_institucionales(self, tmp_path):
        df = pd.DataFrame({"periodo": ["2025T4"], "tasa_actividad_oficial": [41.23]})
        ruta = tmp_path / "indicadores_SDE_2025T4.csv"
        df.to_csv(ruta, index=False)
        meta = generar_metadatos(ruta, df, "Prueba", 2025, 4)
        requeridos = {
            "nombre_archivo", "descripcion", "clasificacion_load", "fuente",
            "organismo_productor", "url_origen", "aglomerado_codigo",
            "aglomerado_nombre", "periodo", "anio", "trimestre",
            "fecha_hora_generacion", "version_pipeline", "filas", "columnas",
            "variables", "definicion_variables", "tipos_de_datos", "unidades",
            "formulas", "filtros_aplicados", "ponderador", "cantidad_nulos",
            "codigos_especiales", "advertencias_metodologicas", "ingresos_nominales",
            "estado_validacion", "ultima_ejecucion_exitosa", "archivo_origen",
            "identificador_ejecucion", "hash_sha256",
        }
        assert requeridos <= set(meta)

    def test_formula_oficial_documentada(self, tmp_path):
        df = pd.DataFrame({"tasa_actividad_oficial": [40.0]})
        ruta = tmp_path / "test.csv"
        df.to_csv(ruta, index=False)
        meta = generar_metadatos(ruta, df, "Prueba")
        assert "población total" in meta["formulas"]["tasa_actividad_oficial"]

    def test_nombre_meta_corresponde_al_csv(self, tmp_path):
        df = pd.DataFrame({"x": [1]})
        ruta = tmp_path / "archivo.csv"
        df.to_csv(ruta, index=False)
        ruta_meta = guardar_metadatos(ruta, generar_metadatos(ruta, df, "Prueba"))
        assert ruta_meta.name == "archivo.meta.json"
        assert json.loads(ruta_meta.read_text(encoding="utf-8"))["nombre_archivo"] == "archivo.csv"

    def test_hash_consistente(self, tmp_path):
        ruta = tmp_path / "a.csv"
        ruta.write_text("a\n1\n", encoding="utf-8")
        assert calcular_hash(ruta) == calcular_hash(ruta)
        assert len(calcular_hash(ruta)) == 64

    def test_diccionario_y_version(self):
        assert PIPELINE_VERSION == "3.0.0"
        assert "tasa_actividad_oficial" in DICCIONARIO_COLUMNAS


class TestManifiestoYEstados:
    def test_clasificaciones(self):
        assert clasificar_salida("historico_SDE.csv") == "Crítica"
        assert clasificar_salida("indicadores_SDE_2025T4.csv") == "Analítica"
        assert clasificar_salida("calidad_datos_SDE_2025T4.csv") == "Calidad"
        assert clasificar_salida("validacion_esquema_2025T4.json") == "Auditoría"

    def test_manifiesto_asocia_metadata(self, tmp_path):
        df = pd.DataFrame({"periodo": ["2025T4"]})
        ruta = tmp_path / "historico_SDE.csv"
        df.to_csv(ruta, index=False)
        guardar_metadatos(ruta, generar_metadatos(ruta, df, "Histórico", estado_validacion="VALIDADO"))
        manifiesto = generar_manifiesto(tmp_path)
        salida = next(s for s in manifiesto["salidas"] if s["nombre_archivo"] == ruta.name)
        assert salida["archivo_metadatos"] == "historico_SDE.meta.json"
        assert salida["clasificacion_load"] == "Crítica"

    def test_estado_periodo_no_duplica(self, tmp_path):
        actualizar_estado_periodo(" 2025t4 ", " pendiente ", "Inicio", tmp_path, True)
        resultado = actualizar_estado_periodo("2025-T4", " validado ", "Correcto", tmp_path)
        assert len(resultado) == 1
        assert resultado.iloc[0]["periodo"] == "2025T4"
        assert resultado.iloc[0]["estado"] == "VALIDADO"
        assert (tmp_path / "estado_periodos.meta.json").exists()


class TestValidacionPublicacion:
    def _bases_grandes(self, datos_individuales_mock, datos_hogar_mock):
        ind = pd.concat([datos_individuales_mock] * 20, ignore_index=True)
        hog = pd.concat([datos_hogar_mock] * 7, ignore_index=True)
        return ind, hog

    def test_publicacion_valida(self, tmp_path, datos_individuales_mock, datos_hogar_mock):
        ind, hog = self._bases_grandes(datos_individuales_mock, datos_hogar_mock)
        indicadores = calcular_indicadores(ind, hog, 2025, 4)
        historico = pd.DataFrame([indicadores])
        rutas = []
        for nombre in ["a.csv", "a.meta.json"]:
            ruta = tmp_path / nombre
            ruta.write_text("x", encoding="utf-8")
            rutas.append(ruta)
        resultado = validar_publicacion(indicadores, historico, ind, hog, rutas)
        assert resultado["es_valida"]
        assert resultado["estado"] == "VALIDADO"

    def test_bloquea_poblacion_cero(self, tmp_path, datos_individuales_mock, datos_hogar_mock):
        ind, hog = self._bases_grandes(datos_individuales_mock, datos_hogar_mock)
        indicadores = calcular_indicadores(ind, hog, 2025, 4)
        indicadores["poblacion_expandida_total"] = 0
        resultado = validar_publicacion(indicadores, pd.DataFrame([indicadores]), ind, hog, [])
        assert not resultado["es_valida"]
        assert resultado["estado"] == "FALLIDO"

    def test_bloquea_periodos_duplicados(self, datos_individuales_mock, datos_hogar_mock):
        ind, hog = self._bases_grandes(datos_individuales_mock, datos_hogar_mock)
        indicadores = calcular_indicadores(ind, hog, 2025, 4)
        historico = pd.DataFrame([indicadores, indicadores])
        resultado = validar_publicacion(indicadores, historico, ind, hog, [])
        assert not resultado["es_valida"]

    def test_bloquea_tasa_fuera_de_rango(self, datos_individuales_mock, datos_hogar_mock):
        ind, hog = self._bases_grandes(datos_individuales_mock, datos_hogar_mock)
        indicadores = calcular_indicadores(ind, hog, 2025, 4)
        indicadores["tasa_empleo_oficial"] = 120
        resultado = validar_publicacion(indicadores, pd.DataFrame([indicadores]), ind, hog, [])
        assert not resultado["es_valida"]

    def test_guardado_transaccional_genera_salidas(
        self, tmp_path, datos_individuales_mock, datos_hogar_mock
    ):
        indicadores = calcular_indicadores(datos_individuales_mock, datos_hogar_mock, 2025, 4)
        resultado = guardar_trimestre(
            indicadores, datos_individuales_mock, datos_hogar_mock,
            tmp_path / "results", minimo_personas=1, minimo_hogares=1,
        )
        assert resultado["es_valida"]
        assert (tmp_path / "results" / "historico_SDE.csv").exists()
        assert (tmp_path / "results" / "manifest_salidas.json").exists()

    def test_guardado_fallido_no_reemplaza_historico(
        self, tmp_path, datos_individuales_mock, datos_hogar_mock
    ):
        resultados = tmp_path / "results"
        resultados.mkdir()
        anterior = resultados / "historico_SDE.csv"
        anterior.write_text("periodo\n2024T4\n", encoding="utf-8")
        contenido = anterior.read_bytes()
        indicadores = calcular_indicadores(datos_individuales_mock, datos_hogar_mock, 2025, 4)
        resultado = guardar_trimestre(
            indicadores, datos_individuales_mock, datos_hogar_mock,
            resultados, minimo_personas=1000, minimo_hogares=1000,
        )
        assert not resultado["es_valida"]
        assert anterior.read_bytes() == contenido

    def test_validacion_fallida_conserva_reporte_de_auditoria(
        self, tmp_path, datos_individuales_mock, datos_hogar_mock
    ):
        resultados = tmp_path / "results"
        indicadores = calcular_indicadores(datos_individuales_mock, datos_hogar_mock, 2025, 4)
        resultado = guardar_trimestre(
            indicadores, datos_individuales_mock, datos_hogar_mock,
            resultados, minimo_personas=1000, minimo_hogares=1000,
        )
        assert not resultado["es_valida"]
        assert (resultados / "validacion_publicacion_2025T4.json").exists()
        assert (resultados / "validacion_publicacion_2025T4.meta.json").exists()


class TestSnapshot:
    def _historico(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "anio": 2025, "trimestre": 4, "periodo": "2025T4", "aglomerado": 18,
            "n_personas_muestra": 1400, "n_hogares_muestra": 400,
            "poblacion_expandida_total": 1000, "poblacion_expandida_mayor10": 800,
            "pea_expandida": 400, "ocupados_expandidos": 350,
            "desocupados_expandidos": 50, "inactivos_expandidos": 400,
            "tasa_actividad": 50.0, "tasa_empleo": 43.75,
            "tasa_desocupacion": 12.5, "tasa_inactividad": 50.0,
            "tasa_informalidad": None, "ingreso_promedio_observado": 100,
            "ingreso_mediano_observado": 90,
            "ingreso_promedio_ponderado_observado": 110,
            "n_ocupados_con_ingreso_valido": 10,
            "n_ocupados_sin_respuesta_ingreso": 1,
            "tasa_no_respuesta_ingresos_ocupados": 2.0,
            "hogares_encuestados": 400, "tasa_no_respuesta_hogar": 0.0,
            "fecha_procesamiento": "2026-07-01 10:00:00", "fuente": "INDEC",
        }])

    def test_snapshot_agregado_sin_microdatos(self, tmp_path):
        origen = tmp_path / "historico.csv"
        self._historico().to_csv(origen, index=False)
        destino = tmp_path / "snapshot"
        preparar_snapshot_desde_historico(origen, destino, tmp_path / "sin_validaciones")
        assert (destino / "historico_SDE.csv").exists()
        assert (destino / "calidad_snapshot_SDE.csv").exists()
        assert not list(destino.glob("base_unida*.csv"))
        assert not list(destino.glob("*.zip"))

    def test_snapshot_es_idempotente(self, tmp_path):
        origen = tmp_path / "historico.csv"
        self._historico().to_csv(origen, index=False)
        destino = tmp_path / "snapshot"
        preparar_snapshot_desde_historico(origen, destino, tmp_path / "sin_validaciones")
        preparar_snapshot_desde_historico(destino / "historico_SDE.csv", destino, destino)
        assert (destino / "manifest_salidas.json").exists()

    def test_snapshot_conserva_anterior_si_origen_invalido(self, tmp_path):
        destino = tmp_path / "snapshot"
        destino.mkdir()
        marcador = destino / "vigente.txt"
        marcador.write_text("válido", encoding="utf-8")
        origen = tmp_path / "invalido.csv"
        pd.DataFrame([{"periodo": "2025T4"}]).to_csv(origen, index=False)
        with pytest.raises(ValueError):
            preparar_snapshot_desde_historico(origen, destino)
        assert marcador.read_text(encoding="utf-8") == "válido"

    def test_publicacion_bloqueada_conserva_snapshot(self, tmp_path):
        origen = tmp_path / "results"
        destino = tmp_path / "snapshot"
        origen.mkdir()
        destino.mkdir()
        marcador = destino / "vigente.txt"
        marcador.write_text("válido", encoding="utf-8")
        self._historico().to_csv(origen / "historico_SDE.csv", index=False)
        pd.DataFrame([{"periodo": "2025T4", "estado": "FALLIDO"}]).to_csv(
            origen / "estado_periodos.csv", index=False
        )
        with pytest.raises(RuntimeError):
            publicar_snapshot_validado(origen, destino)
        assert marcador.read_text(encoding="utf-8") == "válido"

    def test_dashboard_usa_rutas_relativas(self):
        codigo = (RAIZ / "notebooks" / "app.py").read_text(encoding="utf-8")
        assert "Path(__file__).resolve().parent.parent" in codigo
        assert ":\\\\" not in codigo


class TestCalendarioYEsquema:
    def test_fechas_publicacion(self):
        assert fecha_publicacion_esperada(2025, 1) == ("Junio", 2025)
        assert fecha_publicacion_esperada(2025, 4) == ("Marzo", 2026)

    def test_esquema_completo(self):
        df = pd.DataFrame(columns=ESQUEMA_OBLIGATORIO_INDIVIDUAL + ESQUEMA_OPCIONAL_INDIVIDUAL)
        resultado = validar_esquema(
            df, ESQUEMA_OBLIGATORIO_INDIVIDUAL, ESQUEMA_OPCIONAL_INDIVIDUAL,
            "individual", 2025, 4,
        )
        assert resultado["nivel"] == "ok"

    def test_esquema_critico(self):
        df = pd.DataFrame(columns=[c for c in ESQUEMA_OBLIGATORIO_HOGAR if c != "REALIZADA"])
        resultado = validar_esquema(df, ESQUEMA_OBLIGATORIO_HOGAR, [], "hogar", 2025, 4)
        assert resultado["nivel"] == "critico"
        assert "REALIZADA" in resultado["obligatorias_faltantes"]

    def test_esquema_advertencia_por_empleo(self):
        df = pd.DataFrame(columns=ESQUEMA_OBLIGATORIO_INDIVIDUAL)
        resultado = validar_esquema(
            df, ESQUEMA_OBLIGATORIO_INDIVIDUAL, ESQUEMA_OPCIONAL_INDIVIDUAL,
            "individual", 2023, 1,
        )
        assert resultado["nivel"] == "advertencia"

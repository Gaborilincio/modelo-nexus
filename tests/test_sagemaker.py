"""Contrato del puntuador remoto, del ranking y del plan B."""

import json

import numpy as np
import pandas as pd
import pytest

from app.recomendador import Recomendador
from app.sagemaker_cliente import ErrorRemoto, PuntuadorSageMaker


class Cuerpo:
    def __init__(self, datos):
        self.datos = datos

    def read(self):
        return self.datos


class ClienteFalso:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []

    def invoke_endpoint(self, **kwargs):
        self.llamadas.append(kwargs)
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        datos = self.respuesta
        if not isinstance(datos, bytes):
            datos = json.dumps(datos).encode()
        return {"Body": Cuerpo(datos)}


def puntuador(respuesta, features=("a", "b"), cols_cat=("b",)):
    p = PuntuadorSageMaker("endpoint-prueba", cliente=ClienteFalso(respuesta))
    p.configurar(features, cols_cat)
    return p


class PuntuadorFalso:
    endpoint = "prueba"

    def __init__(self, error=None):
        self.error = error
        self.columnas = None

    def configurar(self, features, cols_cat):
        self.features = list(features)

    def puntuar(self, X):
        self.columnas = list(X.columns)
        if self.error is not None:
            raise self.error
        return np.linspace(0, 1, len(X))


# --------------------------------------------------------------- cliente remoto
def test_envia_columnas_en_orden_y_devuelve_puntajes():
    X = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", "y"]})
    p = puntuador({"puntajes": [0.5, 0.25]})

    assert np.allclose(p.puntuar(X), [0.5, 0.25])
    llamada = p.cliente.llamadas[0]
    assert llamada["EndpointName"] == "endpoint-prueba"
    assert llamada["ContentType"] == "application/json"
    assert json.loads(llamada["Body"]) == {"filas": [[1.0, "x"], [2.0, "y"]]}


@pytest.mark.parametrize(
    "respuesta",
    [
        {"puntajes": [0.5]},
        {"puntajes": [0.5, float("nan")]},
        {"otra_cosa": []},
        b"no es json",
        RuntimeError("endpoint caído"),
    ],
)
def test_respuesta_invalida_es_error_remoto(respuesta):
    X = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", "y"]})
    with pytest.raises(ErrorRemoto):
        puntuador(respuesta).puntuar(X)


def test_columnas_fuera_de_orden_no_se_envian():
    p = puntuador({"puntajes": [0.5]})
    with pytest.raises(ErrorRemoto):
        p.puntuar(pd.DataFrame({"b": ["x"], "a": [1.0]}))
    assert p.cliente.llamadas == []


def test_desde_entorno(monkeypatch):
    monkeypatch.delenv("SAGEMAKER_ENDPOINT", raising=False)
    assert PuntuadorSageMaker.desde_entorno() is None
    monkeypatch.setenv("SAGEMAKER_ENDPOINT", "nexus-reco")
    p = PuntuadorSageMaker.desde_entorno()
    assert p is not None and p.endpoint == "nexus-reco"


def test_esquema_del_handler_coincide_con_el_entrenamiento():
    import importlib.util
    from pathlib import Path

    carpeta = Path(__file__).resolve().parents[1] / "sagemaker"
    espec = importlib.util.spec_from_file_location(
        "inferencia_handler", carpeta / "inferencia.py"
    )
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)

    esquema = json.loads((carpeta / "esquema.json").read_text(encoding="utf-8"))
    assert modulo.FEATURES == esquema["features"]
    assert modulo.COLS_CAT == esquema["cols_cat"]


# ------------------------------------------------------------------- recomendador
def test_recomendar_puntua_remoto_y_mantiene_orden(hay_modelo):
    r = Recomendador()
    falso = PuntuadorFalso()
    r.puntuador = falso

    uid = next(iter(set(r.estado["comprados"]) & set(r.usuarios["usuario_id"])))
    recs = r.recomendar(uid, 5)

    assert falso.columnas == r.features
    assert r.resumen()["origen_puntajes"] == "sagemaker:prueba"
    puntajes = [x["puntaje"] for x in recs]
    assert puntajes == sorted(puntajes, reverse=True)
    assert [x["puesto"] for x in recs] == [1, 2, 3, 4, 5]


def test_fallo_remoto_llega_al_plan_b(cliente, hay_modelo):
    from app import main

    r = main.estado["recomendador"]
    original, r.puntuador = r.puntuador, PuntuadorFalso(error=ErrorRemoto("caído"))
    try:
        uid = next(iter(set(r.estado["comprados"]) & set(r.usuarios["usuario_id"])))
        cuerpo = cliente.post("/predict", json={"usuario_id": uid, "k": 4}).json()
    finally:
        r.puntuador = original

    assert cuerpo["origen"] == "fallback"
    assert cuerpo["motivo"] == "error al calcular la predicción"
    assert all(x["puntaje"] is None for x in cuerpo["recomendaciones"])

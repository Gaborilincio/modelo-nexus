"""Handler del endpoint: recibe features en JSON y devuelve los puntajes del pipeline.

Contrato: POST con {"filas": [[...], ...]}, una fila por candidato y los 25 valores en el
orden de esquema.json. No recibe usuario_id, sku ni datos personales.

El esquema está embebido porque el contenedor instala este módulo fuera de la carpeta del
modelo; tests/test_sagemaker.py comprueba que coincide con esquema.json.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

FEATURES = [
    "n_pedidos",
    "recencia_dias",
    "frecuencia",
    "unidades_totales",
    "categorias_distintas",
    "antiguedad_registro_dias",
    "region",
    "canal_captacion",
    "unidades_vendidas",
    "n_compradores",
    "precio_lista",
    "categoria",
    "marca",
    "antiguedad_sku_dias",
    "compradores_30d",
    "compradores_90d",
    "tendencia_30_90",
    "n_vistas",
    "n_clics",
    "n_agregados_carrito",
    "afinidad_categoria",
    "afinidad_marca",
    "recencia_cat_dias",
    "regla_pop_categoria",
    "senal_implicita",
]
COLS_CAT = ["region", "canal_captacion", "categoria", "marca"]
NUM = [c for c in FEATURES if c not in COLS_CAT]


def model_fn(model_dir):
    return joblib.load(Path(model_dir) / "model.joblib")


def input_fn(cuerpo, content_type):
    if content_type.split(";")[0].strip() != "application/json":
        raise ValueError("Content-Type debe ser application/json")
    filas = json.loads(cuerpo).get("filas")
    if not isinstance(filas, list) or not filas:
        raise ValueError("Se espera {'filas': [[...], ...]} con al menos una fila")
    if any(not isinstance(f, list) or len(f) != len(FEATURES) for f in filas):
        raise ValueError(
            f"Cada fila debe tener {len(FEATURES)} valores en el orden del esquema"
        )

    df = pd.DataFrame(filas, columns=FEATURES)
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors="raise")
        if not np.isfinite(df[c].to_numpy(float)).all():
            raise ValueError(f"{c}: valor no finito")
    for c in COLS_CAT:
        df[c] = df[c].astype(str)
    return df


def predict_fn(df, modelo):
    return modelo.decision_function(df).astype(float).tolist()


def output_fn(puntajes, accept):
    return json.dumps({"puntajes": puntajes}, allow_nan=False), "application/json"

"""Las variables que calcula la API deben ser las mismas que calculó el notebook 02 al entrenar."""

import joblib
import numpy as np
import pytest

from app import features as F
from app.recomendador import DIR_PROCESADOS


def test_variables_iguales_al_notebook(hay_modelo):
    ruta = DIR_PROCESADOS / "ranking_validacion.pkl"
    if not ruta.exists():
        pytest.skip("Falta ranking_validacion.pkl (notebook 02)")
    rk = joblib.load(ruta)
    meta = joblib.load(DIR_PROCESADOS / "metadatos.pkl")
    rk = rk.assign(usuario_id=rk["usuario_id"].astype(str), sku=rk["sku"].astype(str))
    muestra = rk[rk["usuario_id"].isin(rk["usuario_id"].drop_duplicates().head(30))][
        ["usuario_id", "sku"]
    ]

    productos, usuarios, trx, clk = F.cargar_tablas(DIR_PROCESADOS)
    E = F.construir_estado(
        productos, usuarios, trx, clk, meta["corte_validacion"], meta
    )
    E["fp"] = E["fp"].assign(sku=E["fp"]["sku"].astype(str))
    E["it"] = E["it"].assign(sku=E["it"]["sku"].astype(str))
    X = F.tratar_nulos(
        F.ensamblar(muestra, E, meta),
        *F.medianas_precio(productos),
        meta["medianas_antiguedad"],
    )

    m = rk.merge(muestra, on=["usuario_id", "sku"]).merge(
        X, on=["usuario_id", "sku"], suffixes=("_nb", "_api")
    )
    assert len(m) == len(muestra)
    distintas = []
    for c in meta["features"]:
        a, b = m[c + "_nb"], m[c + "_api"]
        igual = (
            np.allclose(a, b, equal_nan=True)
            if a.dtype.kind in "fiub"
            else (a.astype(str) == b.astype(str)).all()
        )
        if not igual:
            distintas.append(c)
    assert not distintas, f"Variables distintas entre notebook y API: {distintas}"

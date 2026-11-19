"""Comprueba el endpoint Nexus: paridad con el artefacto, entradas inválidas, ranking y latencia.

Se ejecuta donde estén los datos procesados (p. ej. el contenedor de la IA) y con AWS ya
autenticado por el perfil de instancia.
"""

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from app.sagemaker_cliente import PuntuadorSageMaker

RAIZ = Path(__file__).resolve().parent
ESTADO = RAIZ / "estado"
PROCESADOS = RAIZ.parent / "datos" / "procesados"


def metricas_ranking(ranking: pd.DataFrame, puntaje: np.ndarray, k: int = 5) -> dict:
    df = ranking[["usuario_id", "compra"]].assign(p=puntaje)
    positivos = df.groupby("usuario_id")["compra"].sum()
    ndcg, ap, hit = [], [], []
    for uid, g in df.groupby("usuario_id", sort=False):
        rel = (
            g.sort_values("p", ascending=False, kind="stable")
            .head(k)["compra"]
            .to_numpy(float)
        )
        dcg = (rel / np.log2(np.arange(2, len(rel) + 2))).sum()
        ideal = min(int(positivos[uid]), k)
        idcg = (1 / np.log2(np.arange(2, ideal + 2))).sum()
        ndcg.append(dcg / idcg if idcg else 0.0)
        aciertos = np.cumsum(rel) / np.arange(1, len(rel) + 1)
        ap.append(
            (aciertos * rel).sum() / ideal if ideal else 0.0
        )
        hit.append(float(rel.sum() > 0))
    return {
        "ndcg@5": round(float(np.mean(ndcg)), 4),
        "map@5": round(float(np.mean(ap)), 4),
        "hit@5": round(float(np.mean(hit)), 4),
        "usuarios": int(len(ndcg)),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", default=None)
    p.add_argument("--llamadas", type=int, default=20)
    a = p.parse_args()

    endpoint = a.endpoint or json.loads(
        (ESTADO / "endpoint.json").read_text()
    )["endpoint"]
    meta = json.loads((ESTADO / "metadatos.json").read_text())
    nuevo = joblib.load(ESTADO / "model.joblib")
    previo = joblib.load(RAIZ.parent / "datos" / "modelos" / "modelo_recomendador.joblib")
    features = meta["features"]

    puntuador = PuntuadorSageMaker(endpoint)
    puntuador.configurar(features, meta["cols_cat"])

    ranking = joblib.load(PROCESADOS / "ranking_validacion.pkl")

    # 1. Paridad: mismo artefacto cargado localmente contra el endpoint
    muestra = ranking[ranking["usuario_id"].isin(
        ranking["usuario_id"].drop_duplicates().head(2)
    )][features]
    local = np.asarray(nuevo.decision_function(muestra), dtype=float)
    remoto = puntuador.puntuar(muestra)
    diferencia = float(np.abs(local - remoto).max())
    print(
        f"Paridad · {len(muestra):,} filas · diferencia máxima {diferencia:.2e}"
    )
    if diferencia > 1e-4:
        raise SystemExit("La paridad supera la tolerancia 1e-4")

    # 2. Entradas inválidas: deben ser rechazadas
    for etiqueta, cuerpo, tipo in (
        ("24 columnas", {"filas": [[0.0] * 24]}, "application/json"),
        ("tipo no JSON", {"filas": [[0.0] * len(features)]}, "text/csv"),
    ):
        try:
            puntuador.cliente.invoke_endpoint(
                EndpointName=endpoint,
                ContentType=tipo,
                Accept="application/json",
                Body=json.dumps(cuerpo).encode(),
            )
        except Exception as e:
            print(f"Entrada inválida ({etiqueta}) rechazada: {type(e).__name__}")
        else:
            raise SystemExit(f"El endpoint aceptó una entrada inválida: {etiqueta}")

    # 3. Latencia con la matriz de un usuario (todos sus candidatos)
    uid = ranking["usuario_id"].iloc[0]
    X = ranking[ranking["usuario_id"] == uid][features]
    tiempos = []
    for i in range(a.llamadas):
        inicio = time.perf_counter()
        puntuador.puntuar(X)
        tiempos.append((time.perf_counter() - inicio) * 1000)
        if i < 2:
            print(f"Invocación {i + 1}: {tiempos[-1]:.0f} ms · {len(X):,} filas")
        time.sleep(0.3)  # ritmo de 3 llamadas/s para no agotar la concurrencia 2
    print(
        f"Latencia {a.llamadas} invocaciones ({len(X):,} filas): "
        f"p50 {np.percentile(tiempos, 50):.0f} ms · p95 {np.percentile(tiempos, 95):.0f} ms"
    )

    # 4. Ranking y pares: nuevo artefacto contra el desplegado en EP2
    prior = meta["pop_alpha"] * np.log(
        ranking["n_compradores"].to_numpy(float) + meta["eps_pop"]
    )
    validacion = joblib.load(PROCESADOS / "validacion.pkl")
    for nombre, modelo in (("nuevo", nuevo), ("previo EP2", previo)):
        pares = modelo.decision_function(validacion[features])
        ranking_m = metricas_ranking(
            ranking, modelo.decision_function(ranking[features]) + prior
        )
        print(
            f"{nombre}: AUC pares {roc_auc_score(validacion['compra'], pares):.4f} · "
            f"AP pares {average_precision_score(validacion['compra'], pares):.4f} · "
            f"{ranking_m}"
        )


if __name__ == "__main__":
    main()

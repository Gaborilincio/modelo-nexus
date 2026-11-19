"""Exporta las matrices del proyecto a CSV sin identificadores y fija el esquema del modelo.

Se ejecuta donde estén los datos procesados (p. ej. el contenedor de la IA), no en SageMaker.
El esquema queda en sagemaker/esquema.json y lo usan entrenamiento e inferencia.
"""

import json
import os
from pathlib import Path

import joblib

RAIZ = Path(__file__).resolve().parent
PROYECTO = RAIZ.parent
PROCESADOS = Path(os.environ.get("DATOS_PROCESADOS", PROYECTO / "datos" / "procesados"))
MODELOS = Path(os.environ.get("DIR_MODELOS", PROYECTO / "datos" / "modelos"))
SALIDA = RAIZ / "salida"


def main() -> None:
    entrenamiento = joblib.load(PROCESADOS / "entrenamiento.pkl")
    validacion = joblib.load(PROCESADOS / "validacion.pkl")
    metadatos = joblib.load(MODELOS / "modelo_metadatos.joblib")
    features = metadatos["features"]
    cols_cat = metadatos["cols_cat"]

    SALIDA.mkdir(exist_ok=True)
    for nombre, df in (("train", entrenamiento), ("validation", validacion)):
        matriz = df[features + ["compra"]]
        if matriz.isna().any().any():
            raise ValueError(f"{nombre}: hay nulos en features o etiqueta")
        matriz.to_csv(SALIDA / f"{nombre}.csv", index=False)
        print(
            f"{nombre}.csv · {len(matriz):,} filas · {int(matriz['compra'].sum()):,} positivos"
        )

    esquema = {
        "features": features,
        "cols_cat": cols_cat,
        "hiperparametros": metadatos["hiperparametros"],
        "max_iter": 150,
        "semilla": metadatos["random_state"],
        "pop_alpha": metadatos["pop_alpha"],
        "eps_pop": metadatos["eps_pop"],
        "cortes_entrenamiento": [
            str(c) for c in sorted(entrenamiento["corte"].unique())
        ],
        "uso": (
            "puntaje = decision_function(X[features]) + pop_alpha*log(n_compradores + eps_pop). "
            "La API ordena, excluye comprados y filtra recomendables."
        ),
    }
    (RAIZ / "esquema.json").write_text(
        json.dumps(esquema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"esquema.json · {len(features)} features · categóricas {cols_cat}")
    print("Sin usuario_id, sku ni corte: solo features y etiqueta.")


if __name__ == "__main__":
    main()

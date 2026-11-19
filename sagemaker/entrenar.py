"""Entrena dentro de SageMaker el mismo pipeline boosting del notebook 03 (celda 25).

Replica pipeline_boosting y el ajuste final con entrenamiento + validación. La validación
también se usó para elegir el modelo, así que sus métricas son diagnóstico, no prueba
independiente.
"""

import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

RAIZ = Path(__file__).resolve().parent
ESQUEMA = json.loads((RAIZ / "esquema.json").read_text(encoding="utf-8"))
FEATURES = ESQUEMA["features"]


def leer(carpeta: str, nombre: str) -> pd.DataFrame:
    df = pd.read_csv(Path(carpeta) / nombre)
    faltan = set(FEATURES + ["compra"]) - set(df.columns)
    if faltan:
        raise ValueError(f"{nombre}: faltan columnas {sorted(faltan)}")
    return df


def construir() -> Pipeline:
    pre = ColumnTransformer(
        [
            (
                "cat",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value", unknown_value=-1
                ),
                ESQUEMA["cols_cat"],
            )
        ],
        remainder="passthrough",
    )
    clf = HistGradientBoostingClassifier(
        **ESQUEMA["hiperparametros"],
        max_iter=ESQUEMA["max_iter"],
        categorical_features=list(range(len(ESQUEMA["cols_cat"]))),
        random_state=ESQUEMA["semilla"],
    )
    return Pipeline([("pre", pre), ("clf", clf)])


def main() -> None:
    entrenamiento = leer(os.environ["SM_CHANNEL_TRAIN"], "train.csv")
    validacion = leer(os.environ["SM_CHANNEL_VALIDATION"], "validation.csv")
    modelo_dir = Path(os.environ["SM_MODEL_DIR"])
    modelo_dir.mkdir(parents=True, exist_ok=True)

    todo = pd.concat([entrenamiento, validacion], ignore_index=True)
    print(f"Ajuste final con {len(todo):,} filas, igual que la celda 25 del notebook")
    modelo = construir().fit(todo[FEATURES], todo["compra"])

    pares = modelo.decision_function(validacion[FEATURES])
    metricas = {
        "auc_pares_validacion": float(
            roc_auc_score(validacion["compra"], pares)
        ),
        "ap_pares_validacion": float(
            average_precision_score(validacion["compra"], pares)
        ),
    }
    print(
        "Diagnóstico en validación (usada también en el ajuste, no es prueba "
        f"independiente): {metricas}"
    )

    joblib.dump(modelo, modelo_dir / "model.joblib")
    metadatos = {
        **ESQUEMA,
        "metricas": metricas,
        "filas_ajuste": int(len(todo)),
        "positivos_ajuste": int(todo["compra"].sum()),
        "versiones": {
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }
    (modelo_dir / "metadatos.json").write_text(
        json.dumps(metadatos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Modelo y metadatos guardados en {modelo_dir}")


if __name__ == "__main__":
    main()

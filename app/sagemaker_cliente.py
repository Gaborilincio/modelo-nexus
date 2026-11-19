"""Cliente del endpoint de SageMaker: envía features y devuelve puntajes.

Sin credenciales en código ni en .env: en EC2 boto3 usa el perfil de instancia (LabRole).
No hay inferencia local silenciosa: si el endpoint falla se lanza ErrorRemoto y la API
responde con el plan B de más vendidos.
"""

from __future__ import annotations

import json
import logging
import os

import boto3
import numpy as np
import pandas as pd
from botocore.config import Config

log = logging.getLogger("nexus.sagemaker")


class ErrorRemoto(RuntimeError):
    """El endpoint no respondió o devolvió algo distinto del contrato."""


class PuntuadorSageMaker:
    def __init__(
        self,
        endpoint: str,
        version_modelo: str | None = None,
        region: str | None = None,
        cliente=None,
        timeout: float | None = None,
    ):
        self.endpoint = endpoint
        self.version_modelo = version_modelo or endpoint
        self.region = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self.timeout = timeout or float(os.environ.get("SAGEMAKER_TIMEOUT", "10"))
        self.cliente = cliente or boto3.client(
            "sagemaker-runtime",
            region_name=self.region,
            config=Config(
                connect_timeout=3,
                read_timeout=self.timeout,
                # Solo reintenta errores reintentables (throttling, 5xx); los de entrada no.
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        self.features: list[str] | None = None
        self.cols_cat: set[str] = set()

    @classmethod
    def desde_entorno(cls) -> "PuntuadorSageMaker | None":
        endpoint = os.environ.get("SAGEMAKER_ENDPOINT")
        if not endpoint:
            return None
        version = os.environ.get("SAGEMAKER_MODEL_VERSION")
        if not version:
            raise ValueError("Falta SAGEMAKER_MODEL_VERSION para el endpoint remoto")
        return cls(endpoint, version_modelo=version)

    def configurar(self, features, cols_cat) -> None:
        self.features = list(features)
        self.cols_cat = set(cols_cat)

    def puntuar(self, X: pd.DataFrame) -> np.ndarray:
        if self.features is None:
            raise ErrorRemoto("Las features del esquema no están configuradas")
        if list(X.columns) != self.features:
            raise ErrorRemoto("Las columnas no coinciden con el esquema del modelo")

        filas = [
            [
                str(v) if c in self.cols_cat else float(v)
                for c, v in zip(self.features, fila)
            ]
            for fila in X.itertuples(index=False, name=None)
        ]
        cuerpo = json.dumps({"filas": filas}, allow_nan=False).encode()
        try:
            respuesta = self.cliente.invoke_endpoint(
                EndpointName=self.endpoint,
                ContentType="application/json",
                Accept="application/json",
                Body=cuerpo,
            )
            datos = json.loads(respuesta["Body"].read())
            puntajes = np.asarray(datos["puntajes"], dtype=float)
        except Exception as e:  # cualquier fallo remoto termina en el plan B
            raise ErrorRemoto(f"{type(e).__name__}: {e}") from e

        if puntajes.shape != (len(filas),) or not np.isfinite(puntajes).all():
            raise ErrorRemoto(
                f"Respuesta inválida: {puntajes.shape} para {len(filas)} filas"
            )
        return puntajes

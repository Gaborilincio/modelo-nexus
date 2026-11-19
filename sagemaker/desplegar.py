"""Empaqueta el artefacto con el handler, crea el endpoint Nexus y lo deja InService.

Serverless: 3072 MB y concurrencia máxima 1 (el laboratorio deniega endpoints de tiempo real).
El endpoint se llama nexus-reco y se actualiza si ya existe.
"""

import json
import os
import shutil
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

RAIZ = Path(__file__).resolve().parent
ESTADO = RAIZ / "estado"
# La imagen oficial no puede instalar el handler sin permisos; se usa la derivada con root.
IMAGEN = os.environ.get(
    "NEXUS_IMAGEN",
    "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.9-0-cpu-py3",
)
MEMORIA = int(os.environ.get("NEXUS_MEMORIA", "2048"))
HANDLERS = os.environ.get("NEXUS_HANDLERS", "2")
# Con 1 instancia caliente no aparece una segunda en frío a mitad del tráfico.
CONCURRENCIA = int(os.environ.get("NEXUS_CONCURRENCIA", "2"))
ENDPOINT = "nexus-reco"


def esperar(sm, nombre: str) -> None:
    inicio = time.time()
    while True:
        d = sm.describe_endpoint(EndpointName=nombre)
        print(f"{int(time.time() - inicio):5d} s · {d['EndpointStatus']}", flush=True)
        if d["EndpointStatus"] in ("InService", "Failed"):
            break
        time.sleep(20)
    if d["EndpointStatus"] != "InService":
        raise SystemExit(f"Endpoint en {d['EndpointStatus']}: {d.get('FailureReason')}")


def main() -> None:
    entrenamiento = json.loads((ESTADO / "entrenamiento.json").read_text())
    region, bucket = entrenamiento["region"], entrenamiento["bucket"]
    marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    sesion = boto3.session.Session(region_name=region)
    cuenta = sesion.client("sts").get_caller_identity()["Account"]
    s3 = sesion.client("s3")
    sm = sesion.client("sagemaker")
    rol = f"arn:aws:iam::{cuenta}:role/LabRole"

    resto = entrenamiento["artefacto"].split(f"s3://{bucket}/", 1)[1]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        s3.download_file(bucket, resto, str(tmp / "model.tar.gz"))
        with tarfile.open(tmp / "model.tar.gz") as t:
            t.extractall(tmp / "modelo")

        codigo = tmp / "modelo" / "code"
        codigo.mkdir(exist_ok=True)
        for archivo in ("inferencia.py", "esquema.json"):
            shutil.copy(RAIZ / archivo, codigo / archivo)

        paquete = tmp / "nexus-modelo.tar.gz"
        with tarfile.open(paquete, "w:gz") as t:
            for hijo in sorted((tmp / "modelo").iterdir()):
                t.add(hijo, arcname=hijo.name)
        shutil.copy(tmp / "modelo" / "model.joblib", ESTADO / "model.joblib")
        shutil.copy(tmp / "modelo" / "metadatos.json", ESTADO / "metadatos.json")
        clave = f"nexus/modelos/nexus-modelo-{marca}.tar.gz"
        s3.upload_file(str(paquete), bucket, clave)
        print(f"Modelo empaquetado: s3://{bucket}/{clave}")

    modelo = f"nexus-reco-{marca}"
    sm.create_model(
        ModelName=modelo,
        PrimaryContainer={
            "Image": IMAGEN,
            "ModelDataUrl": f"s3://{bucket}/{clave}",
            "Environment": {
                "SAGEMAKER_PROGRAM": "inferencia.py",
                "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
                "SAGEMAKER_REGION": region,
                # Un handler por instancia: con 1 concurrencia no compite por memoria.
                "SAGEMAKER_MODEL_SERVER_WORKERS": HANDLERS,
            },
        },
        ExecutionRoleArn=rol,
    )
    sm.create_endpoint_config(
        EndpointConfigName=modelo,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": modelo,
                "ServerlessConfig": {
                    "MemorySizeInMB": MEMORIA,
                    "MaxConcurrency": CONCURRENCIA,
                },
            }
        ],
    )
    tipo_texto = f"serverless · {MEMORIA} MB · concurrencia {CONCURRENCIA} · {HANDLERS} handlers"
    print(f"Modelo y configuración {modelo} creados · {tipo_texto}")

    try:
        sm.describe_endpoint(EndpointName=ENDPOINT)
        sm.update_endpoint(
            EndpointName=ENDPOINT, EndpointConfigName=modelo
        )
        print(f"Actualizando endpoint {ENDPOINT}")
    except ClientError:
        sm.create_endpoint(EndpointName=ENDPOINT, EndpointConfigName=modelo)
        print(f"Creando endpoint {ENDPOINT}")
    esperar(sm, ENDPOINT)

    (ESTADO / "endpoint.json").write_text(
        json.dumps(
            {
                "endpoint": ENDPOINT,
                "modelo": modelo,
                "config": modelo,
                "region": region,
                "tipo": tipo_texto,
                "imagen": IMAGEN,
                "artefacto": f"s3://{bucket}/{clave}",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Endpoint {ENDPOINT} InService con {modelo}. Siguiente: python sagemaker/probar.py")


if __name__ == "__main__":
    main()

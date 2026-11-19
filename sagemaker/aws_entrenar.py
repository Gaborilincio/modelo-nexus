"""Sube datos y código, lanza el Training Job del pipeline real y guarda el estado.

Usa LabRole desde el perfil de instancia; no se crean usuarios ni claves.
"""

import argparse
import json
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "salida"
ESTADO = RAIZ / "estado"
IMAGEN = (
    "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.9-0-cpu-py3"
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default=None)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--instancia", default="ml.m5.large")
    a = p.parse_args()

    sesion = boto3.session.Session(region_name=a.region)
    cuenta = sesion.client("sts").get_caller_identity()["Account"]
    bucket = a.bucket or f"nexus-sagemaker-{cuenta}"
    s3 = sesion.client("s3")
    marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    trabajo = f"nexus-reco-{marca}"

    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)  # us-east-1 no lleva LocationConstraint

    for canal, archivo in (("train", "train.csv"), ("validation", "validation.csv")):
        s3.upload_file(
            str(SALIDA / archivo), bucket, f"nexus/datos/{canal}/{archivo}"
        )
        print(f"Subido s3://{bucket}/nexus/datos/{canal}/{archivo}")

    paquete = ESTADO / "sourcedir.tar.gz"
    ESTADO.mkdir(exist_ok=True)
    with tarfile.open(paquete, "w:gz") as t:
        t.add(RAIZ / "entrenar.py", arcname="entrenar.py")
        t.add(RAIZ / "esquema.json", arcname="esquema.json")
    s3.upload_file(str(paquete), bucket, "nexus/codigo/sourcedir.tar.gz")
    print(f"Subido s3://{bucket}/nexus/codigo/sourcedir.tar.gz")

    sm = sesion.client("sagemaker")
    sm.create_training_job(
        TrainingJobName=trabajo,
        AlgorithmSpecification={
            "TrainingImage": IMAGEN,
            "TrainingInputMode": "File",
        },
        RoleArn=f"arn:aws:iam::{cuenta}:role/LabRole",
        InputDataConfig=[
            {
                "ChannelName": canal,
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{bucket}/nexus/datos/{canal}",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
                "ContentType": "text/csv",
                "InputMode": "File",
            }
            for canal in ("train", "validation")
        ],
        OutputDataConfig={"S3OutputPath": f"s3://{bucket}/nexus/modelos/"},
        ResourceConfig={
            "InstanceType": a.instancia,
            "InstanceCount": 1,
            "VolumeSizeInGB": 20,
        },
        StoppingCondition={"MaxRuntimeInSeconds": 1800},
        HyperParameters={
            "sagemaker_program": "entrenar.py",
            "sagemaker_submit_directory": f"s3://{bucket}/nexus/codigo/sourcedir.tar.gz",
            "sagemaker_region": a.region,
            "sagemaker_container_log_level": "20",
        },
    )
    print(f"Training Job {trabajo} creado en {a.instancia}. Se revisa cada 20 s.")

    inicio = time.time()
    while True:
        d = sm.describe_training_job(TrainingJobName=trabajo)
        estado, secundario = d["TrainingJobStatus"], d.get("SecondaryStatus", "")
        print(f"{int(time.time() - inicio):5d} s · {estado} · {secundario}", flush=True)
        if estado in ("Completed", "Failed", "Stopped"):
            break
        time.sleep(20)

    if estado != "Completed":
        raise SystemExit(f"El trabajo terminó en {estado}: {d.get('FailureReason')}")

    artefacto = d["ModelArtifacts"]["S3ModelArtifacts"]
    print(f"Artefacto: {artefacto}")
    ESTADO.mkdir(exist_ok=True)
    (ESTADO / "entrenamiento.json").write_text(
        json.dumps(
            {
                "trabajo": trabajo,
                "bucket": bucket,
                "region": a.region,
                "instancia": a.instancia,
                "imagen": IMAGEN,
                "artefacto": artefacto,
                "segundos_entrenamiento": d["TrainingTimeInSeconds"],
                "segundos_totales": d["BillableTimeInSeconds"],
                "creado": str(d["CreationTime"]),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Siguiente: python sagemaker/desplegar.py")


if __name__ == "__main__":
    main()

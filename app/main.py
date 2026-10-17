"""API de predicción de Nexus: recomienda productos a un usuario."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.recomendador import Recomendador

log = logging.getLogger("nexus.api")

K_MIN, K_MAX = 4, 8  # RF1: entre 4 y 8 recomendaciones por slot
estado: dict = {"recomendador": None, "error": None}


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    try:
        estado["recomendador"] = Recomendador()
    except Exception as e:  # sin modelo la API arranca igual y /health lo informa
        estado["error"] = f"{type(e).__name__}: {e}"
        log.exception("No se pudo cargar el recomendador")
    yield


app = FastAPI(
    title="Nexus · API de recomendación", version="1.0.0", lifespan=ciclo_de_vida
)


class PeticionPrediccion(BaseModel):
    usuario_id: str = Field(..., min_length=1, examples=["U100001"])
    k: int = Field(
        8, ge=K_MIN, le=K_MAX, description="Cantidad de recomendaciones (4 a 8)"
    )


class Recomendacion(BaseModel):
    puesto: int
    sku: str
    categoria: str | None = None
    marca: str | None = None
    precio_lista: float | None = None
    puntaje: float | None = None


class RespuestaPrediccion(BaseModel):
    usuario_id: str
    origen: str  # "modelo" o "fallback"
    motivo: str | None  # por qué se usó el plan B (None si origen == "modelo")
    recomendaciones: list[Recomendacion]


@app.get("/")
def inicio():
    return {
        "servicio": "Nexus API de recomendación",
        "estado": "activo",
        "documentacion": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    r = estado["recomendador"]
    if r is None:
        raise HTTPException(
            status_code=503, detail={"estado": "sin_modelo", "error": estado["error"]}
        )
    return {"estado": "ok", **r.resumen()}


@app.post("/predict", response_model=RespuestaPrediccion)
def predict(p: PeticionPrediccion):
    r = estado["recomendador"]
    if r is None:
        raise HTTPException(status_code=503, detail="El modelo no está disponible")
    uid = p.usuario_id.strip()

    if not r.usuario_consentido(uid):
        # Sin consentimiento (o usuario desconocido) no se perfila: solo se entrega el listado general.
        return RespuestaPrediccion(
            usuario_id=uid,
            origen="fallback",
            motivo="usuario sin consentimiento o desconocido: no se personaliza",
            recomendaciones=r.recomendar_fallback(p.k),
        )
    try:
        recs = r.recomendar(uid, p.k)
        if recs:
            return RespuestaPrediccion(
                usuario_id=uid, origen="modelo", motivo=None, recomendaciones=recs
            )
        motivo = "no quedan productos recomendables que el usuario no haya comprado"
    except KeyError:
        motivo = "usuario sin historial de compras"
    except Exception:
        log.exception("Falló la predicción para %s", uid)
        motivo = "error al calcular la predicción"
    return RespuestaPrediccion(
        usuario_id=uid,
        origen="fallback",
        motivo=motivo,
        recomendaciones=r.recomendar_fallback(
            p.k, excluir=r.estado["comprados"].get(uid)
        ),
    )

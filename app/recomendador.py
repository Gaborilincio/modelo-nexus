"""Carga del modelo y generación de recomendaciones para un usuario."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from app import features as F

log = logging.getLogger("nexus.recomendador")

RAIZ = Path(__file__).resolve().parent.parent
DIR_PROCESADOS = Path(os.environ.get("DIR_PROCESADOS", RAIZ / "datos" / "procesados"))
DIR_MODELOS = Path(os.environ.get("DIR_MODELOS", RAIZ / "datos" / "modelos"))


class Recomendador:
    """Mantiene en memoria el modelo y el estado de usuarios/productos al corte de servicio."""

    def __init__(
        self,
        dir_procesados: Path = DIR_PROCESADOS,
        dir_modelos: Path = DIR_MODELOS,
        corte=None,
    ):
        self.modelo = joblib.load(dir_modelos / "modelo_recomendador.joblib")
        self.meta_modelo = joblib.load(dir_modelos / "modelo_metadatos.joblib")
        self.fallback = joblib.load(
            dir_modelos / "fallback_mas_vendidos.joblib"
        )  # Series: sku -> unidades
        self.meta = joblib.load(dir_procesados / "metadatos.pkl")

        v_modelo = self.meta_modelo.get("versiones", {}).get("scikit-learn")
        self.version_sklearn_distinta = bool(
            v_modelo and v_modelo != sklearn.__version__
        )
        if self.version_sklearn_distinta:
            log.warning(
                "El modelo se entrenó con scikit-learn %s y aquí hay %s; instala la misma versión.",
                v_modelo,
                sklearn.__version__,
            )

        self.productos, self.usuarios, trx, clk = F.cargar_tablas(dir_procesados)
        # Corte de servicio: "hoy" = fin de los datos (exclusivo), igual que el último corte de entrenamiento + 90 días.
        self.corte = (
            pd.Timestamp(corte) if corte is not None else self.meta["fin_datos"]
        )
        self.estado = F.construir_estado(
            self.productos, self.usuarios, trx, clk, self.corte, self.meta
        )
        self.med_precio_cat, self.med_precio_global = F.medianas_precio(self.productos)
        self.features = self.meta_modelo["features"]
        self.ficha = self.productos.set_index(self.productos["sku"].astype(str))[
            ["categoria", "marca", "precio_lista"]
        ]

    # ------------------------------------------------------------------ consultas
    def usuario_consentido(self, usuario_id: str) -> bool:
        return bool((self.usuarios["usuario_id"] == usuario_id).any())

    def tiene_historial(self, usuario_id: str) -> bool:
        return usuario_id in self.estado["comprados"]

    def _item(self, sku: str, puesto: int, puntaje=None) -> dict:
        f = self.ficha.loc[sku] if sku in self.ficha.index else None
        return {
            "puesto": puesto,
            "sku": sku,
            "categoria": None if f is None else f["categoria"],
            "marca": None if f is None else f["marca"],
            "precio_lista": None
            if f is None or pd.isna(f["precio_lista"])
            else float(f["precio_lista"]),
            "puntaje": None if puntaje is None else round(float(puntaje), 4),
        }

    def recomendar_fallback(
        self, k: int, excluir: set[str] | None = None
    ) -> list[dict]:
        excluir = excluir or set()
        skus = [str(s) for s in self.fallback.index if str(s) not in excluir][:k]
        return [self._item(s, i + 1) for i, s in enumerate(skus)]

    def recomendar(self, usuario_id: str, k: int) -> list[dict]:
        """Top-k para un usuario con consentimiento e historial. Lanza KeyError si no se le puede perfilar."""
        E = self.estado
        if not self.usuario_consentido(usuario_id) or not self.tiene_historial(
            usuario_id
        ):
            raise KeyError(usuario_id)

        fp = E["fp"]
        cand = fp[fp["recomendable"] & fp["existe_en_ventana"]]["sku"].astype(str)
        cand = cand[
            ~cand.isin(E["comprados"][usuario_id])
        ]  # no se recomienda lo ya comprado
        if cand.empty:
            return []

        # Se filtran las tablas al usuario: el resultado es idéntico y la consulta es más liviana.
        Eu = {
            **E,
            "fu": E["fu"][E["fu"]["usuario_id"] == usuario_id],
            "it": E["it"][E["it"]["usuario_id"] == usuario_id],
            "u_cat": E["u_cat"][E["u_cat"]["usuario_id"] == usuario_id],
            "u_marca": E["u_marca"][E["u_marca"]["usuario_id"] == usuario_id],
            "ult_cat": E["ult_cat"][E["ult_cat"]["usuario_id"] == usuario_id],
        }
        Eu["it"] = Eu["it"].assign(sku=Eu["it"]["sku"].astype(str))
        Eu["fp"] = fp.assign(sku=fp["sku"].astype(str))

        pares = pd.DataFrame({"usuario_id": usuario_id, "sku": cand.to_numpy()})
        X = F.ensamblar(pares, Eu, self.meta)
        X = F.tratar_nulos(
            X,
            self.med_precio_cat,
            self.med_precio_global,
            self.meta["medianas_antiguedad"],
        )

        puntaje = self.modelo.decision_function(X[self.features])
        if self.meta_modelo["usa_prior_popularidad"]:
            puntaje = puntaje + self.meta_modelo["pop_alpha"] * np.log(
                X["n_compradores"].to_numpy(float) + self.meta_modelo["eps_pop"]
            )
        orden = np.argsort(-puntaje, kind="stable")[:k]
        return [
            self._item(str(X["sku"].iloc[i]), n + 1, puntaje[i])
            for n, i in enumerate(orden)
        ]

    # ------------------------------------------------------------------ estado
    def resumen(self) -> dict:
        return {
            "modelo": self.meta_modelo["familia"],
            "usa_prior_popularidad": self.meta_modelo["usa_prior_popularidad"],
            "corte_servicio": str(self.corte.date()),
            "usuarios_con_historial": len(self.estado["comprados"]),
            "skus_recomendables": int(self.estado["fp"]["recomendable"].sum()),
            "skus_fallback": len(self.fallback),
            "sklearn_distinta_a_entrenamiento": self.version_sklearn_distinta,
        }

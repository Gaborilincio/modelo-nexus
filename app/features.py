"""Construcción de variables para el servicio de predicción.

Reproduce la lógica de ``notebooks/02_limpieza.ipynb`` (funciones ``estado_corte``,
``ensamblar`` y ``tratar_nulos``). Si se cambia una variable en el notebook, hay que
cambiarla aquí también; ``tests/test_paridad.py`` comprueba que ambas versiones
entregan los mismos valores.
"""

from __future__ import annotations

import pandas as pd

EPS_POP = 1e-3  # el mismo +1e-3 que usa el notebook 03 en log(n_compradores + eps)


def cargar_tablas(dir_procesados):
    """Lee los CSV limpios generados por el notebook 02, con las fechas ya parseadas."""
    d = dir_procesados
    productos = pd.read_csv(d / "productos_limpio.csv", parse_dates=["fecha_alta"])
    usuarios = pd.read_csv(d / "usuarios_limpio.csv", parse_dates=["fecha_registro"])
    trx = pd.read_csv(d / "transacciones_limpio.csv", parse_dates=["fecha_dt"])
    clk = pd.read_csv(d / "clickstream_limpio.csv", parse_dates=["timestamp_dt"])
    for df in (usuarios, trx, clk):
        df["usuario_id"] = df["usuario_id"].astype(str)
    for df in (productos, trx, clk):
        df["sku"] = df["sku"].astype("string")
    return productos, usuarios, trx, clk


def construir_estado(productos, usuarios, trx, clk, corte, meta):
    """Todo lo que se sabe de usuarios y productos ANTES de `corte` (sin la ventana de evaluación)."""
    horizonte = pd.Timedelta(days=meta["horizonte_dias"])
    fin = corte + horizonte
    ventanas = tuple(meta["ventanas_tendencia"])

    hist = trx[trx["fecha_dt"] < corte]
    clk = clk[(clk["timestamp_dt"] < corte) & clk["sku"].notna()]
    h = hist.merge(productos[["sku", "categoria", "marca"]], on="sku", how="left")

    # --- usuario
    fu = (
        h.groupby("usuario_id")
        .agg(
            n_pedidos=("pedido_id", "nunique"),
            unidades_totales=("cantidad", "sum"),
            categorias_distintas=("categoria", "nunique"),
            primera=("fecha_dt", "min"),
            ultima=("fecha_dt", "max"),
        )
        .reset_index()
    )
    fu["recencia_dias"] = (corte - fu["ultima"]).dt.days
    fu["frecuencia"] = (
        fu["n_pedidos"] / (corte - fu["primera"]).dt.days.clip(lower=1)
    ).round(4)
    fu = fu.merge(
        usuarios[["usuario_id", "region", "canal_captacion", "fecha_registro"]],
        on="usuario_id",
        how="left",
    )
    fu["antiguedad_registro_dias"] = (corte - fu["fecha_registro"]).dt.days.clip(
        lower=0
    )
    fu = fu.drop(columns=["primera", "ultima", "fecha_registro"])

    # --- producto
    ventas = (
        h.groupby("sku")
        .agg(
            unidades_vendidas=("cantidad", "sum"),
            n_compradores=("usuario_id", "nunique"),
        )
        .reset_index()
    )
    for dias in ventanas:
        reciente = h[h["fecha_dt"] >= corte - pd.Timedelta(days=dias)]
        ventas = ventas.merge(
            reciente.groupby("sku")["usuario_id"]
            .nunique()
            .rename(f"compradores_{dias}d")
            .reset_index(),
            on="sku",
            how="left",
        )
    fp = productos[
        [
            "sku",
            "precio_lista",
            "categoria",
            "marca",
            "fecha_alta",
            "recomendable",
            "precio_sospechoso",
        ]
    ].merge(ventas, on="sku", how="left")
    fp["unidades_vendidas"] = fp["unidades_vendidas"].fillna(0).astype(int)
    fp["n_compradores"] = fp["n_compradores"].fillna(0).astype(int)
    for dias in ventanas:
        fp[f"compradores_{dias}d"] = fp[f"compradores_{dias}d"].fillna(0).astype(int)
    c_corta, c_larga = (f"compradores_{d}d" for d in ventanas)
    fp["tendencia_30_90"] = fp[c_corta] / (fp[c_larga] + 1)
    fp["antiguedad_sku_dias"] = (corte - fp["fecha_alta"]).dt.days.clip(lower=0)
    fp["existe_en_ventana"] = fp["fecha_alta"].isna() | (fp["fecha_alta"] < fin)
    fp = fp.drop(columns=["fecha_alta"])

    # --- interacción usuario-producto (clickstream previo al corte)
    it = (
        clk.pivot_table(
            index=["usuario_id", "sku"],
            columns="tipo_evento_norm",
            values="evento_id",
            aggfunc="count",
            fill_value=0,
        )
        .reindex(columns=["vista", "clic", "agregar_carrito"], fill_value=0)
        .rename(
            columns={
                "vista": "n_vistas",
                "clic": "n_clics",
                "agregar_carrito": "n_agregados_carrito",
            }
        )
        .reset_index()
    )

    # --- afinidad y recencia por categoría / marca
    u_cat = (
        h.groupby(["usuario_id", "categoria"])["cantidad"]
        .sum()
        .rename("u_cat")
        .reset_index()
    )
    u_marca = (
        h.groupby(["usuario_id", "marca"])["cantidad"]
        .sum()
        .rename("u_marca")
        .reset_index()
    )
    ult_cat = h.groupby(["usuario_id", "categoria"])["fecha_dt"].max().reset_index()
    ult_cat["recencia_cat_dias"] = (corte - ult_cat["fecha_dt"]).dt.days
    ult_cat = ult_cat.drop(columns="fecha_dt")

    comprados = (
        h.groupby("usuario_id")["sku"].apply(lambda s: set(s.astype(str))).to_dict()
    )
    return {
        "corte": corte,
        "fin": fin,
        "fu": fu,
        "fp": fp,
        "it": it,
        "u_cat": u_cat,
        "u_marca": u_marca,
        "ult_cat": ult_cat,
        "comprados": comprados,
    }


def ensamblar(pares, E, meta):
    """Une pares (usuario, sku) con los predictores del estado del corte."""
    d = (
        pares.merge(E["fu"], on="usuario_id", how="left")
        .merge(E["fp"], on="sku", how="left")
        .merge(E["it"], on=["usuario_id", "sku"], how="left")
        .merge(E["u_cat"], on=["usuario_id", "categoria"], how="left")
        .merge(E["u_marca"], on=["usuario_id", "marca"], how="left")
        .merge(E["ult_cat"], on=["usuario_id", "categoria"], how="left")
    )
    for c in ["n_vistas", "n_clics", "n_agregados_carrito"]:
        d[c] = d[c].fillna(0).astype(int)
    d["afinidad_categoria"] = d["u_cat"].fillna(0) / d["unidades_totales"]
    d["afinidad_marca"] = d["u_marca"].fillna(0) / d["unidades_totales"]
    d["recencia_cat_dias"] = d["recencia_cat_dias"].fillna(meta["recencia_sin_compra"])
    d["regla_pop_categoria"] = d["n_compradores"] * (
        d["afinidad_categoria"] + meta["suavizado_afinidad"]
    )
    d["senal_implicita"] = (
        d["n_vistas"] + 2 * d["n_clics"] + 3 * d["n_agregados_carrito"]
    )
    return d.drop(columns=["u_cat", "u_marca"])


def medianas_precio(productos):
    """Medianas de precio por categoría y global, para imputar precios inválidos."""
    ok = productos[productos["precio_lista"] > 0]
    return ok.groupby("categoria")["precio_lista"].median(), ok["precio_lista"].median()


def tratar_nulos(d, med_precio_cat, med_precio_global, medianas_antiguedad):
    d = d.copy()
    invalido = d["precio_lista"].isna() | (d["precio_lista"] <= 0)
    d["precio_lista"] = (
        d["precio_lista"]
        .mask(invalido)
        .fillna(d["categoria"].map(med_precio_cat))
        .fillna(med_precio_global)
    )
    for col in ["antiguedad_sku_dias", "antiguedad_registro_dias"]:
        d[col] = d[col].fillna(medianas_antiguedad[col])
    for col in ["region", "canal_captacion", "marca", "categoria"]:
        d[col] = d[col].fillna("sin_dato")
    for col in ["n_vistas", "n_clics", "n_agregados_carrito"]:
        d[col] = d[col].fillna(0).astype(int)
    return d.drop(columns=["existe_en_ventana"])

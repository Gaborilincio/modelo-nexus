"""Calidad de los datos limpios y procesados que generan los notebooks (02 principalmente).

Son las mismas garantías que el notebook 02 comprueba al ejecutarse, pero aquí quedan como pruebas
automáticas: si alguien cambia el notebook o vuelve a generar los datos y algo se rompe, falla `pytest`.
Si todavía no se han ejecutado los notebooks, las pruebas se omiten.
"""

import joblib
import pandas as pd
import pytest

from app.recomendador import DIR_MODELOS, DIR_PROCESADOS

COMODINES = {"unknown", "invitado"}
ESTADOS_VALIDOS = {"pagado", "devuelto"}


def _cargar(nombre):
    ruta = DIR_PROCESADOS / nombre
    if not ruta.exists():
        pytest.skip(f"Falta {ruta} (ejecutar el notebook 02)")
    return joblib.load(ruta) if ruta.suffix == ".pkl" else pd.read_csv(ruta)


@pytest.fixture(scope="module")
def meta():
    return _cargar("metadatos.pkl")


@pytest.fixture(scope="module")
def productos():
    return _cargar("productos_limpio.csv")


@pytest.fixture(scope="module")
def usuarios():
    return _cargar("usuarios_limpio.csv")


@pytest.fixture(scope="module")
def trx(meta):
    d = _cargar("transacciones_limpio.csv")
    d["fecha_dt"] = pd.to_datetime(d["fecha_dt"])
    return d


@pytest.fixture(scope="module")
def clk():
    d = _cargar("clickstream_limpio.csv")
    d["timestamp_dt"] = pd.to_datetime(d["timestamp_dt"])
    return d


@pytest.fixture(scope="module")
def entrenamiento():
    return _cargar("entrenamiento.pkl")


@pytest.fixture(scope="module")
def validacion():
    return _cargar("validacion.pkl")


# ------------------------------------------------------------------ archivos limpios
def test_productos_sin_duplicados_y_recomendable_coherente(productos, meta):
    assert not productos["sku"].duplicated().any(), "hay SKU repetidos en el catálogo"
    rec = productos[productos["recomendable"]]
    assert rec["activo"].all(), "hay SKU recomendables que están inactivos"
    assert (rec["precio_lista"] > 0).all(), "hay SKU recomendables con precio 0 o nulo"
    assert (rec["stock"] >= meta["stock_minimo"]).all(), (
        "hay SKU recomendables con stock bajo el mínimo"
    )


def test_usuarios_solo_con_consentimiento(usuarios):
    assert not usuarios["usuario_id"].duplicated().any(), "hay usuarios repetidos"
    assert usuarios["consentimiento"].all(), "hay usuarios sin consentimiento"
    assert not set(usuarios["usuario_id"].astype(str).str.lower()) & COMODINES, (
        "hay cuentas comodín"
    )


def test_transacciones_limpias(trx, usuarios, productos, meta):
    assert set(trx["usuario_id"].astype(str)) <= set(
        usuarios["usuario_id"].astype(str)
    ), "hay compras de usuarios sin consentimiento o desconocidos"
    assert set(trx["sku"].astype(str)) <= set(productos["sku"].astype(str)), (
        "hay compras de SKU fuera del catálogo"
    )
    assert set(trx["estado_norm"]) <= ESTADOS_VALIDOS, (
        "hay estados de compra no contemplados"
    )
    assert (trx["cantidad"] > 0).all(), "hay cantidades no positivas"
    assert (trx["monto"] >= 0).all(), "hay montos negativos"
    assert (
        trx["fecha_dt"].notna().all() and trx["fecha_dt"].max() < meta["fin_datos"]
    ), "hay compras con fecha nula o posterior al fin de los datos"
    assert not trx.duplicated(["pedido_id", "linea"]).any(), (
        "hay líneas de pedido repetidas"
    )


def test_clickstream_limpio(clk, usuarios, meta):
    assert set(clk["usuario_id"].astype(str)) <= set(
        usuarios["usuario_id"].astype(str)
    ), "hay eventos de usuarios sin consentimiento o anónimos"
    assert clk["timestamp_dt"].max() < meta["fin_datos"], (
        "hay eventos posteriores al fin de los datos"
    )
    assert not clk["evento_id"].duplicated().any(), "hay eventos repetidos"


# ------------------------------------------------------------------ conjuntos de entrenamiento y validación
def test_sin_nulos_en_predictores(entrenamiento, validacion, meta):
    for nombre, d in (("entrenamiento", entrenamiento), ("validacion", validacion)):
        assert set(meta["features"]) <= set(d.columns), f"faltan variables en {nombre}"
        assert d[meta["features"]].isna().sum().sum() == 0, (
            f"hay nulos en los predictores de {nombre}"
        )


def test_etiquetas_y_pares(entrenamiento, validacion):
    for nombre, d in (("entrenamiento", entrenamiento), ("validacion", validacion)):
        assert set(d["compra"].unique()) <= {0, 1}, (
            f"`compra` no es binaria en {nombre}"
        )
        assert (d["compra"] == 1).any() and (d["compra"] == 0).any(), (
            f"{nombre} no tiene positivos y negativos"
        )
        assert not d.duplicated(["corte", "usuario_id", "sku"]).any(), (
            f"pares repetidos en {nombre}"
        )


def test_usuarios_del_dataset_con_consentimiento(entrenamiento, validacion, usuarios):
    consentidos = set(usuarios["usuario_id"].astype(str))
    for d in (entrenamiento, validacion):
        assert set(d["usuario_id"].astype(str)) <= consentidos
        assert not set(d["usuario_id"].astype(str).str.lower()) & COMODINES


def test_cortes_en_orden_y_contiguos(entrenamiento, validacion, meta):
    cortes = sorted(meta["cortes"])
    paso = pd.Timedelta(days=meta["horizonte_dias"])
    assert all(b - a == paso for a, b in zip(cortes[:-1], cortes[1:])), (
        "las ventanas no son contiguas"
    )
    assert set(entrenamiento["corte"].unique()) == set(cortes[:-1])
    assert (
        set(validacion["corte"].unique()) == {meta["corte_validacion"]} == {cortes[-1]}
    )
    assert entrenamiento["corte"].max() < validacion["corte"].min(), (
        "el entrenamiento no es anterior a la validación"
    )
    assert cortes[-1] + paso <= meta["fin_datos"], (
        "la ventana de validación pasa del fin de los datos"
    )


def test_sin_fuga_entre_entrenamiento_y_validacion(entrenamiento, validacion):
    comprados_tr = entrenamiento[entrenamiento["compra"] == 1]
    pares_tr = set(
        zip(comprados_tr["usuario_id"].astype(str), comprados_tr["sku"].astype(str))
    )
    pares_va = set(
        zip(validacion["usuario_id"].astype(str), validacion["sku"].astype(str))
    )
    assert not pares_tr & pares_va, (
        "un par comprado en entrenamiento reaparece en validación (se recomendaría lo ya comprado)"
    )


# ------------------------------------------------------------------ rankings y listas auxiliares
@pytest.mark.parametrize(
    "archivo,clave_corte",
    [
        ("ranking_validacion.pkl", "corte_validacion"),
        ("ranking_seleccion.pkl", "corte_seleccion"),
    ],
)
def test_rankings(archivo, clave_corte, meta, usuarios):
    rk = _cargar(archivo)
    assert set(rk["corte"].unique()) == {meta[clave_corte]}, (
        f"{archivo} mezcla cortes o usa uno equivocado"
    )
    assert (rk["compra"] == 1).any(), f"{archivo} no tiene compras reales"
    assert not rk.duplicated(["usuario_id", "sku"]).any(), (
        f"pares repetidos en {archivo}"
    )
    assert rk[meta["features"]].isna().sum().sum() == 0, (
        f"hay nulos en los predictores de {archivo}"
    )
    assert set(rk["usuario_id"].astype(str)) <= set(usuarios["usuario_id"].astype(str))


def test_sku_recomendables_coincide_con_catalogo(productos):
    lista = set(map(str, _cargar("sku_recomendables.pkl")))
    esperado = set(productos.loc[productos["recomendable"], "sku"].astype(str))
    assert lista == esperado, (
        "sku_recomendables.pkl no coincide con los SKU recomendables del catálogo"
    )


# ------------------------------------------------------------------ coherencia datos <-> modelo
def test_variables_del_modelo_coinciden_con_las_de_los_datos(meta):
    ruta = DIR_MODELOS / "modelo_metadatos.joblib"
    if not ruta.exists():
        pytest.skip(f"Falta {ruta} (ejecutar el notebook 03)")
    assert list(joblib.load(ruta)["features"]) == list(meta["features"]), (
        "el modelo se entrenó con otras variables que las de los datos procesados actuales: hay que reentrenar"
    )

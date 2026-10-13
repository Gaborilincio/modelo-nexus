def test_health(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_predict_usuario_con_historial(cliente, recomendador):
    uid = next(iter(recomendador.estado["comprados"]))
    r = cliente.post("/predict", json={"usuario_id": uid, "k": 6})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["origen"] == "modelo" and cuerpo["motivo"] is None
    skus = [x["sku"] for x in cuerpo["recomendaciones"]]
    assert len(skus) == 6 and len(set(skus)) == 6
    assert [x["puesto"] for x in cuerpo["recomendaciones"]] == list(range(1, 7))
    puntajes = [x["puntaje"] for x in cuerpo["recomendaciones"]]
    assert puntajes == sorted(puntajes, reverse=True)


def test_no_recomienda_lo_ya_comprado_ni_no_recomendables(cliente, recomendador):
    E = recomendador.estado
    recomendables = set(E["fp"].loc[E["fp"]["recomendable"], "sku"].astype(str))
    for uid in list(E["comprados"])[:25]:
        skus = {
            x["sku"]
            for x in cliente.post("/predict", json={"usuario_id": uid, "k": 8}).json()[
                "recomendaciones"
            ]
        }
        assert not skus & E["comprados"][uid]
        assert skus <= recomendables


def test_usuario_desconocido_usa_fallback(cliente):
    r = cliente.post("/predict", json={"usuario_id": "NO-EXISTE"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["origen"] == "fallback" and cuerpo["motivo"]
    assert 0 < len(cuerpo["recomendaciones"]) <= 8
    assert all(x["puntaje"] is None for x in cuerpo["recomendaciones"])


def test_validacion_de_entrada(cliente):
    assert (
        cliente.post("/predict", json={"usuario_id": "U1", "k": 3}).status_code == 422
    )
    assert (
        cliente.post("/predict", json={"usuario_id": "U1", "k": 9}).status_code == 422
    )
    assert cliente.post("/predict", json={"usuario_id": ""}).status_code == 422
    assert cliente.post("/predict", json={}).status_code == 422

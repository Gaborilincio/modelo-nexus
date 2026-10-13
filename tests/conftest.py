import pytest

from app.recomendador import DIR_MODELOS, DIR_PROCESADOS

ARCHIVOS = [
    DIR_MODELOS / "modelo_recomendador.joblib",
    DIR_MODELOS / "modelo_metadatos.joblib",
    DIR_MODELOS / "fallback_mas_vendidos.joblib",
    DIR_PROCESADOS / "metadatos.pkl",
]


@pytest.fixture(scope="session")
def hay_modelo():
    faltan = [str(a) for a in ARCHIVOS if not a.exists()]
    if faltan:
        pytest.skip(
            "Faltan archivos generados por los notebooks 02 y 03: " + ", ".join(faltan)
        )


@pytest.fixture(scope="session")
def cliente(hay_modelo):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:  
        yield c


@pytest.fixture(scope="session")
def recomendador(hay_modelo):
    from app.recomendador import Recomendador

    return Recomendador()

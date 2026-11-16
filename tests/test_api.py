"""La API de solo lectura."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from verificador.api import router  # noqa: E402

app = FastAPI()
app.include_router(router)
c = TestClient(app)


def test_factura():
    f = c.get("/factura").json()
    assert len(f["renglones"]) == 8 and f["renglones"][0]["por_pallet"] == 40


def test_resultado_por_defecto_y_con_parametros():
    r = c.get("/resultado").json()
    assert r["parametros"]["flete"] == "tonelada" and r["parametros"]["flete_valor"] == 85000
    e = c.get("/resultado", params={"flete": "expreso", "sin_flete": "7, 8", "descuentos": "$6000/pallet",
                                    "percepcion": "recupera"}).json()
    assert e["parametros"]["sin_flete"] == [7, 8] and e["parametros"]["flete_valor"] == 180000
    assert [x["flete"] for x in e["renglones"]][-2:] == [0, 0]


@pytest.mark.parametrize("params", [{"flete": "barco"}, {"descuentos": "diez"}, {"sin_flete": "99"},
                                    {"percepcion": "a veces"}, {"flete_valor": "mucho"}, {"percepcion_flete": "50"}])
def test_parametros_que_no_sirven(params):
    r = c.get("/resultado", params=params)
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)


def test_solo_lectura():
    assert c.post("/resultado").status_code == 405

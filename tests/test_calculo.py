"""El cálculo de punta a punta, con cuentas hechas a mano."""
import pytest

from verificador import EXPRESO, POR_PALLET, Config, Descuento, Factura, Renglon, calcular, demo
from verificador.reglas import BULTO, PALLET


def _factura(*renglones):
    return Factura(cabecera={}, renglones=list(renglones), iva=21, percepcion=3, jurisdiccion="Río Negro",
                   totales_proveedor={"neto": 0, "iva": 0, "percepcion": 0, "total": 0})


def _r(n, desc, adicional, cantidad, unidad, peso, lista, bonif=0):
    return Renglon(n, f"X{n}", desc, adicional, cantidad, unidad, peso, lista, bonif, cantidad * lista * (1 - bonif / 100))


def test_cemento_a_mano():
    """Lista $9.850, bonificación 10 %, $6.000 por pallet de 40, flete $85.000/t, percepción 3 % al costo."""
    f = demo.cargar()
    r = calcular(f, Config([Descuento(6000, True, PALLET)], "tonelada", 85000))["renglones"][0]
    assert r["neto"] == 8865 - 150
    assert r["flete"] == 2125                       # 85.000 × 25 kg ÷ 1.000
    assert r["percepciones"] == pytest.approx(261.45)   # 3 % de 8.715
    assert r["costo"] == pytest.approx(11101.45)
    assert r["total"] == pytest.approx(2220290.00)


def test_expreso_repartido_por_renglon():
    """El ejemplo de Timo: $12.000 entre cemento y OSB, tornillos destildados."""
    f = _factura(_r(1, "Cemento", "PALLET X 40", 10, "bolsa", 25, 1000),
                 _r(2, "OSB", "PALLET X 70", 2, "placa", 17.5, 1000),
                 _r(3, "Tornillos", "BULTO X 20", 1, "caja", 1.2, 1000))
    r = calcular(f, Config([], EXPRESO, 12000, frozenset({3}), percepcion_al_costo=False))["renglones"]
    assert [x["flete"] for x in r] == [600, 3000, 0]
    assert sum(x["flete"] * x["cantidad"] for x in r) == 12000   # se reparte todo, ni un peso más


def test_expreso_sin_renglones_avisa():
    f = _factura(_r(1, "Cemento", "", 10, "bolsa", 25, 1000))
    with pytest.raises(ValueError):
        calcular(f, Config([], EXPRESO, 12000, frozenset({1})))


def test_flete_por_pallet_y_lo_que_no_viene_en_pallet():
    f = demo.cargar()
    r = calcular(f, Config([], POR_PALLET, 45000))["renglones"]
    assert r[0]["flete"] == pytest.approx(45000 / 40)
    sin_pallet = [x for x in r if not x["por_pallet"]]
    assert {x["codigo"] for x in sin_pallet} == {"DA-20534", "DA-20610", "DA-20705"}
    assert all(x["flete"] == 0 and x["avisos"] for x in sin_pallet)


def test_descuento_por_bulto_y_por_pallet_solo_donde_corresponde():
    f = demo.cargar()
    r = calcular(f, Config([Descuento(5000, True, BULTO)], "ninguno", 0, percepcion_al_costo=False))["renglones"]
    hierro = next(x for x in r if x["codigo"] == "DA-20534")      # atado x 50
    cemento = r[0]
    assert hierro["neto"] == pytest.approx(10176.79 * 0.95 - 100)
    assert cemento["neto"] == pytest.approx(8865)                   # no viene por bulto: no aplica
    assert "No aplica" in cemento["pasos"][2]["detalle"]


def test_percepcion_que_se_recupera_no_suma():
    f = demo.cargar()
    al_costo = calcular(f, Config([], "ninguno", 0, percepcion_al_costo=True))["renglones"][0]
    recupera = calcular(f, Config([], "ninguno", 0, percepcion_al_costo=False))["renglones"][0]
    assert recupera["costo"] == 8865 and al_costo["costo"] == pytest.approx(8865 * 1.03)


def test_percepcion_del_flete():
    f = demo.cargar()
    r = calcular(f, Config([], "tonelada", 85000, percepcion_al_costo=False, percepcion_flete=2))["renglones"][0]
    assert r["percepciones"] == pytest.approx(2125 * 0.02)


def test_descuento_que_deja_negativo_avisa_en_el_renglon():
    f = demo.cargar()
    r = calcular(f, Config([Descuento(20000, True)], "ninguno", 0))["renglones"]
    tornillos = r[-1]
    assert tornillos["costo"] is None and "negativo" in tornillos["avisos"][0]


def test_los_dos_errores_del_proveedor():
    r = demo.resultado()
    malos = [x for x in r["renglones"] if not x["control"]["ok"]]
    assert [x["codigo"] for x in malos] == ["DA-20422"]
    assert malos[0]["control"]["diferencia"] == 48900
    assert "sin aplicar la bonificación del 5 %" in malos[0]["control"]["detalle"]
    pie = {x["concepto"].split()[0]: x for x in r["controles"]}
    assert "sobre el neto del proveedor" in pie["IVA"]["detalle"]
    assert "neto más el IVA" in pie["Percepción"]["detalle"]
    assert r["resumen"]["diferencia_total"] == pytest.approx(pie["Total"]["diferencia"]) and r["resumen"]["diferencia_total"] > 0


def test_se_reparte_todo_el_flete_por_tonelada():
    f = demo.cargar()
    r = calcular(f, Config([], "tonelada", 85000))
    kilos = sum(x.cantidad * x.peso_kg for x in f.renglones)
    assert r["totales"]["flete"] == pytest.approx(85000 * kilos / 1000, abs=0.05)

"""Lectura de la descripción adicional y de la cadena de descuentos."""
import pytest

from verificador.reglas import BULTO, PALLET, UNIDAD, Descuento, leer_descuentos, leer_empaque, leer_numero


@pytest.mark.parametrize("texto, esperado", [
    ("PALLET X 40 BOLSAS", (40, None)),
    ("Pallet de 70 placas", (70, None)),
    ("40 bolsas por pallet", (40, None)),
    ("ATADO X 50 BARRAS", (None, 50)),
    ("BULTO X 20 CAJAS", (None, 20)),
    ("pallet x 40 - caja x 5", (40, 5)),
    ("", (None, None)),
    ("COLOR GRIS", (None, None)),
    ("PALLET X 0", (None, None)),
])
def test_empaque_desde_la_descripcion_adicional(texto, esperado):
    assert leer_empaque(texto) == esperado


@pytest.mark.parametrize("texto, esperado", [("6.000", 6000), ("6000", 6000), ("150,50", 150.5), ("1.234,5", 1234.5), ("2.5", 2.5)])
def test_numeros_a_la_argentina(texto, esperado):
    assert leer_numero(texto) == esperado


def test_cadena_de_descuentos():
    assert leer_descuentos("10 + $6.000/pallet + $150 + $500/bulto + 2,5%") == [
        Descuento(10), Descuento(6000, True, PALLET), Descuento(150, True, UNIDAD),
        Descuento(500, True, BULTO), Descuento(2.5)]
    assert leer_descuentos("") == []


@pytest.mark.parametrize("texto", ["diez", "150", "$", "$100/camion", "0", "10 + - 5"])
def test_descuentos_que_no_se_entienden(texto):
    with pytest.raises(ValueError):
        leer_descuentos(texto)

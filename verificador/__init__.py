"""Verificador de cotizaciones.

Recalcula una factura de proveedor renglón por renglón, marca lo que no cuadra
y lleva cada artículo a su costo final: descuentos (porcentaje o fijos por
unidad, pallet o bulto), flete (por tonelada, por pallet o expreso repartido
por renglón) y percepciones que no se recuperan. Cada paso queda explicado.
"""
from .calculo import EXPRESO, MODOS_FLETE, POR_PALLET, SIN_FLETE, TONELADA, Config, Factura, Renglon, calcular
from .reglas import BULTO, PALLET, UNIDAD, Descuento, leer_descuentos, leer_empaque

__all__ = ["EXPRESO", "MODOS_FLETE", "POR_PALLET", "SIN_FLETE", "TONELADA", "Config", "Factura", "Renglon",
           "calcular", "BULTO", "PALLET", "UNIDAD", "Descuento", "leer_descuentos", "leer_empaque"]

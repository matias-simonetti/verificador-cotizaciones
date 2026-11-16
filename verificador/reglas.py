"""Cómo se leen los datos sueltos de una factura.

- Las unidades por pallet o por bulto, que en la empresa están en la
  "descripción adicional" del artículo, escritas a mano ("PALLET X 40 BOLSAS").
- La cadena de descuentos que escribe quien carga: "10 + $6000/pallet + $150".
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

UNIDAD, PALLET, BULTO = "unidad", "pallet", "bulto"
_BASES = {"u": UNIDAD, "un": UNIDAD, "unidad": UNIDAD, "pallet": PALLET, "bulto": BULTO}
_BULTOS = r"(?:ATADO|BULTO|CAJA|FARDO|PAQUETE)"


def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.upper().split())


def leer_empaque(adicional: str) -> tuple[int | None, int | None]:
    """Unidades por pallet y por bulto escritas en la descripción adicional.

    >>> leer_empaque("PALLET X 40 BOLSAS")
    (40, None)
    >>> leer_empaque("40 bolsas por pallet - atado x 5")
    (40, 5)
    """
    t = _plano(adicional)
    pallet = re.search(r"\bPALLETS?\s*(?:X|DE|POR|CON)?\s*(\d+)", t) or re.search(r"\b(\d+)\s*\w*\s*POR\s+PALLET", t)
    bulto = (re.search(rf"\b{_BULTOS}\s*(?:X|DE|POR|CON)?\s*(\d+)", t)
             or re.search(rf"\b(\d+)\s*\w*\s*POR\s+{_BULTOS}", t))
    a_numero = lambda m: int(m.group(1)) if m and int(m.group(1)) > 0 else None  # noqa: E731
    return a_numero(pallet), a_numero(bulto)


def leer_numero(texto: str) -> float:
    """Número escrito a la argentina o no: "6.000", "6000", "150,50", "1.234,5"."""
    t = texto.strip().replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    return float(t)


@dataclass(frozen=True)
class Descuento:
    valor: float
    fijo: bool = False      # False = porcentaje
    base: str = UNIDAD      # para los fijos: por unidad, por pallet o por bulto

    def __post_init__(self):
        if self.valor <= 0:
            raise ValueError("Un descuento tiene que ser mayor que cero")
        if not self.fijo and self.valor > 100:
            raise ValueError(f"Un descuento de {self.valor:g} % no tiene sentido")
        if self.base not in (UNIDAD, PALLET, BULTO):
            raise ValueError(f"No conozco la base {self.base!r}")


_PORCENTAJE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*%?$")
_FIJO = re.compile(r"^\$\s*([\d.,]+)\s*(?:/\s*([a-z]+))?$")


def leer_descuentos(texto: str) -> list[Descuento]:
    """"10 + $6000/pallet + $150" -> [10 %, $6000 por pallet, $150 por unidad]."""
    pasos = []
    for parte in (p.strip().lower() for p in (texto or "").split("+")):
        if not parte:
            continue
        m = _PORCENTAJE.match(parte)
        if m:
            pasos.append(Descuento(leer_numero(m.group(1))))
            continue
        m = _FIJO.match(parte)
        if m and re.fullmatch(r"[\d.,]+", m.group(1)):
            base = _BASES.get(m.group(2) or "u")
            if base is None:
                raise ValueError(f"En {parte!r}: después de la barra va u, pallet o bulto")
            pasos.append(Descuento(leer_numero(m.group(1)), fijo=True, base=base))
            continue
        raise ValueError(f"No entiendo el descuento {parte!r}. Ejemplos: 10, $150, $6000/pallet, $500/bulto")
    return pasos

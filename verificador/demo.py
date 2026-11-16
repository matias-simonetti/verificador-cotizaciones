"""La demo: la factura ficticia de datos/factura_demo.json y los parámetros que llegan de la web.

Todo corre con la biblioteca estándar de Python. Los parámetros llegan como texto
(así los manda un formulario) y acá se validan con mensajes para mostrar.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .calculo import EXPRESO, MODOS_FLETE, POR_PALLET, SIN_FLETE, TONELADA, Config, Factura, Renglon, calcular, num, pesos
from .reglas import PALLET, UNIDAD, Descuento, leer_descuentos, leer_numero

DATOS = Path(__file__).resolve().parent.parent / "datos" / "factura_demo.json"
MAX_TEXTO = 80
MAX_PASOS = 8


@lru_cache(maxsize=4)
def cargar(ruta: str = str(DATOS)) -> Factura:
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    imp = d["impuestos"]
    return Factura(
        cabecera=d["factura"],
        renglones=[Renglon(**r) for r in d["renglones"]],
        iva=float(imp["iva"]),
        percepcion=float(imp["percepcion_iibb"]),
        jurisdiccion=imp.get("percepcion_jurisdiccion", ""),
        totales_proveedor=d["totales_proveedor"],
        pie=d.get("pie", ""),
        fletes_sugeridos=d.get("fletes_sugeridos", {}),
    )


def _cabecera(f: Factura) -> dict:
    return {"cabecera": f.cabecera, "pie": f.pie, "fletes_sugeridos": f.fletes_sugeridos,
            "impuestos": {"iva": f.iva, "percepcion": f.percepcion, "jurisdiccion": f.jurisdiccion},
            "totales_proveedor": f.totales_proveedor}


def factura(ruta: str = str(DATOS)) -> dict:
    """La factura tal como la mandó el proveedor, para mostrarla antes de calcular."""
    f = cargar(ruta)
    return {**_cabecera(f), "renglones": [
        {"n": r.n, "codigo": r.codigo, "descripcion": r.descripcion, "adicional": r.adicional,
         "cantidad": r.cantidad, "unidad": r.unidad, "peso_kg": r.peso_kg, "precio_lista": r.precio_lista,
         "bonificacion": r.bonificacion, "importe_proveedor": r.importe_proveedor,
         "por_pallet": r.por_pallet, "por_bulto": r.por_bulto} for r in f.renglones]}


def _numero(texto: str, nombre: str, minimo: float, maximo: float) -> float:
    try:
        valor = leer_numero(texto)
    except ValueError:
        raise ValueError(f"{nombre}: {texto!r} no es un número") from None
    if not minimo <= valor <= maximo:
        raise ValueError(f"{nombre} tiene que estar entre {num(minimo)} y {num(maximo)}")
    return valor


def config(descuentos: str = "", flete: str = "", flete_valor: str = "", sin_flete: str = "",
           percepcion: str = "", percepcion_flete: str = "", ruta: str = str(DATOS)) -> Config:
    f = cargar(ruta)
    if len(descuentos or "") > MAX_TEXTO:
        raise ValueError(f"Los descuentos no pueden pasar de {MAX_TEXTO} caracteres")
    pasos = leer_descuentos(descuentos)
    if len(pasos) > MAX_PASOS:
        raise ValueError(f"Como máximo {MAX_PASOS} descuentos")
    modo = (flete or TONELADA).strip().lower()
    if modo not in MODOS_FLETE:
        raise ValueError(f"No conozco el flete {modo!r}. Opciones: {', '.join(MODOS_FLETE)}")
    valor = (_numero(flete_valor, "El flete", 0, 100_000_000) if (flete_valor or "").strip()
             else float(f.fletes_sugeridos.get(modo, 0)))
    excluidos = set()
    for parte in (sin_flete or "").replace(";", ",").split(","):
        if parte.strip():
            if not parte.strip().isdigit() or not 1 <= int(parte) <= len(f.renglones):
                raise ValueError(f"Renglón {parte.strip()!r}: los renglones van del 1 al {len(f.renglones)}")
            excluidos.add(int(parte))
    perc = (percepcion or "costo").strip().lower()
    if perc not in ("costo", "recupera"):
        raise ValueError("La percepción va al costo o se recupera: 'costo' o 'recupera'")
    pf = _numero(percepcion_flete, "La percepción del flete", 0, 20) if (percepcion_flete or "").strip() else 0.0
    return Config(pasos, modo, valor, frozenset(excluidos), perc == "costo", pf)


def texto_descuento(d: Descuento) -> str:
    if not d.fijo:
        return f"{num(d.valor)} %"
    return f"{pesos(d.valor)} por {'unidad' if d.base == UNIDAD else 'pallet' if d.base == PALLET else 'bulto'}"


def _explicar(f: Factura, c: Config) -> list[str]:
    flete = {
        TONELADA: f"Flete en camión a {pesos(c.flete_valor)} por tonelada: cada artículo carga ese precio según su peso.",
        POR_PALLET: f"Flete a {pesos(c.flete_valor)} por pallet: cada artículo carga su parte según cuántas unidades trae el pallet.",
        EXPRESO: f"Expreso de {pesos(c.flete_valor)} en total, repartido en partes iguales entre los renglones que llevan flete.",
        SIN_FLETE: "Sin flete.",
    }[c.flete]
    lineas = [
        "Descuentos extra: " + (" + ".join(texto_descuento(d) for d in c.descuentos) + ", en ese orden, después de la "
                                "bonificación del proveedor." if c.descuentos else "ninguno."),
        flete,
        f"Percepción de Ingresos Brutos {num(f.percepcion)} % ({f.jurisdiccion}): " +
        ("no computable, va al costo." if c.percepcion_al_costo else "se recupera, no suma al costo."),
        f"IVA {num(f.iva)} %: se recupera como crédito fiscal, no suma al costo.",
    ]
    if c.flete == EXPRESO and c.sin_flete:
        lineas.insert(2, "Renglones sin flete: " + ", ".join(str(n) for n in sorted(c.sin_flete)) + ".")
    if c.percepcion_flete:
        lineas.insert(-1, f"El flete trae una percepción no computable del {num(c.percepcion_flete)} %: va al costo.")
    return lineas


def resultado(descuentos: str = "", flete: str = "", flete_valor: str = "", sin_flete: str = "",
              percepcion: str = "", percepcion_flete: str = "", ruta: str = str(DATOS)) -> dict:
    """Corre la factura con esos parámetros. Lanza ValueError con un mensaje para mostrar si no sirven."""
    f = cargar(ruta)
    c = config(descuentos, flete, flete_valor, sin_flete, percepcion, percepcion_flete, ruta)
    r = calcular(f, c)
    r["factura"] = _cabecera(f)
    r["parametros"] = {
        "descuentos": " + ".join(texto_descuento(d) for d in c.descuentos),
        "flete": c.flete, "flete_valor": c.flete_valor, "sin_flete": sorted(c.sin_flete),
        "percepcion": "costo" if c.percepcion_al_costo else "recupera", "percepcion_flete": c.percepcion_flete,
        "explicacion": _explicar(f, c),
    }
    return r

"""El cálculo de la factura, paso a paso y explicado.

Cada renglón termina con un costo por unidad y la lista de pasos que llevaron
hasta ahí, escritos para que los entienda cualquiera. Además se controla lo que
cobra el proveedor: cada renglón y el pie de la factura.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .reglas import BULTO, PALLET, UNIDAD, Descuento, leer_empaque

TONELADA, POR_PALLET, EXPRESO, SIN_FLETE = "tonelada", "pallet", "expreso", "ninguno"
MODOS_FLETE = (TONELADA, POR_PALLET, EXPRESO, SIN_FLETE)
TOLERANCIA = 1.0   # pesos: menos que esto no se marca como diferencia


def ar(x: float, decimales: int = 2) -> str:
    """1234.5 -> '1.234,50'"""
    return f"{x:,.{decimales}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def pesos(x: float) -> str:
    return f"-$ {ar(-x)}" if x < 0 else f"$ {ar(x)}"


def num(x: float) -> str:
    """3.0 -> '3', 7.4 -> '7,4'"""
    return str(int(x)) if float(x).is_integer() else ar(x, 2).rstrip("0").rstrip(",")


@dataclass
class Renglon:
    n: int
    codigo: str
    descripcion: str
    adicional: str
    cantidad: float
    unidad: str
    peso_kg: float | None
    precio_lista: float
    bonificacion: float
    importe_proveedor: float
    por_pallet: int | None = field(init=False)
    por_bulto: int | None = field(init=False)

    def __post_init__(self):
        self.por_pallet, self.por_bulto = leer_empaque(self.adicional)

    @property
    def plural(self) -> str:
        return self.unidad + "s"


@dataclass
class Factura:
    cabecera: dict
    renglones: list
    iva: float
    percepcion: float
    jurisdiccion: str
    totales_proveedor: dict
    pie: str = ""
    fletes_sugeridos: dict = field(default_factory=dict)


@dataclass
class Config:
    descuentos: list = field(default_factory=list)
    flete: str = TONELADA
    flete_valor: float = 0.0
    sin_flete: frozenset = frozenset()     # renglones destildados (solo cuenta en el expreso)
    percepcion_al_costo: bool = True
    percepcion_flete: float = 0.0          # % no computable que trae el flete

    def __post_init__(self):
        if self.flete not in MODOS_FLETE:
            raise ValueError(f"No conozco el flete {self.flete!r}. Opciones: {', '.join(MODOS_FLETE)}")


def _paso(concepto: str, detalle: str, unitario: float | None, monto: float | None = None) -> dict:
    return {"concepto": concepto, "detalle": detalle,
            "monto": None if monto is None else round(monto, 2),
            "unitario": None if unitario is None else round(unitario, 2)}


def _descuento(r: Renglon, d: Descuento, unit: float) -> tuple[float, dict]:
    if not d.fijo:
        monto = unit * d.valor / 100
        return unit - monto, _paso(f"Descuento {num(d.valor)} %", f"{num(d.valor)} % de {pesos(unit)} = {pesos(monto)} menos.",
                                   unit - monto, -monto)
    if d.base == UNIDAD:
        return unit - d.valor, _paso(f"Descuento {pesos(d.valor)} por {r.unidad}",
                                     f"{pesos(d.valor)} menos en cada {r.unidad}.", unit - d.valor, -d.valor)
    cuantas = r.por_pallet if d.base == PALLET else r.por_bulto
    nombre = "pallet" if d.base == PALLET else "bulto"
    if not cuantas:
        return unit, _paso(f"Descuento {pesos(d.valor)} por {nombre}",
                           f"No aplica: este artículo no viene por {nombre} (no lo dice su descripción adicional).", unit, 0.0)
    monto = d.valor / cuantas
    return unit - monto, _paso(
        f"Descuento {pesos(d.valor)} por {nombre}",
        f"El {nombre} trae {cuantas} {r.plural} (lo dice la descripción adicional: «{r.adicional}»). "
        f"{pesos(d.valor)} ÷ {cuantas} = {pesos(monto)} menos por {r.unidad}.", unit - monto, -monto)


def _flete(r: Renglon, c: Config, incluidos: int) -> tuple[float, dict, str | None]:
    v = c.flete_valor
    if c.flete == TONELADA:
        if not r.peso_kg:
            return 0.0, _paso("Flete", "Sin flete: el artículo no tiene peso cargado.", None), "Sin peso: no se le pudo cargar flete."
        f = v * r.peso_kg / 1000
        return f, _paso("Flete en camión por tonelada",
                        f"{pesos(v)} por tonelada. Cada {r.unidad} pesa {num(r.peso_kg)} kg: "
                        f"{pesos(v)} × {num(r.peso_kg)} ÷ 1.000 = {pesos(f)}.", None, f), None
    if c.flete == POR_PALLET:
        if not r.por_pallet:
            return 0.0, _paso("Flete por pallet", "No le corresponde: este artículo no viene en pallet.", None), \
                "No viene en pallet: quedó sin flete."
        f = v / r.por_pallet
        return f, _paso("Flete por pallet", f"{pesos(v)} por pallet, que trae {r.por_pallet} {r.plural}: "
                                            f"{pesos(v)} ÷ {r.por_pallet} = {pesos(f)}.", None, f), None
    if c.flete == EXPRESO:
        if r.n in c.sin_flete:
            return 0.0, _paso("Expreso", "Sin flete: este renglón se destildó y no lleva parte del expreso.", None), None
        parte = v / incluidos
        f = parte / r.cantidad
        return f, _paso("Expreso repartido por renglón",
                        f"{pesos(v)} en partes iguales entre {incluidos} renglones = {pesos(parte)} para este renglón. "
                        f"Dividido sus {num(r.cantidad)} {r.plural}: {pesos(f)}.", None, f), None
    return 0.0, _paso("Flete", "Sin flete.", None), None


def _control_renglon(r: Renglon) -> dict:
    calculado = r.cantidad * r.precio_lista * (1 - r.bonificacion / 100)
    dif = r.importe_proveedor - calculado
    ok = abs(dif) < TOLERANCIA
    detalle = (f"Cuadra: {num(r.cantidad)} × {pesos(r.precio_lista)}"
               + (f" − {num(r.bonificacion)} %" if r.bonificacion else "") + f" = {pesos(calculado)}.")
    if not ok:
        detalle = (f"No cuadra: el proveedor cobra {pesos(r.importe_proveedor)} y la cuenta da {pesos(calculado)}, "
                   f"{pesos(abs(dif))} {'de más' if dif > 0 else 'de menos'}.")
        if r.bonificacion and abs(r.importe_proveedor - r.cantidad * r.precio_lista) < TOLERANCIA:
            detalle += f" Es exactamente lo que da sin aplicar la bonificación del {num(r.bonificacion)} %."
    return {"ok": ok, "proveedor": round(r.importe_proveedor, 2), "calculado": round(calculado, 2),
            "diferencia": round(dif, 2), "detalle": detalle}


def _controles_pie(f: Factura, neto: float) -> list[dict]:
    p = f.totales_proveedor
    iva, perc = neto * f.iva / 100, neto * f.percepcion / 100
    filas = []

    def fila(concepto, proveedor, calculado, detalle_ok, pista=None):
        dif = proveedor - calculado
        ok = abs(dif) < TOLERANCIA
        detalle = detalle_ok if ok else (f"No cuadra: el proveedor pone {pesos(proveedor)} y da {pesos(calculado)}, "
                                         f"{pesos(abs(dif))} {'de más' if dif > 0 else 'de menos'}." + (f" {pista}" if pista else ""))
        filas.append({"concepto": concepto, "proveedor": round(proveedor, 2), "calculado": round(calculado, 2),
                      "diferencia": round(dif, 2), "ok": ok, "detalle": detalle})

    fila("Neto", p["neto"], neto, "Cuadra con la suma de los renglones.",
         "La diferencia es la de los renglones que no cuadran.")
    pista_iva = ("El IVA está bien calculado sobre el neto del proveedor: la diferencia viene del neto."
                 if abs(p["iva"] - p["neto"] * f.iva / 100) < TOLERANCIA else None)
    fila(f"IVA {num(f.iva)} %", p["iva"], iva, f"Cuadra: {num(f.iva)} % del neto.", pista_iva)
    sobre_total = abs(p["percepcion"] - (p["neto"] + p["iva"]) * f.percepcion / 100) < TOLERANCIA
    fila(f"Percepción IIBB {num(f.percepcion)} %", p["percepcion"], perc, f"Cuadra: {num(f.percepcion)} % del neto.",
         "Coincide con haberla calculado sobre el neto más el IVA, en lugar de sobre el neto." if sobre_total else None)
    fila("Total", p["total"], neto + iva + perc, "Cuadra.", "Es la suma de las diferencias de arriba.")
    return filas


def calcular(f: Factura, c: Config) -> dict:
    incluidos = sum(1 for r in f.renglones if r.n not in c.sin_flete)
    if c.flete == EXPRESO and incluidos == 0:
        raise ValueError("Destildaste todos los renglones: el expreso no tiene a quién cargarse")
    if c.flete_valor < 0:
        raise ValueError("El flete no puede ser negativo")

    renglones, avisos_totales = [], 0
    neto_lista = costo_total = flete_total = percepciones_total = mercaderia_total = 0.0
    for r in f.renglones:
        avisos = []
        unit = r.precio_lista
        pasos = [_paso("Precio de lista", f"Lo que dice la lista por {r.unidad}.", unit)]
        if r.bonificacion:
            monto = unit * r.bonificacion / 100
            unit -= monto
            pasos.append(_paso(f"Bonificación del proveedor {num(r.bonificacion)} %",
                               f"{num(r.bonificacion)} % de {pesos(r.precio_lista)} = {pesos(monto)} menos.", unit, -monto))
        for d in c.descuentos:
            unit, paso = _descuento(r, d, unit)
            pasos.append(paso)
        control = _control_renglon(r)
        neto_lista += control["calculado"]
        if unit < 0:
            avisos.append("Los descuentos dejan el precio en negativo: revisá la cadena.")
            renglones.append({**_datos(r), "pasos": pasos, "neto": round(unit, 2), "costo": None, "total": None,
                              "control": control, "avisos": avisos})
            avisos_totales += 1
            continue
        pasos.append(_paso("Precio neto", "Lo que queda después de todos los descuentos.", unit))

        flete, paso, aviso = _flete(r, c, incluidos)
        pasos.append(paso)
        if aviso:
            avisos.append(aviso)

        percep = unit * f.percepcion / 100 if c.percepcion_al_costo else 0.0
        if c.percepcion_al_costo:
            pasos.append(_paso(f"Percepción IIBB {num(f.percepcion)} % ({f.jurisdiccion})",
                               f"No computable: va al costo. {num(f.percepcion)} % de {pesos(unit)} = {pesos(percep)}.", None, percep))
        else:
            pasos.append(_paso(f"Percepción IIBB {num(f.percepcion)} % ({f.jurisdiccion})",
                               "Se recupera: no suma al costo.", None, 0.0))
        percep_flete = flete * c.percepcion_flete / 100
        if percep_flete:
            pasos.append(_paso(f"Percepción del flete {num(c.percepcion_flete)} %",
                               f"No computable: va al costo. {num(c.percepcion_flete)} % de {pesos(flete)} = {pesos(percep_flete)}.",
                               None, percep_flete))
        costo = unit + flete + percep + percep_flete
        total = costo * r.cantidad
        pasos.append(_paso("Costo final", f"{pesos(unit)} de mercadería + {pesos(flete)} de flete + "
                                          f"{pesos(percep + percep_flete)} de percepciones = {pesos(costo)} por {r.unidad}. "
                                          f"Por {num(r.cantidad)} {r.plural}: {pesos(total)}.", costo))
        mercaderia_total += unit * r.cantidad
        flete_total += flete * r.cantidad
        percepciones_total += (percep + percep_flete) * r.cantidad
        costo_total += total
        avisos_totales += len(avisos)
        renglones.append({**_datos(r), "pasos": pasos, "neto": round(unit, 2), "flete": round(flete, 2),
                          "percepciones": round(percep + percep_flete, 2), "costo": round(costo, 2),
                          "total": round(total, 2), "control": control, "avisos": avisos})

    controles = _controles_pie(f, neto_lista)
    return {
        "renglones": renglones,
        "controles": controles,
        "totales": {
            "mercaderia": round(mercaderia_total, 2), "flete": round(flete_total, 2),
            "percepciones": round(percepciones_total, 2), "costo": round(costo_total, 2),
            "iva_recuperable": round(neto_lista * f.iva / 100, 2),
        },
        "resumen": {
            "renglones": len(f.renglones),
            "renglones_con_diferencia": sum(1 for r in renglones if not r["control"]["ok"]),
            "pie_con_diferencia": sum(1 for x in controles if not x["ok"]),
            # Lo que cobra el proveedor menos lo que da la cuenta, al pie: positivo = cobra de más.
            "diferencia_total": controles[-1]["diferencia"],
            "avisos": avisos_totales,
        },
    }


def _datos(r: Renglon) -> dict:
    return {"n": r.n, "codigo": r.codigo, "descripcion": r.descripcion, "adicional": r.adicional,
            "cantidad": r.cantidad, "unidad": r.unidad, "peso_kg": r.peso_kg, "precio_lista": r.precio_lista,
            "bonificacion": r.bonificacion, "por_pallet": r.por_pallet, "por_bulto": r.por_bulto}

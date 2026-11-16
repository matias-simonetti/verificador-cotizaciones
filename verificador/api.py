"""API web de la demo (FastAPI). Solo lectura: no recibe archivos ni guarda nada.

    GET /factura      la factura ficticia tal como la mandó el proveedor
    GET /resultado    el cálculo con estos parámetros (todos opcionales):
        descuentos        "10 + $6000/pallet + $150"
        flete             tonelada | pallet | expreso | ninguno
        flete_valor       monto (si falta, el sugerido de la factura)
        sin_flete         renglones que no llevan expreso, "7,8"
        percepcion        costo | recupera
        percepcion_flete  % no computable que trae el flete

Así la usa simonetti.uno, montada en /a/proyectos/api/verificador/.
Para probarla sola en tu compu: python servir.py
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from . import demo

router = APIRouter(tags=["verificador"])


@router.get("/factura")
def factura():
    return demo.factura()


@router.get("/resultado")
def resultado(descuentos: str = "", flete: str = "", flete_valor: str = "", sin_flete: str = "",
              percepcion: str = "", percepcion_flete: str = ""):
    try:
        return demo.resultado(descuentos, flete, flete_valor, sin_flete, percepcion, percepcion_flete)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

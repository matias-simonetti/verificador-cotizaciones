# Verificador de cotizaciones

Recalcula una factura de proveedor renglón por renglón, marca lo que no cuadra y
lleva cada artículo a su **costo final**, con cada paso explicado para que lo
entienda cualquiera. Pensado para un corralón de materiales.

> Los datos son ficticios. "Distribuidora Andina de Materiales" y "Corralón Los
> Coihues" no existen. La factura de prueba trae **dos errores del proveedor
> puestos a propósito**, para mostrar cómo los encuentra.

Es el segundo caso de [simonetti.uno/proyectos](https://simonetti.uno/proyectos).
El primero es el [Comparador de costos](https://github.com/matias-simonetti/comparador-costos).

## El problema

Las facturas y cotizaciones llegan con errores de cálculo más seguido de lo que
uno quisiera, y el costo real de cada artículo no es el precio de lista: hay
bonificaciones, descuentos fijos por pallet o por bulto, fletes que se cobran de
formas distintas y percepciones que a veces no se pueden recuperar. Hacer esa
cuenta a mano, renglón por renglón, es lento y fácil de errar.

## Qué hace

**Controla lo que cobra el proveedor.** Cada renglón (cantidad × lista −
bonificación) y el pie de la factura (neto, IVA, percepción, total). Cuando algo
no cuadra, dice cuánto y, si reconoce el error, cuál fue:

- *"Es exactamente lo que da sin aplicar la bonificación del 5 %."*
- *"Coincide con haber calculado la percepción sobre el neto más el IVA."*

**Lleva cada artículo a su costo final**, con estas reglas del rubro:

| Concepto | Cómo se aplica |
|---|---|
| Descuentos | Porcentaje, o monto fijo por unidad, por pallet o por bulto, en el orden que se escriben: `10 + $6000/pallet + $150` |
| Pallet y bulto | Las unidades salen de la "descripción adicional" del artículo, escrita a mano: `PALLET X 40 BOLSAS`, `ATADO X 50 BARRAS` |
| Flete en camión | Por tonelada (cada artículo carga el precio según su peso) o por pallet |
| Expreso | El monto total se reparte **en partes iguales por renglón**, como lo hace administración. Los renglones que quedarían con un flete ridículo se destildan |
| Percepciones | Cada una "se recupera" o "va al costo" (no computable). La del flete, aparte |
| IVA | Se recupera: se muestra pero no suma al costo |

**Explica cada paso.** Cada renglón trae la lista de pasos con la cuenta escrita,
lista para un informe impreso.

## Decisiones

- **Por factura, no por lista.** El expreso y la carga completa se pagan una vez
  por todo el envío: repartirlos necesita los renglones y las cantidades.
- **Si un dato falta, avisa en vez de inventar.** Un artículo sin pallet no recibe
  el descuento por pallet ni el flete por pallet, y el informe dice por qué.
- **Nada se pierde en el reparto.** Un test controla que la suma de lo repartido
  sea exactamente el flete cobrado.
- **Solo biblioteca estándar en el motor.** La API es FastAPI de solo lectura.

## Cómo se hizo

El código lo escribió una IA (Claude, de Anthropic) trabajando con Matías
Simonetti. Matías trajo el problema, las reglas del rubro (cómo se reparte el
expreso, dónde están las unidades por pallet, qué percepciones no se recuperan)
y las decisiones de alcance.

## Uso

```bash
pip install -r requirements.txt
python -m pytest                  # pruebas, con cuentas hechas a mano
python servir.py                  # API de la demo en http://127.0.0.1:8000/docs
```

## Estructura

```
verificador/
  reglas.py    descripción adicional (pallet, bulto) y cadena de descuentos
  calculo.py   el cálculo explicado y los controles de lo que cobra el proveedor
  demo.py      la factura ficticia y la validación de parámetros
  api.py       API de solo lectura (FastAPI)
datos/factura_demo.json   la factura de prueba, con sus dos errores
servir.py                 levanta la API en tu compu
tests/                    pruebas
```

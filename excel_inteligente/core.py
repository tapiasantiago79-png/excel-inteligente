"""Validación y cálculos monetarios exactos (centavos USD)."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date

MODULES = {
 'productos': {'nombre':'Producto', 'inicial':'Existencia inicial', 'minimo':'Stock mínimo'},
 'ventas': {'fecha':'Fecha', 'producto':'Producto', 'cantidad':'Cantidad', 'precio':'Precio unitario', 'costo':'Costo unitario', 'medio':'Medio de pago'},
 'movimientos': {'fecha':'Fecha', 'producto':'Producto', 'tipo':'Tipo', 'cantidad':'Cantidad', 'concepto':'Concepto'},
 'gastos': {'fecha':'Fecha', 'proveedor':'Proveedor', 'concepto':'Concepto', 'categoria':'Categoría', 'importe':'Importe', 'estado':'Estado de pago', 'medio':'Medio de pago'},
 'caja': {'fecha':'Fecha', 'apertura':'Fondo inicial', 'entradas':'Otras entradas', 'salidas':'Otras salidas', 'contado':'Efectivo contado'},
}
MONEY = {'precio','costo','importe','apertura','entradas','salidas','contado'}
QUANTITIES = {'cantidad','inicial','minimo'}
OPTIONS = {'medio':['Efectivo','Transferencia','Tarjeta'], 'tipo':['Entrada','Salida'], 'estado':['Pendiente','Pagado'], 'categoria':['Compra','Gasto']}

def cents(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > Decimal('1000000000'):
            raise ValueError('El importe debe estar entre 0 y 1.000.000.000 USD.')
        return int((number * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError):
        raise ValueError('Importe inválido.') from None

def quantity(value, positive=False):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n != n.to_integral_value() or n < (1 if positive else 0) or n > 1000000000:
            raise ValueError('La cantidad debe ser un entero válido y no negativo; en operaciones debe ser mayor a cero.')
        return int(n)
    except InvalidOperation:
        raise ValueError('Cantidad inválida.') from None

def sale(row):
    revenue = row['cantidad'] * row['precio']
    cost = row['cantidad'] * row['costo']
    return revenue, cost, revenue-cost

def stock(data, product):
    initial = next(p['inicial'] for p in data['productos'] if p['id'] == product)
    movements = sum((1 if r['tipo']=='Entrada' else -1)*r['cantidad'] for r in data['movimientos'] if r['producto']==product)
    sold = sum(r['cantidad'] for r in data['ventas'] if r['producto']==product)
    return initial + movements - sold

def cash(data, row):
    income = sum(sale(r)[0] for r in data['ventas'] if r['fecha']==row['fecha'] and r['medio']=='Efectivo')
    expense = sum(r['importe'] for r in data['gastos'] if r['fecha']==row['fecha'] and r['medio']=='Efectivo' and r['estado']=='Pagado')
    expected = row['apertura'] + row['entradas'] + income - row['salidas'] - expense
    return expected, row['contado']-expected

def validate(data):
    names = set()
    for table, rows in data.items():
        for r in rows:
            for key in MODULES[table]:
                value = r[key]
                if key in MONEY:
                    quantity(value)
                    if value > 100000000000: raise ValueError('Importe fuera de rango.')
                elif key in QUANTITIES: quantity(value, key=='cantidad')
                elif key == 'fecha': date.fromisoformat(value)
                elif key == 'producto':
                    if value not in {p['id'] for p in data['productos']}: raise ValueError('El producto no existe o tiene registros asociados.')
                elif key in OPTIONS:
                    if value not in OPTIONS[key]: raise ValueError('Opción inválida.')
                elif not str(value).strip() or len(str(value))>200: raise ValueError('Completa los textos requeridos (máximo 200 caracteres).')
            if table=='productos':
                name=r['nombre'].strip().casefold()
                if name in names: raise ValueError('Ya existe un producto con ese nombre.')
                names.add(name)
    dates=[r['fecha'] for r in data['caja']]
    if len(dates)!=len(set(dates)): raise ValueError('Solo se permite un cuadre por fecha.')
    for p in data['productos']:
        balance=p['inicial']
        events=[(r['fecha'], 0 if r['tipo']=='Entrada' else 1, r['id'], r['cantidad']*(1 if r['tipo']=='Entrada' else -1)) for r in data['movimientos'] if r['producto']==p['id']]
        events += [(r['fecha'],2,r['id'],-r['cantidad']) for r in data['ventas'] if r['producto']==p['id']]
        for _,_,_,delta in sorted(events):
            balance+=delta
            if balance<0: raise ValueError(f"Stock insuficiente para {p['nombre']}. Revisa fechas, entradas y ventas.")

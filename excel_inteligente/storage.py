"""Persistencia transaccional SQLite, sin dependencias externas."""
import json
import sqlite3
from pathlib import Path
from uuid import uuid4
from .core import MODULES, validate

class Store:
    def __init__(self, path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (module TEXT, id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    def connect(self):
        return sqlite3.connect(self.path, timeout=15)
    def read(self, db=None):
        if db is None:
            with self.connect() as conn: return self.read(conn)
        data={k:[] for k in MODULES}
        for module, payload in db.execute('SELECT module,payload FROM records ORDER BY rowid'):
            data[module].append(json.loads(payload))
        return data
    def change(self, module, row=None, delete=None):
        if module not in MODULES: raise ValueError('Módulo inválido.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            data=self.read(db)
            if delete:
                data[module]=[r for r in data[module] if r['id']!=delete]
                db.execute('DELETE FROM records WHERE module=? AND id=?',(module,delete))
            else:
                row=dict(row, id=row.get('id') or uuid4().hex)
                data[module]=[r for r in data[module] if r['id']!=row['id']]+[row]
                db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)',(module,row['id'],json.dumps(row)))
            validate(data)
    def demo(self):
        from datetime import date
        today=date.today().isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT count(*) FROM records').fetchone()[0]: raise ValueError('Los ejemplos solo se cargan en una base vacía.')
            data={k:[] for k in MODULES}
            data['productos']=[dict(id='cafe',nombre='Café de especialidad',inicial=80,minimo=15),dict(id='taza',nombre='Taza artesanal',inicial=40,minimo=10)]
            data['ventas']=[dict(id='v1',fecha=today,producto='cafe',cantidad=6,precio=1250,costo=700,medio='Efectivo'),dict(id='v2',fecha=today,producto='taza',cantidad=3,precio=1800,costo=900,medio='Tarjeta')]
            data['gastos']=[dict(id='g1',fecha=today,proveedor='Papelería Central',concepto='Material de empaque',categoria='Gasto',importe=1500,estado='Pagado',medio='Efectivo')]
            data['caja']=[dict(id='c1',fecha=today,apertura=5000,entradas=0,salidas=0,contado=11000)]
            validate(data)
            for module,rows in data.items():
                db.executemany('INSERT INTO records VALUES (?,?,?)',[(module,r['id'],json.dumps(r)) for r in rows])

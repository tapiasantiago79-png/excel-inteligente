from datetime import date
from pathlib import Path
import os
import pandas as pd
import streamlit as st
from excel_inteligente.core import MODULES, MONEY, QUANTITIES, OPTIONS, cents, sale, stock, cash
from excel_inteligente.storage import Store
from excel_inteligente.export import workbook

st.set_page_config(page_title='Excel Inteligente',page_icon='📊',layout='wide')
st.markdown('''<style>
.stApp {background:#f4f7f6} .block-container {max-width:1300px;padding-top:2rem}
h1,h2,h3 {color:#123e41} [data-testid="stMetric"] {background:white;border:1px solid #e0e8e5;border-radius:14px;padding:18px}
[data-testid="stSidebar"] {background:#e8f0ed} .stButton button {border-radius:9px}
@media(max-width:640px){.block-container{padding:1rem}.stMain h1{font-size:2rem}}
</style>''',unsafe_allow_html=True)
store=Store(os.environ.get('EXCEL_DB',str(Path(__file__).parent/'data'/'negocio.sqlite3')))
data=store.read()
products={p['id']:p['nombre'] for p in data['productos']}
labels={'ventas':'Control de ventas','caja':'Cuadre de caja','movimientos':'Inventario','gastos':'Compras y gastos'}
with st.sidebar:
    st.title('📊 Excel Inteligente')
    st.caption('TU NEGOCIO, EN ORDEN')
    section=st.radio('Espacio de trabajo',['Resumen']+list(labels.values()))
    st.divider()
    st.download_button('↓ Exportar libro Excel',workbook(data),'Excel_Inteligente.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
    with st.expander('Datos de ejemplo'):
        st.caption('Disponibles únicamente si la base está vacía.')
        if st.button('Cargar ejemplos',disabled=any(data.values())):
            try: store.demo(); st.rerun()
            except ValueError as e: st.error(str(e))
    st.caption('Datos locales · Moneda USD')
st.title(section)
st.caption('Gestión sencilla para tomar mejores decisiones.')
if 'notice' in st.session_state: st.success(st.session_state.pop('notice'))

def money(n): return f'${n/100:,.2f}'

def editor(module):
    rows=data[module]
    names={r['id']:f"{r.get('fecha','')} · {r.get('nombre',r.get('concepto',products.get(r.get('producto'),'Cuadre')))} · {r['id'][:6]}" for r in rows}
    mode=st.radio('Acción',['Nuevo registro','Editar registro','Eliminar registro'],horizontal=True,key='mode_'+module)
    selected=None
    if mode!='Nuevo registro':
        if not rows: st.info('No hay registros disponibles.'); return
        selected=st.selectbox('Selecciona un registro',list(names),format_func=names.get,key='pick_'+module)
    original=next((r for r in rows if r['id']==selected),{})
    if mode=='Eliminar registro':
        with st.form('delete_'+module):
            confirm=st.checkbox('Confirmo que deseo eliminar este registro')
            if st.form_submit_button('Eliminar',disabled=False):
                if not confirm: st.warning('Marca la confirmación para eliminar.'); return
                try: store.change(module,delete=selected); st.session_state.notice='Registro eliminado.'; st.rerun()
                except ValueError as e: st.error(str(e))
        return
    if 'producto' in MODULES[module] and not products:
        st.info('Crea un producto en Inventario antes de registrar operaciones.'); return
    with st.form('form_'+module+'_'+str(selected),clear_on_submit=False):
        values={}
        columns=st.columns(2)
        for i,(key,label) in enumerate(MODULES[module].items()):
            with columns[i%2]:
                old=original.get(key)
                if key in MONEY: values[key]=st.number_input(label+' (USD)',min_value=0.0,max_value=1_000_000_000.0,value=float((old or 0)/100),step=0.01,format='%.2f')
                elif key in QUANTITIES: values[key]=st.number_input(label,min_value=1 if key=='cantidad' else 0,max_value=1000000000,value=int(old if old is not None else (1 if key=='cantidad' else 0)),step=1)
                elif key=='fecha': values[key]=st.date_input(label,value=date.fromisoformat(old) if old else date.today()).isoformat()
                elif key=='producto': values[key]=st.selectbox(label,list(products),index=list(products).index(old) if old in products else 0,format_func=products.get)
                elif key in OPTIONS: values[key]=st.selectbox(label,OPTIONS[key],index=OPTIONS[key].index(old) if old in OPTIONS[key] else 0)
                else: values[key]=st.text_input(label,value=old or '',max_chars=200).strip()
        if st.form_submit_button('Guardar registro',type='primary',use_container_width=True):
            try:
                values={k:cents(v) if k in MONEY else v for k,v in values.items()}
                if selected: values['id']=selected
                store.change(module,values)
                st.session_state.notice='Registro guardado. Los cálculos se actualizaron.'
                st.rerun()
            except (ValueError,OverflowError) as e: st.error(str(e))

def table(module):
    result=[]
    for r in data[module]:
        view={'ID':r['id'][:8]}
        for key,label in MODULES[module].items(): view[label]=r[key]/100 if key in MONEY else products.get(r[key],r[key]) if key=='producto' else r[key]
        if module=='ventas': view.update(zip(['Ingresos USD','Costos USD','Ganancia USD'],[v/100 for v in sale(r)]))
        if module=='productos': view['Existencias']=stock(data,r['id']); view['Estado']='Reponer' if view['Existencias']<=r['minimo'] else 'Disponible'
        if module=='caja': view.update(zip(['Esperado USD','Diferencia USD'],[v/100 for v in cash(data,r)]))
        result.append(view)
    if result:
        frame=pd.DataFrame(result)
        configs={c:st.column_config.NumberColumn(c,format='$%.2f') for c in frame.columns if c.endswith('USD') or c in [MODULES[module].get(k) for k in MONEY]}
        st.dataframe(frame,hide_index=True,use_container_width=True,column_config=configs)
    else: st.info('Aún no hay registros. Agrega el primero o carga los ejemplos desde el menú lateral.')

revenue=sum(sale(r)[0] for r in data['ventas']); cost=sum(sale(r)[1] for r in data['ventas'])
if section=='Resumen':
    a,b,c=st.columns(3)
    a.metric('Ingresos por ventas',money(revenue)); b.metric('Costos de ventas',money(cost)); c.metric('Ganancia bruta',money(revenue-cost))
    a,b,c=st.columns(3)
    a.metric('Productos',len(products)); b.metric('Unidades disponibles',sum(stock(data,p) for p in products)); c.metric('Pendiente de pago',money(sum(r['importe'] for r in data['gastos'] if r['estado']=='Pendiente')))
    st.subheader('Tu operación, conectada')
    st.markdown('Registra productos y entradas en **Inventario**, agrega tus **ventas** y revisa el **cuadre de caja** por fecha. Descarga todas las hojas desde el menú lateral.')
    st.info('La ganancia bruta es ingresos menos costos de ventas. Los gastos se muestran por separado. Los importes se calculan en centavos USD.')
    st.subheader('Disponibilidad de productos'); table('productos')
else:
    module=next(k for k,v in labels.items() if v==section)
    if module=='movimientos':
        st.info('Las ventas generan salidas automáticamente. Las compras no crean entradas: registra aquí la recepción física. El stock inicial corresponde al inicio de tu historial. Se impide stock negativo por fecha; las entradas del día se consideran antes que las salidas.')
        tab1,tab2=st.tabs(['Existencias y productos','Entradas y salidas'])
        with tab1: table('productos'); editor('productos')
        with tab2: table('movimientos'); editor('movimientos')
    else:
        if module=='caja': st.info('Esperado = fondo inicial + ventas en efectivo + otras entradas − compras y gastos pagados en efectivo − otras salidas. Diferencia = contado − esperado. No dupliques gastos en otras salidas. Cada cuadre corresponde a un día completo; se recalcula al modificar sus operaciones.')
        if module=='gastos': st.caption('La fecha determina cuándo afecta caja si el registro está pagado en efectivo. Para pagos posteriores, usa la fecha efectiva de pago. No se admiten pagos parciales en esta versión.')
        if module=='ventas':
            a,b,c=st.columns(3); a.metric('Ingresos',money(revenue)); b.metric('Costos',money(cost)); c.metric('Ganancia bruta',money(revenue-cost))
        st.subheader('Registros'); table(module)
        with st.expander('Agregar, editar o eliminar',expanded=True): editor(module)

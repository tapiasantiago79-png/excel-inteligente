"""Libros XLSX con fórmulas recalculables y estilos de impresión."""
from io import BytesIO
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties
from .core import MODULES, MONEY

SHEETS={'productos':'Productos','ventas':'Ventas','movimientos':'Movimientos','gastos':'Compras y gastos','caja':'Caja'}
USD='"$"#,##0.00;[Red]("$"#,##0.00)'

def safe(value):
    # Forzar texto para que los conceptos no se interpreten como fórmulas.
    if isinstance(value,str) and value.startswith(('=','+','-','@')): return "'"+value
    return value

def workbook(data):
    wb=Workbook()
    summary=wb.active
    summary.title='Resumen'
    wb.calculation=CalcProperties(calcId=191029,fullCalcOnLoad=True)
    for module,fields in MODULES.items():
        ws=wb.create_sheet(SHEETS[module])
        headers=['ID']+list(fields.values())
        extras={'productos':['Existencias','Alerta'],'ventas':['Ingresos','Costos','Ganancia'],'caja':['Ventas efectivo','Gastos efectivo','Efectivo esperado','Diferencia']}.get(module,[])
        ws.append(headers+extras)
        for r in data[module]:
            ws.append([r['id']]+[r[k]/100 if k in MONEY else date.fromisoformat(r[k]) if k=='fecha' else safe(r[k]) for k in fields])
        # Una fila vacía mantiene filtros y fórmulas incluso sin registros.
        if ws.max_row==1: ws.append([None]*len(headers))
        for i in range(2,ws.max_row+1):
            if module=='ventas':
                for col,formula in [('H',f'D{i}*E{i}'),('I',f'D{i}*F{i}'),('J',f'H{i}-I{i}')]: ws[f'{col}{i}']='='+formula
            elif module=='productos':
                ws[f'E{i}']=f'=C{i}+SUMIFS(Movimientos!E:E,Movimientos!C:C,A{i},Movimientos!D:D,"Entrada")-SUMIFS(Movimientos!E:E,Movimientos!C:C,A{i},Movimientos!D:D,"Salida")-SUMIF(Ventas!C:C,A{i},Ventas!D:D)'
                ws[f'F{i}']=f'=IF(E{i}<=D{i},"REPOSICIÓN","OK")'
            elif module=='caja':
                ws[f'G{i}']=f'=SUMIFS(Ventas!H:H,Ventas!B:B,B{i},Ventas!G:G,"Efectivo")'
                ws[f'H{i}']=f'=SUMIFS(\'Compras y gastos\'!F:F,\'Compras y gastos\'!B:B,B{i},\'Compras y gastos\'!G:G,"Pagado",\'Compras y gastos\'!H:H,"Efectivo")'
                ws[f'I{i}']=f'=C{i}+D{i}+G{i}-E{i}-H{i}'
                ws[f'J{i}']=f'=F{i}-I{i}'
        for j,key in enumerate(fields,2):
            for cells in ws.iter_rows(min_row=2,min_col=j,max_col=j):
                cells[0].number_format=USD if key in MONEY else 'yyyy-mm-dd' if key=='fecha' else 'General'
        if module in ('ventas','caja'):
            for row in ws.iter_rows(min_row=2,min_col=8 if module=='ventas' else 7):
                for cell in row: cell.number_format=USD
        table=Table(displayName='Tabla_'+module,ref=ws.dimensions)
        table.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True)
        ws.add_table(table)
    summary.append(['EXCEL INTELIGENTE','Resumen general · USD'])
    for label,formula in [('Ingresos','=SUM(Ventas!H:H)'),('Costos de ventas','=SUM(Ventas!I:I)'),('Ganancia bruta','=SUM(Ventas!J:J)'),('Compras y gastos registrados',"=SUM('Compras y gastos'!F:F)"),('Pendiente de pago',"=SUMIF('Compras y gastos'!G:G,\"Pendiente\",'Compras y gastos'!F:F)"),('Unidades disponibles','=SUM(Productos!E:E)'),('Diferencias de caja','=SUM(Caja!J:J)')]: summary.append([label,formula])
    summary.append(['Nota','La ganancia bruta no descuenta compras ni gastos. Las compras no generan entradas de inventario automáticamente.'])
    for row in summary.iter_rows(min_row=2,max_row=8,min_col=2,max_col=2): row[0].number_format=USD
    summary['B7'].number_format='0'
    for ws in wb:
        ws.freeze_panes='B2'
        ws.sheet_view.showGridLines=False
        for cell in ws[1]:
            cell.font=Font(name='Calibri',bold=True,color='FFFFFF',size=12)
            cell.fill=PatternFill('solid',fgColor='123E41')
            cell.alignment=Alignment(vertical='center')
        ws.row_dimensions[1].height=32
        for j in range(1,ws.max_column+1): ws.column_dimensions[get_column_letter(j)].width=24 if j>1 else 35
        ws.sheet_properties.pageSetUpPr.fitToPage=True
        ws.page_setup.orientation='landscape'
        ws.page_setup.paperSize=ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth=1
        ws.page_setup.fitToHeight=0
        ws.print_title_rows='1:1'
        ws.print_options.horizontalCentered=True
        ws.oddFooter.center.text='Excel Inteligente · Página &P de &N'
    summary.column_dimensions['B'].width=65
    summary['B9'].alignment=Alignment(wrap_text=True)
    summary.row_dimensions[9].height=45
    result=BytesIO()
    wb.save(result)
    return result.getvalue()

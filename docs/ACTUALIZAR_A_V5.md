# Actualización V5: gráficas filtrables y reporte de entradas

## Actualizar

Detén la aplicación, respalda la base y copia el código V5 sobre tu instalación:

```powershell
cd C:\Users\chach\Documents\smart_access_university
Copy-Item smart_access.db smart_access.respaldo-antes-v5.db
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python migrate.py
python app.py
```

Conserva `.env`, `smart_access.db`, `qrcodes` y `static/uploads`. No ejecutes `seed.py`.

Esta versión no necesita tablas nuevas, pero `migrate.py` sigue siendo seguro y verifica que las actualizaciones anteriores estén aplicadas.

## Filtros de las gráficas

El diseño y los indicadores generales del dashboard permanecen iguales.

En **Entradas y salidas** hay dos selectores:

- periodo: día, semana, mes o año;
- carrera: todas las carreras o una carrera individual.

En **Carreras con más accesos** hay selectores independientes. Puedes cambiar su periodo y mostrar todas las carreras o sólo una. Cambiar una gráfica no modifica la otra ni los indicadores superiores.

Los periodos representan el día actual, la semana actual, el mes actual y el año actual.

## Reporte de quiénes entraron

Abre **Panel → Registros** y usa los filtros de fecha, nombre o carrera. El resumen muestra:

- número de eventos de entrada;
- cantidad de personas únicas que entraron;
- alumnos y miembros del personal únicos;
- carreras con entradas y sus cantidades.

Pulsa **Ver sólo entradas** para mostrar exclusivamente entradas autorizadas. También puedes descargar:

- **Excel detallado**: resumen general, entradas por carrera y hoja con todas las personas;
- **PDF**: resumen y tabla imprimible;
- **CSV**: resumen y detalle compatible con Excel.

Las descargas respetan los filtros de fecha, nombre y carrera, y excluyen salidas, rechazos, papelera y lecturas duplicadas no registradas.

# Actualización V6: credenciales PDF y consultas rápidas

## Actualizar

```powershell
cd C:\Users\chach\Documents\smart_access_university
Copy-Item smart_access.db smart_access.respaldo-antes-v6.db
```

Descomprime la V6 sobre la instalación, conserva `.env`, `smart_access.db`, `qrcodes` y `static/uploads`, y ejecuta:

```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python migrate.py
python app.py
```

No ejecutes `seed.py`.

## Descargar una credencial

1. Abre **Alumnos** o **Docentes y personal**.
2. Entra al perfil mediante el icono de credencial.
3. Pulsa **Descargar credencial PDF**.

El archivo tiene dos páginas del tamaño CR80 (85.60 x 53.98 mm): frente y reverso. Para imprimirlo, selecciona tamaño real o escala 100 %, sin ajustar a página. El reverso contiene el mismo QR firmado utilizado por el escáner.

El botón **Sólo QR** se mantiene disponible. Regenerar el QR invalida las copias anteriores, incluida cualquier credencial PDF previamente descargada; después de regenerarlo, descarga nuevamente la credencial.

## Consultas rápidas de Registros

El antiguo botón de sólo entradas ahora es **Consultas rápidas** y abre estas opciones:

- sólo entradas autorizadas;
- sólo salidas autorizadas;
- accesos rechazados;
- todos los movimientos;
- entradas de hoy;
- entradas de la semana;
- entradas del mes;
- personas que todavía no registran salida.

Los accesos rápidos conservan los filtros compatibles de nombre y carrera. Los periodos rápidos reemplazan las fechas para mostrar el periodo elegido.

## Excel mejorado

El reporte detallado contiene:

- **Resumen**: eventos, personas únicas, alumnos, personal y entradas por carrera;
- **Quiénes entraron**: cada evento con fecha, hora, persona, carrera/área, grupo y plantel;
- **Personas únicas**: una fila por persona, primera entrada, última entrada y total de entradas.

# Actualización V3: papelera y consulta de jornadas

Esta versión agrega borrado seguro en **Alumnos**, **Registros** y **Jornadas**. Borrar significa mover a una papelera; no se elimina físicamente la información y se puede restaurar.

## Antes de actualizar

1. Cierra la aplicación con `Ctrl+C`.
2. Conserva estos elementos de tu instalación actual:

   - `.env`
   - `smart_access.db`
   - carpeta `qrcodes`
   - carpeta `static/uploads`

3. Como respaldo adicional, ejecuta dentro de la carpeta actual:

```powershell
Copy-Item smart_access.db smart_access.respaldo-antes-v3.db
```

## Instalar la actualización

Descomprime el paquete V3 y copia su contenido sobre:

```text
C:\Users\chach\Documents\smart_access_university
```

Acepta reemplazar el código, las plantillas y los archivos estáticos. No reemplaces tu `.env` ni tu base `smart_access.db`.

Después abre PowerShell en esa carpeta y ejecuta:

```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python migrate.py
python app.py
```

`python migrate.py` agrega las columnas de papelera y la bitácora. Conserva todos los datos previos. No ejecutes `seed.py` durante una actualización.

## Uso de los botones

### Alumnos

1. Entra a **Panel → Alumnos**.
2. Pulsa el icono rojo de papelera en la fila.
3. Confirma la acción.
4. Para recuperar al alumno, abre **Papelera**, pulsa **Restaurar** y luego activa su credencial desde el perfil si corresponde.

Al borrar un alumno, su QR deja de autorizar accesos inmediatamente. Sus registros anteriores permanecen vinculados.

### Registros

1. Entra a **Panel → Registros**.
2. Pulsa el icono rojo de papelera en el movimiento.
3. El movimiento deja de contar en entradas, salidas, ocupación y exportaciones normales.
4. Usa **Papelera → Restaurar** para devolverlo al historial y recalcular las métricas.

### Jornadas

1. Entra a **Panel → Jornadas**.
2. Pulsa el botón de ojo para consultar métricas, notas y movimientos de cualquier fecha.
3. En una jornada histórica, pulsa el icono rojo para moverla a la papelera.
4. Abre **Papelera** para consultarla o restaurarla.

La jornada de hoy no puede borrarse. Primero debe finalizar el día y convertirse en histórica. Borrar una jornada no borra sus movimientos.

## Verificación rápida

Después de iniciar la aplicación:

1. Abre `http://127.0.0.1:5000/admin`.
2. Comprueba que Alumnos, Registros y Jornadas muestran el botón **Papelera**.
3. Abre una jornada con el botón de ojo.
4. Prueba borrar y restaurar un dato de prueba.

Si aparece un error de columna inexistente, detén la aplicación y vuelve a ejecutar `python migrate.py` desde la carpeta correcta.

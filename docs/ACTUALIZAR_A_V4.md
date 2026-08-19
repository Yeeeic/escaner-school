# Actualización V4: selección masiva, docentes, personal y grupos

## Respaldo y actualización

Detén la aplicación con `Ctrl+C` y ejecuta desde la carpeta actual:

```powershell
Copy-Item smart_access.db smart_access.respaldo-antes-v4.db
```

Descomprime la V4 sobre la instalación existente. Conserva `.env`, `smart_access.db`, `qrcodes` y `static/uploads`. Después ejecuta:

```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python migrate.py
python app.py
```

No ejecutes `seed.py`. La migración conserva los datos y agrega el directorio de personal, la relación con los registros y el campo de grupo.

## Seleccionar uno, varios o todos

En **Alumnos**, **Registros**, **Jornadas** y **Docentes y personal**:

1. Marca una o varias casillas de las filas.
2. Para marcar todas las filas que aparecen en pantalla, usa **Seleccionar todos los visibles**.
3. Pulsa **Borrar selección**.
4. Confirma la acción.

En la papelera, el mismo procedimiento muestra **Restaurar selección**. En Registros se seleccionan las 20 filas de la página actual; cambia de página para procesar otro bloque. La jornada actual no se puede seleccionar para borrar.

## Docentes y personal autorizado

Abre **Panel → Docentes y personal** y pulsa **Agregar personal**. Registra:

- número de empleado;
- nombre;
- tipo: docente, administrativo, seguridad, directivo, servicios o visitante autorizado;
- área o departamento;
- plantel y turno;
- fotografía y vigencia.

Al guardar se genera un QR firmado. Descárgalo desde el perfil. Se usa en el mismo escáner de los alumnos y alterna automáticamente entre entrada y salida.

## Grupos de alumnos

Al crear o editar un alumno aparece el campo **Grupo**. Ejemplos: `1A`, `3B`, `Sistemas-6`. Los alumnos existentes quedan inicialmente como `Sin grupo`.

La importación admite una columna opcional llamada `grupo`. Si falta, se asigna `Sin grupo` y el archivo anterior sigue siendo compatible.

## Personas dentro

La pantalla se divide en:

- **Alumnos por grupo**, con matrícula, plantel, hora de entrada y permanencia;
- **Docentes y personal autorizado**, agrupados por tipo de personal.

Los contadores superiores muestran alumnos, personal y total. La información se actualiza cada 15 segundos.

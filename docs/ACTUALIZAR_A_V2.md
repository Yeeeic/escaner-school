# Actualizar una instalación existente a la versión 2

Este procedimiento conserva alumnos, fotografías, códigos QR, administradores y movimientos históricos.

## 1. Detener y respaldar

En la terminal donde se ejecuta la aplicación, presione:

```text
Ctrl+C
```

Copie estos elementos a una carpeta de respaldo:

```text
smart_access.db
.env
static/uploads/
qrcodes/
```

## 2. Copiar la actualización

Extraiga el ZIP de la versión 2 en otra carpeta. Copie su contenido sobre la instalación actual y permita reemplazar los archivos de código.

No sustituya ni elimine:

```text
.env
smart_access.db
static/uploads/
qrcodes/
```

El paquete no contiene una base de datos ni un `.env`, por lo que una copia normal conserva esos archivos.

## 3. Añadir configuración

Agregue al final de su `.env`:

```env
CAPACITY_LIMIT=500
LONG_STAY_HOURS=10
STUDENT_DEFAULT_VALIDITY_DAYS=365
```

Ajuste `CAPACITY_LIMIT` al aforo operativo del plantel.

## 4. Aplicar la migración

Abra PowerShell en la carpeta actualizada:

```powershell
venv\Scripts\activate
pip install -r requirements.txt
python migrate.py
```

Debe aparecer:

```text
Esquema actualizado. Jornada AAAA-MM-DD: ABIERTA
Los alumnos y registros existentes se conservaron.
```

No ejecute `seed.py` durante la actualización.

## 5. Iniciar y verificar

```powershell
python app.py
```

Compruebe:

1. que puede iniciar sesión;
2. que **Registros** conserva días anteriores;
3. que aparece **Jornadas** en el menú;
4. que la jornada actual está abierta;
5. que **Alumnos** conserva fotografías y QR;
6. que un escaneo de prueba registra una entrada del día actual.

Si algo falla, detenga la aplicación y restaure el respaldo de `smart_access.db` y `.env`.

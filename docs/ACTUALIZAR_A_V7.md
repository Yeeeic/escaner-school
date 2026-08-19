# Actualización V7: Escáner School

Esta versión cambia la marca visible del sistema a **Escáner School** sin modificar alumnos, personal, QR ni registros.

## Actualizar

```powershell
cd C:\Users\chach\Documents\smart_access_university
Copy-Item smart_access.db smart_access.respaldo-antes-v7.db
```

Descomprime la V7 sobre la instalación existente, conserva `.env`, `smart_access.db`, `qrcodes` y `static/uploads`, y ejecuta:

```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python migrate.py
python app.py
```

No ejecutes `seed.py`.

## Compatibilidad

- No se cambia la carpeta `smart_access_university`.
- No se cambian los identificadores internos `SAU-...` de los QR.
- No se cambia el nombre de la base `smart_access.db`.
- No se cambia la cookie técnica de sesión.

Conservar estos nombres evita invalidar credenciales o perder compatibilidad. Aunque tu `.env` conserve `INSTITUTION_NAME=Smart Access University`, la aplicación lo reconoce como el valor anterior y muestra automáticamente **Escáner School**. Si utilizas el nombre real de otra institución en `INSTITUTION_NAME`, se respeta ese nombre personalizado en reportes y credenciales PDF.

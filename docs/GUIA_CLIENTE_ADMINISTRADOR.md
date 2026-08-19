# Guía de uso para el cliente y administrador

## Escáner School

Esta guía está dirigida al responsable de sistemas, personal de seguridad, control escolar y operadores autorizados que instalarán o administrarán el sistema.

## 1. Funciones disponibles

El cliente puede:

- operar una terminal con cámara integrada o USB;
- registrar, modificar, buscar y desactivar alumnos;
- generar, descargar y revocar códigos QR;
- consultar entradas, salidas y accesos rechazados;
- conocer quién permanece dentro del plantel;
- consultar estadísticas y actividad reciente;
- exportar información a CSV, Excel y PDF;
- usar el escáner en modo kiosco o pantalla completa.

## 2. Requisitos

- Windows 10 u 11 actualizado;
- Python 3.12 o posterior;
- Microsoft Edge o Google Chrome;
- cámara web integrada o USB;
- iluminación suficiente en el punto de acceso;
- permiso de Windows para utilizar la cámara.

Se recomienda una pantalla de al menos 1366 × 768, 8 GB de RAM y una cámara 720p.

## 3. Instalación inicial

Abra PowerShell dentro de `smart_access_university` y ejecute:

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env` y cambie:

```env
SECRET_KEY=UNA_CLAVE_ALEATORIA_LARGA
QR_SECRET_KEY=OTRA_CLAVE_ALEATORIA_DIFERENTE
ADMIN_INITIAL_PASSWORD=CONTRASEÑA_INICIAL_DEL_ADMINISTRADOR
```

Para generar cada clave aleatoria:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

No utilice la misma cadena para ambas claves. La contraseña debe tener al menos ocho caracteres.

Inicialice el sistema:

```powershell
python seed.py
```

Esto crea el usuario `admin`, diez alumnos ficticios, sus QR y `smart_access.db`.

## 4. Iniciar y cerrar el sistema

Cada vez que se encienda el equipo:

```powershell
cd RUTA\A\smart_access_university
venv\Scripts\activate
python app.py
```

Abra:

- escáner: `http://127.0.0.1:5000`;
- modo kiosco: `http://127.0.0.1:5000/kiosk`;
- administración: `http://127.0.0.1:5000/admin`.

Mantenga PowerShell abierto. Para detener el servidor, presione `Ctrl+C`.

## 5. Preparar la terminal

1. Conecte la cámara antes de iniciar el navegador.
2. Abra el modo kiosco.
3. Autorice el permiso de cámara.
4. Seleccione la cámara correcta en el menú superior.
5. Presione el botón de pantalla completa.
6. Muestre un QR de prueba.
7. Compruebe nombre, fotografía, resultado y movimiento.

La cámara elegida queda guardada en el navegador. Si se desconecta, el sistema intenta recuperarla automáticamente.

## 6. Indicadores de operación

- `CÁMARA CONECTADA`: la webcam está disponible.
- `SERVIDOR ACTIVO`: la interfaz se comunica con FastAPI.
- `BASE DE DATOS ACTIVA`: la aplicación inició correctamente.

La terminal también muestra personas dentro, entradas, salidas, rechazos y movimientos recientes.

## 7. Acceso administrativo

1. Abra `/admin`.
2. Escriba `admin`.
3. Use la contraseña definida en `ADMIN_INITIAL_PASSWORD` antes de ejecutar `seed.py`.
4. Seleccione **Iniciar sesión**.

La sesión dura como máximo ocho horas. Cierre sesión al abandonar el equipo.

## 8. Dashboard

El dashboard presenta:

- alumnos activos;
- personas dentro del plantel;
- entradas del día;
- accesos rechazados;
- entradas por hora;
- actividad de los últimos siete días;
- carreras con más accesos;
- movimientos recientes.

## 9. Registrar un alumno

1. Entre a **Alumnos**.
2. Seleccione **Registrar alumno**.
3. Capture matrícula, nombres y apellidos.
4. Capture carrera, plantel y turno.
5. Seleccione la fecha de vencimiento.
6. Adjunte una fotografía JPG, PNG o WebP de hasta 5 MB.
7. Mantenga activa **Credencial activa**.
8. Seleccione **Registrar y generar QR**.

El QR no almacena nombre, carrera, fotografía ni otros datos personales.

## 10. Descargar o imprimir un QR

1. Abra el perfil del alumno.
2. Seleccione **Descargar QR**.
3. Guarde el PNG.
4. Imprímalo con buena definición y conserve el margen blanco.

No recorte el borde, no deforme la imagen y evite cubiertas reflectantes.

## 11. Revocar y regenerar un QR

Use **Regenerar** cuando una credencial se pierda, sea robada o exista sospecha de copia.

Al regenerar:

- se crea un token nuevo;
- el QR anterior deja de ser válido;
- debe entregarse el nuevo PNG;
- el historial permanece intacto.

## 12. Editar, activar o desactivar

Desde el perfil puede corregir datos, cambiar vigencia, sustituir la fotografía o activar/desactivar la credencial.

Una credencial desactivada produce `ACCESO DENEGADO` y registra el motivo correspondiente sin borrar el historial.

## 13. Entrada, salida y cooldown

La primera lectura registra `ENTRADA`. Si el último movimiento autorizado fue una entrada, la siguiente lectura registra `SALIDA`; después vuelve a entrada.

El cooldown predeterminado es de diez segundos. Las lecturas repetidas durante ese periodo no crean movimientos adicionales.

Para modificarlo:

```env
ACCESS_COOLDOWN_SECONDS=10
```

Reinicie el servidor después del cambio.

## 14. Consultar registros

Abra **Registros** para filtrar por:

- nombre o matrícula;
- fecha inicial y final;
- carrera;
- entrada o salida;
- autorizado o denegado.

La columna **Motivo** identifica accesos vencidos, alterados, desactivados, inválidos o no registrados.

## 15. Exportar información

Después de aplicar filtros, utilice:

- **Excel** para análisis;
- **CSV** para integraciones;
- **PDF** para un reporte institucional.

El archivo conserva los filtros activos y admite hasta 10,000 movimientos.

## 16. Personas dentro

La sección muestra fotografía, nombre, matrícula, carrera, hora de entrada y tiempo transcurrido. Se actualiza cada quince segundos.

Si una persona abandona el plantel sin escanear, seguirá apareciendo dentro. El operador debe garantizar el registro tanto de entrada como de salida.

## 17. Alertas y acciones

| Mensaje | Acción recomendada |
|---|---|
| `ACCESO AUTORIZADO` | Permitir el paso y comparar la fotografía. |
| `CREDENCIAL VENCIDA` | Remitir a control escolar. |
| `CREDENCIAL DESACTIVADA` | No permitir el paso sin autorización. |
| `ALUMNO NO REGISTRADO` | Revisar el registro institucional. |
| `QR INVÁLIDO` | Solicitar la credencial oficial. |
| `QR ALTERADO` | Denegar el paso y reportar el incidente. |
| `LECTURA DUPLICADA IGNORADA` | No requiere acción. |
| `CÁMARA DESCONECTADA` | Revisar cable, permisos y otras aplicaciones. |

## 18. Respaldo

Realice respaldos con el servidor detenido:

1. Presione `Ctrl+C`.
2. Copie `smart_access.db` a una ubicación cifrada.
3. Registre fecha, responsable y ubicación.
4. Reinicie la aplicación.

Se recomienda un respaldo diario y una prueba de restauración mensual.

## 19. Seguridad operativa

- No comparta `.env` ni la contraseña administrativa.
- No publique la carpeta `qrcodes`.
- Restrinja el acceso físico al servidor.
- Cierre sesión al terminar.
- Mantenga Windows, Python y el navegador actualizados.
- No cambie `QR_SECRET_KEY` sin regenerar todas las credenciales.
- Defina políticas de privacidad y conservación de datos.

## 20. Apertura diaria

1. Encender computadora y cámara.
2. Iniciar el servidor.
3. Abrir modo kiosco.
4. Confirmar los indicadores.
5. Probar una credencial autorizada.
6. Verificar el movimiento en el dashboard.

La sección **Jornadas** se abre automáticamente al cambiar la fecha. Los contadores y la ocupación comienzan en cero, pero el archivo de días y la tabla de movimientos conservan toda la información anterior.

## 21. Cierre diario

1. Revisar accesos rechazados.
2. Investigar personas que continúen marcadas dentro.
3. Exportar el reporte cuando corresponda.
4. Abrir **Jornadas**, escribir una nota y seleccionar **Cerrar jornada**.
5. Confirmar que el escáner indique `JORNADA CERRADA`.
6. Cerrar sesión.
7. Detener el servidor.
8. Ejecutar el respaldo.

Si se cerró por error, use **Reabrir hoy**. Al llegar un día nuevo, el sistema cierra automáticamente jornadas anteriores pendientes y crea la jornada actual sin eliminar registros.

## 22. Importación masiva de alumnos

1. Abra **Alumnos → Importar lista**.
2. Descargue la plantilla CSV.
3. Complete hasta 500 filas sin cambiar los encabezados.
4. Use **Validar solamente** para detectar duplicados, vigencias o datos faltantes.
5. Corrija el archivo.
6. Vuelva a seleccionarlo y use **Validar e importar**.

Cada alumno válido recibe automáticamente su identificador y QR firmado. Las filas con error se muestran con su número y motivo.

## 23. Solución de problemas

### La cámara permanece negra

- permita la cámara desde el navegador;
- cierre Teams, Zoom u otras videollamadas;
- seleccione otra cámara;
- reconecte la cámara USB;
- recargue la página.

### El QR no se detecta

- limpie la cámara;
- mejore la iluminación;
- retire reflejos;
- centre el código;
- pruebe el PNG original.

### El panel no abre

- confirme que PowerShell muestre `Uvicorn running on http://127.0.0.1:5000`;
- compruebe que el puerto 5000 esté libre;
- revise `logs/smart_access.log`;
- reinicie el servidor.

### La contraseña no funciona

La contraseña válida es la que estaba en `ADMIN_INITIAL_PASSWORD` cuando se creó por primera vez la base. Cambiar `.env` posteriormente no modifica el hash existente.

## 24. Antes de producción

Se recomienda añadir HTTPS, PostgreSQL, migraciones Alembic, cuentas individuales, permisos por rol, autenticación de dispositivos, respaldos automáticos, monitoreo y una evaluación formal de privacidad y ciberseguridad.

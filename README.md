# Escáner School

Sistema funcional de control de acceso universitario mediante credenciales con QR firmado. Incluye escáner WebRTC en tiempo real, validación HMAC, cooldown anti-duplicados, registro automático de entrada/salida, panel administrativo, estadísticas, personas dentro, CRUD de alumnos y exportación CSV, Excel y PDF.

Proyecto de portafolio desarrollado por **Jean Carlos Bustos Ramos**, estudiante de Ingeniería en Computación.

> Los nombres y matrículas incluidos en `seed.py` son datos ficticios para demostración. El repositorio no contiene contraseñas, bases de datos, registros, fotografías ni códigos QR generados.

## Manuales de uso

- [Guía para el cliente y administrador](docs/GUIA_CLIENTE_ADMINISTRADOR.md)
- [Guía para el usuario final o alumno](docs/GUIA_USUARIO_ALUMNO.md)
- [Actualización segura desde la versión anterior](docs/ACTUALIZAR_A_V2.md)
- [Borrado seguro, papelera y consulta de jornadas](docs/ACTUALIZAR_A_V3.md)
- [Selección masiva, docentes, personal y grupos](docs/ACTUALIZAR_A_V4.md)
- [Filtros en gráficas y reporte detallado de entradas](docs/ACTUALIZAR_A_V5.md)
- [Credenciales PDF y centro de consultas rápidas](docs/ACTUALIZAR_A_V6.md)
- [Cambio de marca a Escáner School](docs/ACTUALIZAR_A_V7.md)

## Novedades de la versión 2

- jornadas diarias con apertura, cierre, reapertura y archivo histórico;
- reinicio automático de contadores y ocupación al cambiar de fecha, sin borrar registros;
- cierre automático de jornadas anteriores que hayan quedado abiertas;
- primera lectura de cada alumno en un día nuevo tratada como entrada;
- directorio de alumnos con indicadores de vigencia y calidad de datos;
- matrícula y fecha de vigencia sugeridas en el alta;
- vista previa de fotografía;
- importación de hasta 500 alumnos desde CSV o XLSX con QR automático;
- centro de atención para vencimientos, fotografías faltantes, estancia prolongada y rechazos repetidos;
- indicador preventivo de capacidad del plantel.

## Novedades de la versión 3

- botón de borrar con confirmación en Alumnos, Registros y Jornadas;
- papelera independiente con restauración para cada apartado;
- borrado lógico: no se destruyen alumnos, movimientos ni jornadas;
- bloqueo inmediato del QR cuando un alumno se mueve a la papelera;
- movimientos borrados excluidos automáticamente de métricas, aforo y reportes normales;
- consulta detallada de cada jornada con métricas, notas y lista completa de movimientos;
- protección de la jornada actual para que no pueda borrarse;
- bitácora interna con administrador, fecha, entidad y acción de borrar/restaurar.

## Novedades de la versión 4

- casillas para seleccionar uno, varios o todos los elementos visibles en Alumnos, Registros y Jornadas;
- borrado y restauración masiva con confirmación y protección CSRF;
- nuevo directorio de docentes y personal autorizado con alta, edición, fotografía, vigencia y papelera;
- QR firmado para docentes, administrativos, seguridad, directivos, servicios y visitantes autorizados;
- el mismo escáner registra entradas y salidas de alumnos y personal;
- campo académico `grupo` para alumnos, compatible con alta manual e importación;
- Personas dentro separa alumnos por grupo y personal por tipo;
- registros, jornadas y exportaciones identifican tanto alumnos como colaboradores.

## Novedades de la versión 5

- la gráfica de entradas y salidas permite elegir día, semana, mes o año;
- esa gráfica puede mostrar todas las personas o una carrera individual;
- la gráfica de carreras tiene selectores propios de periodo y carrera, sin alterar el resto del dashboard;
- Registros muestra eventos de entrada, personas únicas, alumnos/personal y carreras con actividad;
- botón para ver exclusivamente quiénes entraron usando los filtros actuales;
- reporte especializado de entradas en Excel, PDF y CSV;
- el Excel incluye una hoja de resumen por carrera y otra con fecha, hora, nombre, identificador, tipo, carrera, grupo y plantel.

## Novedades de la versión 6

- credencial PDF descargable para cada alumno, docente y miembro del personal;
- formato CR80 de dos caras, listo para imprimir al 100 %;
- frente con fotografía/iniciales, nombre, identificador, carrera/área, grupo, turno, plantel y vigencia;
- reverso con QR firmado, identificador público e instrucciones de seguridad;
- menú de consultas rápidas en Registros: entradas, salidas, rechazos, todos, hoy, semana, mes y personas sin salida;
- el Excel de entradas agrega una hoja de Personas únicas con primera entrada, última entrada y total de entradas.

### Actualizar una instalación existente

Conserva tu archivo `.env`, `smart_access.db`, fotografías y QR. Copia los archivos de esta versión sobre la instalación anterior y ejecuta:

```powershell
venv\Scripts\activate
pip install -r requirements.txt
python migrate.py
python app.py
```

`migrate.py` crea únicamente las estructuras nuevas. No elimina alumnos ni movimientos existentes. No vuelvas a ejecutar `seed.py` para actualizar.

## Arquitectura

- **FastAPI + Jinja2** entrega el kiosco, panel web y API REST.
- **SQLAlchemy 2 + SQLite (WAL)** conserva alumnos, administradores, dispositivos y auditoría.
- **WebRTC (`getUserMedia`)** captura la cámara directamente en Edge/Chrome. Esto es más estable en una PC Windows que abrir la webcam dentro del proceso del servidor: no bloquea FastAPI, permite cambiar de cámara USB y mantiene la interfaz fluida.
- **`BarcodeDetector`** decodifica localmente cuando el navegador lo soporta. El fallback envía un fotograma JPEG reducido al endpoint local, donde **OpenCV `QRCodeDetector`** lo procesa. Los datos personales nunca viajan en el QR.
- **HMAC-SHA256 + nonce revocable** protegen el QR. El contenido tiene la forma `student_id|nonce.firma`; la firma usa `QR_SECRET_KEY`. Regenerar un QR invalida el anterior.
- La lógica de dominio del backend decide si corresponde `ENTRADA` o `SALIDA`, revisa vigencia/estado, aplica cooldown y registra la auditoría. El navegador nunca decide el acceso.

## Requisitos

- Windows 10/11
- Python 3.12 o superior
- Microsoft Edge o Google Chrome actual
- Webcam integrada o USB

## Instalación en Windows

Abre PowerShell dentro de la carpeta del proyecto:

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` y reemplaza `SECRET_KEY`, `QR_SECRET_KEY` y `ADMIN_INITIAL_PASSWORD`. Puedes generar cada clave con:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Usa claves distintas para `SECRET_KEY` y `QR_SECRET_KEY`. La contraseña inicial debe tener al menos 8 caracteres.

Inicializa la base, el usuario `admin`, diez alumnos ficticios y sus QR:

```powershell
python seed.py
```

Ejecuta:

```powershell
python app.py
```

Abre:

- Escáner: <http://127.0.0.1:5000>
- Modo kiosco: <http://127.0.0.1:5000/kiosk>
- Panel: <http://127.0.0.1:5000/admin>
- Documentación API en desarrollo: <http://127.0.0.1:5000/api/docs>

El usuario inicial es `admin`; la contraseña es exactamente la configurada en `ADMIN_INITIAL_PASSWORD` al ejecutar `seed.py`.

## Primera prueba de acceso

1. Abre el escáner y concede permiso para usar la cámara.
2. Abre en otro dispositivo o imprime uno de los PNG de `qrcodes/`.
3. Coloca el QR dentro del marco. La primera lectura registra `ENTRADA`.
4. Mantener el mismo QR frente a la cámara no crea movimientos adicionales durante el cooldown.
5. Retira el QR. Tras el cooldown (10 segundos por defecto), vuelve a mostrarlo para registrar `SALIDA`.
6. Consulta el movimiento desde **Panel → Registros** y la ocupación en **Personas dentro**.

## Configuración `.env`

| Variable | Función |
|---|---|
| `APP_ENV` | Usa `production` para exigir claves explícitas y ocultar Swagger. |
| `SECRET_KEY` | Firma la cookie de sesión administrativa. |
| `QR_SECRET_KEY` | Firma criptográficamente todos los QR. Cambiarla invalida todos los QR existentes. |
| `ADMIN_INITIAL_PASSWORD` | Sólo la consume `seed.py`; nunca está fija en el código. |
| `DATABASE_URL` | SQLite por defecto; permite migrar a otro motor compatible con SQLAlchemy. |
| `ACCESS_COOLDOWN_SECONDS` | Ventana anti-duplicados, 10 segundos por defecto. |
| `TIMEZONE` | Zona IANA para fecha/hora local. |
| `DEVICE_IDENTIFIER` | Identificador almacenado en cada movimiento. |
| `SESSION_HTTPS_ONLY` | Pon `true` cuando se publique detrás de HTTPS. |
| `MAX_UPLOAD_MB` | Tamaño máximo de fotografía. |
| `CAPACITY_LIMIT` | Aforo de referencia para el indicador preventivo. |
| `LONG_STAY_HOURS` | Horas para marcar una estancia como prolongada. |
| `STUDENT_DEFAULT_VALIDITY_DAYS` | Vigencia sugerida al registrar un alumno. |

No subas `.env` al control de versiones. Ya está incluido en `.gitignore`.

## Uso del panel

### Jornadas

Cada fecha tiene una jornada independiente. A medianoche se archiva cualquier jornada anterior abierta y se crea una nueva con contadores en cero. Los registros continúan disponibles en **Registros** y en el archivo de **Jornadas**. Cerrar manualmente bloquea el escáner; puede reabrirse el mismo día si fue necesario continuar operaciones.

El botón de ojo abre la consulta completa del día. Una jornada histórica puede moverse a la papelera y restaurarse; la jornada actual está protegida.

### Alumnos

- Alta y edición con fotografía validada (JPG, PNG o WebP).
- Búsqueda por nombre/matrícula y filtros por carrera, plantel o estado.
- Activar/desactivar credencial sin borrar el historial.
- Descargar o regenerar QR. Regenerar rota el nonce e invalida copias anteriores.
- Borrar mueve al alumno a la papelera, desactiva su credencial y conserva su historial. Al restaurarlo queda inactivo hasta que un administrador decida activarlo.

### Registros

- Filtros por rango de fechas, nombre/matrícula, carrera, movimiento y resultado.
- Paginación web.
- Exportación de hasta 10,000 filas filtradas a CSV UTF-8, XLSX y PDF.
- Los QR inválidos, alterados, vencidos, desactivados y no registrados quedan auditados como `DENEGADO`. Las repeticiones dentro del cooldown no inflan el historial.
- Borrar un movimiento lo excluye del historial normal y de las métricas, pero puede restaurarse desde **Papelera**.

### Personas dentro

Se calcula con el último movimiento autorizado de cada alumno. Si el último es `ENTRADA`, aparece dentro; si es `SALIDA`, no aparece. La vista se actualiza cada 15 segundos.

## API REST

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/student/{matricula}` | Consulta datos públicos operativos del alumno. |
| `POST` | `/api/access/scan` | Procesa `{"qr_data":"..."}`; requiere token CSRF de la sesión del escáner. |
| `POST` | `/api/access/decode-frame` | Fallback OpenCV para un fotograma JPEG; requiere CSRF. |
| `GET` | `/api/access/recent` | Últimos movimientos. |
| `GET` | `/api/stats/today` | Entradas, salidas, rechazos y ocupación actual. |
| `GET` | `/api/inside` | Personas actualmente dentro. |

La UI obtiene el CSRF mediante la sesión firmada y lo envía en `X-CSRF-Token`. No desactives esta validación al integrar otros clientes; crea un esquema de autenticación de dispositivo para una instalación distribuida.

## Seguridad implementada

- bcrypt con costo 12 para contraseñas.
- Cookie de sesión firmada, `HttpOnly`, `SameSite=Lax`, vida de 8 horas y opción `Secure`.
- Protección CSRF en login, logout, formularios mutables y escaneo.
- ORM y consultas parametrizadas contra inyección SQL.
- Normalización, límites de longitud y validación de archivos por contenido.
- Firma HMAC comparada en tiempo constante; nonce aleatorio y revocable.
- CSP, `X-Frame-Options`, `nosniff`, política de cámara y manejo central de errores.
- Logs rotativos en `logs/smart_access.log` (5 copias de 2 MB).
- Los datos personales se consultan sólo después de validar el QR.

Para producción añade HTTPS, autenticación por dispositivo, copias de seguridad, rotación de secretos, migraciones Alembic, un proxy como IIS/Nginx y políticas institucionales de retención/privacidad.

## Pruebas

Con el entorno virtual activo:

```powershell
pytest -q
```

Las pruebas cubren firma válida, manipulación de QR, entrada, cooldown, credencial vencida y carga básica de web/API.

## Estructura

```text
smart_access_university/
├── app.py                  # Aplicación, middleware, logging y arranque
├── config.py               # Configuración por entorno
├── security.py             # bcrypt, sesión administrativa y CSRF
├── seed.py                 # Admin, dispositivo, 10 alumnos y QR
├── migrate.py              # Actualización segura del esquema existente
├── database/
│   ├── database.py         # Motor SQLAlchemy y sesión
│   └── models.py           # Tablas y relaciones
├── routes/
│   ├── scanner.py          # Pantallas escáner/kiosco
│   ├── admin.py            # Login y dashboard
│   ├── students.py         # CRUD, fotos y QR
│   ├── records.py          # Historial, ocupación y exportaciones
│   ├── days.py             # Apertura, cierre y archivo diario
│   └── api.py              # API JSON y fallback OpenCV
├── services/
│   ├── qr_service.py       # Generación y validación firmada
│   ├── access_service.py   # process_access y estadísticas
│   ├── day_service.py      # Ciclo diario y alertas operativas
│   ├── student_import_service.py # Importación CSV/XLSX
│   └── report_service.py   # CSV/XLSX/PDF
├── templates/              # Jinja2
├── static/css/style.css    # Diseño responsive completo
├── static/js/              # Cámara, escáner, panel y gráficas
├── qrcodes/                # QR generados (ignorados por Git)
├── reports/                # Espacio para reportes
├── logs/                   # Log rotativo
└── tests/                  # Pruebas pytest
```

## Solución de problemas

### La cámara no inicia

- Usa `127.0.0.1` o `localhost`; los navegadores exigen un contexto seguro para cámara y hacen excepción para localhost.
- En Windows: **Configuración → Privacidad y seguridad → Cámara** y habilita acceso para aplicaciones de escritorio.
- Cierra Teams, Zoom u otra aplicación que pueda monopolizar la webcam.
- Usa el selector superior para elegir la cámara USB.
- Revisa que el sitio no tenga el permiso bloqueado en Edge/Chrome y recarga.

### Detecta cámara pero no lee QR

- Mejora iluminación, evita reflejos, deja margen blanco alrededor del QR y no lo acerques demasiado.
- El sistema cae automáticamente a OpenCV si `BarcodeDetector` no está disponible.
- Prueba primero con los PNG generados en `qrcodes/`.

### `CREDENCIAL VENCIDA`, `DESACTIVADA` o `QR ALTERADO`

- Revisa estado y fecha en **Alumnos**.
- Si regeneraste el QR, sólo el PNG nuevo es válido.
- Si cambiaste `QR_SECRET_KEY`, vuelve a generar todos los QR desde el panel o ejecuta un script de rotación controlado.

### Error de zona horaria

Instala de nuevo `tzdata` con `pip install -U tzdata` y verifica `TIMEZONE=America/Mexico_City`.

### Base de datos bloqueada

SQLite usa WAL y timeout de 30 segundos. Para una sola terminal es suficiente. Detén instancias duplicadas de la aplicación. Para varios kioscos simultáneos migra a PostgreSQL.

### No puedo iniciar sesión

`seed.py` no cambia el hash si `admin` ya existe. Para un prototipo nuevo detén la app, respalda/elimina la base local y vuelve a ejecutar el seed; en producción implementa un flujo formal de cambio de contraseña.

## Licencia y datos

Este proyecto está disponible bajo la [licencia MIT](LICENSE). Puede utilizarse, modificarse y distribuirse conservando el aviso de copyright y la licencia.

Prototipo sin logotipos protegidos ni datos reales. Los alumnos de `seed.py` son ficticios. Antes de utilizarlo físicamente, realiza revisión legal, de privacidad, accesibilidad, amenazas y continuidad operativa.

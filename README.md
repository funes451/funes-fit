# Funes Fit

Aplicación web instalable (PWA) para organizar menú, compra, entrenamiento y progreso, con cuentas separadas para Funes y su amigo, sincronización entre móvil y ordenador y registro sin conexión.

> **Para usarla gratis desde el móvil sin tener el PC encendido, sigue [DESPLIEGUE_VERCEL.md](DESPLIEGUE_VERCEL.md).** Lo de abajo es para ejecutarla en tu propio ordenador.

- **Backend:** FastAPI + SQLAlchemy 2 + Alembic. Usa SQLite en local y PostgreSQL (Neon) en Vercel, según `DATABASE_URL`.
- **Frontend:** React 19 + TypeScript + Vite, service worker propio, cola offline en IndexedDB.
- **Cálculos:** funciones deterministas en `backend/app/calculos/` (energía, nutrientes, compra, progresión, tendencia). Ningún cálculo depende de una IA y no hace falta ninguna API de pago.

## 1. Instalación en Windows

Requisitos: Python 3.12 o posterior y Node.js 20 o posterior (con «Add to PATH» marcado al instalarlos).

1. Descomprime la carpeta `funes-fit` donde quieras.
2. Doble clic en `instalar.bat`. Crea el entorno, instala dependencias, compila la web y crea la base de datos.
3. Crea la cuenta de Funes (pide la contraseña sin mostrarla):

   ```
   .venv\Scripts\activate
   cd backend
   python -m app.cli crear-cuenta --email TU_CORREO --plan funes
   ```

   Esto carga explícitamente en **esa** cuenta el perfil, el menú del 23–29/11/2026, la rutina de cinco días y el objetivo provisional. Ninguna cuenta recibe estos datos por ser la primera en registrarse: el registro libre está cerrado.
4. Doble clic en `iniciar.bat` y abre <http://localhost:8000>.

`actualizar.bat` reinstala dependencias, recompila y migra (con copia de seguridad previa solo si hay migraciones nuevas).

## 2. Cuenta del amigo

```
python -m app.cli invitar --plan amigo --url https://TU-DIRECCION
```

Imprime un enlace de un solo uso que caduca en 72 h (`--horas` para cambiarlo). El enlace no contiene datos personales y **no se envía a nadie**: se lo pasas tú. Al abrirlo, tu amigo elige su correo y contraseña, entra en su cuenta y confirma su plan (nombre, fecha de inicio, alergias, alimentos que no le gustan, molestias, horarios, actividad diaria y presupuesto).

Hasta que confirma, el menú y la rutina aparecen como propuesta. No hereda tus exclusiones, tu experiencia ni tu fecha de inicio, y su peso de 55 kg se guarda como referencia del plan, no como medición.

**Pendiente:** el archivo `plan_gimnasio_nutricion_web.md` no llegó con los prompts. Sin él, sus sesiones (Torso A, Piernas y abdomen, Torso B ligero, Torso C) existen en el calendario pero **sin ejercicios**, y la app lo indica. Cuando esté el documento se rellenan `RUTINA_AMIGO` y `ADVERTENCIA_AMIGO` en `backend/app/datos_amigo.py` y se ejecuta:

```
python -m app.cli cargar-plan --email CORREO_DEL_AMIGO --plan amigo
```

La carga es idempotente: no duplica rutinas, comidas ni sesiones, y no borra sus cambios.

Para más cuentas sin plan: `--plan vacio`. Para abrir el registro libre temporalmente: `FUNES_PERMITIR_REGISTRO=1` (crea cuentas vacías).

## 3. Acceso desde el móvil (HTTPS)

Los service workers, la instalación como app y los avisos web necesitan HTTPS (salvo en `localhost`). Hay tres opciones:

| Opción | Coste orientativo | Disponible | Notas |
|---|---|---|---|
| PC de casa + [Tailscale](https://tailscale.com) con `tailscale serve` | Plan personal gratuito (compruébalo) | Solo con el PC encendido | Instala Tailscale en el PC y en los móviles, activa los certificados HTTPS en su panel y ejecuta `tailscale serve --bg 8000`. La dirección queda como `https://tu-pc.tu-red.ts.net`, solo accesible para dispositivos de tu red Tailscale. |
| Servidor siempre encendido (VPS) | Unos 5,5 € al mes sin IVA el más barato de Hetzner (CX23) tras sus subidas de 2026, con disponibilidad limitada; otras empresas tienen precios similares. Verifica el precio al contratar. | 24 h | Usa `despliegue/funes-fit.service` (systemd) y `despliegue/Caddyfile` (HTTPS automático). Pon `FUNES_COOKIE_SEGURA=1`. Hace falta un dominio o subdominio (unos 10 € al año). Mantenimiento: actualizaciones del sistema y revisar las copias. |
| Mini PC o Raspberry Pi en casa + Tailscale | Compra única del equipo y unos pocos euros de luz al año | 24 h si no se apaga | Igual que la primera opción pero sin depender del PC principal. |

No se ha contratado ni publicado nada: la decisión es tuya.

**Si el servidor está en un PC que apagas:** mientras esté apagado no hay sincronización remota ni avisos. El móvil puede seguir mostrando el menú y la rutina ya cargados y guardar registros, que se envían al volver a encenderlo. No es un servicio de 24 h.

## 4. Instalar como app

- **iPhone (Safari):** Compartir → «Añadir a pantalla de inicio». Los avisos solo funcionan con la app instalada así y en iOS 16.4 o posterior.
- **Android (Chrome):** menú ⋮ → «Instalar aplicación».
- **Ordenador (Chrome o Edge):** icono de instalar en la barra de direcciones.

## 5. Avisos

1. Pon tu correo en `FUNES_VAPID_CONTACTO`. Las claves de avisos se generan solas la primera vez.
2. En la app: Perfil → Avisos → «Activar en este dispositivo», elige horas, días y la franja de silencio.
3. «Enviar prueba» manda un aviso real a los dispositivos de tu cuenta.

El planificador corre dentro del servidor (no depende de una pestaña abierta) y usa la hora de Madrid, cambios de horario incluidos. Cada aviso se envía como máximo una vez al día. Por defecto el texto es genérico para no mostrar nada privado en la pantalla bloqueada. Al cerrar sesión se borra la suscripción de ese dispositivo, y si otra cuenta se suscribe desde el mismo dispositivo, la anterior deja de recibir. No se garantiza la hora exacta de entrega ni que el aviso se lea.

Alternativa sin avisos web: Perfil → Avisos → «Descargar recordatorios para el calendario» (`.ics`).

## 6. Copias de seguridad y restauración

- `python -m app.cli copia` crea en `backend/datos/copias/` un `.zip` con la base de datos SQLite completa (todas las cuentas) y la carpeta de fotos privadas.
- Se hace una copia automática antes de cada migración, alta de cuenta, recarga de plan y restauración.
- Para restaurar, para el servidor y ejecuta `python -m app.cli restaurar ruta\a\la\copia.zip`. Antes se guarda una copia del estado actual. Luego vuelve a arrancar.
- Guarda copias fuera del PC (USB o nube cifrada). La carpeta `backend/datos/` contiene datos de salud: no la compartas.
- `python -m app.cli verificar` muestra un resumen por cuenta para comprobar que todo está en su sitio.
- Cada usuario puede exportar sus propios datos (JSON y CSV) e importarlos desde Perfil → Tus datos. La importación no borra ni sobrescribe nada.

## 7. Variables de entorno (`backend/.env`)

| Variable | Por defecto | Uso |
|---|---|---|
| `FUNES_DATOS` | `backend/datos` | Base de datos, fotos y copias |
| `FUNES_URL_BD` o `DATABASE_URL` | SQLite en `FUNES_DATOS` | Dirección de PostgreSQL (la de Neon vale tal cual) |
| `FUNES_CLAVE_ADMIN` | vacía | Activa la pantalla `/#/admin` para crear cuentas e invitaciones desde la web |
| `FUNES_CLAVE_CRON` | vacía | Clave para que un cron externo llame a `/api/avisos/procesar` |
| `FUNES_FOTOS_EN_BD` | sí con PostgreSQL | Guarda las fotos dentro de la base de datos |
| `FUNES_COOKIE_SEGURA` | `0` | `1` cuando se sirve por HTTPS |
| `FUNES_PERMITIR_REGISTRO` | `0` | Registro libre (cuentas vacías) |
| `FUNES_DURACION_SESION_DIAS` | `30` | Duración de la sesión |
| `FUNES_AVISOS_ACTIVOS` | `1` | Planificador de avisos |
| `FUNES_VAPID_PUBLICA` / `FUNES_VAPID_PRIVADA` | vacías | Opcionales: si faltan, el servidor genera las claves de avisos y las guarda en la base de datos |
| `FUNES_VAPID_CONTACTO` | `mailto:admin@localhost` | Correo de contacto para los avisos |

## 8. Seguridad y privacidad

- Contraseñas con Argon2, sesiones en cookie `HttpOnly` y `SameSite=Lax`, límite de intentos (5 por correo y 20 por IP cada 15 minutos) y segundo factor TOTP opcional con códigos de recuperación de un solo uso.
- Cada consulta y cada cambio se filtran en el servidor por el usuario de la sesión. El servidor nunca usa un identificador de usuario enviado por el navegador para decidir qué datos se leen.
- Las peticiones que modifican datos exigen una cabecera propia, como protección CSRF.
- Las fotos se guardan con nombre aleatorio y solo se sirven con sesión, sin caché pública.
- No hay credenciales por defecto, analítica ni envío de datos a terceros. No hay IA integrada.
- En el dispositivo, la cola offline y la caché de datos van separadas por cuenta. Al cerrar sesión se borra la caché de datos, y los registros pendientes se quedan guardados para esa cuenta y solo se envían cuando vuelve a entrar. El servidor rechaza una cola que pertenezca a otra cuenta. Límite: esos pendientes no van cifrados en el almacenamiento del navegador.

## 9. Pruebas

```
.venv\Scripts\activate
cd backend
pip install -r requirements-pruebas.txt
python -m pytest
cd ..\frontend
npm test
```

Ejecutadas en esta entrega: **85 pruebas del backend, que pasan tanto con SQLite como con PostgreSQL 16, y 5 del frontend**, más un recorrido real en Chrome (pantalla de móvil de 360 px y ordenador) contra una simulación de Vercel con PostgreSQL. Ver `PROGRESO.md`.

Para lanzar las pruebas contra PostgreSQL: `FUNES_PRUEBAS_BD=postgresql://usuario@localhost/base python -m pytest`.

## 10. Estructura

```
backend/app/calculos/      energía, nutrición, compra, entrenamiento, progreso, fechas, números
backend/app/rutas/         auth, perfil, menu, cocina (recetas/alimentos/productos/despensa), gym, progreso, sync, avisos, cuenta
backend/app/servicios/     núcleo de consultas, registros sincronizables, exportación
backend/app/datos_iniciales.py, datos_amigo.py, semilla.py, semilla_amigo.py
backend/migraciones/       Alembic
frontend/src/              App, cola offline, pantallas
frontend/public/sw.js      service worker (caché, avisos)
public/                    web compilada (la sirve Vercel o el propio servidor)
server.py, pyproject.toml, vercel.json   configuración para Vercel
```

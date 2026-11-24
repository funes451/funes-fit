# Publicar Funes Fit en Vercel gratis

Resultado: una dirección `https://tu-proyecto.vercel.app` que se abre desde el móvil y el ordenador sin tener el PC encendido.

Piezas, todas con plan gratuito (revisa sus condiciones al darte de alta):

- **GitHub**: guarda el código.
- **Vercel** (plan Hobby): publica la web y la API.
- **Neon**: base de datos PostgreSQL. Se crea desde el propio Vercel.
- **cron-job.org**: llama a la app cada 5 minutos para que salgan los avisos. Sin esto la app funciona igual, pero sin avisos.

## 1. Subir el código a GitHub

1. Crea una cuenta en <https://github.com> si no tienes.
2. Instala **GitHub Desktop** (<https://desktop.github.com>). Es más fácil que la web, que no deja subir más de 100 archivos de golpe.
3. En GitHub Desktop: *File → Add local repository* → elige la carpeta `funes-fit` descomprimida → te dirá que no es un repositorio → *create a repository* → *Create repository*.
4. Pulsa **Publish repository**. Deja marcado **Keep this code private**.

## 2. Crear el proyecto en Vercel

1. Entra en <https://vercel.com> con tu cuenta de GitHub. Elige el plan **Hobby**.
2. *Add New… → Project* → importa el repositorio `funes-fit`.
3. No cambies nada de la configuración (Vercel detecta FastAPI solo) y pulsa **Deploy**.
4. Al terminar, la API responde «Falta conectar la base de datos». Es lo esperado: es lo que se hace en el paso siguiente.

## 3. Conectar la base de datos

1. En el proyecto de Vercel: pestaña **Storage** → **Create Database** → **Neon** (Postgres) → plan gratuito, región Europa (Frankfurt).
2. Conéctala al proyecto. Vercel añade automáticamente la variable `DATABASE_URL`.

## 4. Añadir las claves

En el proyecto: *Settings → Environment Variables*. Añade estas tres, para todos los entornos:

| Nombre | Valor |
|---|---|
| `FUNES_CLAVE_ADMIN` | Una contraseña larga inventada (20 caracteres o más). Solo sirve para crear cuentas. |
| `FUNES_CLAVE_CRON` | Otra contraseña larga distinta, para los avisos. |
| `FUNES_VAPID_CONTACTO` | `mailto:tu-correo@ejemplo.com` |

Luego, en *Deployments*, abre el último despliegue → menú ⋯ → **Redeploy**.

Al arrancar, la app crea sola las tablas de la base de datos y las claves de los avisos. No hay que ejecutar nada más.

## 5. Crear tu cuenta y la de tu amigo

1. Abre `https://tu-proyecto.vercel.app/#/admin`.
2. Escribe la `FUNES_CLAVE_ADMIN` y pulsa **Comprobar**.
3. **Crear cuenta** → plan **Plan de Funes** → tu correo y tu contraseña. Así se carga tu menú, tu rutina y tu perfil en tu cuenta.
4. **Invitar a tu amigo** → **Generar enlace** → cópialo y pásaselo. Es de un solo uso y caduca en 72 h. Al abrirlo, él crea su cuenta y confirma su plan.

## 6. Abrirla en el móvil

- **iPhone (Safari):** abre la dirección, entra con tu cuenta, pulsa Compartir → **Añadir a pantalla de inicio**, y a partir de ahí ábrela desde el icono.
- **Android (Chrome):** menú ⋮ → **Instalar aplicación**.

## 7. Activar los avisos (opcional)

1. Crea una cuenta gratuita en <https://cron-job.org>.
2. *Create cronjob*:
   - **URL:** `https://tu-proyecto.vercel.app/api/avisos/procesar?clave=TU_FUNES_CLAVE_CRON`
   - **Execution schedule:** cada 5 minutos.
   - Si prefieres no poner la clave en la dirección, en *Advanced → Headers* añade `Authorization` con el valor `Bearer TU_FUNES_CLAVE_CRON` y quita `?clave=…` de la URL.
3. En la app: **Perfil → Avisos → Activar en este dispositivo**, elige las horas y pulsa **Enviar prueba**.

Los avisos pueden llegar hasta 5 minutos tarde (lo que tarde el cron en llamar). En iPhone solo funcionan con la app añadida a la pantalla de inicio.

## 8. Copias de seguridad

- Cada uno puede descargar sus datos desde **Perfil → Tus datos → Exportar todo (JSON)**. Hazlo de vez en cuando y guárdalo en tu nube.
- Neon guarda además su propio historial para restaurar la base de datos, con los límites que tenga su plan gratuito.

## 9. Actualizar la app

Cuando cambie el código, cópialo encima de la carpeta, abre GitHub Desktop → **Commit to main** → **Push origin**. Vercel publica la nueva versión solo, y si hay cambios en la base de datos los aplica al arrancar.

## Límites del plan gratuito

- Vercel Hobby es para uso personal, no comercial.
- Neon gratis tiene un espacio limitado. Las fotos se reducen en el móvil antes de subirse (máximo 4 MB cada una) y se guardan en la base de datos, de forma privada.
- La primera petición después de un rato sin uso puede tardar uno o dos segundos más.

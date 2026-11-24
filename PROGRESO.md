# Estado de Funes Fit

Última actualización: 24/11/2026.

## Hecho y probado

**Menú y compra**
- Semana del 23 al 29/11/2026 precargada con las 7 recetas del plan, más desayuno y merienda. La mezcla de verduras está concretada por tipo en cada receta, sin calabacín, purés ni morcilla.
- Los totales salen de los ingredientes. Las cantidades netas semanales coinciden con la tabla del plan: verduras 3.700 g, aceite 175 g, queso batido 3.500 g, etc.
- Los consumos guardan una copia de los valores con los que se registraron, así que editar una receta o un alimento no cambia el historial.
- Se puede registrar una comida como prevista (sin duplicados aunque se toque dos veces), una parte, otras cantidades, otra cosa o un extra. «Sin registro» se muestra como ausencia, no como cero.
- Se pueden sustituir comidas por recetas equivalentes, moverlas, cambiar la hora y las raciones. Cada cambio queda en el historial de versiones del menú.
- Ajuste de raciones a unas kcal objetivo, que se aplica solo al aceptarlo y recalcula la compra.
- La siguiente semana se puede generar como repetición programada o variando platos.
- Lista de la compra con despensa, merma (factor visible), peso escurrido, envases redondeados hacia arriba, sobrantes, secciones y estado comprado. Separa el coste de lo consumido del desembolso. Los precios desconocidos no cuentan como cero, y los dos precios de referencia de terceros aparecen como «orientativo».
- Cierre de semana: lo que sobra queda en la despensa.
- Modo «abaratar semana» con aceptación, importación de precios desde un ticket con revisión, impresión/PDF y CSV.
- Plan de cocina en dos tandas con normas de conservación (arroz como máximo 24 h, sobras 2 días o congelar).

**Rutina y registro**
- Distribución de cinco días o de lunes a viernes con volumen ajustado. La primera semana es de calibración, ampliada si hubo un parón largo.
- Progresión por dos sesiones en el máximo del rango con margen, siempre aceptada a mano.
- Editor de sesión con autoguardado, reanudación tras cerrar, cronómetro que aguanta bloquear el móvil, sustituciones, cambio de orden, series añadidas o quitadas y final parcial.
- Calendario con varias actividades por día (gimnasio, fútbol, recuperación, partido configurable cada semana). Se pueden reprogramar sin duplicados.

**Sincronización**
- Cola offline por cuenta con identificadores únicos, fusión de guardados, reintentos y versión base. Probado: sin conexión → reconexión → otro dispositivo, con una sola aplicación de cada operación y peticiones simultáneas sin duplicados.
- Los conflictos guardan las dos versiones para que el usuario elija.

**Progreso y avisos**
- Peso con puntos originales y media semanal (con 3 pesajes o más), medidas, fotos privadas, cargas, diario con campos propios y resumen semanal.
- Propuestas de ajuste para perder, mantener y ganar, siempre con aceptación. Se detienen si hay señales de alerta.
- Objetivos con fecha de vigencia que nunca se aplican al pasado.
- Web Push con planificador en el servidor, hora de Madrid (probados los cambios de horario), franja de silencio, sin duplicados, usuario correcto y alternativa `.ics`.

**Multiusuario**
- Altas por comando o por invitación de un solo uso con caducidad. Registro libre cerrado.
- Aislamiento probado en recetas, comidas, compra, despensa, medidas, fotos, exportación y sincronización. Borrar la cuenta del amigo no toca la de Funes.
- Perfil del amigo con modo «ganar», hitos de 60 y 65 kg, objetivos del documento (2.900 kcal; 110 g de proteína, 400 g de hidratos, 95 g de grasas y unos 30 g de fibra), menú propuesta de 7 días con snack opcional, batido como receta alternativa (no sumado por defecto) y adaptación de 2 semanas con 1–2 series.

**Despliegue en Vercel**
- PostgreSQL (Neon) mediante `DATABASE_URL`, con migraciones automáticas al arrancar protegidas con un bloqueo para que dos instancias no migren a la vez.
- Fotos guardadas en la base de datos (reducidas en el móvil antes de subirse) y claves de avisos generadas y guardadas en la base de datos.
- Avisos lanzados por un cron externo con clave, y pantalla `/#/admin` para crear cuentas e invitaciones.
- IP real detrás del proxy para limitar intentos, y cookie segura.
- Si falta la base de datos, la API lo avisa con un mensaje claro en lugar de guardar en un disco que se borra.

## Verificación ejecutada

- `pytest`: 85 pruebas correctas con SQLite y las mismas 85 con PostgreSQL 16 (cálculos, menú, compra, registros, sincronización, seguridad, avisos, exportación, amigo y despliegue).
- Simulación local de Vercel (`VERCEL=1` + PostgreSQL): arranque con migración automática, alta desde la administración, invitación, cron de avisos y recorrido completo de la interfaz sin errores.
- `vitest`: 5 pruebas correctas de la cola offline.
- Recorrido en Chrome a 360 px (móvil) y 1280 px (ordenador): sin desbordes horizontales ni errores de JavaScript. Se probaron sesión de gym reanudada tras recargar, registro sin conexión que se sincroniza al volver la red, invitación del amigo y aislamiento (el amigo no ve el peso de Funes).

## Pendiente o no verificable aquí

1. **Documento del amigo** (`plan_gimnasio_nutricion_web.md`): no se recibió. Faltan sus ejercicios, series, repeticiones, tiempos, notas y la advertencia sanitaria. No se han inventado.
2. **Envío real de avisos:** la lógica está probada con un enviador simulado. Que lleguen al móvil hay que comprobarlo en tu dispositivo, ya publicada con HTTPS.
9. **Despliegue real en Vercel y Neon:** no se ha podido hacer desde aquí (requiere tus cuentas). Está simulado localmente con la misma configuración.
3. **Precios de Mercadona:** no hay API oficial y no se consultó el catálogo. Los formatos de envase son orientativos y aparecen como «sin verificar».
4. **Escáner de código de barras y OCR de tickets:** no incluidos. Se puede buscar por código escrito a mano, y los tickets se pegan como texto con revisión.
5. **Apple Health:** no integrado (una web no puede leer HealthKit). Hay importación de medidas por CSV.
6. **Código QR para el TOTP:** se muestran la clave y un enlace `otpauth://`, sin imagen QR.
7. **Instalación real en Windows:** los `.bat` no se han ejecutado en Windows en este entorno.
8. Los datos de Funes que faltan (sexo para la fórmula, actividad y pasos, presupuesto, horarios, equipo, continuidad) se piden en Perfil. Mientras tanto, el objetivo es la media de la plantilla, marcada como provisional.

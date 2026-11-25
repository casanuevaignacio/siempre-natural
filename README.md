# Siempre Natural

Tienda web para administrar un catálogo y registrar pedidos sin pagos en línea.
En una instalación local nueva, agrega productos y precios desde Django Admin;
el blueprint de Render incluye un catálogo público inicial para el primer deploy.

## Requisitos

- Python 3.12 a 3.14 (el backend usa Django 5.2).
- Node.js 20.19 o posterior y npm.
- Git.

## Configuración

Desde esta carpeta, crea tu configuración local. No guardes credenciales en Git.

```powershell
Copy-Item .env.example .env
```

Define `DJANGO_SECRET_KEY` en `.env` con una clave aleatoria generada localmente.
Por ejemplo, en PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Pega el resultado en `DJANGO_SECRET_KEY` dentro de `.env`. La configuración de
ejemplo activa `DJANGO_DEBUG=True` y WhiteNoise busca los estáticos del Admin
durante el desarrollo. Antes de producción, usa `DJANGO_DEBUG=False` y
`WHITENOISE_USE_FINDERS=False`, y ejecuta `collectstatic`.

La configuración también permite establecer un `DATABASE_URL` de PostgreSQL.
Déjalo vacío para usar SQLite durante el desarrollo. El número confirmado de
WhatsApp se configura en `WHATSAPP_BUSINESS_NUMBER` en `.env`; el ejemplo
versionado deja ese dato en blanco. La tienda solo genera enlaces con números
internacionales válidos. `VITE_API_URL` se configura en el mismo `.env` si el
backend se ejecuta en otra dirección.

El correo `STORE_CONTACT_EMAIL` recibe avisos de pedidos. El mismo SMTP se usa
para verificar cuentas, reclamar pedidos de invitado y recuperar contraseñas.
Configúralo con `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD` y `DEFAULT_FROM_EMAIL`; define también
`FRONTEND_BASE_URL` para que los enlaces de verificación y recuperación apunten
al frontend correcto. Para Gmail, usa una contraseña de aplicación y guárdala
solo en `.env`, nunca en Git; no uses ni compartas la contraseña habitual. Sin
SMTP, los pedidos se guardan, pero los correos de cuenta y los avisos no pueden
enviarse.

El enlace de WhatsApp permite que el cliente inicie el contacto manualmente.
Los avisos automáticos de pedidos por WhatsApp requieren configurar la API
oficial de WhatsApp Business; usar la aplicación del teléfono no basta.

## Backend Django

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\manage.py migrate
python backend\manage.py createsuperuser
python backend\manage.py runserver
```

Admin: <http://127.0.0.1:8000/admin/>
API: <http://127.0.0.1:8000/api/>

## Costos y márgenes de gestión

En Django Admin, registra cada compra desde **Compras de productos**. Ingresa
la cantidad en kilogramos para productos a granel o en unidades para productos
por presentación, junto con el costo total y la fecha. Puedes incluir flete o
envases en ese costo total si quieres que formen parte del costo del producto.

En **Catálogo → Productos → Planilla de precios y costos**, puedes descargar un
Excel con dos hojas: **Precios de venta** y **Compras y costos**. En la primera
hoja edita precio de venta, tramo de 250 g y costo actual por kg o por unidad.
En la segunda puedes revisar y corregir compras individuales. Edita las celdas
amarillas y carga el archivo en la misma página. Para agregar o borrar una
compra usa el Admin; borrar filas de Excel no elimina registros.

Al marcar un pedido como **Completado**, el sistema guarda el costo actual del
producto. Si no se ha indicado ese costo, usa como alternativa el costo promedio
ponderado de las compras registradas hasta esa fecha. El costo queda congelado
para conservar el margen histórico; editar después el costo actual o las
compras no cambia pedidos completados anteriormente. Si no hay costo actual ni
compras anteriores, el costo y el margen quedan sin determinar.

El reporte está en **Pedidos → Ver márgenes** y muestra ventas completadas,
costos registrados, utilidad bruta y margen por producto en un rango de fechas.
Incluye gráficos de ventas y utilidad, productos con mejor margen, mayor
utilidad y rankings por cantidad de pedidos completados. Los productos activos
sin ventas se muestran con cero pedidos en el ranking de menor movimiento. Estos
rankings cuentan pedidos que incluyeron el producto, no comparan kilogramos con
unidades.
Solo lo ven los usuarios con el permiso **Puede ver el reporte de márgenes**
(`orders.view_margin_report`); asígnalo desde **Administración → Usuarios**.
El enlace también aparece en el inicio del Admin para esos usuarios.
Los pedidos completados no necesariamente están pagados, y este reporte no
incluye gastos generales ni reemplaza la contabilidad tributaria.

La cuenta de superusuario de desarrollo es local y no se distribuye con el
código. Si ya existe una cuenta en tu instalación, establece o cambia su
contraseña localmente en una terminal interactiva:

```powershell
Set-Location backend
python manage.py changepassword <nombre_de_usuario>
```

No uses contraseñas débiles ni compartas credenciales por el chat. En una
instalación nueva crea su superusuario con
`python manage.py createsuperuser`.

Los endpoints públicos son `GET /api/categories/`, `GET /api/products/`,
`GET /api/products/{slug}/`, `GET /api/store-config/` y `POST /api/orders/`.
Los pedidos de invitado requieren correo electrónico. Los clientes pueden crear
una cuenta en `POST /api/customer/register/`; deben verificar el correo antes de
iniciar sesión y ver `GET /api/customer/orders/`. Al verificarlo, los pedidos
anteriores de invitado asociados a esa dirección se vinculan a la cuenta. Las
rutas `/api/customer/login/`, `/api/customer/logout/`,
`/api/customer/password/reset/` y
`/api/customer/password/reset/confirm/` administran la sesión y la recuperación
de acceso. El botón para buscar pedidos anteriores envía un enlace de
confirmación al correo. Si el cliente elimina la cuenta, los datos personales
de sus pedidos se anonimizan y se conservan los importes, productos y estados.
La API solo devuelve productos activos y disponibles. El precio y total del
pedido se calculan en el servidor a partir de los precios vigentes al registrar
la solicitud. `GET /api/wholesale/prices/` publica la lista mayorista vigente.
Las operaciones administrativas y los datos de clientes siguen protegidos.

## Lista mayorista

La tarifa mayorista se conserva separada de los precios minoristas. El Excel con
la tarifa vigente se importa con el comando:

```powershell
Set-Location backend
python manage.py load_wholesale_workbook --xlsx "C:\ruta\precios-mayorista.xlsx"
```

La tarifa aparece en la sección pública **Mayoristas** y también se administra
desde Django Admin. Los precios de esta lista son visibles para cualquier
visitante. Los productos y costos internos no se publican en esa página.
Disponibilidad, cantidades y condiciones de compra se confirman con la tienda.

## Lista normal de precios

El CSV con los precios minoristas reales también está excluido de GitHub.
Conserva una copia segura local y cópiala a
`backend\catalog\data\lista_precios_normal_2026.csv` antes de importar. Para
cargar desde otra ruta local:

```powershell
Set-Location backend
python manage.py load_retail_prices --csv "C:\ruta-privada\lista_precios_normal_2026.csv"
```

La planilla contiene 157 productos en 13 categorías. Los productos por peso
admiten cantidades desde 50 g. Para cantidades menores a 1 kg se prorratea el
precio del tramo de 250 g cuando está disponible; si la planilla no indica ese
tramo, se prorratea el precio por kilogramo. Desde 1 kg se usa el precio por
kilogramo de la segunda columna. Los formatos especificados y los molinillos
se venden por presentación/unidad. Los dos productos sin ningún precio en la
planilla quedan sin publicar hasta que se confirme su valor.

La importación conserva la tarifa mayorista por separado, actualiza los nombres
de categorías coincidentes y retira del catálogo los productos que ya no están
en la lista sin borrar sus registros ni afectar pedidos anteriores. El catálogo
prioriza frutos secos, frutos semi secos, semillas, cereales y condimentos; las
demás categorías y los productos se ordenan alfabéticamente.

Desde **Catálogo → Productos → Planilla Excel de precios y costos** puedes
editar nombres, identificadores, categorías, unidades, formatos, precios y
costos. El ID identifica cada producto existente aunque cambien su nombre o
identificador. Para agregar productos, añade una fila sin ID; la importación
crea las categorías que aún no existan. Los productos que quites de la planilla
se desactivan en la tienda, pero sus registros y su historial de compras y
ventas se conservan.

Las fotos de producto incluidas en `frontend\public\images\products` se asignan
por slug en `frontend\src\components\ProductCard.tsx`. Si el producto tiene una
imagen cargada desde Django Admin, esa imagen tiene prioridad. Para agregar una
foto local, copia el archivo a esa carpeta y asocia su ruta al slug del producto.

## Frontend React

En otra terminal, desde esta carpeta:

```powershell
cd frontend
npm install
npm run dev
```

Abre <http://localhost:5173/>.

## Datos comerciales y operación

- Los productos y precios minoristas, la cobertura, los costos de despacho y el
  dominio siguen pendientes de confirmación por el negocio.
- Retiro y despacho se registran como modalidades solicitadas; el sistema no
  asume ni cobra costos de entrega.
- Al registrar un pedido, el cliente elige envase sin plástico o bolsa plástica.
  La preferencia queda guardada en el Admin y se incluye en el aviso a la tienda.
- WhatsApp permite coordinar cobertura y costos de despacho. La tienda confirma
  disponibilidad y total del pedido antes de enviar los datos para transferencia.
  Si el navegador no abre el enlace, el pedido queda guardado en el Admin.
- Los pedidos no constituyen pagos, facturación ni integración con el SII.
- El acceso al Admin requiere una cuenta creada con `createsuperuser`; no hay
  contraseñas predeterminadas. Asigna permisos y cuentas individuales al operar.
- El Admin conserva datos de contacto mínimos necesarios para tramitar pedidos.
  Protege el acceso y la base de datos en cualquier entorno compartido.

## Pruebas y verificaciones

```powershell
python backend\manage.py check
Set-Location backend
python manage.py test
Set-Location ..\frontend
npm run build
```

## Despliegue público en Render

El archivo `render.yaml` crea un servicio Docker con frontend React y backend
Django en el mismo dominio, más una base PostgreSQL. En la primera puesta en
marcha ejecuta migraciones, carga un catálogo público inicial si la base está
vacía y crea el usuario administrador indicado en las variables de entorno.
El fixture incluye categorías, productos y precios publicados; excluye costos
internos, compras, pedidos y cuentas de clientes. Las fotos del sitio viajan en
el frontend. La carga de fotos desde Admin permanece desactivada en producción.

Para publicarla:

1. Sube este repositorio a GitHub.
2. En Render, elige **New → Blueprint**, conecta el repositorio y aplica el
   `render.yaml` de la raíz.
3. Cuando Render lo solicite, configura un usuario, correo y contraseña únicos
   para `DJANGO_BOOTSTRAP_ADMIN_USERNAME`, `DJANGO_BOOTSTRAP_ADMIN_EMAIL` y
   `DJANGO_BOOTSTRAP_ADMIN_PASSWORD`. Ingresa el número comercial de WhatsApp
   internacional en `WHATSAPP_BUSINESS_NUMBER`.
4. Al terminar el deploy, abre el dominio del servicio; el Admin queda en
   `/admin/`.

El blueprint usa planes gratuitos para facilitar una primera prueba. Render
apaga el servicio web gratuito tras 15 minutos sin tráfico y la base PostgreSQL
gratuita vence a los 30 días; luego de otros 14 días puede eliminarse junto con
los datos. Antes de recibir pedidos reales, cambia la base a un plan pagado y
mantén respaldos. Consulta las [limitaciones de Render Free](https://render.com/docs/free).

El frontend y Django comparten origen para que carrito, pedidos y sesiones
funcionen sin cookies de terceros. Si agregas un dominio propio, actualiza
`DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`,
`DJANGO_CSRF_TRUSTED_ORIGINS` y `FRONTEND_BASE_URL` en Render. Para verificación
de cuentas, recuperación de contraseñas y avisos por correo, configura SMTP en
las variables `EMAIL_*`; sin SMTP, esas notificaciones no se envían.

## Antes de producción

En la plataforma de alojamiento, configura las variables como secretos o
variables privadas; no subas `.env`. Usa una `DJANGO_SECRET_KEY` aleatoria y
exclusiva para producción (al menos 43 caracteres), `DJANGO_DEBUG=False`, y
establece `DJANGO_ALLOWED_HOSTS` con el dominio del backend. Configura
`DJANGO_CORS_ALLOWED_ORIGINS` y `DJANGO_CSRF_TRUSTED_ORIGINS` con los orígenes
HTTPS reales del frontend, y `DATABASE_URL` con la URL privada de PostgreSQL.
En producción, Django ahora se niega a iniciar si faltan estos valores, si se
usan orígenes HTTP o si la base de datos es SQLite.

Las fotos actuales del catálogo están incluidas en el frontend y se publican
junto con él; no necesitan un volumen de medios. Para esta primera publicación,
la carga de imágenes desde Django Admin queda deshabilitada automáticamente en
producción. Antes de habilitarla, configura almacenamiento externo de archivos
y la entrega pública de esas imágenes (por ejemplo, un servicio compatible con
S3); un disco persistente de Render por sí solo no hace públicas las rutas de
medios en esta aplicación.

Activa HTTPS en el alojamiento y conserva `DJANGO_SECURE_SSL_REDIRECT=True`.
Si la plataforma termina HTTPS en un proxy, activa
`DJANGO_TRUST_X_FORWARDED_PROTO=True` únicamente si confías en ese proxy y este
establece `X-Forwarded-Proto`. Los cookies de sesión y CSRF se marcan como
seguros automáticamente con `DJANGO_DEBUG=False`. Mantén HSTS desactivado
(`DJANGO_SECURE_HSTS_SECONDS=0`) hasta comprobar HTTPS con el dominio final;
después puedes aumentarlo gradualmente. Si frontend y backend están en sitios
distintos, revisa `DJANGO_COOKIE_SAMESITE` y usa `None` solo con HTTPS.

Antes de abrir el sitio al público, ejecuta `python backend\manage.py check
--deploy`, revisa sus avisos y verifica respaldos, acceso a datos personales,
límite de carga de imágenes y protección contra abuso de la API. No expongas el
servidor de desarrollo. Una pasarela de pago compatible con Chile deberá
incorporarse posteriormente con credenciales en variables de entorno y pruebas
propias; esta versión no implementa pagos.

El middleware WhiteNoise entrega los archivos estáticos de Django. En desarrollo
usa los archivos encontrados en las aplicaciones; para producción, ejecuta
`python backend\manage.py collectstatic` durante el proceso de despliegue.

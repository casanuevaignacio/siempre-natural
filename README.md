# Siempre Natural

Tienda web local en español para administrar un catálogo y registrar pedidos sin
pagos en línea. El catálogo parte vacío: agrega productos y precios reales desde
Django Admin antes de publicarlos.

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
la solicitud. La sección privada usa `GET /api/wholesale/session/` para consultar
el estado de acceso, `POST /api/wholesale/login/` y
`POST /api/wholesale/logout/` para gestionar la sesión, y
`GET /api/wholesale/prices/` para consultar la tarifa únicamente con una sesión
de administrador o una cuenta del grupo **Mayoristas aprobados**.

## Lista mayorista

La tarifa mayorista se conserva separada de los precios minoristas. El CSV con
los precios reales está excluido de GitHub porque contiene información
comercial privada. Conserva una copia segura local y cópiala a
`backend\catalog\data\lista_mayorista_2026.csv` antes de importar. También
puedes indicar una ruta local explícita:

```powershell
Set-Location backend
python manage.py load_wholesale_prices --csv "C:\ruta-privada\lista_mayorista_2026.csv"
```

La tarifa se consulta en la sección **Mayoristas** de la tienda, con una cuenta
habilitada, y también desde Django Admin. Los productos mayoristas se mantienen
inactivos, sin precio minorista ni disponibilidad; no aparecen en el catálogo
público ni se pueden incluir en pedidos minoristas. El comando puede ejecutarse
nuevamente sin duplicar registros. Cuatro importes del PDF no tienen producto
asociado ($5.500, $11.000, $23.000 y $24.000), así que no se cargan sin confirmar
a qué productos corresponden. Esta lista no define mínimos de compra,
descuentos por volumen ni vigencia más allá de la etiqueta 2026 del documento.

Para autorizar a un comprador, entra a **Administración → Usuarios**, crea o
abre su cuenta y agrégala al grupo **Mayoristas aprobados**. La cuenta debe estar
activa y tener una contraseña establecida. Comparte con el cliente el nombre de
usuario y la contraseña de forma privada; la página **Mayoristas** permite
iniciar sesión y ver los precios, pero no ofrece registro público. Quitar al
usuario del grupo revoca el acceso. El catálogo mayorista es solo de consulta:
disponibilidad, cantidades y condiciones de compra se confirman con la tienda.

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

## Antes de producción

En la plataforma de alojamiento, configura las variables como secretos o
variables privadas; no subas `.env`. Usa una `DJANGO_SECRET_KEY` aleatoria y
exclusiva para producción (al menos 50 caracteres), `DJANGO_DEBUG=False`, y
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

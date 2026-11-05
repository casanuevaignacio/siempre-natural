from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import CustomerAccount
from catalog.models import Category, Product
from .models import Order


class OrderCreationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        category = Category.objects.create(name="Semillas", slug="semillas")
        self.product = Product.objects.create(
            category=category,
            name="Producto disponible",
            slug="producto-disponible",
            price=Decimal("9000"),
            price_250g=Decimal("2250"),
            sale_unit=Product.SaleUnit.KILOGRAM,
            is_active=True,
            is_available=True,
        )
        self.payload = {
            "customer_name": "Cliente de prueba",
            "customer_phone": "+56900000000",
            "customer_email": "cliente@example.com",
            "delivery_mode": "pickup",
            "items": [{"product_id": self.product.id, "quantity_grams": 50}],
        }

    def test_order_uses_database_price_and_saves_snapshot(self):
        payload = {**self.payload, "total": 1}
        response = self.client.post("/api/orders/", payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total"], "450")
        order = Order.objects.get(pk=response.data["id"])
        item = order.items.get()
        self.assertEqual(item.unit_price, Decimal("2250"))
        self.assertEqual(item.pricing_tier, "250g")
        self.assertEqual(item.subtotal, Decimal("450"))

    def test_unverified_customer_can_place_order_and_see_it_in_history(self):
        user = get_user_model().objects.create_user(
            username="unverified-customer",
            email="cliente@example.com",
            password="Strong-password-923!",
        )
        CustomerAccount.objects.create(
            user=user,
            email="cliente@example.com",
            email_verified=False,
        )
        self.client.force_login(user)
        self.payload["customer_email"] = "different@example.com"

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["id"])
        self.assertEqual(order.customer_id, user.customer_account.pk)
        self.assertEqual(order.customer_email, "cliente@example.com")
        history_response = self.client.get("/api/customer/orders/")
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(str(history_response.data[0]["id"]), str(order.pk))

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_HOST_USER="store@example.com",
        EMAIL_HOST_PASSWORD="test-only",
        DEFAULT_FROM_EMAIL="store@example.com",
        STORE_CONTACT_EMAIL="store@example.com",
        STORE_NAME="Siempre Natural",
    )
    def test_order_sends_store_email_without_customer_rut(self):
        self.payload.update(
            {
                "customer_email": "customer@example.com",
                "customer_rut": "12.345.678-9",
                "delivery_mode": "shipping",
                "delivery_address": "Calle de prueba 123",
            }
        )

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["email_notification_sent"])
        self.assertEqual(len(mail.outbox), 1)
        notification = mail.outbox[0]
        self.assertEqual(notification.to, ["store@example.com"])
        self.assertIn("Cliente de prueba", notification.body)
        self.assertIn("Calle de prueba 123", notification.body)
        self.assertIn("Producto disponible", notification.body)
        self.assertNotIn("12.345.678-9", notification.body)

    @override_settings(
        EMAIL_HOST="",
        STORE_CONTACT_EMAIL="store@example.com",
    )
    def test_order_remains_saved_when_email_is_not_configured(self):
        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["email_notification_sent"])
        self.assertEqual(Order.objects.count(), 1)

    def test_order_switches_to_kilogram_price_at_one_kilogram(self):
        self.payload["items"] = [
            {"product_id": self.product.id, "quantity_grams": 1000}
        ]

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        item = Order.objects.get(pk=response.data["id"]).items.get()
        self.assertEqual(item.unit_price, Decimal("9000"))
        self.assertEqual(item.pricing_tier, "kg")
        self.assertEqual(item.subtotal, Decimal("9000"))

    def test_order_rejects_weight_below_minimum(self):
        self.payload["items"] = [
            {"product_id": self.product.id, "quantity_grams": 49}
        ]

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_order_uses_kilogram_rate_below_one_kilogram_without_250g_tier(self):
        self.product.price_250g = None
        self.product.save(update_fields=["price_250g"])
        self.payload["items"] = [
            {"product_id": self.product.id, "quantity_grams": 50}
        ]

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        item = Order.objects.get(pk=response.data["id"]).items.get()
        self.assertEqual(item.unit_price, Decimal("9000"))
        self.assertEqual(item.pricing_tier, "kg")
        self.assertEqual(item.subtotal, Decimal("450"))

    def test_shipping_requires_address(self):
        self.payload["delivery_mode"] = "shipping"
        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_rejects_unavailable_product(self):
        self.product.is_available = False
        self.product.save(update_fields=["is_available"])

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_rejects_product_without_retail_price(self):
        self.product.price = None
        self.product.save(update_fields=["price"])

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_guest_order_requires_email_for_history_claim(self):
        self.payload.pop("customer_email")

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_rejects_client_unit_for_weighted_product(self):
        self.payload["items"] = [{"product_id": self.product.id, "quantity_units": 1}]

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_normalizes_phone_number(self):
        self.payload["customer_phone"] = "+56 9 1234 5678"

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.get(pk=response.data["id"]).customer_phone, "+56912345678")

    def test_unit_order_uses_unit_price(self):
        self.product.sale_unit = Product.SaleUnit.UNIT
        self.product.price = Decimal("350")
        self.product.save(update_fields=["sale_unit", "price"])
        self.payload["items"] = [{"product_id": self.product.id, "quantity_units": 4}]

        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total"], "1400")
        item = Order.objects.get(pk=response.data["id"]).items.get()
        self.assertEqual(item.quantity_units, 4)
        self.assertEqual(item.quantity_grams, 0)


class OrderCsrfTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        category = Category.objects.create(name="CSRF", slug="csrf")
        product = Product.objects.create(
            category=category,
            name="Producto",
            slug="producto-csrf",
            price=Decimal("2000"),
            price_250g=Decimal("500"),
            is_active=True,
            is_available=True,
        )
        self.payload = {
            "customer_name": "Cliente",
            "customer_phone": "912345678",
            "customer_email": "csrf@example.com",
            "delivery_mode": "pickup",
            "items": [{"product_id": product.id, "quantity_grams": 50}],
        }

    def test_order_creation_requires_csrf_token(self):
        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Order.objects.exists())

    def test_csrf_token_allows_order_creation(self):
        token_response = self.client.get("/api/csrf/")
        token = token_response.data["csrf_token"]

        response = self.client.post(
            "/api/orders/",
            self.payload,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(token_response.status_code, 200)
        self.assertEqual(response.status_code, 201)


class AdminAccessTests(TestCase):
    def test_admin_requires_authentication(self):
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_admin_uses_store_branding_and_custom_styles(self):
        response = self.client.get("/admin/login/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Siempre Natural")
        self.assertContains(response, "Panel de administración")
        self.assertContains(response, "admin/css/siempre-natural.css")

    def test_admin_styles_are_available_without_debug_mode(self):
        from django.test import override_settings

        with TemporaryDirectory() as static_root:
            with override_settings(
                DEBUG=False,
                WHITENOISE_USE_FINDERS=True,
                STATIC_ROOT=static_root,
            ):
                response = self.client.get("/static/admin/css/siempre-natural.css")

        self.assertEqual(response.status_code, 200)

    def test_admin_logo_is_available(self):
        response = self.client.get("/static/img/logo-siempre-natural.png")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")

    def test_authenticated_admin_dashboard_uses_store_branding(self):
        user = get_user_model().objects.create_superuser(
            username="admin-visual",
            email="admin@example.test",
            password=None,
        )
        self.client.force_login(user)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Siempre Natural")
        self.assertContains(response, "admin/css/siempre-natural.css")

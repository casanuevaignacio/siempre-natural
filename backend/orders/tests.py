from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomerAccount
from catalog.models import Category, Product, ProductPurchase
from .admin import OrderAdmin
from .models import Order, OrderItem
from .services import snapshot_order_costs


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
            "packaging_preference": "no_plastic",
            "items": [{"product_id": self.product.id, "quantity_grams": 50}],
        }

    def test_order_uses_database_price_and_saves_snapshot(self):
        payload = {**self.payload, "total": 1}
        response = self.client.post("/api/orders/", payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total"], "450")
        self.assertEqual(
            response.data["packaging_preference"],
            "Envase sin plástico (opción sustentable)",
        )
        order = Order.objects.get(pk=response.data["id"])
        item = order.items.get()
        self.assertEqual(item.unit_price, Decimal("2250"))
        self.assertEqual(item.pricing_tier, "250g")
        self.assertEqual(item.subtotal, Decimal("450"))
        self.assertEqual(order.packaging_preference, "no_plastic")

    def test_order_requires_a_valid_packaging_preference(self):
        self.payload.pop("packaging_preference")
        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

        self.payload["packaging_preference"] = "paper"
        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

        self.payload["packaging_preference"] = ""
        response = self.client.post("/api/orders/", self.payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

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
        self.assertIn("Envase sin plástico", notification.body)
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
            "packaging_preference": "no_plastic",
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


class OrderMarginTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Margen", slug="margen")
        self.product = Product.objects.create(
            category=category,
            name="Producto con costo",
            slug="producto-con-costo",
            price=Decimal("9000"),
            price_250g=Decimal("2250"),
        )
        self.order = Order.objects.create(
            customer_name="Cliente",
            customer_phone="+56900000000",
            delivery_mode=Order.DeliveryMode.PICKUP,
            total=Decimal("2250"),
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            sale_unit=Product.SaleUnit.KILOGRAM,
            unit_price=Decimal("2250"),
            pricing_tier=OrderItem.PricingTier.PER_250G,
            quantity_grams=250,
            subtotal=Decimal("2250"),
        )

    def test_completion_captures_weighted_average_cost_and_freezes_it(self):
        completed_on = timezone.localdate()
        ProductPurchase.objects.create(
            product=self.product,
            purchased_on=completed_on - timedelta(days=2),
            purchase_unit=Product.SaleUnit.KILOGRAM,
            quantity=Decimal("2"),
            total_cost=Decimal("10000"),
        )
        ProductPurchase.objects.create(
            product=self.product,
            purchased_on=completed_on - timedelta(days=1),
            purchase_unit=Product.SaleUnit.KILOGRAM,
            quantity=Decimal("1"),
            total_cost=Decimal("6000"),
        )
        ProductPurchase.objects.create(
            product=self.product,
            purchased_on=completed_on + timedelta(days=1),
            purchase_unit=Product.SaleUnit.KILOGRAM,
            quantity=Decimal("10"),
            total_cost=Decimal("1"),
        )
        self.order.status = Order.Status.COMPLETED

        order_admin = OrderAdmin(Order, admin.site)
        order_admin.save_model(
            SimpleNamespace(),
            self.order,
            form=None,
            change=True,
        )
        order_admin.save_related(
            SimpleNamespace(),
            SimpleNamespace(instance=self.order, save_m2m=lambda: None),
            [],
            change=True,
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.unit_cost_snapshot, Decimal("5333.3333"))
        self.assertEqual(self.item.cost_subtotal, Decimal("1333"))
        self.assertIsNotNone(self.order.completed_at)

        ProductPurchase.objects.create(
            product=self.product,
            purchased_on=completed_on,
            purchase_unit=Product.SaleUnit.KILOGRAM,
            quantity=Decimal("100"),
            total_cost=Decimal("100"),
        )
        snapshot_order_costs(self.order)
        self.item.refresh_from_db()
        self.assertEqual(self.item.cost_subtotal, Decimal("1333"))

    def test_unit_products_use_weighted_cost_per_unit(self):
        self.product.sale_unit = Product.SaleUnit.UNIT
        self.product.save(update_fields=["sale_unit"])
        for quantity, cost in ((Decimal("4"), Decimal("1000")), (Decimal("1"), Decimal("300"))):
            ProductPurchase.objects.create(
                product=self.product,
                purchased_on=timezone.localdate(),
                purchase_unit=Product.SaleUnit.UNIT,
                quantity=quantity,
                total_cost=cost,
            )
        order = Order.objects.create(
            customer_name="Cliente",
            customer_phone="+56900000000",
            delivery_mode=Order.DeliveryMode.PICKUP,
            total=Decimal("1050"),
            status=Order.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            sale_unit=Product.SaleUnit.UNIT,
            unit_price=Decimal("350"),
            pricing_tier=OrderItem.PricingTier.PER_UNIT,
            quantity_units=3,
            subtotal=Decimal("1050"),
        )

        snapshot_order_costs(order)

        item.refresh_from_db()
        self.assertEqual(item.unit_cost_snapshot, Decimal("260.0000"))
        self.assertEqual(item.cost_subtotal, Decimal("780"))

    def test_missing_purchase_cost_remains_unavailable(self):
        self.order.completed_at = timezone.now()

        snapshot_order_costs(self.order)

        self.item.refresh_from_db()
        self.assertIsNone(self.item.unit_cost_snapshot)
        self.assertIsNone(self.item.cost_subtotal)

    def test_current_product_cost_takes_precedence_over_purchase_average(self):
        ProductPurchase.objects.create(
            product=self.product,
            purchased_on=timezone.localdate(),
            purchase_unit=Product.SaleUnit.KILOGRAM,
            quantity=Decimal("1"),
            total_cost=Decimal("4000"),
        )
        self.product.current_unit_cost = Decimal("6000.5")
        self.product.save(update_fields=["current_unit_cost"])
        self.order.completed_at = timezone.now()

        snapshot_order_costs(self.order)

        self.item.refresh_from_db()
        self.assertEqual(self.item.unit_cost_snapshot, Decimal("6000.5000"))
        self.assertEqual(self.item.cost_subtotal, Decimal("1500"))

    def test_margin_report_requires_explicit_permission(self):
        user = get_user_model().objects.create_user(
            username="staff-without-margin-permission",
            password="test-only",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get("/admin/orders/order/margins/")

        self.assertEqual(response.status_code, 403)

    def test_margin_report_shows_sales_but_withholds_incomplete_margin(self):
        user = get_user_model().objects.create_user(
            username="margin-viewer",
            password="test-only",
            is_staff=True,
        )
        permission = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(Order),
            codename="view_margin_report",
        )
        user.user_permissions.add(permission)
        self.order.status = Order.Status.COMPLETED
        self.order.completed_at = timezone.now()
        self.order.save(update_fields=["status", "completed_at"])
        self.client.force_login(user)

        response = self.client.get("/admin/orders/order/margins/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ventas completadas")
        self.assertContains(response, "$2250")
        self.assertContains(response, "No disponible")
        self.assertContains(response, "1 producto vendido sin costo")
        self.assertContains(self.client.get("/admin/"), "Reporte de márgenes")

    def test_margin_report_calculates_profit_when_all_costs_are_known(self):
        user = get_user_model().objects.create_user(
            username="complete-margin-viewer",
            password="test-only",
            is_staff=True,
        )
        permission = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(Order),
            codename="view_margin_report",
        )
        user.user_permissions.add(permission)
        self.order.status = Order.Status.COMPLETED
        self.order.completed_at = timezone.now()
        self.order.save(update_fields=["status", "completed_at"])
        self.item.unit_cost_snapshot = Decimal("5333.3333")
        self.item.cost_subtotal = Decimal("1333")
        self.item.save(update_fields=["unit_cost_snapshot", "cost_subtotal"])
        self.client.force_login(user)

        response = self.client.get("/admin/orders/order/margins/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$917")
        self.assertContains(response, "40,8%")

    def test_dashboard_ranks_products_and_builds_sales_charts(self):
        viewer = get_user_model().objects.create_user(
            username="dashboard-viewer",
            password="test-only",
            is_staff=True,
        )
        permission = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(Order),
            codename="view_margin_report",
        )
        viewer.user_permissions.add(permission)
        self.client.force_login(viewer)

        self.order.status = Order.Status.COMPLETED
        self.order.completed_at = timezone.now()
        self.order.save(update_fields=["status", "completed_at"])
        self.item.unit_cost_snapshot = Decimal("5333.3333")
        self.item.cost_subtotal = Decimal("1333")
        self.item.save(update_fields=["unit_cost_snapshot", "cost_subtotal"])

        popular = Product.objects.create(
            category=self.product.category,
            name="Producto popular",
            slug="producto-popular",
            sale_unit=Product.SaleUnit.UNIT,
            price=Decimal("5000"),
            is_active=True,
        )
        for index in range(2):
            order = Order.objects.create(
                customer_name=f"Cliente {index}",
                customer_phone="+56900000000",
                delivery_mode=Order.DeliveryMode.PICKUP,
                total=Decimal("5000"),
                status=Order.Status.COMPLETED,
                completed_at=timezone.now(),
            )
            OrderItem.objects.create(
                order=order,
                product=popular,
                product_name=popular.name,
                sale_unit=Product.SaleUnit.UNIT,
                unit_price=Decimal("5000"),
                pricing_tier=OrderItem.PricingTier.PER_UNIT,
                quantity_units=1,
                subtotal=Decimal("5000"),
                unit_cost_snapshot=Decimal("1000"),
                cost_subtotal=Decimal("1000"),
            )
        Product.objects.create(
            category=self.product.category,
            name="Producto sin ventas",
            slug="producto-sin-ventas",
            price=Decimal("1000"),
            is_active=True,
        )

        response = self.client.get("/admin/orders/order/margins/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["best_margin"][0]["name"], "Producto popular")
        self.assertEqual(response.context["highest_profit"][0]["profit"], Decimal("8000"))
        self.assertEqual(response.context["most_ordered"][0]["order_count"], 2)
        self.assertEqual(response.context["least_ordered"][0]["name"], "Producto sin ventas")
        self.assertEqual(response.context["least_ordered"][0]["order_count"], 0)
        self.assertEqual(response.context["sales_chart"][0]["name"], "Producto popular")
        self.assertEqual(response.context["pie_data"][-1]["end"], 100)
        self.assertContains(response, "Utilidad bruta por producto")
        self.assertContains(response, "Producto sin ventas")

from decimal import Decimal
from io import StringIO

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .admin import ProductAdmin
from .models import Category, Product, WholesalePrice
from .serializers import valid_whatsapp_number


class ProductAdminImageUploadTests(TestCase):
    def test_image_upload_is_read_only_when_media_storage_is_disabled(self):
        product_admin = ProductAdmin(Product, admin.site)
        with override_settings(MEDIA_UPLOADS_ENABLED=False):
            readonly_fields = product_admin.get_readonly_fields(None)

        self.assertIn("image", readonly_fields)
        self.assertIn("media_uploads_notice", readonly_fields)

    def test_image_upload_is_available_when_media_storage_is_enabled(self):
        product_admin = ProductAdmin(Product, admin.site)
        with override_settings(MEDIA_UPLOADS_ENABLED=True):
            readonly_fields = product_admin.get_readonly_fields(None)

        self.assertNotIn("image", readonly_fields)
        self.assertNotIn("media_uploads_notice", readonly_fields)


class ProductSubtotalTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Prueba", slug="prueba")
        self.weighted = Product.objects.create(
            category=category,
            name="Producto por peso",
            slug="producto-por-peso",
            price=Decimal("12500"),
            price_250g=Decimal("3125"),
            sale_unit=Product.SaleUnit.KILOGRAM,
        )
        self.unit = Product.objects.create(
            category=category,
            name="Producto por unidad",
            slug="producto-por-unidad",
            price=Decimal("750"),
            sale_unit=Product.SaleUnit.UNIT,
        )

    def test_weighted_subtotal_uses_grams_and_rounds_to_clp(self):
        self.assertEqual(self.weighted.subtotal_for(grams=250), Decimal("3125"))

    def test_weighted_subtotal_rounds_half_peso_up(self):
        self.weighted.price = Decimal("1")
        self.weighted.price_250g = Decimal("1")
        self.assertEqual(self.weighted.subtotal_for(grams=375), Decimal("2"))

    def test_weighted_subtotal_uses_250g_rate_until_one_kilogram(self):
        self.assertEqual(self.weighted.subtotal_for(grams=50), Decimal("625"))
        self.assertEqual(self.weighted.subtotal_for(grams=999), Decimal("12488"))
        self.assertEqual(self.weighted.subtotal_for(grams=1000), Decimal("12500"))

    def test_weighted_product_without_250g_price_prorates_kilogram_rate(self):
        self.weighted.price_250g = None
        self.assertEqual(self.weighted.minimum_grams, 50)
        self.assertEqual(self.weighted.subtotal_for(grams=50), Decimal("625"))
        self.assertEqual(self.weighted.subtotal_for(grams=999), Decimal("12488"))

    def test_weighted_product_rejects_quantity_below_50_grams(self):
        with self.assertRaisesMessage(ValidationError, "cantidad mínima"):
            self.weighted.subtotal_for(grams=49)

    def test_unit_subtotal_uses_unit_count(self):
        self.assertEqual(self.unit.subtotal_for(units=3), Decimal("2250"))


class PublicCatalogApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="Activa", slug="activa")
        Product.objects.create(
            category=self.category,
            name="Disponible",
            slug="disponible",
            price=Decimal("1000"),
            is_active=True,
            is_available=True,
        )
        Product.objects.create(
            category=self.category,
            name="No disponible",
            slug="no-disponible",
            price=Decimal("1000"),
            is_active=True,
            is_available=False,
        )

    def test_public_catalog_excludes_unavailable_products(self):
        response = self.client.get("/api/products/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["slug"] for item in response.data], ["disponible"])

    def test_product_detail_uses_slug(self):
        response = self.client.get("/api/products/disponible/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Disponible")
        self.assertIsNone(response.data["price_250g"])

    def test_wholesale_only_product_is_not_public(self):
        Product.objects.create(
            category=self.category,
            name="Solo mayorista",
            slug="solo-mayorista",
            price=None,
            is_active=True,
            is_available=True,
        )

        products_response = self.client.get("/api/products/")
        detail_response = self.client.get("/api/products/solo-mayorista/")

        self.assertEqual(products_response.status_code, 200)
        self.assertEqual(
            [item["slug"] for item in products_response.data],
            ["disponible"],
        )
        self.assertEqual(detail_response.status_code, 404)


class WhatsAppConfigurationTests(TestCase):
    def test_only_international_number_is_normalized(self):
        self.assertEqual(valid_whatsapp_number("+56 9 1234 5678"), "56912345678")
        self.assertEqual(valid_whatsapp_number("912345678"), "")

    @override_settings(
        WHATSAPP_BUSINESS_NUMBER="+56900000000",
        STORE_NAME="Siempre Natural",
        STORE_PICKUP_ADDRESS="Santa Elena 201, Concón",
        STORE_BUSINESS_HOURS="Lunes a viernes de 10:00 a 18:00",
        STORE_CONTACT_EMAIL="superalimentosagranel@gmail.com",
    )
    def test_public_store_config_exposes_confirmed_contact_number(self):
        response = APIClient().get("/api/store-config/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Siempre Natural")
        self.assertEqual(response.data["pickup_address"], "Santa Elena 201, Concón")
        self.assertEqual(
            response.data["business_hours"],
            "Lunes a viernes de 10:00 a 18:00",
        )
        self.assertEqual(
            response.data["contact_email"],
            "superalimentosagranel@gmail.com",
        )
        self.assertEqual(response.data["whatsapp_number"], "56900000000")


class WholesalePriceImportTests(TestCase):
    def test_import_loads_143_internal_prices_and_is_idempotent(self):
        first_output = StringIO()
        call_command("load_wholesale_prices", stdout=first_output)

        self.assertEqual(Product.objects.count(), 143)
        self.assertEqual(WholesalePrice.objects.count(), 143)
        self.assertEqual(Category.objects.count(), 12)
        self.assertEqual(Category.objects.filter(is_active=True).count(), 0)
        self.assertEqual(Product.objects.filter(price__isnull=False).count(), 0)
        self.assertIn("143 precios en 12 categorías", first_output.getvalue())

        second_output = StringIO()
        call_command("load_wholesale_prices", stdout=second_output)

        self.assertEqual(Product.objects.count(), 143)
        self.assertEqual(WholesalePrice.objects.count(), 143)

    def test_import_preserves_kg_and_explicit_package_units(self):
        call_command("load_wholesale_prices", stdout=StringIO())

        almonds = WholesalePrice.objects.get(product__name="Almendras enteras")
        peanut_butter = WholesalePrice.objects.get(
            product__name="Mantequilla de maní 500 g"
        )
        agave = WholesalePrice.objects.get(
            product__name="Jarabe de agave 5,6 lt"
        )

        self.assertEqual(almonds.price, Decimal("14000"))
        self.assertEqual(almonds.price_unit, WholesalePrice.PriceUnit.KILOGRAM)
        self.assertEqual(peanut_butter.price_unit, WholesalePrice.PriceUnit.PACKAGE)
        self.assertEqual(peanut_butter.package_label, "500 g")
        self.assertEqual(agave.package_label, "5,6 lt")


class PrivateWholesaleApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        category = Category.objects.create(
            name="Frutos Secos",
            slug="frutos-secos",
            is_active=False,
        )
        product = Product.objects.create(
            category=category,
            name="Almendras enteras",
            slug="almendras-enteras",
            price=None,
            is_active=False,
            is_available=False,
        )
        WholesalePrice.objects.create(
            product=product,
            price_list="Lista mayorista privada",
            price=Decimal("12500"),
            price_unit=WholesalePrice.PriceUnit.KILOGRAM,
        )
        self.user = get_user_model().objects.create_user(
            username="cliente-mayorista",
            password="ClaveSegura-2026",
        )
        self.approved_group = Group.objects.get(name="Mayoristas aprobados")

    def test_wholesale_prices_are_not_visible_without_approved_login(self):
        response = self.client.get("/api/wholesale/prices/")
        session_response = self.client.get("/api/wholesale/session/")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(session_response.data["is_authenticated"])
        self.assertFalse(session_response.data["is_wholesale_customer"])

    def test_authenticated_but_unapproved_user_cannot_see_prices(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/wholesale/prices/")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            self.client.get("/api/wholesale/session/").data[
                "is_wholesale_customer"
            ]
        )

    def test_approved_user_can_sign_in_and_see_wholesale_prices(self):
        self.user.groups.add(self.approved_group)

        login_response = self.client.post(
            "/api/wholesale/login/",
            {"username": "cliente-mayorista", "password": "ClaveSegura-2026"},
            format="json",
        )
        prices_response = self.client.get("/api/wholesale/prices/")

        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(login_response.data["is_wholesale_customer"])
        self.assertEqual(prices_response.status_code, 200)
        self.assertEqual(prices_response.data[0]["product_name"], "Almendras enteras")
        self.assertEqual(prices_response.data[0]["price"], "12500")

    def test_login_does_not_authorize_unapproved_users(self):
        response = self.client.post(
            "/api/wholesale/login/",
            {"username": "cliente-mayorista", "password": "ClaveSegura-2026"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.client.session.get("_auth_user_id"))

    def test_login_requires_csrf_and_logout_clears_approved_session(self):
        self.user.groups.add(self.approved_group)
        csrf_client = APIClient(enforce_csrf_checks=True)
        denied = csrf_client.post(
            "/api/wholesale/login/",
            {"username": "cliente-mayorista", "password": "ClaveSegura-2026"},
            format="json",
        )
        csrf_client.get("/api/csrf/")
        csrf_token = csrf_client.cookies["csrftoken"].value
        allowed = csrf_client.post(
            "/api/wholesale/login/",
            {"username": "cliente-mayorista", "password": "ClaveSegura-2026"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        csrf_client.get("/api/csrf/")
        logout_csrf_token = csrf_client.cookies["csrftoken"].value
        logout_denied = csrf_client.post("/api/wholesale/logout/")
        logout_allowed = csrf_client.post(
            "/api/wholesale/logout/",
            HTTP_X_CSRFTOKEN=logout_csrf_token,
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(logout_denied.status_code, 403)
        self.assertEqual(logout_allowed.status_code, 200)
        self.assertFalse(
            csrf_client.get("/api/wholesale/session/").data["is_authenticated"]
        )


class RetailPriceImportTests(TestCase):
    def test_import_publishes_priced_products_and_is_idempotent(self):
        first_output = StringIO()
        call_command("load_retail_prices", stdout=first_output)

        self.assertEqual(Product.objects.count(), 157)
        self.assertEqual(Category.objects.count(), 13)
        self.assertEqual(Category.objects.filter(is_active=True).count(), 13)
        self.assertEqual(
            Product.objects.filter(
                is_active=True,
                is_available=True,
                price__isnull=False,
            ).count(),
            155,
        )
        self.assertEqual(
            Product.objects.filter(sale_unit=Product.SaleUnit.UNIT).count(),
            14,
        )
        self.assertEqual(
            Product.objects.filter(sale_unit=Product.SaleUnit.KILOGRAM).count(),
            143,
        )
        self.assertEqual(Product.objects.filter(price_250g__isnull=False).count(), 139)
        self.assertIn("157 productos en 13 categorías", first_output.getvalue())
        self.assertIn("155 productos con precio", first_output.getvalue())

        call_command("load_retail_prices", stdout=StringIO())

        self.assertEqual(Product.objects.count(), 157)
        self.assertEqual(Category.objects.count(), 13)

    def test_import_renames_existing_category_without_creating_a_duplicate(self):
        category = Category.objects.create(
            name="Frutos semisecos",
            slug="frutos-semisecos",
            is_active=False,
        )

        call_command("load_retail_prices", stdout=StringIO())

        category.refresh_from_db()
        self.assertEqual(category.name, "Frutos Semi Secos")
        self.assertTrue(category.is_active)
        self.assertEqual(Category.objects.count(), 13)

    def test_missing_prices_are_hidden_and_removed_products_are_retired(self):
        category = Category.objects.create(
            name="Categoría anterior",
            slug="categoria-anterior",
            is_active=True,
        )
        removed = Product.objects.create(
            category=category,
            name="Producto retirado",
            slug="producto-retirado",
            price=Decimal("1000"),
            is_active=True,
            is_available=True,
        )

        call_command("load_retail_prices", stdout=StringIO())

        removed.refresh_from_db()
        self.assertFalse(removed.is_active)
        self.assertFalse(removed.is_available)
        self.assertFalse(Category.objects.get(slug="categoria-anterior").is_active)
        for name in ("Canela polvo", "Piña en cubo"):
            product = Product.objects.get(name=name)
            self.assertIsNone(product.price)
            self.assertIsNone(product.price_250g)
            self.assertFalse(product.is_active)
            self.assertFalse(product.is_available)

    def test_import_preserves_weight_and_package_pricing(self):
        call_command("load_retail_prices", stdout=StringIO())

        almonds = Product.objects.get(name="Almendras enteras")
        coconut_cream = Product.objects.get(name="Crema de coco 400 cc")
        molinillo = Product.objects.get(name="Molinillo con pimientas")
        honey = Product.objects.get(name="Miel orgánica (Cordillera del Maule)")

        self.assertEqual(almonds.price_250g, Decimal("3500"))
        self.assertEqual(almonds.price, Decimal("14000"))
        self.assertEqual(coconut_cream.sale_unit, Product.SaleUnit.UNIT)
        self.assertEqual(coconut_cream.package_label, "400 cc")
        self.assertEqual(molinillo.package_label, "unidad")
        self.assertEqual(honey.minimum_grams, 50)

    def test_normal_price_import_preserves_separate_wholesale_price(self):
        category = Category.objects.create(
            name="Frutos secos",
            slug="frutos-secos",
            is_active=False,
        )
        product = Product.objects.create(
            category=category,
            name="Almendras enteras",
            slug="almendras-enteras",
            price=None,
            is_active=False,
            is_available=False,
        )
        wholesale = WholesalePrice.objects.create(
            product=product,
            price_list="Tarifa mayorista independiente",
            price=Decimal("12500"),
            price_unit=WholesalePrice.PriceUnit.KILOGRAM,
        )

        call_command("load_retail_prices", stdout=StringIO())

        product.refresh_from_db()
        wholesale.refresh_from_db()
        self.assertEqual(product.price, Decimal("14000"))
        self.assertEqual(product.price_250g, Decimal("3500"))
        self.assertEqual(product.category.name, "Frutos Secos")
        self.assertTrue(product.is_active)
        self.assertTrue(product.is_available)
        self.assertEqual(wholesale.price, Decimal("12500"))

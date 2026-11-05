from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.models import Category, Product
from orders.models import Order

from .models import CustomerAccount


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST="smtp.example.com",
    EMAIL_HOST_USER="store@example.com",
    EMAIL_HOST_PASSWORD="test-only",
    DEFAULT_FROM_EMAIL="store@example.com",
    FRONTEND_BASE_URL="http://localhost:5173",
)
class CustomerAccountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def register(self, email="client@example.com"):
        return self.client.post(
            "/api/customer/register/",
            {"email": email, "password": "Strong-password-923!"},
            format="json",
        )

    def verification_payload(self, message):
        link = message.body.splitlines()[2]
        query = parse_qs(urlparse(link).query)
        return {
            "token": query["token"][0],
            "action": query["action"][0],
        }

    def test_registration_sends_verification_and_claims_guest_orders(self):
        order = Order.objects.create(
            customer_name="Cliente anterior",
            customer_phone="912345678",
            customer_email="client@example.com",
            delivery_mode=Order.DeliveryMode.PICKUP,
            total=Decimal("1200"),
        )

        response = self.register()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["verification_email_sent"])
        self.assertTrue(response.data["is_authenticated"])
        self.assertEqual(response.data["email"], "client@example.com")
        self.assertFalse(response.data["email_verified"])
        self.assertEqual(len(mail.outbox), 1)
        account = CustomerAccount.objects.get(email="client@example.com")
        self.assertFalse(account.email_verified)
        self.assertIsNone(order.customer_id)

        verify_response = self.client.post(
            "/api/customer/verify-email/",
            self.verification_payload(mail.outbox[0]),
            format="json",
        )

        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.data["claimed_orders"], 1)
        account.refresh_from_db()
        order.refresh_from_db()
        self.assertTrue(account.email_verified)
        self.assertEqual(order.customer_id, account.pk)

    def test_unverified_customer_can_login_and_read_own_history(self):
        self.assertEqual(self.register().status_code, 201)
        account = CustomerAccount.objects.get(email="client@example.com")
        own_order = Order.objects.create(
            customer=account,
            customer_name="Cliente",
            customer_phone="912345678",
            customer_email=account.email,
            delivery_mode=Order.DeliveryMode.PICKUP,
            total=Decimal("1200"),
        )
        login_response = self.client.post(
            "/api/customer/login/",
            {
                "email": "client@example.com",
                "password": "Strong-password-923!",
            },
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(login_response.data["is_authenticated"])
        self.assertFalse(login_response.data["email_verified"])
        self.assertEqual(
            self.client.get("/api/customer/session/").data,
            {
                "is_authenticated": True,
                "email": "client@example.com",
                "email_verified": False,
            },
        )
        history_response = self.client.get("/api/customer/orders/")
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(len(history_response.data), 1)
        self.assertEqual(str(history_response.data[0]["id"]), str(own_order.pk))

    def test_verified_customer_can_login_and_read_only_own_orders(self):
        self.register()
        account = CustomerAccount.objects.get(email="client@example.com")
        account.email_verified = True
        account.save(update_fields=["email_verified"])
        own_order = Order.objects.create(
            customer=account,
            customer_name="Cliente",
            customer_phone="912345678",
            customer_email=account.email,
            delivery_mode=Order.DeliveryMode.PICKUP,
            total=Decimal("1200"),
        )
        Order.objects.create(
            customer=CustomerAccount.objects.create(
                user=get_user_model().objects.create_user(
                    username="another-customer",
                    email="other@example.com",
                    password="Another-strong-password-639!",
                ),
                email="other@example.com",
                email_verified=True,
            ),
            customer_name="Otra persona",
            customer_phone="987654321",
            customer_email="other@example.com",
            delivery_mode=Order.DeliveryMode.PICKUP,
            total=Decimal("3400"),
        )

        login_response = self.client.post(
            "/api/customer/login/",
            {
                "email": account.email,
                "password": "Strong-password-923!",
            },
            format="json",
        )
        history_response = self.client.get("/api/customer/orders/")

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(len(history_response.data), 1)
        self.assertEqual(str(history_response.data[0]["id"]), str(own_order.pk))

    def test_authenticated_customer_order_is_linked_to_account(self):
        self.register()
        account = CustomerAccount.objects.get(email="client@example.com")
        category = Category.objects.create(name="Semillas", slug="semillas")
        product = Product.objects.create(
            category=category,
            name="Semillas",
            slug="semillas-pedido-cuenta",
            price=Decimal("10000"),
            price_250g=Decimal("2500"),
            is_active=True,
            is_available=True,
        )
        self.client.force_login(account.user)

        response = self.client.post(
            "/api/orders/",
            {
                "customer_name": "Cliente",
                "customer_phone": "912345678",
                "customer_email": account.email,
                "delivery_mode": "pickup",
                "items": [{"product_id": product.pk, "quantity_grams": 100}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["id"])
        self.assertEqual(order.customer_id, account.pk)

    def test_guest_order_claim_requires_signed_email_link(self):
        self.register()
        account = CustomerAccount.objects.get(email="client@example.com")
        account.email_verified = True
        account.save(update_fields=["email_verified"])
        order = Order.objects.create(
            customer_name="Cliente",
            customer_phone="912345678",
            customer_email=account.email,
            delivery_mode=Order.DeliveryMode.PICKUP,
            total=Decimal("1000"),
        )
        self.client.force_login(account.user)

        claim_response = self.client.post(
            "/api/customer/orders/claim/",
            {},
            format="json",
        )
        claim_data = self.verification_payload(mail.outbox[-1])
        verify_response = self.client.post(
            "/api/customer/verify-email/",
            claim_data,
            format="json",
        )

        self.assertTrue(claim_response.data["email_sent"])
        self.assertEqual(claim_data["action"], "claim")
        self.assertEqual(verify_response.data["claimed_orders"], 1)
        order.refresh_from_db()
        self.assertEqual(order.customer_id, account.pk)

    def test_password_reset_email_can_change_customer_password(self):
        self.register()
        account = CustomerAccount.objects.get(email="client@example.com")
        account.email_verified = True
        account.save(update_fields=["email_verified"])

        request_response = self.client.post(
            "/api/customer/password/reset/",
            {"email": account.email},
            format="json",
        )
        link = mail.outbox[-1].body.splitlines()[2]
        query = parse_qs(urlparse(link).query)
        reset_response = self.client.post(
            "/api/customer/password/reset/confirm/",
            {
                "uid": query["uid"][0],
                "token": query["token"][0],
                "password": "New-strong-password-657!",
            },
            format="json",
        )

        self.assertEqual(request_response.status_code, 200)
        self.assertEqual(reset_response.status_code, 200)
        account.user.refresh_from_db()
        self.assertTrue(account.user.check_password("New-strong-password-657!"))

    def test_customer_account_deletion_anonymizes_orders(self):
        self.register()
        account = CustomerAccount.objects.get(email="client@example.com")
        account.email_verified = True
        account.save(update_fields=["email_verified"])
        order = Order.objects.create(
            customer=account,
            customer_name="Cliente",
            customer_phone="912345678",
            customer_email=account.email,
            customer_rut="12.345.678-9",
            delivery_mode=Order.DeliveryMode.SHIPPING,
            delivery_address="Dirección privada 12",
            notes="Dejar en recepción",
            total=Decimal("1200"),
        )
        user_id = account.user_id
        self.client.force_login(account.user)

        response = self.client.post(
            "/api/customer/account/delete/",
            {"password": "Strong-password-923!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CustomerAccount.objects.filter(pk=account.pk).exists())
        self.assertFalse(get_user_model().objects.filter(pk=user_id).exists())
        order.refresh_from_db()
        self.assertIsNone(order.customer_id)
        self.assertEqual(order.customer_name, "Cliente eliminado")
        self.assertEqual(order.customer_email, "")
        self.assertEqual(order.customer_rut, "")
        self.assertEqual(order.delivery_address, "")
        self.assertEqual(order.notes, "")
        self.assertEqual(order.total, Decimal("1200"))

    def test_customer_account_deletion_does_not_remove_admin_users(self):
        self.register()
        account = CustomerAccount.objects.get(email="client@example.com")
        account.email_verified = True
        account.save(update_fields=["email_verified"])
        account.user.is_staff = True
        account.user.save(update_fields=["is_staff"])
        user_id = account.user_id
        self.client.force_login(account.user)

        response = self.client.post(
            "/api/customer/account/delete/",
            {"password": "Strong-password-923!"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(CustomerAccount.objects.filter(pk=account.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=user_id).exists())

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        self.assertEqual(self.register().status_code, 201)

        response = self.register("CLIENT@example.com")

        self.assertEqual(response.status_code, 400)

    def test_registration_rejects_password_matching_email(self):
        response = self.client.post(
            "/api/customer/register/",
            {"email": "client@example.com", "password": "client@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CustomerAccountCsrfTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)

    def test_registration_requires_csrf_token(self):
        response = self.client.post(
            "/api/customer/register/",
            {"email": "client@example.com", "password": "Strong-password-923!"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_registration_uses_token_returned_by_csrf_endpoint(self):
        token_response = self.client.get("/api/csrf/")
        response = self.client.post(
            "/api/customer/register/",
            {"email": "client@example.com", "password": "Strong-password-923!"},
            format="json",
            HTTP_X_CSRFTOKEN=token_response.data["csrf_token"],
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["verification_email_sent"])

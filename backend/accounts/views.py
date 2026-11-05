from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.utils.encoding import force_bytes, force_str
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from orders.models import Order

from .emails import account_url, send_configured_email
from .models import CustomerAccount
from .serializers import (
    CustomerLoginSerializer,
    CustomerOrderHistorySerializer,
    CustomerRegistrationSerializer,
    DeleteAccountSerializer,
    EmailSerializer,
    PasswordResetSerializer,
)


EMAIL_VERIFICATION_SALT = "accounts.customer-email-verification"
GUEST_CLAIM_SALT = "accounts.guest-order-claim"


def send_verification_email(account):
    token = signing.dumps(account.pk, salt=EMAIL_VERIFICATION_SALT)
    link = account_url("/cuenta/verificar", token=token, action="verify")
    return send_configured_email(
        recipient=account.email,
        subject=f"Confirma tu correo - {settings.STORE_NAME}",
        message=(
            f"Confirma tu correo para activar tu cuenta en {settings.STORE_NAME} "
            f"y consultar tu historial de compras:\n\n{link}\n\n"
            "El enlace vence en 24 horas. Si no creaste esta cuenta, ignora este correo."
        ),
    )


@method_decorator(csrf_protect, name="dispatch")
class CustomerRegistrationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "customer_register"

    def post(self, request):
        serializer = CustomerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save()
        login(request, account.user, backend=settings.AUTHENTICATION_BACKENDS[0])
        email_sent = send_verification_email(account)
        return Response(
            {
                "detail": "Cuenta creada. Tu sesión ya está iniciada.",
                "verification_email_sent": email_sent,
                "is_authenticated": True,
                "email": account.email,
                "email_verified": account.email_verified,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
class CustomerLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "customer_login"

    def post(self, request):
        serializer = CustomerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().casefold()
        account = CustomerAccount.objects.select_related("user").filter(
            email__iexact=email,
        ).first()
        if account is None:
            return Response(
                {"detail": "Correo o contraseña incorrectos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            request,
            username=account.user.get_username(),
            password=serializer.validated_data["password"],
        )
        if user is None or user.pk != account.user_id:
            return Response(
                {"detail": "Correo o contraseña incorrectos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(
            {
                "is_authenticated": True,
                "email": account.email,
                "email_verified": account.email_verified,
            }
        )


class CustomerSessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        account = None
        if request.user.is_authenticated:
            account = CustomerAccount.objects.filter(
                user=request.user,
            ).first()
        return Response(
            {
                "is_authenticated": account is not None,
                "email": account.email if account else "",
                "email_verified": account.email_verified if account else False,
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class CustomerLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not hasattr(request.user, "customer_account"):
            return Response(
                {"detail": "No hay una sesión de cliente activa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        logout(request)
        return Response({"detail": "Sesión cerrada."})


@method_decorator(csrf_protect, name="dispatch")
class VerifyCustomerEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "customer_verify"

    def post(self, request):
        token = request.data.get("token", "")
        action = request.data.get("action", "verify")
        if (
            not isinstance(token, str)
            or not isinstance(action, str)
            or action not in {"verify", "claim"}
        ):
            return Response(
                {"detail": "El enlace no es válido o venció."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        salt = EMAIL_VERIFICATION_SALT if action == "verify" else GUEST_CLAIM_SALT
        try:
            account_id = signing.loads(token, salt=salt, max_age=24 * 60 * 60)
            account = CustomerAccount.objects.get(pk=account_id)
        except (signing.BadSignature, CustomerAccount.DoesNotExist, TypeError, ValueError):
            return Response(
                {"detail": "El enlace no es válido o venció."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action == "verify" and not account.email_verified:
            account.email_verified = True
            account.save(update_fields=["email_verified"])

        claimed_count = Order.objects.filter(
            customer__isnull=True,
            customer_email__iexact=account.email,
        ).update(customer=account)
        return Response(
            {
                "detail": (
                    "Correo confirmado. Tus pedidos anteriores con este correo "
                    "ya aparecen en tu historial."
                ),
                "claimed_orders": claimed_count,
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class ResendCustomerVerificationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "customer_verify"

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = CustomerAccount.objects.filter(
            email__iexact=serializer.validated_data["email"].strip(),
            email_verified=False,
        ).first()
        if account:
            send_verification_email(account)
        return Response(
            {
                "detail": (
                    "Si existe una cuenta pendiente para ese correo, "
                    "enviaremos un enlace de confirmación."
                )
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class GuestOrderClaimEmailView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "customer_verify"

    def post(self, request):
        account = CustomerAccount.objects.filter(
            user=request.user,
            email_verified=True,
        ).first()
        if account is None:
            return Response(
                {"detail": "Confirma tu correo antes de reclamar pedidos."},
                status=status.HTTP_403_FORBIDDEN,
            )
        token = signing.dumps(account.pk, salt=GUEST_CLAIM_SALT)
        link = account_url("/cuenta/verificar", token=token, action="claim")
        email_sent = send_configured_email(
            recipient=account.email,
            subject=f"Confirma tu historial - {settings.STORE_NAME}",
            message=(
                f"Usa este enlace para añadir a tu historial los pedidos de invitado "
                f"hechos con {account.email}:\n\n{link}\n\n"
                "El enlace vence en 24 horas. Si no solicitaste esto, ignora este correo."
            ),
        )
        return Response(
            {
                "detail": (
                    "Te enviaremos un enlace si el correo está configurado. "
                    "El enlace vence en 24 horas."
                ),
                "email_sent": email_sent,
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class CustomerPasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "customer_password_reset"

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip()
        account = CustomerAccount.objects.select_related("user").filter(
            email__iexact=email,
            email_verified=True,
        ).first()
        if account:
            token = default_token_generator.make_token(account.user)
            uid = urlsafe_base64_encode(force_bytes(account.user.pk))
            link = account_url(
                "/cuenta/restablecer",
                uid=uid,
                token=token,
            )
            send_configured_email(
                recipient=account.email,
                subject=f"Restablece tu contraseña - {settings.STORE_NAME}",
                message=(
                    f"Recibimos una solicitud para cambiar la contraseña de tu cuenta.\n\n"
                    f"{link}\n\nSi no la solicitaste, ignora este correo."
                ),
            )
        return Response(
            {
                "detail": (
                    "Si existe una cuenta verificada para ese correo, "
                    "enviaremos instrucciones para cambiar la contraseña."
                )
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class CustomerPasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "customer_password_reset"

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user_id = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
            account = CustomerAccount.objects.select_related("user").get(
                user_id=user_id,
                email_verified=True,
            )
        except (CustomerAccount.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": "El enlace no es válido o ya venció."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not default_token_generator.check_token(
            account.user,
            serializer.validated_data["token"],
        ):
            return Response(
                {"detail": "El enlace no es válido o ya venció."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(
                serializer.validated_data["password"],
                user=account.user,
            )
        except DjangoValidationError as cause:
            raise serializers.ValidationError(
                {"password": cause.messages}
            ) from cause

        account.user.set_password(serializer.validated_data["password"])
        account.user.save(update_fields=["password"])
        return Response({"detail": "Tu contraseña fue actualizada."})


class CustomerOrderHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account = CustomerAccount.objects.filter(
            user=request.user,
        ).first()
        if account is None:
            return Response(
                {"detail": "Se requiere una cuenta de cliente."},
                status=status.HTTP_403_FORBIDDEN,
            )
        orders = (
            Order.objects.filter(customer=account)
            .prefetch_related("items")
            .order_by("-created_at")
        )
        return Response(CustomerOrderHistorySerializer(orders, many=True).data)


@method_decorator(csrf_protect, name="dispatch")
class CustomerAccountDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeleteAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.user.is_staff or request.user.is_superuser:
            return Response(
                {
                    "detail": (
                        "Las cuentas administrativas no se eliminan desde este "
                        "formulario."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        account = CustomerAccount.objects.filter(user=request.user).first()
        if (
            account is None
            or not request.user.check_password(
                serializer.validated_data["password"]
            )
        ):
            return Response(
                {"detail": "La contraseña no es correcta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            Order.objects.filter(
                Q(customer=account) | Q(customer__isnull=True, customer_email__iexact=account.email)
            ).update(
                customer=None,
                customer_name="Cliente eliminado",
                customer_phone="",
                customer_email="",
                customer_rut="",
                delivery_address="",
                notes="",
            )
            user = request.user
            logout(request)
            user.delete()
        return Response(
            {
                "detail": (
                    "La cuenta y sus datos personales se eliminaron. "
                    "Se conservaron los productos, importes y estados de los pedidos "
                    "sin datos que te identifiquen."
                )
            }
        )

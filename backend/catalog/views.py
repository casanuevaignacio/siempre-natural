from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Product, WholesalePrice
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    WholesalePriceSerializer,
    valid_whatsapp_number,
)


WHOLESALE_GROUP_NAME = "Mayoristas aprobados"


def is_approved_wholesale_user(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.groups.filter(name=WHOLESALE_GROUP_NAME).exists()
    )


class ApprovedWholesalePermission(BasePermission):
    message = "Se requiere una cuenta mayorista autorizada."

    def has_permission(self, request, view):
        return is_approved_wholesale_user(request.user)


class WholesaleLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


@method_decorator(csrf_protect, name="dispatch")
class WholesaleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = WholesaleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None or not is_approved_wholesale_user(user):
            return Response(
                {"detail": "Usuario o contraseña incorrectos, o cuenta no autorizada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(
            {"username": user.get_username(), "is_wholesale_customer": True}
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def wholesale_session(request):
    user = request.user
    approved = is_approved_wholesale_user(user)
    return Response(
        {
            "is_authenticated": bool(user.is_authenticated),
            "is_wholesale_customer": approved,
            "username": user.get_username() if approved else "",
        }
    )


@method_decorator(csrf_protect, name="dispatch")
class WholesaleLogoutView(APIView):
    permission_classes = [ApprovedWholesalePermission]

    def post(self, request):
        logout(request)
        return Response({"detail": "Sesión cerrada."})


class WholesalePriceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WholesalePriceSerializer
    permission_classes = [ApprovedWholesalePermission]
    queryset = WholesalePrice.objects.select_related(
        "product",
        "product__category",
    ).order_by("product__category__name", "product__name")


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    queryset = Category.objects.filter(
        is_active=True,
        products__is_active=True,
        products__is_available=True,
        products__price__isnull=False,
    ).distinct()


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        queryset = Product.objects.filter(
            is_active=True,
            is_available=True,
            price__isnull=False,
            category__is_active=True,
        ).select_related("category")
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__slug=category)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset


@api_view(["GET"])
@permission_classes([AllowAny])
def store_config(request):
    return Response(
        {
            "name": settings.STORE_NAME,
            "tagline": settings.STORE_TAGLINE,
            "pickup_address": settings.STORE_PICKUP_ADDRESS,
            "business_hours": settings.STORE_BUSINESS_HOURS,
            "contact_email": settings.STORE_CONTACT_EMAIL,
            "whatsapp_number": valid_whatsapp_number(
                settings.WHATSAPP_BUSINESS_NUMBER
            ),
        }
    )


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_token(request):
    return Response({"csrf_token": get_token(request)})

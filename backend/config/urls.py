from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static

admin.site.site_header = "Siempre Natural"
admin.site.site_title = "Siempre Natural | Administración"
admin.site.index_title = "Panel de administración"
admin.site.enable_nav_sidebar = False
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import (
    CustomerAccountDeleteView,
    CustomerLoginView,
    CustomerLogoutView,
    CustomerOrderHistoryView,
    CustomerPasswordResetConfirmView,
    CustomerPasswordResetRequestView,
    CustomerRegistrationView,
    CustomerSessionView,
    GuestOrderClaimEmailView,
    ResendCustomerVerificationView,
    VerifyCustomerEmailView,
)
from catalog.views import (
    CategoryViewSet,
    ProductViewSet,
    WholesaleLoginView,
    WholesaleLogoutView,
    WholesalePriceViewSet,
    csrf_token,
    store_config,
    wholesale_session,
)
from orders.views import OrderCreateView

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")
router.register("wholesale/prices", WholesalePriceViewSet, basename="wholesale-price")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/store-config/", store_config, name="store-config"),
    path("api/csrf/", csrf_token, name="csrf-token"),
    path("api/wholesale/login/", WholesaleLoginView.as_view(), name="wholesale-login"),
    path("api/wholesale/logout/", WholesaleLogoutView.as_view(), name="wholesale-logout"),
    path("api/wholesale/session/", wholesale_session, name="wholesale-session"),
    path("api/orders/", OrderCreateView.as_view(), name="order-create"),
    path("api/customer/register/", CustomerRegistrationView.as_view(), name="customer-register"),
    path("api/customer/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("api/customer/session/", CustomerSessionView.as_view(), name="customer-session"),
    path("api/customer/logout/", CustomerLogoutView.as_view(), name="customer-logout"),
    path("api/customer/verify-email/", VerifyCustomerEmailView.as_view(), name="customer-verify-email"),
    path("api/customer/verification/resend/", ResendCustomerVerificationView.as_view(), name="customer-verification-resend"),
    path("api/customer/orders/claim/", GuestOrderClaimEmailView.as_view(), name="customer-orders-claim"),
    path("api/customer/orders/", CustomerOrderHistoryView.as_view(), name="customer-orders"),
    path("api/customer/password/reset/", CustomerPasswordResetRequestView.as_view(), name="customer-password-reset"),
    path("api/customer/password/reset/confirm/", CustomerPasswordResetConfirmView.as_view(), name="customer-password-reset-confirm"),
    path("api/customer/account/delete/", CustomerAccountDeleteView.as_view(), name="customer-account-delete"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

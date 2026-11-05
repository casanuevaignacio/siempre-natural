from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product",
        "product_name",
        "sale_unit",
        "unit_price",
        "pricing_tier",
        "quantity_grams",
        "quantity_units",
        "subtotal",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "customer_name",
        "customer_email",
        "customer_account",
        "delivery_mode",
        "total",
        "status",
    )
    list_filter = ("status", "delivery_mode", "created_at")
    search_fields = (
        "id",
        "customer_name",
        "customer_phone",
        "customer_email",
        "customer__email",
    )
    readonly_fields = ("id", "created_at", "total")
    inlines = [OrderItemInline]

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj:
            fields.extend(
                [
                    "customer_name",
                    "customer_phone",
                    "customer_email",
                    "customer_rut",
                    "delivery_mode",
                    "delivery_address",
                    "notes",
                ]
            )
        return fields

    @admin.display(description="Cuenta de cliente")
    def customer_account(self, order):
        return order.customer.email if order.customer_id else "Pedido de invitado"

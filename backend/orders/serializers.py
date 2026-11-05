import re

from django.db import transaction
from rest_framework import serializers

from accounts.models import CustomerAccount
from catalog.models import Product
from .models import Order, OrderItem


class RequestedOrderItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity_grams = serializers.IntegerField(min_value=1, required=False, default=0)
    quantity_units = serializers.IntegerField(min_value=1, required=False, default=0)

    def validate(self, attrs):
        grams = attrs["quantity_grams"]
        units = attrs["quantity_units"]
        if bool(grams) == bool(units):
            raise serializers.ValidationError(
                "Indica una cantidad positiva en gramos o en unidades, no ambas."
            )
        return attrs


class OrderCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=160)
    customer_phone = serializers.RegexField(r"^[+0-9()\-\s]{8,32}$")
    customer_email = serializers.EmailField()
    customer_rut = serializers.CharField(max_length=16, required=False, allow_blank=True)
    delivery_mode = serializers.ChoiceField(choices=Order.DeliveryMode.choices)
    delivery_address = serializers.CharField(
        max_length=250,
        required=False,
        allow_blank=True,
    )
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    items = RequestedOrderItemSerializer(many=True, allow_empty=False)

    def validate_customer_phone(self, value):
        digits = re.sub(r"\D", "", value)
        if not 8 <= len(digits) <= 15:
            raise serializers.ValidationError(
                "Ingresa un teléfono de contacto válido."
            )
        return f"+{digits}" if value.strip().startswith("+") else digits

    def validate(self, attrs):
        request = self.context.get("request")
        account = (
            CustomerAccount.objects.filter(user=request.user).first()
            if request and request.user.is_authenticated
            else None
        )
        if account:
            attrs["customer"] = account
            attrs["customer_email"] = account.email
        else:
            attrs["customer_email"] = attrs["customer_email"].strip().casefold()

        if attrs["delivery_mode"] == Order.DeliveryMode.SHIPPING:
            if not attrs.get("delivery_address", "").strip():
                raise serializers.ValidationError(
                    {"delivery_address": "Indica la dirección para el despacho."}
                )
        else:
            attrs["delivery_address"] = ""

        product_ids = [item["product_id"] for item in attrs["items"]]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                {"items": "Cada producto debe aparecer una sola vez en el pedido."}
            )
        products = Product.objects.filter(
            id__in=product_ids,
            is_active=True,
            is_available=True,
            price__isnull=False,
            category__is_active=True,
        )
        product_map = {product.id: product for product in products}
        if len(product_map) != len(set(product_ids)):
            raise serializers.ValidationError(
                {"items": "Uno o más productos ya no están disponibles."}
            )

        for item in attrs["items"]:
            product = product_map[item["product_id"]]
            has_grams = bool(item["quantity_grams"])
            if (product.sale_unit == Product.SaleUnit.KILOGRAM) != has_grams:
                raise serializers.ValidationError(
                    {"items": f"La cantidad no coincide con la unidad de {product.name}."}
                )
            if has_grams and item["quantity_grams"] < product.minimum_grams:
                raise serializers.ValidationError(
                    {
                        "items": (
                            f"La cantidad mínima de {product.name} es "
                            f"{product.minimum_grams} g."
                        )
                    }
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        requested_items = validated_data.pop("items")
        product_ids = [item["product_id"] for item in requested_items]
        products = Product.objects.select_for_update().filter(
            id__in=product_ids,
            is_active=True,
            is_available=True,
            price__isnull=False,
            category__is_active=True,
        )
        product_map = {product.id: product for product in products}
        if len(product_map) != len(set(product_ids)):
            raise serializers.ValidationError(
                {"items": "Uno o más productos ya no están disponibles."}
            )

        order = Order.objects.create(total=0, **validated_data)
        total = 0
        order_items = []

        for requested in requested_items:
            product = product_map[requested["product_id"]]
            grams = requested["quantity_grams"]
            units = requested["quantity_units"]
            has_grams = bool(grams)
            if (product.sale_unit == Product.SaleUnit.KILOGRAM) != has_grams:
                raise serializers.ValidationError(
                    {"items": f"La cantidad no coincide con la unidad de {product.name}."}
                )
            unit_price, pricing_tier, subtotal = product.quote_for(
                grams=grams,
                units=units,
            )
            total += subtotal
            order_items.append(
                OrderItem(
                    order=order,
                    product=product,
                    product_name=product.name,
                    sale_unit=product.sale_unit,
                    unit_price=unit_price,
                    pricing_tier=pricing_tier,
                    quantity_grams=grams,
                    quantity_units=units,
                    subtotal=subtotal,
                )
            )

        OrderItem.objects.bulk_create(order_items)
        order.total = total
        order.save(update_fields=["total"])
        return order


class OrderCreatedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "created_at", "total", "status")

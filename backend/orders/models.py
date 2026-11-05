import uuid

from django.db import models

from accounts.models import CustomerAccount
from catalog.models import Product


class Order(models.Model):
    class DeliveryMode(models.TextChoices):
        PICKUP = "pickup", "Retiro"
        SHIPPING = "shipping", "Despacho"

    class Status(models.TextChoices):
        RECEIVED = "received", "Recibido"
        CONFIRMED = "confirmed", "Confirmado"
        PREPARING = "preparing", "En preparación"
        COMPLETED = "completed", "Completado"
        CANCELLED = "cancelled", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField("fecha de creación", auto_now_add=True)
    customer_name = models.CharField("nombre del cliente", max_length=160)
    customer_phone = models.CharField("teléfono", max_length=32)
    customer_email = models.EmailField("correo electrónico", blank=True)
    customer = models.ForeignKey(
        CustomerAccount,
        on_delete=models.SET_NULL,
        related_name="orders",
        verbose_name="cuenta de cliente",
        blank=True,
        null=True,
    )
    customer_rut = models.CharField("RUT (opcional)", max_length=16, blank=True)
    delivery_mode = models.CharField(
        "modalidad de entrega",
        max_length=8,
        choices=DeliveryMode.choices,
    )
    delivery_address = models.CharField("dirección de despacho", max_length=250, blank=True)
    notes = models.CharField("indicaciones", max_length=500, blank=True)
    total = models.DecimalField("total", max_digits=14, decimal_places=0)
    status = models.CharField(
        "estado",
        max_length=12,
        choices=Status.choices,
        default=Status.RECEIVED,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"

    def __str__(self):
        return f"Pedido {self.id}"


class OrderItem(models.Model):
    class PricingTier(models.TextChoices):
        LEGACY = "legacy", "Precio histórico"
        PER_250G = "250g", "Tramo desde 250 g"
        PER_KILOGRAM = "kg", "Tramo por kilogramo"
        PER_UNIT = "unit", "Precio por presentación"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="pedido",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name="producto",
    )
    product_name = models.CharField("nombre del producto", max_length=160)
    sale_unit = models.CharField("unidad de venta", max_length=8)
    unit_price = models.DecimalField(
        "precio unitario aplicado",
        max_digits=12,
        decimal_places=0,
    )
    pricing_tier = models.CharField(
        "tramo de precio aplicado",
        max_length=8,
        choices=PricingTier.choices,
        default=PricingTier.LEGACY,
    )
    quantity_grams = models.PositiveIntegerField("cantidad en gramos", default=0)
    quantity_units = models.PositiveIntegerField("cantidad de unidades", default=0)
    subtotal = models.DecimalField("subtotal", max_digits=14, decimal_places=0)

    class Meta:
        verbose_name = "producto del pedido"
        verbose_name_plural = "productos del pedido"

    def __str__(self):
        return self.product_name

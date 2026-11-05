from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models


def validate_image_size(image):
    if image.size > 5 * 1024 * 1024:
        raise ValidationError("La imagen no puede superar los 5 MB.")


class Category(models.Model):
    name = models.CharField("nombre", max_length=100, unique=True)
    slug = models.SlugField("identificador", max_length=110, unique=True)
    description = models.TextField("descripción", blank=True)
    is_active = models.BooleanField("activa", default=True)
    sort_order = models.PositiveIntegerField("orden", default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"

    def __str__(self):
        return self.name


class Product(models.Model):
    class SaleUnit(models.TextChoices):
        KILOGRAM = "kg", "Kilogramo"
        UNIT = "unit", "Unidad"

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="categoría",
    )
    name = models.CharField("nombre", max_length=160)
    slug = models.SlugField("identificador", max_length=170, unique=True)
    description = models.TextField("descripción", blank=True)
    image = models.ImageField(
        "imagen",
        upload_to="products/",
        blank=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"]),
            validate_image_size,
        ],
    )
    price = models.DecimalField(
        "precio por kilogramo o presentación",
        max_digits=12,
        decimal_places=0,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    price_250g = models.DecimalField(
        "precio desde 250 g",
        max_digits=12,
        decimal_places=0,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    sale_unit = models.CharField(
        "unidad de venta",
        max_length=8,
        choices=SaleUnit.choices,
        default=SaleUnit.KILOGRAM,
    )
    package_label = models.CharField("formato de presentación", max_length=64, blank=True)
    is_active = models.BooleanField("activo", default=False)
    is_available = models.BooleanField("disponible", default=False)
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "producto"
        verbose_name_plural = "productos"

    def __str__(self):
        return self.name

    @property
    def minimum_grams(self):
        return 50

    def quote_for(self, *, grams=0, units=0):
        if self.sale_unit == self.SaleUnit.KILOGRAM:
            if grams < self.minimum_grams:
                raise ValidationError(
                    f"La cantidad mínima de {self.name} es {self.minimum_grams} g."
                )
            if grams < 1000:
                if self.price_250g is not None:
                    price = self.price_250g
                    divisor = Decimal(250)
                    tier = "250g"
                else:
                    price = self.price
                    divisor = Decimal(1000)
                    tier = "kg"
            else:
                price = self.price
                divisor = Decimal(1000)
                tier = "kg"
            if price is None:
                raise ValidationError("El producto no tiene un precio minorista configurado.")
            subtotal = (price * Decimal(grams) / divisor).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        else:
            if units < 1:
                raise ValidationError("La cantidad de unidades debe ser positiva.")
            if self.price is None:
                raise ValidationError("El producto no tiene un precio minorista configurado.")
            price = self.price
            tier = "unit"
            subtotal = (price * Decimal(units)).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        return price, tier, subtotal

    def subtotal_for(self, *, grams=0, units=0):
        return self.quote_for(grams=grams, units=units)[2]


class WholesalePrice(models.Model):
    class PriceUnit(models.TextChoices):
        KILOGRAM = "kg", "Kilogramo"
        PACKAGE = "package", "Envase / unidad"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="wholesale_prices",
        verbose_name="producto",
    )
    price_list = models.CharField("lista de precios", max_length=120)
    price = models.DecimalField(
        "precio mayorista en CLP",
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(Decimal("1"))],
    )
    price_unit = models.CharField(
        "unidad del precio",
        max_length=8,
        choices=PriceUnit.choices,
    )
    package_label = models.CharField(
        "formato del envase",
        max_length=64,
        blank=True,
    )

    class Meta:
        ordering = ["product__category__name", "product__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "price_list"],
                name="unique_wholesale_price_per_list",
            ),
        ]
        verbose_name = "precio mayorista"
        verbose_name_plural = "precios mayoristas"

    def clean(self):
        super().clean()
        if self.price_unit == self.PriceUnit.PACKAGE and not self.package_label.strip():
            raise ValidationError(
                {"package_label": "Indica el formato que aparece en la lista."}
            )
        if self.price_unit == self.PriceUnit.KILOGRAM and self.package_label:
            raise ValidationError(
                {"package_label": "Un precio por kilogramo no lleva formato de envase."}
            )

    def __str__(self):
        unit = self.package_label or "kg"
        return f"{self.product.name}: ${self.price}/{unit}"

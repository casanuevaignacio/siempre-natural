import re

from rest_framework import serializers

from .models import Category, Product, WholesalePrice


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description")


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "category",
            "image_url",
            "price",
            "price_250g",
            "sale_unit",
            "package_label",
        )

    def get_image_url(self, product):
        if not product.image:
            return None
        request = self.context.get("request")
        url = product.image.url
        return request.build_absolute_uri(url) if request else url


class WholesalePriceSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    category_name = serializers.CharField(
        source="product.category.name",
        read_only=True,
    )

    class Meta:
        model = WholesalePrice
        fields = (
            "id",
            "product_name",
            "category_name",
            "price_list",
            "price",
            "price_unit",
            "package_label",
        )


def valid_whatsapp_number(value):
    value = value.strip()
    if not re.fullmatch(r"\+\d[\d\s().-]*", value):
        return ""
    normalized = re.sub(r"\D", "", value)
    return normalized if 8 <= len(normalized) <= 15 else ""

from django.contrib import admin
from django.conf import settings

from .models import Category, Product, WholesalePrice


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


class WholesalePriceInline(admin.TabularInline):
    model = WholesalePrice
    extra = 0
    fields = ("price_list", "price", "price_unit", "package_label")
    ordering = ("price_list",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price",
        "price_250g",
        "sale_unit",
        "package_label",
        "is_active",
        "is_available",
    )
    list_filter = ("category", "sale_unit", "is_active", "is_available")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_active", "is_available")
    inlines = [WholesalePriceInline]
    ordering = ("category__name", "name")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if settings.MEDIA_UPLOADS_ENABLED:
            return fields
        return (*fields, "image", "media_uploads_notice")

    @admin.display(description="Carga de imágenes")
    def media_uploads_notice(self, obj):
        return (
            "Deshabilitada en producción hasta configurar almacenamiento externo "
            "para las imágenes."
        )


@admin.register(WholesalePrice)
class WholesalePriceAdmin(admin.ModelAdmin):
    list_display = ("product", "price_list", "price", "price_unit", "package_label")
    list_filter = ("price_list", "price_unit", "product__category")
    search_fields = ("product__name", "product__category__name", "price_list")
    autocomplete_fields = ("product",)

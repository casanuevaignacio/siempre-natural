from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .models import Category, Product, ProductPurchase, WholesalePrice
from .spreadsheets import (
    SpreadsheetImportError,
    export_price_cost_workbook,
    import_price_cost_workbook,
)


class SpreadsheetUploadForm(forms.Form):
    workbook = forms.FileField(label="Archivo Excel (.xlsx)")

    def clean_workbook(self):
        uploaded_file = self.cleaned_data["workbook"]
        if not uploaded_file.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Selecciona un archivo Excel .xlsx.")
        if uploaded_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("El archivo no puede superar los 5 MB.")
        return uploaded_file


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
    change_list_template = "admin/catalog/product/change_list.html"
    list_display = (
        "name",
        "category",
        "price",
        "price_250g",
        "current_unit_cost",
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "spreadsheet/",
                self.admin_site.admin_view(self.spreadsheet_view),
                name="catalog_product_spreadsheet",
            ),
            path(
                "spreadsheet/export/",
                self.admin_site.admin_view(self.spreadsheet_export_view),
                name="catalog_product_spreadsheet_export",
            ),
        ]
        return custom_urls + urls

    def _check_spreadsheet_permissions(self, request):
        if not (
            request.user.has_perm("catalog.change_product")
            and request.user.has_perm("catalog.change_productpurchase")
        ):
            raise PermissionDenied

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if (
            request.user.has_perm("catalog.change_product")
            and request.user.has_perm("catalog.change_productpurchase")
        ):
            extra_context["spreadsheet_url"] = reverse(
                "admin:catalog_product_spreadsheet"
            )
        return super().changelist_view(request, extra_context=extra_context)

    def spreadsheet_export_view(self, request):
        self._check_spreadsheet_permissions(request)
        response = HttpResponse(
            export_price_cost_workbook(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = (
            'attachment; filename="precios-y-costos-siempre-natural.xlsx"'
        )
        return response

    def spreadsheet_view(self, request):
        self._check_spreadsheet_permissions(request)
        form = SpreadsheetUploadForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            try:
                counts = import_price_cost_workbook(form.cleaned_data["workbook"])
            except SpreadsheetImportError as exc:
                form.add_error("workbook", str(exc))
            else:
                messages.success(
                    request,
                    (
                        f"Planilla aplicada: {counts['products_updated']} precios "
                        f"y {counts['purchases_updated']} compras actualizados."
                    ),
                )
                return redirect("admin:catalog_product_spreadsheet")

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Planilla de precios y costos",
            "form": form,
            "export_url": reverse("admin:catalog_product_spreadsheet_export"),
        }
        return TemplateResponse(
            request,
            "admin/catalog/product/spreadsheet.html",
            context,
        )


@admin.register(WholesalePrice)
class WholesalePriceAdmin(admin.ModelAdmin):
    list_display = ("product", "price_list", "price", "price_unit", "package_label")
    list_filter = ("price_list", "price_unit", "product__category")
    search_fields = ("product__name", "product__category__name", "price_list")
    autocomplete_fields = ("product",)


class ProductPurchaseAdminForm(forms.ModelForm):
    class Meta:
        model = ProductPurchase
        fields = ("product", "purchased_on", "quantity", "total_cost", "note")

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        quantity = cleaned_data.get("quantity")
        if (
            product
            and quantity is not None
            and product.sale_unit == Product.SaleUnit.UNIT
            and quantity != quantity.to_integral_value()
        ):
            self.add_error("quantity", "La cantidad de productos por unidad debe ser entera.")
        return cleaned_data


@admin.register(ProductPurchase)
class ProductPurchaseAdmin(admin.ModelAdmin):
    list_display = ("purchased_on", "product", "purchase_unit", "quantity", "total_cost")
    list_filter = ("purchased_on", "purchase_unit", "product__category")
    search_fields = ("product__name", "note")
    autocomplete_fields = ("product",)
    date_hierarchy = "purchased_on"
    fields = ("product", "purchased_on", "quantity", "total_cost", "note")
    form = ProductPurchaseAdminForm

    def get_fields(self, _request, obj=None):
        if obj:
            return ("product", "purchase_unit", "purchased_on", "quantity", "total_cost", "note")
        return self.fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.purchase_unit = obj.product.sale_unit
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, _request, obj=None):
        if obj:
            return ("product", "purchase_unit")
        return ()

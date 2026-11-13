from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from catalog.models import Product

from .models import Order, OrderItem
from .services import snapshot_order_costs


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
        "unit_cost_snapshot",
        "cost_subtotal",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    change_list_template = "admin/orders/order/change_list.html"
    list_display = (
        "id",
        "created_at",
        "customer_name",
        "customer_email",
        "customer_account",
        "delivery_mode",
        "packaging_preference",
        "total",
        "status",
        "completed_at",
    )
    list_filter = ("status", "delivery_mode", "packaging_preference", "created_at")
    search_fields = (
        "id",
        "customer_name",
        "customer_phone",
        "customer_email",
        "customer__email",
    )
    readonly_fields = ("id", "created_at", "total", "completed_at")
    inlines = [OrderItemInline]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "margins/",
                self.admin_site.admin_view(self.margin_report_view),
                name="orders_order_margins",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if request.user.has_perm("orders.view_margin_report"):
            extra_context["margin_report_url"] = reverse("admin:orders_order_margins")
        return super().changelist_view(request, extra_context=extra_context)

    def margin_report_view(self, request):
        if not request.user.has_perm("orders.view_margin_report"):
            raise PermissionDenied

        today = timezone.localdate()
        default_start = today.replace(day=1)
        start_value = request.GET.get("start", default_start.isoformat())
        end_value = request.GET.get("end", today.isoformat())
        start_date = parse_date(start_value)
        end_date = parse_date(end_value)
        if not start_date or not end_date or start_date > end_date:
            return HttpResponseBadRequest("Indica un rango de fechas válido.")

        items = (
            OrderItem.objects.filter(
                order__status=Order.Status.COMPLETED,
                order__completed_at__date__gte=start_date,
                order__completed_at__date__lte=end_date,
            )
            .select_related("product")
            .order_by("product_name")
        )
        totals = {
            "sales": 0,
            "cost": 0,
            "items": 0,
            "costed_items": 0,
            "missing_items": 0,
        }
        products = {}
        for item in items:
            product = products.setdefault(
                item.product_id,
                {
                    "product_id": item.product_id,
                    "name": item.product_name,
                    "sales": 0,
                    "cost": 0,
                    "items": 0,
                    "costed_items": 0,
                    "missing_items": 0,
                    "order_ids": set(),
                },
            )
            product["order_ids"].add(item.order_id)
            for bucket in (totals, product):
                bucket["sales"] += item.subtotal
                bucket["items"] += 1
                if item.cost_subtotal is None:
                    bucket["missing_items"] += 1
                else:
                    bucket["cost"] += item.cost_subtotal
                    bucket["costed_items"] += 1

        def add_margin(bucket):
            bucket["profit"] = bucket["sales"] - bucket["cost"]
            bucket["margin"] = (
                bucket["profit"] * 100 / bucket["sales"]
                if bucket["sales"] and not bucket["missing_items"]
                else None
            )

        add_margin(totals)
        product_rows = sorted(products.values(), key=lambda row: row["name"].casefold())
        for product in product_rows:
            product["order_count"] = len(product["order_ids"])
            del product["order_ids"]
            add_margin(product)

        complete_cost_products = [
            product
            for product in product_rows
            if product["sales"] and not product["missing_items"]
        ]
        best_margin = sorted(
            complete_cost_products,
            key=lambda row: (row["margin"], row["profit"]),
            reverse=True,
        )[:10]
        highest_profit = sorted(
            complete_cost_products,
            key=lambda row: row["profit"],
            reverse=True,
        )[:10]

        sold_order_counts = {
            product.pk: 0
            for product in Product.objects.filter(is_active=True).only("pk")
        }
        sold_order_counts.update(
            {product["product_id"]: product["order_count"] for product in product_rows}
        )
        orders_by_product = {
            product["product_id"]: product["order_count"]
            for product in product_rows
        }
        product_names = {
            product.pk: product.name
            for product in Product.objects.filter(pk__in=sold_order_counts).only("pk", "name")
        }
        most_ordered = sorted(
            (
                {"name": product_names[product_id], "order_count": order_count}
                for product_id, order_count in orders_by_product.items()
            ),
            key=lambda row: (-row["order_count"], row["name"].casefold()),
        )[:10]
        least_ordered = sorted(
            (
                {"name": product_names[product_id], "order_count": order_count}
                for product_id, order_count in sold_order_counts.items()
            ),
            key=lambda row: (row["order_count"], row["name"].casefold()),
        )[:10]

        chart_colors = (
            "#365b3d",
            "#77916c",
            "#c3a75c",
            "#627b8c",
            "#a36b53",
            "#8b7896",
        )
        sales_chart = sorted(product_rows, key=lambda row: row["sales"], reverse=True)[:8]
        sales_max = max((product["sales"] for product in sales_chart), default=0)
        for index, product in enumerate(sales_chart):
            product["bar_percent"] = (
                round(product["sales"] * 100 / sales_max, 1) if sales_max else 0
            )
            product["chart_color"] = chart_colors[index % len(chart_colors)]

        profit_chart = highest_profit[:8]
        profit_max = max((abs(product["profit"]) for product in profit_chart), default=0)
        for product in profit_chart:
            product["bar_percent"] = (
                round(abs(product["profit"]) * 100 / profit_max, 1)
                if profit_max
                else 0
            )

        pie_products = sales_chart[:5]
        pie_remainder = totals["sales"] - sum(
            product["sales"] for product in pie_products
        )
        pie_data = [
            {
                "name": product["name"],
                "sales": product["sales"],
                "color": chart_colors[index],
            }
            for index, product in enumerate(pie_products)
        ]
        if pie_remainder > 0:
            pie_data.append(
                {
                    "name": "Otros productos",
                    "sales": pie_remainder,
                    "color": "#b9bcae",
                }
            )
        pie_start = 0
        for index, slice_data in enumerate(pie_data):
            pie_end = (
                100
                if index == len(pie_data) - 1
                else pie_start + slice_data["sales"] * 100 / totals["sales"]
            )
            slice_data["start"] = round(pie_start, 2)
            slice_data["end"] = round(pie_end, 2)
            slice_data["percent"] = round(
                slice_data["sales"] * 100 / totals["sales"],
                1,
            )
            pie_start = pie_end

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Reporte de márgenes",
            "start_date": start_value,
            "end_date": end_value,
            "totals": totals,
            "products": product_rows,
            "best_margin": best_margin,
            "highest_profit": highest_profit,
            "most_ordered": most_ordered,
            "least_ordered": least_ordered,
            "sales_chart": sales_chart,
            "profit_chart": profit_chart,
            "pie_data": pie_data,
        }
        return TemplateResponse(
            request,
            "admin/orders/order/margins.html",
            context,
        )

    def save_model(self, request, obj, form, change):
        was_completed = False
        if change:
            was_completed = (
                Order.objects.only("status")
                .get(pk=obj.pk)
                .status
                == Order.Status.COMPLETED
            )
        newly_completed = obj.status == Order.Status.COMPLETED and not was_completed
        if newly_completed:
            obj.completed_at = timezone.now()
        obj._snapshot_costs_on_save = newly_completed
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if getattr(form.instance, "_snapshot_costs_on_save", False):
            obj = form.instance
            snapshot_order_costs(obj)
            del obj._snapshot_costs_on_save

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
                    "packaging_preference",
                    "delivery_address",
                    "notes",
                ]
            )
        return fields

    @admin.display(description="Cuenta de cliente")
    def customer_account(self, order):
        return order.customer.email if order.customer_id else "Pedido de invitado"

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.utils import timezone

from catalog.models import ProductPurchase

from .models import Order


def snapshot_order_costs(order: Order) -> None:
    if order.completed_at is None:
        raise ValueError("El pedido debe tener fecha de completado para registrar sus costos.")

    completed_on = timezone.localdate(order.completed_at)
    for item in order.items.select_related("product"):
        if item.cost_subtotal is not None:
            continue

        unit_cost = item.product.current_unit_cost
        if unit_cost is None:
            purchases = ProductPurchase.objects.filter(
                product_id=item.product_id,
                purchase_unit=item.sale_unit,
                purchased_on__lte=completed_on,
            ).aggregate(quantity=Sum("quantity"), total_cost=Sum("total_cost"))
            quantity = purchases["quantity"]
            total_cost = purchases["total_cost"]
            if not quantity or total_cost is None:
                continue
            unit_cost = total_cost / quantity
        if item.sale_unit == item.product.SaleUnit.KILOGRAM:
            sold_quantity = Decimal(item.quantity_grams) / Decimal(1000)
        else:
            sold_quantity = Decimal(item.quantity_units)

        item.unit_cost_snapshot = unit_cost.quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )
        item.cost_subtotal = (unit_cost * sold_quantity).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
        item.save(update_fields=["unit_cost_snapshot", "cost_subtotal"])

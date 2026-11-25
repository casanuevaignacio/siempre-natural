from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from catalog.models import Product, WholesalePrice


LIST_NAME = "Lista mayorista 2026 (PDF proporcionado)"
HEADERS = {
    "product": ("producto",),
    "price": ("precio desde 1 kilo clp)", "precio desde 1 kilo clp"),
    "price_250g": ("precio desde 250 g (clp)",),
    "price_5kg": ("precio por 5k",),
    "price_10kg": ("precio por 10k",),
    "closed_price": ("formarto cerrado", "formato cerrado"),
    "closed_format": ("kilos formatos", "formato kilos"),
}


def _header_key(value):
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _optional_price(value, label, row_number):
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or value.upper().startswith("NO"):
            return None
    try:
        number = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        raise CommandError(f"{label} no es válido en la fila {row_number}.") from None
    if not number.is_finite() or number < 0:
        raise CommandError(f"{label} no es válido en la fila {row_number}.")
    if number == 0:
        return None
    if number != number.to_integral_value():
        raise CommandError(f"{label} debe ser un importe entero en la fila {row_number}.")
    return number.quantize(Decimal("1"))


def _package_label(product, existing):
    if existing and existing.package_label and not existing.package_label.startswith("="):
        return existing.package_label
    if product.package_label and not product.package_label.startswith("="):
        return product.package_label
    match = re.search(
        r"(\d+(?:[.,]\d+)?\s*(?:kg|g|ml|cc|lt|l|un|u))\s*$",
        product.name,
        re.IGNORECASE,
    )
    return match.group(1) if match else "Unidad"


class Command(BaseCommand):
    help = "Actualiza la tarifa mayorista y sus tramos desde un archivo Excel."

    def add_arguments(self, parser):
        parser.add_argument("--xlsx", required=True, help="Ruta al Excel mayorista .xlsx.")

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["xlsx"])
        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
        except (OSError, InvalidFileException, ValueError) as exc:
            raise CommandError(f"No se pudo leer el archivo Excel: {path}") from exc

        if not workbook.worksheets:
            raise CommandError("El archivo no contiene hojas.")
        sheet = workbook.active
        headers = [_header_key(cell) for cell in next(sheet.iter_rows(min_row=1, max_row=1, values_only=True))]
        column_indexes = {}
        for key, aliases in HEADERS.items():
            found = next((headers.index(alias) for alias in aliases if alias in headers), None)
            if found is None:
                raise CommandError(f"Falta una columna requerida para {key}.")
            column_indexes[key] = found

        products = list(Product.objects.select_related("category"))
        by_name = {}
        by_slug = {}
        for product in products:
            by_name.setdefault(slugify(product.name), []).append(product)
            by_slug[product.slug] = product

        def match_product(name):
            key = slugify(name)
            candidates = by_name.get(key, [])
            if len(candidates) == 1:
                return candidates[0]
            if key in by_slug:
                return by_slug[key]
            prefix_matches = [product for slug, product in by_slug.items() if slug.startswith(f"{key}-")]
            if len(prefix_matches) == 1:
                return prefix_matches[0]
            return None

        imported_ids = set()
        imported = 0
        unavailable = 0
        created = 0
        for row_number, values in enumerate(
            sheet.iter_rows(min_row=2, values_only=True),
            start=2,
        ):
            if not any(value is not None for value in values):
                continue
            row = {key: values[index] if index < len(values) else None for key, index in column_indexes.items()}
            name = row["product"]
            if not isinstance(name, str) or not name.strip():
                raise CommandError(f"Falta el nombre del producto en la fila {row_number}.")
            name = name.strip()
            product = match_product(name)
            if product is None:
                raise CommandError(
                    f"No se pudo asociar {name!r} con un producto existente (fila {row_number})."
                )
            if product.pk in imported_ids:
                raise CommandError(f"El producto {name!r} está repetido en la fila {row_number}.")
            imported_ids.add(product.pk)

            price = _optional_price(row["price"], "El precio por kilo o unidad", row_number)
            price_250g = _optional_price(row["price_250g"], "El precio desde 250 g", row_number)
            price_5kg = _optional_price(row["price_5kg"], "El precio desde 5 kg", row_number)
            price_10kg = _optional_price(row["price_10kg"], "El precio desde 10 kg", row_number)
            closed_price = _optional_price(row["closed_price"], "El precio de formato cerrado", row_number)
            closed_format = str(row["closed_format"] or "").strip()
            if closed_format == "0":
                closed_format = ""
            if bool(closed_price) != bool(closed_format):
                raise CommandError(
                    f"El precio y la cantidad del formato cerrado deben ir juntos en la fila {row_number}."
                )
            if closed_format and not re.fullmatch(r"\d+(?:[.,]\d+)?\s*[kKuU]", closed_format):
                raise CommandError(f"El formato cerrado no es válido en la fila {row_number}.")

            existing = WholesalePrice.objects.filter(
                product=product,
                price_list=LIST_NAME,
            ).first()
            price_unit = (
                WholesalePrice.PriceUnit.PACKAGE
                if product.sale_unit == Product.SaleUnit.UNIT
                else WholesalePrice.PriceUnit.KILOGRAM
            )
            price_package_label = _package_label(product, existing) if price_unit == WholesalePrice.PriceUnit.PACKAGE else ""
            item, was_created = WholesalePrice.objects.update_or_create(
                product=product,
                price_list=LIST_NAME,
                defaults={
                    "name_override": name,
                    "price": price,
                    "price_250g": price_250g,
                    "price_5kg": price_5kg,
                    "price_10kg": price_10kg,
                    "closed_price": closed_price,
                    "closed_format": closed_format,
                    "price_unit": price_unit,
                    "package_label": price_package_label,
                },
            )
            item.full_clean()
            imported += 1
            created += int(was_created)
            unavailable += int(price is None and not any((price_250g, price_5kg, price_10kg, closed_price)))

        stale = WholesalePrice.objects.filter(price_list=LIST_NAME).exclude(
            product_id__in=imported_ids
        )
        removed = stale.count()
        stale.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Tarifa actualizada: {imported} productos, {created} nuevos, "
                f"{unavailable} sin precio y {removed} precios antiguos retirados."
            )
        )

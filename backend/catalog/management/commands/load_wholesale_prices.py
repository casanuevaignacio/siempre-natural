import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category, Product, WholesalePrice


class Command(BaseCommand):
    help = "Carga la lista mayorista 2026 en el catálogo interno de administración."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            help="Ruta a una lista CSV con el mismo formato que la lista incluida.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = (
            Path(options["csv_path"])
            if options["csv_path"]
            else Path(__file__).resolve().parents[2]
            / "data"
            / "lista_mayorista_2026.csv"
        )
        try:
            file_handle = csv_path.open(encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CommandError(f"No se pudo leer el archivo CSV: {csv_path}") from exc

        list_name = "Lista mayorista 2026 (PDF proporcionado)"
        loaded = 0
        categories = {}

        with file_handle:
            reader = csv.DictReader(file_handle)
            expected_columns = {
                "category",
                "product",
                "price",
                "price_unit",
                "package_label",
            }
            if not reader.fieldnames or set(reader.fieldnames) != expected_columns:
                raise CommandError(
                    "El CSV debe contener las columnas: "
                    "category, product, price, price_unit, package_label."
                )

            for row_number, row in enumerate(reader, start=2):
                category_name = row["category"].strip()
                product_name = row["product"].strip()
                package_label = row["package_label"].strip()
                if not category_name or not product_name:
                    raise CommandError(f"Falta categoría o producto en la fila {row_number}.")
                try:
                    price = Decimal(row["price"])
                except (InvalidOperation, TypeError) as exc:
                    raise CommandError(
                        f"El precio de la fila {row_number} no es un número válido."
                    ) from exc
                if price <= 0:
                    raise CommandError(f"El precio de la fila {row_number} debe ser positivo.")

                price_unit = row["price_unit"].strip()
                if price_unit == WholesalePrice.PriceUnit.PACKAGE and not package_label:
                    raise CommandError(
                        f"Falta el formato de envase de la fila {row_number}."
                    )
                if price_unit == WholesalePrice.PriceUnit.KILOGRAM and package_label:
                    raise CommandError(
                        f"La fila {row_number} tiene formato de envase con precio por kg."
                    )
                if price_unit not in WholesalePrice.PriceUnit.values:
                    raise CommandError(
                        f"La unidad de precio de la fila {row_number} no es válida."
                    )

                category = categories.get(category_name)
                if category is None:
                    category_slug = slugify(category_name)
                    category, _ = Category.objects.get_or_create(
                        slug=category_slug,
                        defaults={
                            "name": category_name,
                            "is_active": False,
                        },
                    )
                    if category.name != category_name:
                        raise CommandError(
                            f"El identificador de categoría {category_slug!r} ya se usa "
                            f"para {category.name!r}."
                        )
                    categories[category_name] = category

                product_slug = slugify(product_name)
                product, _ = Product.objects.get_or_create(
                    slug=product_slug,
                    defaults={
                        "category": category,
                        "name": product_name,
                        "price": None,
                        "is_active": False,
                        "is_available": False,
                    },
                )
                if product.name != product_name or product.category_id != category.id:
                    raise CommandError(
                        f"El identificador de producto {product_slug!r} ya se usa "
                        "para otro producto."
                    )

                WholesalePrice.objects.update_or_create(
                    product=product,
                    price_list=list_name,
                    defaults={
                        "price": price,
                        "price_unit": price_unit,
                        "package_label": package_label,
                    },
                )
                loaded += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Lista cargada: {loaded} precios en {len(categories)} categorías. "
                "Los precios mayoristas no se publican en la tienda."
            )
        )

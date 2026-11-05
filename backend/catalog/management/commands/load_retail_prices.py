import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category, Product


class Command(BaseCommand):
    help = "Importa la lista normal de precios y publica sus productos disponibles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            help="Ruta a una lista CSV con el mismo formato de la lista normal.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = (
            Path(options["csv_path"])
            if options["csv_path"]
            else Path(__file__).resolve().parents[2]
            / "data"
            / "lista_precios_normal_2026.csv"
        )
        try:
            file_handle = csv_path.open(encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CommandError(f"No se pudo leer el archivo CSV: {csv_path}") from exc

        rows = []
        seen_products = set()
        seen_categories = {}
        with file_handle:
            reader = csv.DictReader(file_handle)
            expected_columns = {
                "category",
                "product",
                "price_250g",
                "price",
                "sale_unit",
                "package_label",
            }
            if not reader.fieldnames or set(reader.fieldnames) != expected_columns:
                raise CommandError(
                    "El CSV debe contener las columnas: "
                    "category, product, price_250g, price, sale_unit, package_label."
                )

            for row_number, row in enumerate(reader, start=2):
                category_name = row["category"].strip()
                product_name = row["product"].strip()
                if not category_name or not product_name:
                    raise CommandError(
                        f"Falta categoría o producto en la fila {row_number}."
                    )

                product_slug = slugify(product_name)
                if product_slug in seen_products:
                    raise CommandError(
                        f"El producto {product_name!r} está repetido en la fila "
                        f"{row_number}."
                    )
                seen_products.add(product_slug)

                category_slug = slugify(category_name)
                previous_category = seen_categories.setdefault(category_slug, category_name)
                if previous_category != category_name:
                    raise CommandError(
                        f"Las categorías {previous_category!r} y {category_name!r} "
                        "comparten el mismo identificador."
                    )

                prices = {}
                for field in ("price_250g", "price"):
                    raw_price = row[field].strip()
                    if not raw_price:
                        prices[field] = None
                        continue
                    try:
                        price = Decimal(raw_price)
                    except (InvalidOperation, TypeError) as exc:
                        raise CommandError(
                            f"El precio {field} de la fila {row_number} no es válido."
                        ) from exc
                    if price <= 0 or price != price.to_integral_value():
                        raise CommandError(
                            f"El precio {field} de la fila {row_number} debe ser "
                            "un CLP entero positivo."
                        )
                    prices[field] = price

                sale_unit = row["sale_unit"].strip()
                if sale_unit not in Product.SaleUnit.values:
                    raise CommandError(
                        f"La unidad de venta de la fila {row_number} no es válida."
                    )
                package_label = row["package_label"].strip()
                if sale_unit == Product.SaleUnit.UNIT and not package_label:
                    raise CommandError(
                        f"Falta el formato de presentación en la fila {row_number}."
                    )
                if sale_unit == Product.SaleUnit.KILOGRAM and package_label:
                    raise CommandError(
                        f"La fila {row_number} tiene formato de envase para un producto "
                        "por peso."
                    )

                rows.append(
                    {
                        "category_name": category_name,
                        "category_slug": category_slug,
                        "product_name": product_name,
                        "product_slug": product_slug,
                        "price_250g": prices["price_250g"],
                        "price": prices["price"],
                        "sale_unit": sale_unit,
                        "package_label": package_label,
                    }
                )

        if not rows:
            raise CommandError("El CSV no contiene productos.")

        existing_by_name = {}
        for existing_category in Category.objects.all():
            name_key = slugify(existing_category.name).replace("-", "")
            existing_by_name.setdefault(name_key, []).append(existing_category)
        used_category_slugs = {}
        for row in rows:
            category = Category.objects.filter(slug=row["category_slug"]).first()
            if category is None:
                matches = existing_by_name.get(
                    slugify(row["category_name"]).replace("-", ""),
                    [],
                )
                if len(matches) > 1:
                    raise CommandError(
                        f"No se puede identificar de forma única la categoría "
                        f"{row['category_name']!r}."
                    )
                if matches:
                    category = matches[0]
                    row["category_slug"] = category.slug
            previous_name = used_category_slugs.setdefault(
                row["category_slug"],
                row["category_name"],
            )
            if previous_name != row["category_name"]:
                raise CommandError(
                    f"Las categorías {previous_name!r} y {row['category_name']!r} "
                    "se asignan al mismo registro."
                )

        category_slugs = {row["category_slug"] for row in rows}
        product_slugs = {row["product_slug"] for row in rows}
        Category.objects.exclude(slug__in=category_slugs).update(is_active=False)
        Product.objects.exclude(slug__in=product_slugs).update(
            is_active=False,
            is_available=False,
        )

        categories = {}
        for row in rows:
            category_name = row["category_name"]
            category = categories.get(category_name)
            if category is None:
                category, _ = Category.objects.get_or_create(
                    slug=row["category_slug"],
                    defaults={
                        "name": category_name,
                        "is_active": True,
                        "sort_order": 0,
                    },
                )
                category.name = category_name
                category.is_active = True
                category.save(update_fields=["name", "is_active"])
                categories[category_name] = category

            product, _ = Product.objects.get_or_create(
                slug=row["product_slug"],
                defaults={
                    "category": category,
                    "name": row["product_name"],
                    "price_250g": row["price_250g"],
                    "price": row["price"],
                    "sale_unit": row["sale_unit"],
                    "package_label": row["package_label"],
                    "is_active": bool(row["price"]),
                    "is_available": bool(row["price"]),
                },
            )
            if product.name != row["product_name"]:
                raise CommandError(
                    f"El identificador de producto {row['product_slug']!r} ya se "
                    "usa para otro producto."
                )

            product.category = category
            product.price_250g = row["price_250g"]
            product.price = row["price"]
            product.sale_unit = row["sale_unit"]
            product.package_label = row["package_label"]
            product.is_active = bool(row["price"])
            product.is_available = bool(row["price"])
            product.save(
                update_fields=[
                    "category",
                    "price_250g",
                    "price",
                    "sale_unit",
                    "package_label",
                    "is_active",
                    "is_available",
                    "updated_at",
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Lista normal cargada: {len(rows)} productos en {len(categories)} "
                "categorías; "
                f"{Product.objects.filter(is_active=True, is_available=True).count()} "
                "productos con precio están disponibles en el catálogo público."
            )
        )

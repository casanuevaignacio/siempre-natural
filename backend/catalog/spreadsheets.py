from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import BadZipFile

from django.core.exceptions import ValidationError
from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from django.utils.text import slugify

from .models import Category, Product, ProductPurchase


WORKBOOK_NAME = "precios-y-costos-siempre-natural.xlsx"
MAX_WORKBOOK_SIZE = 5 * 1024 * 1024
MAX_DATA_ROWS = 20_000
PRICE_SHEET = "Precios de venta"
PURCHASE_SHEET = "Compras y costos"
INSTRUCTIONS_SHEET = "Instrucciones"
PRICE_HEADERS = (
    "ID producto",
    "Identificador",
    "Producto",
    "Categoría",
    "Unidad de venta",
    "Precio venta (CLP)",
    "Precio desde 250 g (CLP)",
    "Costo actual por kg/unidad (CLP)",
    "Formato de presentación",
)
LEGACY_PRICE_HEADERS = PRICE_HEADERS[:-1]
PURCHASE_HEADERS = (
    "ID compra",
    "Identificador producto",
    "Producto",
    "Fecha de compra",
    "Unidad",
    "Cantidad",
    "Costo total (CLP)",
    "Nota",
)


class SpreadsheetImportError(Exception):
    pass


def _style_sheet(sheet, editable_columns):
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="365B3D")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for column in editable_columns:
        for cell in sheet.iter_cols(
            min_col=column,
            max_col=column,
            min_row=2,
        ):
            for value in cell:
                value.fill = PatternFill("solid", fgColor="FFF2CC")
    for column_index, column_cells in enumerate(sheet.columns, start=1):
        width = min(
            max(len(str(cell.value or "")) for cell in column_cells) + 2,
            42,
        )
        sheet.column_dimensions[get_column_letter(column_index)].width = max(width, 14)


def export_price_cost_workbook():
    workbook = Workbook()
    price_sheet = workbook.active
    price_sheet.title = PRICE_SHEET
    price_sheet.append(PRICE_HEADERS)
    products = Product.objects.select_related("category").order_by("category__name", "name")
    for product in products:
        price_sheet.append(
            [
                product.pk,
                product.slug,
                product.name,
                product.category.name,
                product.get_sale_unit_display(),
                product.price,
                product.price_250g,
                product.current_unit_cost,
                product.package_label,
            ]
        )
    _style_sheet(price_sheet, (2, 3, 4, 5, 6, 7, 8, 9))
    for row in price_sheet.iter_rows(min_row=2, min_col=6, max_col=8):
        for cell in row:
            cell.number_format = '#,##0.0000' if cell.column == 8 else '#,##0'

    purchase_sheet = workbook.create_sheet(PURCHASE_SHEET)
    purchase_sheet.append(PURCHASE_HEADERS)
    purchases = ProductPurchase.objects.select_related("product").order_by(
        "purchased_on",
        "pk",
    )
    for purchase in purchases:
        purchase_sheet.append(
            [
                purchase.pk,
                purchase.product.slug,
                purchase.product.name,
                purchase.purchased_on,
                purchase.get_purchase_unit_display(),
                purchase.quantity,
                purchase.total_cost,
                purchase.note,
            ]
        )
    _style_sheet(purchase_sheet, (4, 6, 7, 8))
    for cell in purchase_sheet["D"][1:]:
        cell.number_format = "yyyy-mm-dd"
    for cell in purchase_sheet["F"][1:]:
        cell.number_format = "0.000"
    for cell in purchase_sheet["G"][1:]:
        cell.number_format = '#,##0.00'

    instructions = workbook.create_sheet(INSTRUCTIONS_SHEET)
    for line in (
        ("Instrucciones",),
        ("Edita las celdas amarillas. No cambies el ID de un producto existente.",),
        ("Puedes cambiar el nombre, identificador, categoría, unidad, formato, precios y costo.",),
        ("Para agregar un producto, agrega una fila y deja vacío su ID. Si el identificador está vacío, se genera desde el nombre.",),
        ("Usa Kilogramo o Unidad como unidad de venta. Para productos por unidad puedes indicar el formato de presentación.",),
        ("Los precios en blanco quitan ese precio de venta del producto.",),
        ("El costo actual se expresa por kg para productos a granel y por unidad para presentaciones; déjalo en blanco si no lo conoces.",),
        ("Los productos omitidos en la planilla se desactivan en la tienda; no se borran y se conservan sus ventas y compras históricas.",),
        ("Para agregar o eliminar compras usa Catálogo > Compras de productos en Django Admin.",),
        ("El costo actual tiene prioridad al calcular ventas futuras; si está vacío, se usa el promedio de compras anteriores.",),
        ("Cambiar el costo actual o una compra no altera costos históricos ya guardados.",),
        ("Sube este archivo .xlsx en la página Gestión de precios y costos para aplicar los cambios.",),
    ):
        instructions.append(line)
    instructions.column_dimensions["A"].width = 110
    instructions["A1"].font = Font(bold=True, size=14, color="365B3D")
    for row in instructions.iter_rows(min_row=2):
        row[0].alignment = Alignment(wrap_text=True)
    instructions.freeze_panes = "A2"

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _rows_for_sheet(sheet, headers, *, legacy_headers=None):
    if sheet.max_row > MAX_DATA_ROWS + 1:
        raise SpreadsheetImportError(
            f"La hoja {sheet.title!r} supera el máximo de {MAX_DATA_ROWS} filas."
        )
    actual_headers = tuple(cell.value for cell in sheet[1])
    while actual_headers and actual_headers[-1] is None:
        actual_headers = actual_headers[:-1]
    if actual_headers != headers and actual_headers != legacy_headers:
        raise SpreadsheetImportError(
            f"Las columnas de la hoja {sheet.title!r} no coinciden con la plantilla."
        )
    row_headers = actual_headers
    rows = []
    for row_number, values in enumerate(
        sheet.iter_rows(min_row=2, values_only=True),
        start=2,
    ):
        values = values[: len(row_headers)]
        if not any(value is not None for value in values):
            continue
        if len(values) < len(row_headers):
            values = (*values, *(None for _ in range(len(row_headers) - len(values))))
        row = dict(zip(row_headers, values))
        if legacy_headers and row_headers == legacy_headers:
            row["Formato de presentación"] = ""
        rows.append((row_number, row))
    return rows


def _decimal(value, label, row_number, *, allow_blank=False, integer=False):
    if value is None or value == "":
        if allow_blank:
            return None
        raise SpreadsheetImportError(f"Falta {label} en la fila {row_number}.")
    try:
        number = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        raise SpreadsheetImportError(
            f"{label} no es un número válido en la fila {row_number}."
        ) from None
    if not number.is_finite() or number <= 0:
        raise SpreadsheetImportError(
            f"{label} debe ser positivo en la fila {row_number}."
        )
    if integer and number != number.to_integral_value():
        raise SpreadsheetImportError(
            f"{label} debe ser un CLP entero en la fila {row_number}."
        )
    if integer:
        number = number.quantize(Decimal("1"))
    return number


def _identifier(value, label, row_number):
    if value is None or value == "":
        raise SpreadsheetImportError(f"Falta {label} en la fila {row_number}.")
    try:
        identifier = int(value)
    except (TypeError, ValueError, OverflowError):
        raise SpreadsheetImportError(
            f"{label} no es válido en la fila {row_number}."
        ) from None
    if str(value).strip() not in (str(identifier), f"{identifier}.0"):
        raise SpreadsheetImportError(
            f"{label} no es válido en la fila {row_number}."
        )
    return identifier


def _purchase_date(value, row_number):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise SpreadsheetImportError(
        f"La fecha de compra no es válida en la fila {row_number}; usa AAAA-MM-DD."
    )


def _validate_workbook_file(uploaded_file):
    if uploaded_file.size > MAX_WORKBOOK_SIZE:
        raise SpreadsheetImportError("El archivo supera el límite de 5 MB.")
    if not uploaded_file.name.lower().endswith(".xlsx"):
        raise SpreadsheetImportError("Sube el archivo Excel .xlsx descargado desde esta página.")
    try:
        return load_workbook(uploaded_file, data_only=False)
    except (BadZipFile, InvalidFileException, OSError, ValueError) as exc:
        raise SpreadsheetImportError("No se pudo leer el archivo Excel .xlsx.") from exc


@transaction.atomic
def import_price_cost_workbook(
    uploaded_file,
    *,
    can_add_products=True,
    can_add_categories=True,
):
    workbook = _validate_workbook_file(uploaded_file)
    required_sheets = {PRICE_SHEET, PURCHASE_SHEET, INSTRUCTIONS_SHEET}
    if not required_sheets.issubset(workbook.sheetnames):
        raise SpreadsheetImportError(
            "El archivo debe ser la plantilla descargada desde Gestión de precios y costos."
        )

    price_rows = _rows_for_sheet(
        workbook[PRICE_SHEET],
        PRICE_HEADERS,
        legacy_headers=LEGACY_PRICE_HEADERS,
    )
    purchase_rows = _rows_for_sheet(workbook[PURCHASE_SHEET], PURCHASE_HEADERS)
    products = {product.pk: product for product in Product.objects.select_related("category")}
    categories = {
        category.name.strip().casefold(): category
        for category in Category.objects.all()
    }
    purchases = {purchase.pk: purchase for purchase in ProductPurchase.objects.select_related("product")}
    seen_product_ids = set()
    seen_product_slugs = set()
    seen_purchase_ids = set()
    product_updates = []
    product_creations = []
    purchase_updates = []
    categories_to_create = {}
    product_ids_in_workbook = set()

    for row_number, row in price_rows:
        raw_id = row["ID producto"]
        product_id = (
            _identifier(raw_id, "el ID del producto", row_number)
            if raw_id not in (None, "")
            else None
        )
        if product_id in seen_product_ids:
            raise SpreadsheetImportError(f"El producto está repetido en la fila {row_number}.")
        if product_id is not None:
            seen_product_ids.add(product_id)
            product = products.get(product_id)
            if product is None:
                raise SpreadsheetImportError(
                    f"El ID del producto de la fila {row_number} no existe en la base de datos."
                )
            product_ids_in_workbook.add(product_id)
        else:
            if not can_add_products:
                raise SpreadsheetImportError(
                    "No tienes permiso para agregar productos desde la planilla."
                )
            product = Product()

        name = row["Producto"]
        category_name = row["Categoría"]
        if not isinstance(name, str) or not name.strip():
            raise SpreadsheetImportError(f"Falta el nombre del producto en la fila {row_number}.")
        if len(name.strip()) > Product._meta.get_field("name").max_length:
            raise SpreadsheetImportError(f"El nombre del producto es demasiado largo en la fila {row_number}.")
        if not isinstance(category_name, str) or not category_name.strip():
            raise SpreadsheetImportError(
                f"Falta la categoría del producto en la fila {row_number}."
            )
        category_name = category_name.strip()
        category_key = category_name.casefold()
        category = categories.get(category_key)
        if category is None:
            category = categories_to_create.get(category_key)
            if category is None:
                if not can_add_categories:
                    raise SpreadsheetImportError(
                        f"No tienes permiso para crear la categoría {category_name!r}."
                    )
                category_slug = slugify(category_name)
                if not category_slug:
                    raise SpreadsheetImportError(
                        f"No se puede generar un identificador para la categoría de la fila {row_number}."
                    )
                if Category.objects.filter(slug=category_slug).exists():
                    raise SpreadsheetImportError(
                        f"El identificador de categoría {category_slug!r} ya se usa para otra categoría."
                    )
                if any(
                    pending.slug == category_slug
                    for pending in categories_to_create.values()
                ):
                    raise SpreadsheetImportError(
                        f"El identificador de categoría {category_slug!r} se repite en la planilla."
                    )
                category = Category(name=category_name, slug=category_slug)
                category.save()
                categories_to_create[category_key] = category

        raw_slug = row["Identificador"]
        if raw_slug in (None, ""):
            product_slug = slugify(name)
        elif isinstance(raw_slug, str):
            product_slug = slugify(raw_slug)
        else:
            raise SpreadsheetImportError(
                f"El identificador del producto no es válido en la fila {row_number}."
            )
        if not product_slug:
            raise SpreadsheetImportError(
                f"No se puede generar un identificador para el producto de la fila {row_number}."
            )
        if product_slug in seen_product_slugs:
            raise SpreadsheetImportError(
                f"El identificador {product_slug!r} está repetido en la fila {row_number}."
            )
        seen_product_slugs.add(product_slug)
        if Product.objects.filter(slug=product_slug).exclude(pk=product.pk).exists():
            raise SpreadsheetImportError(
                f"El identificador {product_slug!r} ya pertenece a otro producto (fila {row_number})."
            )

        sale_units = {
            label.casefold(): value
            for value, label in Product.SaleUnit.choices
        }
        raw_sale_unit = row["Unidad de venta"]
        sale_unit = (
            sale_units.get(raw_sale_unit.strip().casefold())
            if isinstance(raw_sale_unit, str)
            else None
        )
        if sale_unit is None:
            raise SpreadsheetImportError(
                f"La unidad de venta de la fila {row_number} debe ser Kilogramo o Unidad."
            )

        package_label = row["Formato de presentación"] or ""
        if not isinstance(package_label, str) or len(package_label) > Product._meta.get_field("package_label").max_length:
            raise SpreadsheetImportError(
                f"El formato de presentación no es válido en la fila {row_number}."
            )

        price = _decimal(
            row["Precio venta (CLP)"],
            "el precio de venta",
            row_number,
            allow_blank=True,
            integer=True,
        )
        price_250g = _decimal(
            row["Precio desde 250 g (CLP)"],
            "el precio desde 250 g",
            row_number,
            allow_blank=True,
            integer=True,
        )
        current_unit_cost = _decimal(
            row["Costo actual por kg/unidad (CLP)"],
            "el costo actual por kg o unidad",
            row_number,
            allow_blank=True,
        )
        product.name = name.strip()
        product.slug = product_slug
        product.category = category
        product.sale_unit = sale_unit
        product.package_label = package_label.strip()
        product.price = price
        product.price_250g = price_250g
        product.current_unit_cost = current_unit_cost
        try:
            product.full_clean()
        except ValidationError as exc:
            raise SpreadsheetImportError(
                f"Precios inválidos en la fila {row_number}: {exc.messages}"
            ) from exc
        if product_id is None:
            product.is_active = bool(price)
            product.is_available = bool(price)
            product_creations.append(product)
        else:
            product_updates.append(product)

    for row_number, row in purchase_rows:
        purchase_id = _identifier(row["ID compra"], "el ID de compra", row_number)
        if purchase_id in seen_purchase_ids:
            raise SpreadsheetImportError(f"La compra está repetida en la fila {row_number}.")
        seen_purchase_ids.add(purchase_id)
        purchase = purchases.get(purchase_id)
        if purchase is None or row["Unidad"] != purchase.get_purchase_unit_display():
            raise SpreadsheetImportError(
                f"La compra de la fila {row_number} no coincide con la base de datos."
            )
        purchase.purchased_on = _purchase_date(row["Fecha de compra"], row_number)
        purchase.quantity = _decimal(
            row["Cantidad"],
            "la cantidad",
            row_number,
        )
        purchase.total_cost = _decimal(
            row["Costo total (CLP)"],
            "el costo total",
            row_number,
        )
        note = row["Nota"] or ""
        if not isinstance(note, str) or len(note) > 250:
            raise SpreadsheetImportError(
                f"La nota debe tener máximo 250 caracteres en la fila {row_number}."
            )
        purchase.note = note
        try:
            purchase.full_clean()
        except ValidationError as exc:
            raise SpreadsheetImportError(
                f"Compra inválida en la fila {row_number}: {exc.messages}"
            ) from exc
        purchase_updates.append(purchase)

    if not price_rows and not purchase_rows:
        raise SpreadsheetImportError("El archivo no contiene datos para actualizar.")

    omitted_product_ids = (
        set(products) - product_ids_in_workbook if price_rows else set()
    )
    Product.objects.filter(pk__in=omitted_product_ids).update(
        is_active=False,
        is_available=False,
    )
    Product.objects.bulk_create(product_creations)
    Product.objects.bulk_update(
        product_updates,
        (
            "name",
            "slug",
            "category",
            "sale_unit",
            "package_label",
            "price",
            "price_250g",
            "current_unit_cost",
        ),
    )
    ProductPurchase.objects.bulk_update(
        purchase_updates,
        ("purchased_on", "quantity", "total_cost", "note"),
    )
    return {
        "products_updated": len(product_updates),
        "products_created": len(product_creations),
        "products_deactivated": len(omitted_product_ids),
        "purchases_updated": len(purchase_updates),
    }

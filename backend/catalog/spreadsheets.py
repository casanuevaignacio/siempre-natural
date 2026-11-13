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

from .models import Product, ProductPurchase


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
)
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
            ]
        )
    _style_sheet(price_sheet, (6, 7, 8))
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
        ("Edita solo las celdas amarillas. No cambies IDs ni identificadores.",),
        ("Los precios en blanco quitan ese precio de venta del producto.",),
        ("El costo actual se expresa por kg para productos a granel y por unidad para presentaciones; déjalo en blanco si no lo conoces.",),
        ("Las filas sin cambios se pueden dejar tal cual; las filas eliminadas del Excel no borran datos.",),
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


def _rows_for_sheet(sheet, headers):
    if sheet.max_row > MAX_DATA_ROWS + 1:
        raise SpreadsheetImportError(
            f"La hoja {sheet.title!r} supera el máximo de {MAX_DATA_ROWS} filas."
        )
    actual_headers = tuple(cell.value for cell in sheet[1])
    while actual_headers and actual_headers[-1] is None:
        actual_headers = actual_headers[:-1]
    if actual_headers != headers:
        raise SpreadsheetImportError(
            f"Las columnas de la hoja {sheet.title!r} no coinciden con la plantilla."
        )
    rows = []
    for row_number, values in enumerate(
        sheet.iter_rows(min_row=2, values_only=True),
        start=2,
    ):
        values = values[: len(headers)]
        if not any(value is not None for value in values):
            continue
        if len(values) < len(headers):
            values = (*values, *(None for _ in range(len(headers) - len(values))))
        rows.append((row_number, dict(zip(headers, values))))
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
def import_price_cost_workbook(uploaded_file):
    workbook = _validate_workbook_file(uploaded_file)
    required_sheets = {PRICE_SHEET, PURCHASE_SHEET, INSTRUCTIONS_SHEET}
    if not required_sheets.issubset(workbook.sheetnames):
        raise SpreadsheetImportError(
            "El archivo debe ser la plantilla descargada desde Gestión de precios y costos."
        )

    price_rows = _rows_for_sheet(workbook[PRICE_SHEET], PRICE_HEADERS)
    purchase_rows = _rows_for_sheet(workbook[PURCHASE_SHEET], PURCHASE_HEADERS)
    products = {product.pk: product for product in Product.objects.select_related("category")}
    purchases = {purchase.pk: purchase for purchase in ProductPurchase.objects.select_related("product")}
    seen_product_ids = set()
    seen_purchase_ids = set()
    product_updates = []
    purchase_updates = []

    for row_number, row in price_rows:
        product_id = _identifier(row["ID producto"], "el ID del producto", row_number)
        if product_id in seen_product_ids:
            raise SpreadsheetImportError(f"El producto está repetido en la fila {row_number}.")
        seen_product_ids.add(product_id)
        product = products.get(product_id)
        if product is None or row["Identificador"] != product.slug:
            raise SpreadsheetImportError(
                f"El producto de la fila {row_number} no coincide con la base de datos."
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
        product.price = price
        product.price_250g = price_250g
        product.current_unit_cost = current_unit_cost
        try:
            product.full_clean()
        except ValidationError as exc:
            raise SpreadsheetImportError(
                f"Precios inválidos en la fila {row_number}: {exc.messages}"
            ) from exc
        product_updates.append(product)

    for row_number, row in purchase_rows:
        purchase_id = _identifier(row["ID compra"], "el ID de compra", row_number)
        if purchase_id in seen_purchase_ids:
            raise SpreadsheetImportError(f"La compra está repetida en la fila {row_number}.")
        seen_purchase_ids.add(purchase_id)
        purchase = purchases.get(purchase_id)
        if (
            purchase is None
            or row["Identificador producto"] != purchase.product.slug
            or row["Unidad"] != purchase.get_purchase_unit_display()
        ):
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

    Product.objects.bulk_update(
        product_updates,
        ("price", "price_250g", "current_unit_cost"),
    )
    ProductPurchase.objects.bulk_update(
        purchase_updates,
        ("purchased_on", "quantity", "total_cost", "note"),
    )
    return {
        "products_updated": len(product_updates),
        "purchases_updated": len(purchase_updates),
    }

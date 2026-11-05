import logging

from django.conf import settings

from accounts.emails import send_configured_email


logger = logging.getLogger(__name__)


def send_order_notification(order):
    recipient = settings.STORE_CONTACT_EMAIL
    if not recipient:
        logger.warning(
            "Order notification email was not sent: STORE_CONTACT_EMAIL is empty."
        )
        return False

    item_lines = [
        f"- {item.product_name}: "
        f"{item.quantity_grams} g"
        if item.quantity_grams
        else f"- {item.product_name}: {item.quantity_units} un."
        for item in order.items.all()
    ]
    delivery = order.get_delivery_mode_display()
    if order.delivery_address:
        delivery = f"{delivery}: {order.delivery_address}"

    message_lines = [
        f"Nuevo pedido {order.id}",
        "",
        f"Cliente: {order.customer_name}",
        f"Teléfono: {order.customer_phone}",
    ]
    if order.customer_email:
        message_lines.append(f"Correo del cliente: {order.customer_email}")
    message_lines.extend(
        [
            f"Entrega: {delivery}",
            "",
            "Productos:",
            *item_lines,
            "",
            f"Total estimado: ${order.total:,.0f} CLP",
            "Confirma disponibilidad y total antes de enviar los datos para transferencia.",
        ]
    )
    if order.notes:
        message_lines.extend(["", f"Indicaciones: {order.notes}"])

    email_sent = send_configured_email(
        subject=f"Nuevo pedido {order.id} - {settings.STORE_NAME}",
        message="\n".join(message_lines),
        recipient=recipient,
    )
    if not email_sent:
        logger.error("Could not send notification email for order %s.", order.id)
    return email_sent

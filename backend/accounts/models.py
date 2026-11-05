from django.conf import settings
from django.db import models


class CustomerAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_account",
    )
    email = models.EmailField("correo electrónico", unique=True)
    email_verified = models.BooleanField("correo verificado", default=False)
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        verbose_name = "cuenta de cliente"
        verbose_name_plural = "cuentas de clientes"
        ordering = ["email"]

    def __str__(self):
        return self.email

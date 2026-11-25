import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction

from catalog.models import Product


class Command(BaseCommand):
    help = "Inicializa el catálogo público y la cuenta administradora en Render."

    @transaction.atomic
    def handle(self, *args, **options):
        if not Product.objects.exists():
            fixture = (
                Path(__file__).resolve().parents[2]
                / "fixtures"
                / "render_public_catalog.json"
            )
            if not fixture.is_file():
                raise CommandError(f"No se encontró el catálogo inicial: {fixture}")
            call_command("loaddata", str(fixture), verbosity=0)
            self.stdout.write(self.style.SUCCESS("Catálogo público inicial cargado."))
        else:
            self.stdout.write("El catálogo ya tiene productos; se conserva sin cambios.")

        username = os.environ.get("DJANGO_BOOTSTRAP_ADMIN_USERNAME", "").strip()
        email = os.environ.get("DJANGO_BOOTSTRAP_ADMIN_EMAIL", "").strip()
        password = os.environ.get("DJANGO_BOOTSTRAP_ADMIN_PASSWORD", "")
        supplied = (username, email, password)
        if any(supplied) and not all(supplied):
            raise CommandError(
                "Para crear la cuenta inicial define DJANGO_BOOTSTRAP_ADMIN_USERNAME, "
                "DJANGO_BOOTSTRAP_ADMIN_EMAIL y DJANGO_BOOTSTRAP_ADMIN_PASSWORD."
            )
        if not all(supplied):
            self.stdout.write("No se definió una cuenta administradora inicial.")
            return

        user_model = get_user_model()
        lookup = {user_model.USERNAME_FIELD: username}
        if user_model.objects.filter(**lookup).exists():
            self.stdout.write("La cuenta administradora inicial ya existe.")
            return

        admin_user = user_model(username=username, email=email)
        validate_password(password, user=admin_user)
        user_model.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS("Cuenta administradora inicial creada."))

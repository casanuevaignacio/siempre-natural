from django.contrib import admin

from .models import CustomerAccount


@admin.register(CustomerAccount)
class CustomerAccountAdmin(admin.ModelAdmin):
    list_display = ("email", "email_verified", "created_at")
    list_filter = ("email_verified", "created_at")
    search_fields = ("email", "user__username")
    readonly_fields = ("user", "email", "created_at")

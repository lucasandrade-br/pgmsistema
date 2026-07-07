from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display  = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    list_filter   = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "first_name", "last_name", "email")

    # Herda todos os fieldsets do UserAdmin e acrescenta a seção PGM
    # para que 'telefone' seja editável no formulário de detalhe.
    # 'pin_autorizacao' é omitido intencionalmente (hash interno — não deve
    # ser editado manualmente; a alteração é feita via endpoint de API).
    fieldsets = UserAdmin.fieldsets + (
        ("Dados PGM", {"fields": ("telefone",)}),
    )

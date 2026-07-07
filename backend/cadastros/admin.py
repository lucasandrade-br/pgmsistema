from django.contrib import admin

from .models import NivelPrioridade, Remetente, TipoDocumento


@admin.register(Remetente)
class RemetenteAdmin(admin.ModelAdmin):
    list_display = ("nome_razao_social", "email", "tipo_pessoa")
    search_fields = ("nome_razao_social", "email")
    list_filter = ("tipo_pessoa",)


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("descricao", "ativo")
    search_fields = ("descricao",)
    list_filter = ("ativo",)


@admin.register(NivelPrioridade)
class NivelPrioridadeAdmin(admin.ModelAdmin):
    list_display = ("descricao", "prazo_dias")
    search_fields = ("descricao",)

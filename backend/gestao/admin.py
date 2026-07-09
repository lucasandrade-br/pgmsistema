from django.contrib import admin

from .models import Anexo, Movimentacao, Processo


class AnexoInline(admin.TabularInline):
    model = Anexo
    extra = 0
    fields = ("tipo_documento", "numero_documento", "tipo_anexo", "arquivo", "ativo")


@admin.register(Processo)
class ProcessoAdmin(admin.ModelAdmin):
    list_display = (
        "numero_protocolo",
        "tipo_processo",
        "status",
        "prioridade",
        "remetente",
        "data_limite",
    )
    search_fields = (
        "numero_protocolo",
        "numero_origem",
        "remetente__nome_razao_social",
    )
    list_filter = ("status", "prioridade")
    inlines = [AnexoInline]


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = (
        "processo",
        "tipo_evento",
        "data_criacao",
        "usuario_responsavel",
    )
    search_fields = (
        "processo__numero_protocolo",
        "descricao",
    )
    list_filter = ("tipo_evento", "data_criacao")


@admin.register(Anexo)
class AnexoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "processo",
        "tipo_anexo",
        "tipo_documento",
        "numero_documento",
        "ativo",
        "movimentacao",
    )
    list_filter = ("tipo_anexo", "ativo", "tipo_documento")
    search_fields = (
        "processo__numero_protocolo",
        "numero_documento",
        "observacao",
    )
    readonly_fields = ("movimentacao", "processo")
    fields = (
        "processo",
        "movimentacao",
        "tipo_anexo",
        "tipo_documento",
        "numero_documento",
        "arquivo",
        "observacao",
        "ativo",
    )

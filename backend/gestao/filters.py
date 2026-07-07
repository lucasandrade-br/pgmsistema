import django_filters
from django.db.models import Q

from gestao.models import Processo, SolicitacaoDocumento


class ProcessoFilter(django_filters.FilterSet):
    """
    Filtro avançado para a Consulta Geral de Processos.
    Permite buscas unificadas e recortes temporais.
    """

    numeracao = django_filters.CharFilter(
        method="filter_numeracao",
        label="Numeração (Protocolo, Origem ou SEI)",
    )
    envolvido = django_filters.CharFilter(
        method="filter_envolvido",
        label="Nome do Remetente ou Interessado",
    )
    data_inicio = django_filters.DateFilter(
        method="filter_data_inicio",
        label="Data Inicial do Protocolo",
    )
    data_fim = django_filters.DateFilter(
        method="filter_data_fim",
        label="Data Final do Protocolo",
    )

    class Meta:
        model = Processo
        # Mantém compatibilidade com as listagens existentes (in e exact)
        fields = {
            "status":               ["exact", "in"],
            "procurador_atribuido": ["exact"],
            "tipo_processo":        ["exact"],
        }

    def filter_numeracao(self, queryset, name, value):
        """Varre os 3 campos de numeração simultaneamente (OR)."""
        return queryset.filter(
            Q(numero_protocolo__icontains=value)
            | Q(numero_origem__icontains=value)
            | Q(numero_sei__icontains=value)
        )

    def filter_envolvido(self, queryset, name, value):
        """Varre Remetente e Interessados; distinct() evita duplicatas do M2M."""
        return queryset.filter(
            Q(remetente__nome_razao_social__icontains=value)
            | Q(interessados__nome_razao_social__icontains=value)
        ).distinct()

    def filter_data_inicio(self, queryset, name, value):
        """Filtra processos protocolados a partir de data_inicio."""
        data_str = value.strftime("%Y-%m-%d")
        return queryset.filter(numero_protocolo__gte=data_str)

    def filter_data_fim(self, queryset, name, value):
        """Filtra processos protocolados até data_fim (inclusive)."""
        data_str = value.strftime("%Y-%m-%d")
        return queryset.filter(numero_protocolo__lte=data_str + "-999")


class DiligenciaFilter(django_filters.FilterSet):
    """
    Filtro para o Painel de Controle de Diligências.
    """

    numeracao = django_filters.CharFilter(
        method="filter_numeracao",
        label="Numeração (Protocolo, Origem ou SEI)",
    )

    class Meta:
        model = SolicitacaoDocumento
        fields = {
            "status": ["exact", "in"],
        }

    def filter_numeracao(self, queryset, name, value):
        """Busca simultânea nos 3 campos de numeração do Processo (OR)."""
        return queryset.filter(
            Q(processo__numero_protocolo__icontains=value)
            | Q(processo__numero_origem__icontains=value)
            | Q(processo__numero_sei__icontains=value)
        )

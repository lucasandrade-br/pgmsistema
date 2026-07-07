"""
Views (Endpoints) do app cadastros.

Responsabilidades:
  - Expor listas de dados de referência para o Frontend (read-only).
  - RemetenteViewSet: suporta busca textual via ?search= para o AutoComplete.
  - TipoDocumentoViewSet / NivelPrioridadeViewSet: listas cacheáveis (sem paginação).
"""

from rest_framework import serializers, viewsets
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated

from cadastros.models import NivelPrioridade, Remetente, TipoDocumento


# ---------------------------------------------------------------------------
# Serializers (inline — escopo reduzido, apenas para leitura)
# ---------------------------------------------------------------------------


class RemetenteSerializer(serializers.ModelSerializer):
    # Alias 'nome' para compatibilidade com optionLabel="nome" no AutoComplete Vue
    nome = serializers.CharField(source="nome_razao_social", read_only=True)

    class Meta:
        model = Remetente
        fields = ["id", "nome", "tipo_pessoa"]


class TipoDocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoDocumento
        fields = ["id", "descricao"]


class NivelPrioridadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NivelPrioridade
        fields = ["id", "descricao", "prazo_dias"]


# ---------------------------------------------------------------------------
# ViewSets
# ---------------------------------------------------------------------------


class RemetenteViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/cadastros/remetentes/
    GET /api/v1/cadastros/remetentes/?search=<termo>

    Suporta busca por nome_razao_social via DRF SearchFilter.
    Usado pelo AutoComplete do formulário de Novo Processo.
    """
    queryset = Remetente.objects.all()
    serializer_class = RemetenteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["nome_razao_social"]


class TipoDocumentoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/cadastros/tipos-documento/

    Lista de tipos de documento ativos. Sem paginação para facilitar cache local.
    """
    queryset = TipoDocumento.objects.filter(ativo=True)
    serializer_class = TipoDocumentoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None   # lista completa — pequena, cacheável no frontend


class NivelPrioridadeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/cadastros/niveis-prioridade/

    Lista de níveis de prioridade. Sem paginação.
    """
    queryset = NivelPrioridade.objects.all()
    serializer_class = NivelPrioridadeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None   # lista completa — pequena, cacheável no frontend

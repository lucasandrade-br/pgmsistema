"""
Views (Endpoints) do app cadastros.

Responsabilidades:
  - Expor listas de dados de referência para o Frontend (read-only).
  - RemetenteViewSet: suporta busca textual via ?search= para o AutoComplete.
    Também suporta criação e edição de remetentes (FormularioEnvolvido).
  - TipoDocumentoViewSet / NivelPrioridadeViewSet: listas cacheáveis (sem paginação).
"""

from django.db.models import Q
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cadastros.models import NivelPrioridade, Remetente, TipoDocumento
from cadastros.utils.encryption import decrypt, encrypt, make_hash


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


class RemetenteSerializer(serializers.ModelSerializer):
    """Serializer de leitura: inclui alias 'nome' para compatibilidade com o AutoComplete."""

    nome = serializers.CharField(source="nome_razao_social", read_only=True)

    class Meta:
        model = Remetente
        fields = ["id", "nome", "nome_razao_social", "tipo_pessoa", "doc", "email", "telefone"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Descriptografa campos sensíveis antes de entregar ao cliente
        data["doc"]      = decrypt(data.get("doc")      or "")
        data["telefone"] = decrypt(data.get("telefone") or "")
        return data


class RemetenteWriteSerializer(serializers.ModelSerializer):
    """Serializer de escrita para criação e edição de Remetentes."""

    nome_razao_social = serializers.CharField(max_length=255)
    doc               = serializers.CharField(max_length=255, required=True, allow_blank=False)

    class Meta:
        model = Remetente
        fields = ["nome_razao_social", "tipo_pessoa", "doc", "email", "telefone"]


class TipoDocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoDocumento
        fields = ["id", "descricao", "ativo"]


class NivelPrioridadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NivelPrioridade
        fields = ["id", "descricao", "prazo_dias"]


# ---------------------------------------------------------------------------
# ViewSets
# ---------------------------------------------------------------------------


class RemetenteViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/cadastros/remetentes/          → listagem / autocomplete
    GET    /api/v1/cadastros/remetentes/?search=X → busca combinada (OR)
    POST   /api/v1/cadastros/remetentes/          → criação via FormularioEnvolvido
    PATCH  /api/v1/cadastros/remetentes/{id}/     → edição via FormularioEnvolvido

    Busca:
      - icontains para nome_razao_social e email
      - exact para doc e telefone (compatível com criptografia determinística)
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RemetenteWriteSerializer
        return RemetenteSerializer

    def get_queryset(self):
        qs     = Remetente.objects.all()
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(nome_razao_social__icontains=search)
                | Q(email__icontains=search)
                | Q(doc_hash__exact=make_hash(search))
                | Q(telefone_hash__exact=make_hash(search))
            )
        return qs

    def _apply_encryption(self, data: dict) -> dict:
        """Criptografa doc/telefone e computa hashes de busca no dict de dados validados."""
        if data.get("doc"):
            raw = data["doc"]
            data["doc"]      = encrypt(raw)
            data["doc_hash"] = make_hash(raw)
        if data.get("telefone"):
            raw = data["telefone"]
            data["telefone"]      = encrypt(raw)
            data["telefone_hash"] = make_hash(raw)
        return data

    def create(self, request, *args, **kwargs):
        """Cria Remetente com campos sensíveis criptografados."""
        write_ser = RemetenteWriteSerializer(data=request.data)
        write_ser.is_valid(raise_exception=True)
        payload  = self._apply_encryption(dict(write_ser.validated_data))
        instance = Remetente.objects.create(**payload)
        return Response(RemetenteSerializer(instance).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """Atualiza parcialmente com re-criptografia dos campos alterados."""
        instance  = self.get_object()
        write_ser = RemetenteWriteSerializer(instance, data=request.data, partial=True)
        write_ser.is_valid(raise_exception=True)
        payload = self._apply_encryption(dict(write_ser.validated_data))
        for attr, value in payload.items():
            setattr(instance, attr, value)
        instance.save()
        return Response(RemetenteSerializer(instance).data)


class TipoDocumentoViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/cadastros/tipos-documento/                       → lista ativos (padrão — compatível com dropdowns existentes)
    GET    /api/v1/cadastros/tipos-documento/?incluir_inativos=true → lista todos (usado pela tela de gestão)
    POST   /api/v1/cadastros/tipos-documento/                       → criação
    PATCH  /api/v1/cadastros/tipos-documento/{id}/                  → edição
    """
    serializer_class   = TipoDocumentoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class   = None

    def get_queryset(self):
        qs = TipoDocumento.objects.all()
        # Por padrão retorna apenas ativos; ?incluir_inativos=true é usado pela tela de gestão
        if not self.request.query_params.get("incluir_inativos"):
            qs = qs.filter(ativo=True)
        return qs


class NivelPrioridadeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/cadastros/niveis-prioridade/

    Lista de níveis de prioridade. Sem paginação.
    """
    queryset = NivelPrioridade.objects.all()
    serializer_class = NivelPrioridadeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None   # lista completa — pequena, cacheável no frontend

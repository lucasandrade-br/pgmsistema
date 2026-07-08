"""
Serializers do app gestao.

Responsabilidades:
  - Validar e desserializar entradas (write serializers).
  - Serializar saídas para JSON (read serializers).
  - Nenhuma regra de negócio deve residir aqui.
"""

from rest_framework import serializers

from cadastros.models import Remetente
from gestao.models import Anexo, Movimentacao, Processo, SolicitacaoDocumento


# ---------------------------------------------------------------------------
# Read Serializers (saída / exibição)
# ---------------------------------------------------------------------------


class AnexoSerializer(serializers.ModelSerializer):
    tipo_anexo_display = serializers.CharField(
        source="get_tipo_anexo_display",
        read_only=True,
    )

    class Meta:
        model = Anexo
        fields = [
            "id",
            "arquivo",
            "tipo_anexo",
            "tipo_anexo_display",
            "tipo_documento",
            "numero_documento",
            "observacao",
            "ativo",
        ]


class MovimentacaoSerializer(serializers.ModelSerializer):
    tipo_evento_display = serializers.CharField(
        source="get_tipo_evento_display",
        read_only=True,
    )
    usuario_nome  = serializers.SerializerMethodField()
    anexos        = serializers.SerializerMethodField()
    diligencia_info = serializers.SerializerMethodField()

    class Meta:
        model = Movimentacao
        fields = [
            "id",
            "processo",
            "tipo_evento",
            "tipo_evento_display",
            "usuario_responsavel",
            "usuario_nome",
            "data_criacao",
            "descricao",
            "anexos",
            "diligencia_info",
        ]

    def get_usuario_nome(self, obj: Movimentacao) -> str:
        return obj.usuario_responsavel.get_full_name() or obj.usuario_responsavel.username

    def get_diligencia_info(self, obj: Movimentacao):
        if obj.tipo_evento != obj.TipoEvento.DILIGENCIA_INICIADA:
            return None
        diligencia = obj.solicitacoes_originadas.first()
        if diligencia is None:
            return None
        return {
            "id":                   diligencia.id,
            "status":               diligencia.status,
            "descricao_necessidade": diligencia.descricao_necessidade,
        }

    def get_anexos(self, obj: Movimentacao) -> list:
        result = []
        for a in obj.anexos.filter(ativo=True):
            if a.arquivo:
                nome = a.arquivo.name.split("/")[-1]
                url  = a.arquivo.url
            else:
                nome = "Nota de Texto"
                url  = None
            result.append({
                "id":               a.id,
                "nome":             nome,
                "url":              url,
                "numero_documento": a.numero_documento or "",
                "observacao":       a.observacao or "",
                "tipo_documento_id": a.tipo_documento_id,
                "tipo_anexo":       a.tipo_anexo,
            })
        return result


# ---------------------------------------------------------------------------
# Write Serializers (atualização parcial de recursos)
# ---------------------------------------------------------------------------


class AnexoUpdateSerializer(serializers.ModelSerializer):
    """Serializer de escrita para atualização parcial de um Anexo (PATCH)."""

    class Meta:
        model  = Anexo
        fields = ["tipo_documento", "tipo_anexo", "numero_documento", "observacao", "ativo"]


class ProcessoSerializer(serializers.ModelSerializer):
    """
    Serializer de leitura. Expõe IDs para o frontend usar em requisições e
    valores textuais para exibição, evitando lookups secundários no Vue.
    """

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    prioridade_descricao = serializers.CharField(
        source="prioridade.descricao",
        read_only=True,
    )
    prazo_dias = serializers.IntegerField(
        source="prioridade.prazo_dias",
        read_only=True,
    )
    remetente_nome = serializers.CharField(
        source="remetente.nome_razao_social",
        read_only=True,
    )
    tipo_processo_descricao = serializers.SerializerMethodField()
    procurador_nome         = serializers.SerializerMethodField()
    remetente_email         = serializers.CharField(source="remetente.email",    read_only=True, allow_null=True)
    remetente_telefone      = serializers.CharField(source="remetente.telefone", read_only=True, allow_null=True)
    remetente_tipo          = serializers.SerializerMethodField()
    interessados_info       = serializers.SerializerMethodField()

    class Meta:
        model = Processo
        fields = [
            "id",
            "numero_protocolo",
            "status",
            "status_display",
            "prioridade",
            "prioridade_descricao",
            "prazo_dias",
            "remetente",
            "remetente_nome",
            "interessados",
            "procurador_atribuido",
            "procurador_nome",
            "data_limite",
            "data_atribuicao",
            # ── Campos operacionais (Hotfix Sprint 5) ─────────────────────────────
            "tipo_processo",
            "tipo_processo_descricao",
            "numero_origem",
            "numero_sei",
            "data_origem",
            "observacoes",
            "notificar_remetente",
            "data_resposta_procurador",
            "remetente_email",
            "remetente_telefone",
            "remetente_tipo",
            "interessados_info",
        ]
        # Campos gerados pelo serviço — nunca aceitos via input
        read_only_fields = [
            "numero_protocolo",
            "status",
            "data_atribuicao",
            "data_limite",
            "procurador_atribuido",
        ]

    def get_tipo_processo_descricao(self, obj: Processo) -> str | None:
        return obj.tipo_processo.descricao if obj.tipo_processo_id else None

    def get_procurador_nome(self, obj: Processo) -> str | None:
        if obj.procurador_atribuido:
            return (
                obj.procurador_atribuido.get_full_name()
                or obj.procurador_atribuido.username
            )
        return None

    def get_remetente_tipo(self, obj: Processo) -> str | None:
        return obj.remetente.get_tipo_pessoa_display() if obj.remetente_id else None

    def get_interessados_info(self, obj: Processo) -> list:
        return [
            {
                "nome":     r.nome_razao_social,
                "email":    r.email,
                "telefone": r.telefone,
                "tipo":     r.get_tipo_pessoa_display(),
            }
            for r in obj.interessados.all()
        ]


# ---------------------------------------------------------------------------
# Write Serializers (entrada / validação)
# ---------------------------------------------------------------------------


class ProcessoTramitarSerializer(serializers.Serializer):
    """Entrada para tramitação formal de status de um Processo via endpoint RPC."""

    status = serializers.ChoiceField(choices=Processo.Status.choices)
    motivo = serializers.CharField(required=False, allow_blank=True, default="")


class ProcessoUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer de escrita para atualização parcial de um Processo (PATCH).
    Todos os campos são opcionais — partial=True é garantido no ViewSet.
    """

    interessados = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Remetente.objects.all(),
        required=False,
    )

    class Meta:
        model = Processo
        fields = [
            "prioridade",
            "tipo_processo",
            "numero_origem",
            "numero_sei",
            "data_origem",
            "observacoes",
            "notificar_remetente",
            "procurador_atribuido",
            "data_limite",
            "data_atribuicao",
            "status",
            "remetente",
            "interessados",
        ]

    def update(self, instance, validated_data):
        interessados = validated_data.pop("interessados", None)
        instance = super().update(instance, validated_data)
        if interessados is not None:
            instance.interessados.set(interessados)
        return instance


class ProcessoCreateSerializer(serializers.Serializer):
    """
    Serializer de entrada para o protocolamento de um novo Processo.
    Os arquivos são recebidos via request.FILES (multipart/form-data).
    A metadata por-arquivo vem no campo 'metadata' como JSON array.
    """

    prioridade_id = serializers.IntegerField(min_value=1)
    remetente_id = serializers.IntegerField(min_value=1)
    interessados_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )
    # ── Campos operacionais opcionais (Hotfix Sprint 5) ────────────────────
    tipo_processo_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
        default=None,
    )
    numero_origem = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
    )
    numero_sei = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
    )
    data_origem = serializers.DateField(
        required=False,
        allow_null=True,
        default=None,
    )
    observacoes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
    )
    notificar_remetente = serializers.BooleanField(
        required=False,
        default=False,
    )


class DistribuicaoLoteSerializer(serializers.Serializer):
    """
    Serializer de entrada para a ação distribuir-lote.
    Corresponde ao contrato definido em knowledge/produto/fluxo_distribuicao.md.

    Payload esperado:
        {
            "processos_ids":   [145, 146, 147, 148],
            "procuradores_ids": [2, 5, 8]
        }
    """

    processos_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        error_messages={
            "min_length": "Selecione ao menos um processo para distribuir.",
            "required": "O campo processos_ids é obrigatório.",
        },
    )
    procuradores_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        error_messages={
            "min_length": "Selecione ao menos um procurador.",
            "required": "O campo procuradores_ids é obrigatório.",
        },
    )


# ---------------------------------------------------------------------------
# Write Serializers — Diligências (entrada / validação)
# ---------------------------------------------------------------------------


class DiligenciaLoteCreateSerializer(serializers.Serializer):
    """
    Entrada para abertura de uma nova Diligência (form-data com arquivos).
    Os arquivos são recebidos via request.FILES.getlist('arquivos') na View;
    apenas os campos de texto precisam ser validados aqui.
    """

    processo_id = serializers.IntegerField(
        min_value=1,
        error_messages={"required": "O campo processo_id é obrigatório."},
    )
    descricao_necessidade = serializers.CharField(
        min_length=10,
        error_messages={
            "required": "A descrição da necessidade é obrigatória.",
            "min_length": "A descrição deve ter ao menos 10 caracteres.",
        },
    )


class DiligenciaRejeitarSerializer(serializers.Serializer):
    """Entrada para rejeição de uma Diligência. Motivo é obrigatório."""

    motivo_rejeicao = serializers.CharField(
        min_length=5,
        max_length=50,
        error_messages={
            "required":  "O motivo da rejeição é obrigatório.",
            "min_length": "O motivo deve ter ao menos 5 caracteres.",
            "max_length": "O motivo não pode exceder 50 caracteres.",
        },
    )


class DiligenciaAprovarSerializer(serializers.Serializer):
    """
    Entrada para aprovação e envio de e-mail de Diligência.
    A chefia seleciona os destinatários e quais anexos serão incluídos.
    """

    emails_destino = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1,
        error_messages={
            "min_length": "Informe ao menos um e-mail de destino.",
            "required": "O campo emails_destino é obrigatório.",
        },
    )
    anexos_ids_selecionados = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        error_messages={
            "min_length": "Selecione ao menos um anexo para enviar.",
            "required": "O campo anexos_ids_selecionados é obrigatório.",
        },
    )


class DiligenciaConcluirSerializer(serializers.Serializer):
    """
    Entrada para conclusão manual de uma Diligência.
    Os arquivos de resposta são recebidos via request.FILES.getlist('arquivos').
    A observação da chefia é opcional.
    """

    observacao_resolucao = serializers.CharField(
        required=False,
        allow_blank=True,
        default=None,
        max_length=50,
        error_messages={
            "max_length": "A observação não pode exceder 50 caracteres.",
        },
    )


class DiligenciaMarcarSolicitadaSerializer(serializers.Serializer):
    """
    Entrada para registrar que uma diligência foi solicitada por meios alternativos
    (telefone, WhatsApp, balcão) sem disparar envio de e-mail.
    """

    observacao_contato = serializers.CharField(
        min_length=5,
        max_length=50,
        error_messages={
            "required":  "A observação sobre como o contato foi feito é obrigatória.",
            "min_length": "A observação deve ter ao menos 5 caracteres.",
            "max_length": "A observação não pode exceder 50 caracteres.",
        },
    )


class RedistribuicaoFeriasSerializer(serializers.Serializer):
    """
    Entrada para redistribuição de processos por motivo de férias/afastamento.
    Descobre automaticamente os processos ativos do procurador origem.
    """

    procurador_origem_id = serializers.IntegerField(
        min_value=1,
        error_messages={"required": "O campo procurador_origem_id é obrigatório."},
    )
    procuradores_destino_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        error_messages={
            "min_length": "Selecione ao menos um procurador destino.",
            "required": "O campo procuradores_destino_ids é obrigatório.",
        },
    )


# ---------------------------------------------------------------------------
# Diligência — Read Serializer
# ---------------------------------------------------------------------------


class DiligenciaListSerializer(serializers.ModelSerializer):
    """
    Serializer de leitura para listagem de Diligências no Painel de Controle.
    Inclui dados aninhados do Processo relacionado.
    """

    numero_protocolo = serializers.CharField(source="processo.numero_protocolo", read_only=True)
    numero_origem    = serializers.CharField(source="processo.numero_origem",    read_only=True)
    numero_sei       = serializers.CharField(source="processo.numero_sei",       read_only=True)
    processo_id      = serializers.IntegerField(source="processo.id",            read_only=True)
    procurador_nome  = serializers.SerializerMethodField()

    class Meta:
        model = SolicitacaoDocumento
        fields = [
            "id",
            "status",
            "descricao_necessidade",
            "data_solicitacao",
            "data_conclusao",
            "numero_protocolo",
            "numero_origem",
            "numero_sei",
            "processo_id",
            "procurador_nome",
        ]

    def get_procurador_nome(self, obj: SolicitacaoDocumento) -> str | None:
        procurador = obj.processo.procurador_atribuido
        if not procurador:
            return None
        return procurador.get_full_name() or procurador.username

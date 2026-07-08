import os
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from cadastros.models import NivelPrioridade, Remetente, TipoDocumento


_EXTENSOES_PERMITIDAS = ["pdf", "jpg", "jpeg", "png"]


def upload_path_anexo(instance, filename):
    """
    Gera o caminho de armazenamento seguindo a árvore cronológica do processo:

        anexos/{ano}/{mes}/{protocolo}/{categoria}/{filename}

    O `numero_protocolo` segue o formato YYYY-MM-DD-NNNN, portanto
    ano e mês são extraídos por split para evitar dependência de timezone.
    Fallback para data atual se o processo ainda não estiver atrelado.
    """
    from django.utils import timezone

    # ─ Obter processo via FK direta ou via Movimentação ──────────────────────
    processo = None
    try:
        if instance.processo_id:
            processo = instance.processo
        elif instance.movimentacao_id:
            processo = instance.movimentacao.processo
    except Exception:
        pass

    # ─ Ano / Mês a partir do protocolo (YYYY-MM-DD-NNNN) ──────────────────
    if processo and processo.numero_protocolo:
        protocolo = processo.numero_protocolo
        partes    = protocolo.split("-")
        ano       = partes[0] if len(partes) > 0 else str(timezone.now().year)
        mes       = partes[1] if len(partes) > 1 else str(timezone.now().month).zfill(2)
    else:
        now       = timezone.now()
        ano       = str(now.year)
        mes       = str(now.month).zfill(2)
        protocolo = f"{ano}-{mes}-sem-protocolo"

    # ─ Categoria do documento ──────────────────────────────────────────
    try:
        if instance.tipo_documento_id and instance.tipo_documento:
            categoria = instance.tipo_documento.descricao.upper().replace(" ", "_")[:30]
        elif instance.tipo_anexo:
            categoria = instance.tipo_anexo
        else:
            categoria = "OUTROS"
    except Exception:
        categoria = "OUTROS"

    # Sanitiza o filename para evitar path traversal
    filename = os.path.basename(filename)

    return f"anexos/{ano}/{mes}/{protocolo}/{categoria}/{filename}"


class Processo(models.Model):
    class Status(models.TextChoices):
        AGUARDANDO_DISTRIBUICAO = "AGUARDANDO_DISTRIBUICAO", "Aguardando Distribuição"
        DEVOLVIDO = "DEVOLVIDO", "Devolvido"
        EM_ANALISE = "EM_ANALISE", "Em Análise"
        EM_DILIGENCIA = "EM_DILIGENCIA", "Em Diligência"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        FINALIZADO = "FINALIZADO", "Finalizado"
        ARQUIVADO = "ARQUIVADO", "Arquivado"
        REJEITADO = "REJEITADO", "Rejeitado"

    numero_protocolo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Número de Protocolo",
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.AGUARDANDO_DISTRIBUICAO,
        verbose_name="Status",
    )
    prioridade = models.ForeignKey(
        NivelPrioridade,
        on_delete=models.PROTECT,
        related_name="processos",
        verbose_name="Prioridade",
    )
    remetente = models.ForeignKey(
        Remetente,
        on_delete=models.PROTECT,
        related_name="processos_como_remetente",
        verbose_name="Remetente",
    )
    interessados = models.ManyToManyField(
        Remetente,
        blank=True,
        related_name="processos_como_interessado",
        verbose_name="Interessados",
    )
    procurador_atribuido = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processos_atribuidos",
        verbose_name="Procurador Atribuído",
    )
    data_limite = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data Limite",
    )
    data_atribuicao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Atribuição",
    )
    # ── Campos operacionais adicionados no Hotfix Sprint 5 ────────────────────
    tipo_processo = models.ForeignKey(
        TipoDocumento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processos_tipo",
        verbose_name="Tipo de Processo",
    )
    numero_origem = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Número de Origem",
    )
    numero_sei = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Número SEI",
    )
    data_origem = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Origem",
    )
    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observações",
    )
    notificar_remetente = models.BooleanField(
        default=False,
        verbose_name="Notificar Remetente",
    )
    data_resposta_procurador = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data da Resposta do Procurador",
    )

    class Meta:
        verbose_name = "Processo"
        verbose_name_plural = "Processos"
        ordering = ["-id"]

    def __str__(self):
        return f"Processo {self.numero_protocolo} [{self.get_status_display()}]"


class Movimentacao(models.Model):
    """
    Eixo central da Timeline. Cada registro representa um evento
    imutável na vida de um Processo, seguindo o padrão Event Sourcing.
    """

    class TipoEvento(models.TextChoices):
        PROTOCOLO = "PROTOCOLO", "Protocolo"
        DISTRIBUICAO = "DISTRIBUICAO", "Distribuição"
        CONCLUSAO = "CONCLUSAO", "Conclusão"
        REJEICAO = "REJEICAO", "Rejeição"
        DILIGENCIA_INICIADA = "DILIGENCIA_INICIADA", "Diligência Iniciada"
        DILIGENCIA_RESOLVIDA = "DILIGENCIA_RESOLVIDA", "Diligência Resolvida"
        ARQUIVAMENTO = "ARQUIVAMENTO", "Arquivamento"
        DESARQUIVAMENTO = "DESARQUIVAMENTO", "Desarquivamento"
        FINALIZACAO = "FINALIZACAO", "Finalização"
        DEVOLUCAO = "DEVOLUCAO", "Devolução"
        ANEXO_ARQUIVO = "ANEXO_ARQUIVO", "Anexo de Arquivo"
        OBSERVACAO_SIMPLES = "OBSERVACAO_SIMPLES", "Observação Simples"

    processo = models.ForeignKey(
        Processo,
        on_delete=models.CASCADE,
        related_name="movimentacoes",
        verbose_name="Processo",
    )
    tipo_evento = models.CharField(
        max_length=30,
        choices=TipoEvento.choices,
        verbose_name="Tipo de Evento",
    )
    usuario_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimentacoes",
        verbose_name="Usuário Responsável",
    )
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação",
    )
    descricao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descrição / Despacho / Motivo",
    )

    class Meta:
        verbose_name = "Movimentação"
        verbose_name_plural = "Movimentações"
        ordering = ["data_criacao"]

    def __str__(self):
        return (
            f"{self.get_tipo_evento_display()} — "
            f"Processo {self.processo.numero_protocolo} "
            f"em {self.data_criacao:%d/%m/%Y %H:%M}"
        )


class Anexo(models.Model):
    class TipoAnexo(models.TextChoices):
        INICIAL    = "INICIAL",    "Inicial"
        RESPOSTA   = "RESPOSTA",   "Resposta"
        DILIGENCIA = "DILIGENCIA", "Diligência"
        OUTROS     = "OUTROS",     "Outros"

    movimentacao = models.ForeignKey(
        Movimentacao,
        on_delete=models.CASCADE,
        related_name="anexos",
        verbose_name="Movimentação",
    )
    arquivo = models.FileField(
        upload_to=upload_path_anexo,
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=_EXTENSOES_PERMITIDAS)],
        verbose_name="Arquivo",
    )
    tipo_anexo = models.CharField(
        max_length=20,
        choices=TipoAnexo.choices,
        verbose_name="Tipo de Anexo",
    )
    tipo_documento = models.ForeignKey(
        TipoDocumento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anexos",
        verbose_name="Tipo de Documento",
    )
    numero_documento = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Número do Documento",
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
    )
    # ── Campos operacionais adicionados no Hotfix Sprint 5 ────────────────────
    processo = models.ForeignKey(
        Processo,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="anexos",
        verbose_name="Processo (acesso direto)",
    )
    observacao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observação",
    )

    class Meta:
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"

    def __str__(self):
        nome_arquivo = self.arquivo.name if self.arquivo else "sem arquivo"
        return f"Anexo [{self.get_tipo_anexo_display()}] — {nome_arquivo}"


class SolicitacaoDocumento(models.Model):
    """Representa uma Diligência: solicitação formal de documentação adicional."""

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        ENVIADA = "ENVIADA", "Enviada"
        ATENDIDA = "ATENDIDA", "Atendida"
        REJEITADA = "REJEITADA", "Rejeitada"

    processo = models.ForeignKey(
        Processo,
        on_delete=models.CASCADE,
        related_name="solicitacoes_documento",
        verbose_name="Processo",
    )
    movimentacao_origem = models.ForeignKey(
        Movimentacao,
        on_delete=models.PROTECT,
        related_name="solicitacoes_originadas",
        verbose_name="Movimentação de Origem",
    )
    descricao_necessidade = models.TextField(
        verbose_name="Descrição da Necessidade",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
        verbose_name="Status",
    )
    data_solicitacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data da Solicitação",
    )
    data_envio_email = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Envio do E-mail",
    )
    data_conclusao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Conclusão",
    )
    motivo_rejeicao = models.TextField(
        null=True,
        blank=True,
        verbose_name="Motivo da Rejeição",
    )
    observacao_chefia = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observação da Chefia",
    )

    class Meta:
        verbose_name = "Solicitação de Documento (Diligência)"
        verbose_name_plural = "Solicitações de Documento (Diligências)"
        ordering = ["-data_solicitacao"]

    def __str__(self):
        return (
            f"Diligência #{self.pk} — Processo {self.processo.numero_protocolo} "
            f"[{self.get_status_display()}]"
        )


# ─────────────────────────────────────────────────────────────────────────
# Compartilhamento Externo Seguro
# ─────────────────────────────────────────────────────────────────────────

def default_expiracao():
    """Default de 30 dias a partir da criação do link."""
    return timezone.now() + timedelta(days=30)


class LinkCompartilhamento(models.Model):
    """
    Link público de acesso temporário aos Autos Digitais de um Processo.
    Expirado após `data_expiracao`; o arquivo é armazenado no Cloud Storage.
    """

    processo = models.ForeignKey(
        Processo,
        on_delete=models.CASCADE,
        related_name="links_compartilhamento",
        verbose_name="Processo",
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Token",
    )
    data_expiracao = models.DateTimeField(
        default=default_expiracao,
        verbose_name="Data de Expiração",
    )
    arquivo_gerado = models.FileField(
        upload_to="autos_exportados/",
        verbose_name="Arquivo Gerado",
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado Em",
    )

    class Meta:
        verbose_name = "Link de Compartilhamento"
        verbose_name_plural = "Links de Compartilhamento"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Link {self.token} — {self.processo.numero_protocolo} (exp: {self.data_expiracao:%d/%m/%Y})"

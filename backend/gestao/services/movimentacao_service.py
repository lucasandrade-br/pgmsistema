"""
Camada de Serviço — Domínio: Movimentação

Responsável por adicionar movimentações ao ciclo de vida de um Processo
existente, incluindo a criação de anexos e as transições de status que
determinados tipos de evento disparam.

Regras:
  - Nenhuma lógica de negócio vive nas Views.
  - Toda operação multi-tabela usa transaction.atomic().
  - O padrão "Zip" alinha arquivos ↔ metadata por índice posicional.
  - Se metadata_list for menor que a lista de arquivos, o excedente recebe
    um dicionário vazio {} — sem IndexError.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

from gestao.models import Anexo, Movimentacao, Processo, SolicitacaoDocumento

User = get_user_model()


# ---------------------------------------------------------------------------
# Exceções de Domínio
# ---------------------------------------------------------------------------


class TipoEventoInvalidoError(Exception):
    """Levantada quando tipo_evento não pertence às choices do modelo Movimentacao."""


# ---------------------------------------------------------------------------
# Serviço de Movimentação
# ---------------------------------------------------------------------------


class MovimentacaoService:
    """
    Orquestra a adição de Movimentações a Processos existentes.
    Todos os métodos são estáticos: a classe é um namespace semântico.
    """

    @staticmethod
    @transaction.atomic
    def adicionar_movimentacao(
        processo: Processo,
        usuario: User,
        tipo_evento: str,
        descricao: str,
        arquivos: list,
        metadata_list: list[dict],
    ) -> Movimentacao:
        """
        Adiciona uma Movimentação ao Processo, criando todos os registros
        relacionados em uma única transação ACID.

        Transições de status garantidas atomicamente:
            DILIGENCIA_INICIADA → Processo: <qualquer> → EM_DILIGENCIA
                                → SolicitacaoDocumento: (nova) → PENDENTE

        Etapas internas:
            1. Valida tipo_evento contra as choices do modelo.
            2. Cria a Movimentacao (evento imutável na Timeline).
            3. Se DILIGENCIA_INICIADA: altera status do Processo e cria
               a SolicitacaoDocumento vinculada.
            4. Persiste Anexos para cada arquivo enviado (padrão "Zip").

        Parâmetros:
            processo:      Instância já obtida (e opcionalmente bloqueada) pela View.
            usuario:       Usuário logado, torna-se usuario_responsavel da movimentação.
            tipo_evento:   Deve ser um dos valores de Movimentacao.TipoEvento.
            descricao:     Despacho/observação livre (pode ser string vazia).
            arquivos:      Lista de InMemoryUploadedFile (zero ou mais).
            metadata_list: Lista de dicts posicionalmente alinhada com `arquivos`:
                           [{"categoria_documento_id": int|None,
                             "numero_documento":       str|None,
                             "observacao":             str|None}]

        Retorna:
            A instância de Movimentacao criada.

        Levanta:
            TipoEventoInvalidoError — se tipo_evento não estiver nas choices.
        """
        # ── 1. Validação do tipo_evento ───────────────────────────────────────
        tipos_validos = Movimentacao.TipoEvento.values
        if tipo_evento not in tipos_validos:
            raise TipoEventoInvalidoError(
                f"Tipo de evento '{tipo_evento}' inválido. "
                f"Valores aceitos: {', '.join(tipos_validos)}."
            )

        # ── 2. Cria a Movimentacao (imutável — Event Sourcing) ────────────────
        movimentacao = Movimentacao.objects.create(
            processo=processo,
            usuario_responsavel=usuario,
            tipo_evento=tipo_evento,
            descricao=descricao or None,
        )

        # ── 3. Transições de status por tipo de evento ────────────────────────
        if tipo_evento == Movimentacao.TipoEvento.DILIGENCIA_INICIADA:
            processo.status = Processo.Status.EM_DILIGENCIA
            processo.save(update_fields=["status"])

            SolicitacaoDocumento.objects.create(
                processo=processo,
                movimentacao_origem=movimentacao,
                descricao_necessidade=descricao or "",
            )

        # ── 4. Persiste Anexos (padrão "Zip": metadata guia, arquivos consumidos em ordem)
        tipo_anexo = (
            Anexo.TipoAnexo.DILIGENCIA
            if tipo_evento == Movimentacao.TipoEvento.DILIGENCIA_INICIADA
            else Anexo.TipoAnexo.RESPOSTA
        )

        arquivo_idx = 0
        # Itera sobre metadata_list; se vazia, monta entradas sintéticas por arquivo
        items = metadata_list if metadata_list else [{} for _ in arquivos]
        for meta in items:
            is_nota = meta.get("eh_nota", False)
            if is_nota:
                arquivo = None
            else:
                arquivo = arquivos[arquivo_idx] if arquivo_idx < len(arquivos) else None
                arquivo_idx += 1

            Anexo.objects.create(
                movimentacao=movimentacao,
                processo=processo,
                arquivo=arquivo,
                tipo_anexo=tipo_anexo,
                tipo_documento_id=meta.get("categoria_documento_id") or None,
                numero_documento=meta.get("numero_documento") or None,
                observacao=meta.get("observacao") or None,
            )

        return movimentacao

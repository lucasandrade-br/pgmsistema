"""
Camada de Serviço — Domínio: Diligência (SolicitacaoDocumento)

Responsável por toda a lógica de negócio do ciclo de vida de uma diligência:
  - Abertura em lote pelo Procurador (transição Processo → EM_DILIGENCIA).
  - Rejeição pela chefia (retorno Processo → EM_ANALISE).
  - Aprovação e enfileiramento do e-mail externo via Cloud Tasks.

Regras:
  - Nenhuma lógica de negócio vive nas Views.
  - Toda operação multi-tabela usa transaction.atomic().
  - A tarefa assíncrona de e-mail é enfileirada via transaction.on_commit(),
    garantindo que o Cloud Tasks só seja acionado após o commit bem-sucedido.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from gestao.models import Anexo, Movimentacao, Processo, SolicitacaoDocumento
from gestao.services.notificacao_service import enfileirar_tarefa_email

User = get_user_model()


# ---------------------------------------------------------------------------
# Exceções de Domínio
# ---------------------------------------------------------------------------


class DiligenciaError(Exception):
    """Erro genérico de regra de negócio no domínio de Diligências."""


class StatusInvalidoError(DiligenciaError):
    """
    Levantada quando uma transição de status é inválida dado o estado atual
    do Processo ou da SolicitacaoDocumento.
    """


# ---------------------------------------------------------------------------
# Serviço de Diligência
# ---------------------------------------------------------------------------


class DiligenciaService:
    """
    Orquestra o ciclo de vida de uma SolicitacaoDocumento (Diligência).
    Todos os métodos são estáticos: a classe é um namespace semântico.
    """

    @staticmethod
    @transaction.atomic
    def criar_diligencia_em_lote(
        processo_id: int,
        usuario_logado: User,
        descricao_necessidade: str,
        arquivos_em_memoria: list[dict[str, Any]],
    ) -> SolicitacaoDocumento:
        """
        Abre uma nova Diligência para um Processo, criando todos os registros
        relacionados em uma única transação ACID.

        Transições garantidas atomicamente:
            Processo:            EM_ANALISE → EM_DILIGENCIA
            SolicitacaoDocumento: (nova)    → PENDENTE

        Etapas internas:
            1. Valida que o Processo está em EM_ANALISE (pré-condição).
            2. Cria a Movimentacao DILIGENCIA_INICIADA (evento na Timeline).
            3. Cria a SolicitacaoDocumento vinculada à movimentação origem.
            4. Cria os Anexos do tipo DILIGENCIA para a movimentação.
            5. Atualiza o status do Processo para EM_DILIGENCIA.

        Parâmetros:
            processo_id:          ID do Processo alvo.
            usuario_logado:       Procurador que abre a diligência.
            descricao_necessidade: Texto da necessidade de documentação.
            arquivos_em_memoria:  Lista de dicts [
                {
                    "arquivo":           <InMemoryUploadedFile> | None,
                    "tipo_documento_id": int | None,
                    "numero_documento":  str | None,
                }
            ]

        Retorna:
            A instância da SolicitacaoDocumento criada.

        Levanta:
            StatusInvalidoError — se o Processo não estiver em EM_ANALISE.
            Processo.DoesNotExist — se o processo_id não existir.
        """
        # 1. Obtém e bloqueia o Processo para evitar abertura concorrente
        processo = (
            Processo.objects.select_related("prioridade")
            .select_for_update()
            .get(pk=processo_id)
        )

        if processo.status != Processo.Status.EM_ANALISE:
            raise StatusInvalidoError(
                f"Não é possível abrir uma diligência para o processo "
                f"'{processo.numero_protocolo}'. "
                f"Status atual: '{processo.get_status_display()}'. "
                f"Esperado: 'Em Análise'."
            )

        # 2. Cria a Movimentacao de abertura (evento imutável na Timeline)
        movimentacao = Movimentacao.objects.create(
            processo=processo,
            tipo_evento=Movimentacao.TipoEvento.DILIGENCIA_INICIADA,
            usuario_responsavel=usuario_logado,
            descricao=descricao_necessidade,
        )

        # 3. Cria a SolicitacaoDocumento vinculada à movimentação origem
        diligencia = SolicitacaoDocumento.objects.create(
            processo=processo,
            movimentacao_origem=movimentacao,
            descricao_necessidade=descricao_necessidade,
            status=SolicitacaoDocumento.Status.PENDENTE,
        )

        # 4. Cria os Anexos do tipo DILIGENCIA para a movimentação
        for item in arquivos_em_memoria:
            Anexo.objects.create(
                movimentacao=movimentacao,
                arquivo=item.get("arquivo"),
                tipo_anexo=Anexo.TipoAnexo.DILIGENCIA,
                tipo_documento_id=item.get("tipo_documento_id"),
                numero_documento=item.get("numero_documento"),
            )

        # 5. Transição de status do Processo
        processo.status = Processo.Status.EM_DILIGENCIA
        processo.save(update_fields=["status"])

        return diligencia

    @staticmethod
    @transaction.atomic
    def rejeitar_diligencia(
        diligencia_id: int,
        usuario_logado: User,
        motivo_rejeicao: str,
    ) -> SolicitacaoDocumento:
        """
        Rejeita uma Diligência pendente, retornando o Processo à fila de análise.

        Transições garantidas atomicamente:
            SolicitacaoDocumento: PENDENTE    → REJEITADA
            Processo:             EM_DILIGENCIA → EM_ANALISE

        Etapas internas:
            1. Valida que a diligência está em status PENDENTE (pré-condição).
            2. Preenche motivo_rejeicao e altera status para REJEITADA.
            3. Reverte o status do Processo para EM_ANALISE.
            4. Cria a Movimentacao REJEICAO registrando o motivo na Timeline.

        Parâmetros:
            diligencia_id:  ID da SolicitacaoDocumento a rejeitar.
            usuario_logado: Usuário da chefia que executa a rejeição.
            motivo_rejeicao: Texto obrigatório com a justificativa.

        Retorna:
            A instância da SolicitacaoDocumento atualizada.

        Levanta:
            StatusInvalidoError — se a diligência não estiver em PENDENTE.
            SolicitacaoDocumento.DoesNotExist — se o ID não existir.
        """
        # Bloqueia as linhas relacionadas para evitar rejeição concorrente
        diligencia = (
            SolicitacaoDocumento.objects.select_related("processo")
            .select_for_update()
            .get(pk=diligencia_id)
        )
        processo = diligencia.processo

        if diligencia.status != SolicitacaoDocumento.Status.PENDENTE:
            raise StatusInvalidoError(
                f"A diligência #{diligencia_id} não pode ser rejeitada. "
                f"Status atual: '{diligencia.get_status_display()}'. "
                f"Esperado: 'Pendente'."
            )

        # 2. Atualiza a SolicitacaoDocumento
        diligencia.status = SolicitacaoDocumento.Status.REJEITADA
        diligencia.motivo_rejeicao = motivo_rejeicao
        diligencia.data_conclusao = timezone.now()
        diligencia.save(update_fields=["status", "motivo_rejeicao", "data_conclusao"])

        # 3. Reverte o Processo para EM_ANALISE
        processo.status = Processo.Status.EM_ANALISE
        processo.save(update_fields=["status"])

        # 4. Registra o evento de Rejeição na Timeline (imutável)
        Movimentacao.objects.create(
            processo=processo,
            tipo_evento=Movimentacao.TipoEvento.REJEICAO,
            usuario_responsavel=usuario_logado,
            descricao=(
                f"Diligência #{diligencia_id} rejeitada por "
                f"{usuario_logado.get_full_name() or usuario_logado.username}. "
                f"Motivo: {motivo_rejeicao}"
            ),
        )

        return diligencia

    @staticmethod
    @transaction.atomic
    def aprovar_e_enviar_email(
        diligencia_id: int,
        usuario_logado: User,
        emails_destino: list[str],
        anexos_ids_selecionados: list[int],
    ) -> SolicitacaoDocumento:
        """
        Aprova a diligência e enfileira o envio de e-mail externo via Cloud Tasks.

        Transições garantidas atomicamente:
            SolicitacaoDocumento: PENDENTE|ENVIADA → ENVIADA (atualiza data_envio_email)

        O e-mail NÃO é enviado diretamente neste método. O payload é enfileirado
        via `transaction.on_commit()`, garantindo que o Cloud Tasks só seja
        acionado após o commit bem-sucedido no banco de dados. Isso evita o
        estado inconsistente onde o banco falha após a tarefa já ter sido
        enfileirada.

        Etapas internas:
            1. Valida que a diligência está em PENDENTE (pré-condição).
            2. Registra data_envio_email e muda status para ENVIADA.
            3. Monta o payload para o Cloud Tasks.
            4. Registra on_commit hook que enfileirará a tarefa após o commit.

        Parâmetros:
            diligencia_id:           ID da SolicitacaoDocumento a aprovar.
            usuario_logado:          Usuário da chefia que executa a aprovação.
            emails_destino:          Lista de endereços de e-mail destinatários.
            anexos_ids_selecionados: IDs dos Anexos selecionados para o e-mail.

        Retorna:
            A instância da SolicitacaoDocumento atualizada.

        Levanta:
            StatusInvalidoError — se a diligência não estiver em PENDENTE.
            SolicitacaoDocumento.DoesNotExist — se o ID não existir.
        """
        diligencia = (
            SolicitacaoDocumento.objects.select_related("processo")
            .select_for_update()
            .get(pk=diligencia_id)
        )
        processo = diligencia.processo

        if diligencia.status not in {
            SolicitacaoDocumento.Status.PENDENTE,
            SolicitacaoDocumento.Status.ENVIADA,
        }:
            raise StatusInvalidoError(
                f"A diligência #{diligencia_id} não pode ser aprovada para envio. "
                f"Status atual: '{diligencia.get_status_display()}'. "
                f"Esperado: 'Pendente' ou 'Enviada'."
            )

        agora = timezone.now()

        # 2. Persiste a aprovação (atualiza data_envio_email para registrar este envio)
        diligencia.status = SolicitacaoDocumento.Status.ENVIADA
        diligencia.data_envio_email = agora
        diligencia.save(update_fields=["status", "data_envio_email"])

        # 3. Monta o payload da tarefa assíncrona
        payload: dict[str, Any] = {
            "tipo_tarefa": "ENVIAR_EMAIL_DILIGENCIA",
            "diligencia_id": diligencia_id,
            "processo_id": processo.pk,
            "numero_protocolo": processo.numero_protocolo,
            "emails_destino": emails_destino,
            "anexos_ids": anexos_ids_selecionados,
            "descricao_necessidade": diligencia.descricao_necessidade,
            "aprovado_por_id": usuario_logado.pk,
            "aprovado_por_nome": (
                usuario_logado.get_full_name() or usuario_logado.username
            ),
            "data_envio": agora.isoformat(),
        }

        # 4. Enfileira APÓS o commit — padrão transactional outbox simplificado.
        # Se o DB fizer rollback, o on_commit não dispara e nenhuma tarefa
        # é enviada ao Cloud Tasks, preservando a consistência.
        transaction.on_commit(lambda: enfileirar_tarefa_email(payload))

        return diligencia

    @staticmethod
    @transaction.atomic
    def concluir_diligencia_manual(
        diligencia_id: int,
        usuario_logado: User,
        arquivos_em_memoria: list[dict[str, Any]],
        observacao_resolucao: str | None = None,
    ) -> SolicitacaoDocumento:
        """
        Conclui manualmente uma Diligência com os documentos de resposta recebidos
        fisicamente ou por fora do sistema.

        Transições garantidas atomicamente:
            SolicitacaoDocumento: PENDENTE|ENVIADA → ATENDIDA

            Processo (condicional):
              SE não houver outras diligências ativas no mesmo Processo:
                  EM_DILIGENCIA → EM_ANALISE   (retorna à fila)
              SE houver outras diligências ativas (PENDENTE ou ENVIADA):
                  EM_DILIGENCIA → EM_DILIGENCIA (mantém — processo ainda ocupado)

        Etapas internas:
            1. Bloqueia a SolicitacaoDocumento e o Processo (select_for_update
               em queries separadas, garantindo lock de ambas as linhas no MySQL).
            2. Guard: valida que o status é PENDENTE ou ENVIADA.
            3. Atualiza a SolicitacaoDocumento para ATENDIDA.
            4. Cria a Movimentacao DILIGENCIA_RESOLVIDA (novo nó na Timeline).
            5. Cria os Anexos de RESPOSTA vinculados à nova Movimentacao.
            6. Verifica diligências ativas paralelas com .exists() (O(1) no DB).
            7. Aplica a transição condicional de status no Processo.

        Parâmetros:
            diligencia_id:       ID da SolicitacaoDocumento a concluir.
            usuario_logado:      Usuário da chefia que executa a conclusão.
            arquivos_em_memoria: Lista de dicts com os arquivos de resposta [
                {
                    "arquivo":           <InMemoryUploadedFile> | None,
                    "tipo_documento_id": int | None,
                    "numero_documento":  str | None,
                }
            ]
            observacao_resolucao: Texto opcional da chefia sobre a resolução.

        Retorna:
            A instância da SolicitacaoDocumento atualizada (status ATENDIDA).

        Levanta:
            StatusInvalidoError — se o status não for PENDENTE nem ENVIADA.
            SolicitacaoDocumento.DoesNotExist — se o ID não existir.
        """
        # 1. Bloqueia a diligência e o Processo em queries separadas.
        #    select_related() não propaga o FOR UPDATE para a tabela relacionada
        #    no MySQL; é necessário bloquear o Processo explicitamente para
        #    evitar que duas conclusões concorrentes leiam o mesmo conjunto
        #    de diligências ativas e tomem decisões contraditórias sobre o status.
        diligencia = (
            SolicitacaoDocumento.objects.select_for_update()
            .get(pk=diligencia_id)
        )
        processo = (
            Processo.objects.select_for_update()
            .get(pk=diligencia.processo_id)
        )

        # 2. Guard de pré-condição: aceita tanto PENDENTE quanto ENVIADA,
        #    pois a conclusão manual pode ocorrer após o e-mail já ter sido enviado.
        status_validos = {
            SolicitacaoDocumento.Status.PENDENTE,
            SolicitacaoDocumento.Status.ENVIADA,
        }
        if diligencia.status not in status_validos:
            raise StatusInvalidoError(
                f"A diligência #{diligencia_id} não pode ser concluída manualmente. "
                f"Status atual: '{diligencia.get_status_display()}'. "
                f"Esperado: 'Pendente' ou 'Enviada'."
            )

        agora = timezone.now()

        # 3. Atualiza a SolicitacaoDocumento para ATENDIDA
        diligencia.status = SolicitacaoDocumento.Status.ATENDIDA
        diligencia.data_conclusao = agora
        diligencia.observacao_chefia = observacao_resolucao
        diligencia.save(update_fields=["status", "data_conclusao", "observacao_chefia"])

        # 4. Cria a Movimentacao de fechamento (injetada no topo da Timeline)
        movimentacao_resolucao = Movimentacao.objects.create(
            processo=processo,
            tipo_evento=Movimentacao.TipoEvento.DILIGENCIA_RESOLVIDA,
            usuario_responsavel=usuario_logado,
            descricao=(
                observacao_resolucao
                or f"Diligência #{diligencia_id} concluída manualmente por "
                   f"{usuario_logado.get_full_name() or usuario_logado.username}."
            ),
        )

        # 5. Cria os Anexos de RESPOSTA vinculados à movimentação de resolução
        for item in arquivos_em_memoria:
            Anexo.objects.create(
                movimentacao=movimentacao_resolucao,
                arquivo=item.get("arquivo"),
                tipo_anexo=Anexo.TipoAnexo.RESPOSTA,
                tipo_documento_id=item.get("tipo_documento_id"),
                numero_documento=item.get("numero_documento"),
                observacao=item.get("observacao"),
            )

        # 6. Verifica se ainda existem outras diligências ativas no mesmo Processo.
        #    .exists() traduz para SELECT 1 ... LIMIT 1, sendo O(1) independente
        #    do volume de diligências — o DB para na primeira linha encontrada.
        tem_outras_ativas = (
            SolicitacaoDocumento.objects.filter(
                processo=processo,
                status__in=[
                    SolicitacaoDocumento.Status.PENDENTE,
                    SolicitacaoDocumento.Status.ENVIADA,
                ],
            )
            .exclude(pk=diligencia_id)
            .exists()
        )

        # 7. Transição condicional: só retorna o Processo para EM_ANALISE
        #    quando todas as diligências paralelas também estiverem encerradas.
        if not tem_outras_ativas:
            processo.status = Processo.Status.EM_ANALISE
            processo.save(update_fields=["status"])

        return diligencia

    @staticmethod
    @transaction.atomic
    def marcar_como_solicitada_manualmente(
        diligencia_id: int,
        usuario_logado: User,
        observacao_contato: str,
    ) -> SolicitacaoDocumento:
        """
        Marca a diligência como solicitada via meios alternativos (telefone, balcão, etc.),
        sem enfileirar envio de e-mail.
        """
        diligencia = (
            SolicitacaoDocumento.objects.select_related("processo")
            .select_for_update()
            .get(pk=diligencia_id)
        )
        processo = diligencia.processo

        if diligencia.status != SolicitacaoDocumento.Status.PENDENTE:
            raise StatusInvalidoError(
                f"A diligência #{diligencia_id} não pode ser marcada como solicitada. "
                f"Status atual: '{diligencia.get_status_display()}'. Esperado: 'Pendente'."
            )

        # 1. Muda o status para ENVIADA (reaproveitamos data_envio_email para registrar o momento)
        agora = timezone.now()
        diligencia.status = SolicitacaoDocumento.Status.ENVIADA
        diligencia.data_envio_email = agora
        diligencia.save(update_fields=["status", "data_envio_email"])

        # 2. Registra o evento na Timeline
        Movimentacao.objects.create(
            processo=processo,
            tipo_evento=Movimentacao.TipoEvento.OBSERVACAO_SIMPLES,
            usuario_responsavel=usuario_logado,
            descricao=(
                f"Diligência #{diligencia_id} marcada como solicitada por "
                f"{usuario_logado.get_full_name() or usuario_logado.username}. "
                f"Observação do contato: {observacao_contato}"
            ),
        )

        return diligencia

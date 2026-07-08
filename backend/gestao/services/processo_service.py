"""
Camada de Serviço — Domínio: Processo

Responsável por toda a lógica de negócio relativa ao ciclo de vida de um
Processo: protocolamento e distribuição em lote.

Regras:
  - Nenhuma regra de negócio vive nas Views. As Views apenas chamam estes
    métodos e convertem exceções em respostas HTTP.
  - Toda operação que escreve em múltiplas tabelas usa transaction.atomic().
  - select_for_update() é obrigatório em operações com risco de concorrência.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from gestao.models import Anexo, Movimentacao, Processo

User = get_user_model()


# ---------------------------------------------------------------------------
# Exceções de Domínio
# ---------------------------------------------------------------------------


class ProtocoloSequenciaError(Exception):
    """Levantada quando o sequencial do protocolo não pode ser extraído."""


class DistribuicaoError(Exception):
    """Levantada quando a distribuição em lote não pode ser concluída."""


# ---------------------------------------------------------------------------
# Geração de Número de Protocolo
# ---------------------------------------------------------------------------


def gerar_numero_protocolo() -> str:
    """
    Gera o próximo número de protocolo no formato AAAA-MM-DD-NNN.

    Estratégia anti-concorrência:
        select_for_update() bloqueia todas as linhas do dia atual até o
        commit da transação envolvente. Isso serializa a leitura do último
        sequencial: uma segunda requisição simultânea ficará bloqueada até
        que a primeira persista o novo Processo e libere o lock.

        Caso extremo (primeiro processo do dia com duas requisições
        simultâneas): ambas encontram queryset vazio e nenhum lock é
        aplicado. Nesse cenário, as duas gerarão "-001". Como numero_protocolo
        possui UNIQUE constraint, apenas uma INSERT terá sucesso; a outra
        receberá IntegrityError, que deve ser capturado e retentado pela
        camada de View (retorno HTTP 409 ou retry transparente).

    IMPORTANTE: Esta função DEVE ser chamada dentro de um bloco
    transaction.atomic() para que o select_for_update() seja efetivo.
    """
    hoje = date.today()
    prefixo = hoje.strftime("%Y-%m-%d")

    # Bloqueia as linhas do dia para serializar a sequência entre transações.
    ultimo = (
        Processo.objects.filter(numero_protocolo__startswith=prefixo)
        .select_for_update()
        .order_by("-numero_protocolo")
        .first()
    )

    if ultimo is None:
        sequencial = 1
    else:
        # Extrai o NNN da parte final do protocolo (ex: "2026-07-01-042" → 42)
        try:
            sequencial = int(ultimo.numero_protocolo.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError) as exc:
            raise ProtocoloSequenciaError(
                f"Não foi possível extrair o sequencial do protocolo "
                f"'{ultimo.numero_protocolo}'."
            ) from exc

    return f"{prefixo}-{sequencial:03d}"


def proxima_data_util(data: date) -> date:
    """
    Avança datas de fim de semana para a segunda-feira imediata.

    weekday(): segunda=0, ..., sábado=5, domingo=6
    """
    if data.weekday() == 5:   # sábado → +2 dias
        return data + timedelta(days=2)
    if data.weekday() == 6:   # domingo → +1 dia
        return data + timedelta(days=1)
    return data


# ---------------------------------------------------------------------------
# Serviço de Processo
# ---------------------------------------------------------------------------


class ProcessoService:
    """
    Orquestra o ciclo de vida de um Processo.

    Todos os métodos públicos são estáticos: não há estado interno nesta
    classe. Ela existe apenas como namespace semântico para agrupar as
    operações do domínio de Processo.
    """

    @staticmethod
    @transaction.atomic
    def criar_processo_inicial(
        dados_gerais: dict[str, Any],
        arquivos: list[dict[str, Any]],
        usuario_logado: User,
    ) -> Processo:
        """
        Protocola um novo Processo (evento PROTOCOLO).

        Opera em uma única transação ACID:
            1. Gera o número de protocolo (com lock de sequência).
            2. Persiste o Processo com status AGUARDANDO_DISTRIBUICAO.
            3. Vincula interessados (M2M), se houver.
            4. Cria a Movimentacao de Protocolo.
            5. Cria um Anexo do tipo INICIAL para cada arquivo recebido.

        Parâmetros:
            dados_gerais: {
                "prioridade_id":       int         — FK para NivelPrioridade (obrigatório),
                "remetente_id":        int         — FK para Remetente (obrigatório),
                "interessados_ids":    list[int]   — IDs de Remetente (opcional),
                "tipo_processo_id":    int | None  — FK para TipoDocumento (opcional),
                "numero_origem":       str | None  — numeração de origem (opcional),
                "data_origem":         date | None — data do documento de origem (opcional),
                "observacoes":         str | None  — observações gerais (opcional),
                "notificar_remetente": bool        — flag de notificação (padrão False),
            }
            arquivos: lista de dicts [
                {
                    "arquivo":           <InMemoryUploadedFile>  — pode ser None,
                    "tipo_documento_id": int | None,
                    "numero_documento":  str | None,
                    "observacao":        str | None,
                }
            ]
            usuario_logado: instância de CustomUser autenticado.

        Retorna:
            A instância do Processo recém-criado.

        Levanta:
            ProtocoloSequenciaError — se o sequencial não puder ser determinado.
        """
        # 1. Gera o protocolo dentro da transação (select_for_update ativo)
        numero_protocolo = gerar_numero_protocolo()

        # 2. Persiste o Processo
        processo = Processo.objects.create(
            numero_protocolo=numero_protocolo,
            status=Processo.Status.AGUARDANDO_DISTRIBUICAO,
            prioridade_id=dados_gerais["prioridade_id"],
            remetente_id=dados_gerais["remetente_id"],
            tipo_processo_id=dados_gerais.get("tipo_processo_id"),
            numero_origem=dados_gerais.get("numero_origem") or "",
            numero_sei=dados_gerais.get("numero_sei") or "",
            data_origem=dados_gerais.get("data_origem"),
            observacoes=dados_gerais.get("observacoes") or "",
            notificar_remetente=dados_gerais.get("notificar_remetente", False),
        )

        # 3. Vincula interessados (M2M — operação não gera queries extras se vazio)
        interessados_ids: list[int] = dados_gerais.get("interessados_ids", [])
        if interessados_ids:
            processo.interessados.set(interessados_ids)

        # 4. Cria a Movimentacao de Protocolo (evento imutável na Timeline)
        movimentacao = Movimentacao.objects.create(
            processo=processo,
            tipo_evento=Movimentacao.TipoEvento.PROTOCOLO,
            usuario_responsavel=usuario_logado,
            descricao=(
                f"Processo protocolado por "
                f"{usuario_logado.get_full_name() or usuario_logado.username}."
            ),
        )

        # 5. Cria os Anexos INICIAIS vinculados a esta Movimentacao
        for item in arquivos:
            Anexo.objects.create(
                movimentacao=movimentacao,
                processo=processo,
                arquivo=item.get("arquivo"),
                tipo_anexo=Anexo.TipoAnexo.INICIAL,
                tipo_documento_id=item.get("tipo_documento_id"),
                numero_documento=item.get("numero_documento"),
                observacao=item.get("observacao"),
            )

        return processo

    @staticmethod
    @transaction.atomic
    def distribuir_em_lote(
        processos_ids: list[int],
        procuradores_ids: list[int],
        usuario_responsavel: User,
    ) -> list[Processo]:
        """
        Distribui N processos entre M procuradores pelo algoritmo Round-Robin.

        Algoritmo Round-Robin:
            O índice posicional `i` de cada processo (na ordem recebida)
            determina o procurador receptor via `procuradores[i % M]`.

            Exemplo com 4 processos e 3 procuradores (A, B, C):
                Processo[0] → A  (0 % 3 = 0)
                Processo[1] → B  (1 % 3 = 1)
                Processo[2] → C  (2 % 3 = 2)
                Processo[3] → A  (3 % 3 = 0)  ← recomeça o ciclo

            Isso garante a diferença máxima de 1 processo entre qualquer
            par de procuradores, independente dos valores de N e M.

        Atomicidade:
            Toda a operação está sob transaction.atomic(). Se qualquer
            processo falhar (ex: constraint violation, processo não encontrado),
            TODA a distribuição sofre rollback, preservando a consistência
            da base de dados.

        Parâmetros:
            processos_ids:       IDs dos Processos a distribuir.
            procuradores_ids:    IDs dos CustomUsers receptores.
            usuario_responsavel: Usuário da chefia que acionou a distribuição.

        Retorna:
            Lista das instâncias de Processo após a atualização.

        Levanta:
            DistribuicaoError — se a lista de processos ou procuradores for
                                inválida ou contiver IDs inexistentes.
        """
        if not procuradores_ids:
            raise DistribuicaoError(
                "É obrigatório selecionar ao menos um procurador para a distribuição."
            )
        if not processos_ids:
            raise DistribuicaoError(
                "É obrigatório selecionar ao menos um processo para distribuir."
            )

        hoje = date.today()
        agora = timezone.now()
        total_procuradores = len(procuradores_ids)

        # Carrega e bloqueia os processos para evitar distribuição concorrente
        # do mesmo processo por duas requisições simultâneas.
        processos = list(
            Processo.objects.select_related("prioridade")
            .select_for_update()
            .filter(id__in=processos_ids)
        )

        if len(processos) != len(processos_ids):
            ids_encontrados = {p.id for p in processos}
            ids_faltando = sorted(set(processos_ids) - ids_encontrados)
            raise DistribuicaoError(
                f"Processos não encontrados para distribuição: {ids_faltando}. "
                "Atualize a listagem e tente novamente."
            )

        # Carrega os procuradores para montar a fila Round-Robin.
        # Mantemos a mesma ordem dos IDs recebidos para comportamento previsível.
        procuradores_map = {u.id: u for u in User.objects.filter(id__in=procuradores_ids)}
        if len(procuradores_map) != total_procuradores:
            raise DistribuicaoError(
                "Um ou mais procuradores informados não foram encontrados."
            )
        # Reconstrói a lista na ordem original dos IDs para garantir Round-Robin determinístico
        procuradores = [procuradores_map[pk] for pk in procuradores_ids]

        processos_atualizados: list[Processo] = []

        for i, processo in enumerate(processos):
            # Round-Robin: modulo determina o receptor neste ciclo
            procurador = procuradores[i % total_procuradores]

            # Cálculo de prazo: data atual + dias cadastrados na prioridade.
            # Se o resultado cair em fim de semana, avança para a segunda-feira.
            data_limite = proxima_data_util(
                hoje + timedelta(days=processo.prioridade.prazo_dias)
            )

            # Atualiza apenas os campos necessários (update_fields evita sobrescrever
            # campos que possam ter sido alterados por outra lógica concorrente)
            processo.procurador_atribuido = procurador
            processo.status = Processo.Status.EM_ANALISE
            processo.data_atribuicao = agora
            processo.data_limite = data_limite
            processo.save(
                update_fields=[
                    "procurador_atribuido",
                    "status",
                    "data_atribuicao",
                    "data_limite",
                ]
            )

            # Registra o evento de Distribuição na Timeline (imutável)
            Movimentacao.objects.create(
                processo=processo,
                tipo_evento=Movimentacao.TipoEvento.DISTRIBUICAO,
                usuario_responsavel=usuario_responsavel,
                descricao=(
                    f"Processo distribuído para "
                    f"{procurador.get_full_name() or procurador.username} "
                    f"por {usuario_responsavel.get_full_name() or usuario_responsavel.username}. "
                    f"Prazo: {data_limite.strftime('%d/%m/%Y')}."
                ),
            )

            processos_atualizados.append(processo)

        return processos_atualizados

    # -----------------------------------------------------------------------
    # Status ativos para fins de redistribuição (não inclui estados finais)
    # -----------------------------------------------------------------------
    _STATUS_REDISTRIBUIVEIS = [
        Processo.Status.AGUARDANDO_DISTRIBUICAO,
        Processo.Status.EM_ANALISE,
        Processo.Status.EM_DILIGENCIA,
    ]

    @staticmethod
    @transaction.atomic
    def redistribuir_ferias(
        procurador_origem_id: int,
        procuradores_destino_ids: list[int],
        usuario_responsavel: User,
    ) -> list[Processo]:
        """
        Redistribui os processos ativos de um procurador em férias/afastamento
        para um conjunto de procuradores destino, usando Round-Robin.

        Diferenças em relação a `distribuir_em_lote`:
          - Os processos são descobertos por query (procurador + status ativos),
            não por lista de IDs informada manualmente.
          - O status do processo é PRESERVADO (não é alterado).
          - data_limite é recalculada (hoje + prazo_dias da prioridade), igual a
            distribuir_em_lote.
          - A descrição da Movimentacao identifica o motivo como férias/afastamento.

        Parâmetros:
            procurador_origem_id:    ID do CustomUser que sairá de férias.
            procuradores_destino_ids: IDs dos procuradores que absorverão a carga.
            usuario_responsavel:     Usuário da chefia que executa a redistribuição.

        Retorna:
            Lista das instâncias de Processo redistribuídos.

        Levanta:
            DistribuicaoError — se não houver processos ativos, destinos inválidos
                                ou procuradores não encontrados.
        """
        if not procuradores_destino_ids:
            raise DistribuicaoError(
                "É obrigatório selecionar ao menos um procurador destino."
            )

        # Carrega e bloqueia todos os processos ativos do procurador origem
        processos = list(
            Processo.objects.select_related("prioridade")
            .select_for_update()
            .filter(
                procurador_atribuido_id=procurador_origem_id,
                status__in=ProcessoService._STATUS_REDISTRIBUIVEIS,
            )
        )

        if not processos:
            raise DistribuicaoError(
                f"Nenhum processo ativo encontrado para o procurador ID {procurador_origem_id}."
            )

        total_destinos = len(procuradores_destino_ids)
        procuradores_map = {
            u.id: u
            for u in User.objects.filter(id__in=procuradores_destino_ids)
        }
        if len(procuradores_map) != total_destinos:
            raise DistribuicaoError(
                "Um ou mais procuradores destino informados não foram encontrados."
            )
        # Mantém a ordem dos IDs para Round-Robin determinístico
        procuradores_destino = [procuradores_map[pk] for pk in procuradores_destino_ids]

        agora = timezone.now()
        processos_redistribuidos: list[Processo] = []

        for i, processo in enumerate(processos):
            # Round-Robin: mesmo algoritmo de distribuir_em_lote
            destino = procuradores_destino[i % total_destinos]

            # Recalcula data_limite (hoje + prazo_dias), preserva status.
            # Se o resultado cair em fim de semana, avança para a segunda-feira.
            hoje = agora.date()
            data_limite = proxima_data_util(
                hoje + timedelta(days=processo.prioridade.prazo_dias)
            )

            processo.procurador_atribuido = destino
            processo.data_atribuicao = agora
            processo.data_limite = data_limite
            processo.save(update_fields=["procurador_atribuido", "data_atribuicao", "data_limite"])

            Movimentacao.objects.create(
                processo=processo,
                tipo_evento=Movimentacao.TipoEvento.DISTRIBUICAO,
                usuario_responsavel=usuario_responsavel,
                descricao=(
                    f"Redistribuição por motivo de férias/afastamento. "
                    f"Processo transferido para "
                    f"{destino.get_full_name() or destino.username} "
                    f"por {usuario_responsavel.get_full_name() or usuario_responsavel.username}. "
                    f"Prazo: {data_limite.strftime('%d/%m/%Y')}."
                ),
            )

            processos_redistribuidos.append(processo)

        return processos_redistribuidos

    @staticmethod
    @transaction.atomic
    def enviar_lembrete(
        processo_id: int,
        usuario_responsavel: User,
    ) -> Movimentacao:
        """
        Registra um lembrete de cobrança na Timeline do Processo.

        Cria uma Movimentacao do tipo OBSERVACAO_SIMPLES indicando que a
        chefia enviou uma cobrança ao procurador responsável.
        A integração com e-mail será adicionada na Sprint de Deploy via
        Cloud Tasks, seguindo o mesmo padrão do notificacao_service.

        Parâmetros:
            processo_id:         ID do Processo alvo.
            usuario_responsavel: Usuário da chefia que envia o lembrete.

        Retorna:
            A instância da Movimentacao criada.

        Levanta:
            Processo.DoesNotExist — se o processo_id não existir.
        """
        processo = Processo.objects.get(pk=processo_id)

        movimentacao = Movimentacao.objects.create(
            processo=processo,
            tipo_evento=Movimentacao.TipoEvento.OBSERVACAO_SIMPLES,
            usuario_responsavel=usuario_responsavel,
            descricao=(
                f"Lembrete de cobrança enviado pela chefia "
                f"({usuario_responsavel.get_full_name() or usuario_responsavel.username})."
            ),
        )

        return movimentacao

    @staticmethod
    @transaction.atomic
    def tramitar_processo(
        processo_id: int,
        novo_status: str,
        usuario_responsavel: User,
        motivo: str = "",
    ) -> Processo:
        """
        Transiciona formalmente o status de um Processo, registrando o evento
        correspondente na Timeline (Event Sourcing).

        Parâmetros:
            processo_id:         ID do Processo a ser tramitado.
            novo_status:         Valor de Processo.Status destino.
            usuario_responsavel: Usuário que executa a ação.
            motivo:              Descrição opcional registrada na Timeline.

        Retorna:
            A instância do Processo após a atualização.

        Levanta:
            Processo.DoesNotExist — se o processo_id não existir.
        """
        processo = Processo.objects.select_for_update().get(id=processo_id)

        # Mapeia o Status do Processo para o Tipo de Evento na Timeline
        mapa_eventos = {
            Processo.Status.CONCLUIDO: Movimentacao.TipoEvento.CONCLUSAO,
            Processo.Status.REJEITADO: Movimentacao.TipoEvento.REJEICAO,
            Processo.Status.ARQUIVADO: Movimentacao.TipoEvento.ARQUIVAMENTO,
        }
        tipo_evento = mapa_eventos.get(novo_status, Movimentacao.TipoEvento.OBSERVACAO_SIMPLES)

        # Regras de negócio específicas por status destino
        if novo_status == Processo.Status.AGUARDANDO_DISTRIBUICAO:
            processo.procurador_atribuido = None
            processo.data_limite = None
            processo.data_atribuicao = None
            tipo_evento = Movimentacao.TipoEvento.DEVOLUCAO
            descricao_log = motivo or "Processo devolvido para a fila de distribuição."
        elif novo_status == Processo.Status.EM_ANALISE:
            tipo_evento = Movimentacao.TipoEvento.DESARQUIVAMENTO
            descricao_log = motivo or "Processo reaberto/desarquivado para análise."
        else:
            status_display = dict(Processo.Status.choices).get(novo_status, novo_status)
            descricao_log = motivo or f"Status tramitado para: {status_display}."

        processo.status = novo_status
        processo.save(update_fields=["status", "procurador_atribuido", "data_limite", "data_atribuicao"])

        # Registro obrigatório de auditoria (Timeline)
        Movimentacao.objects.create(
            processo=processo,
            tipo_evento=tipo_evento,
            usuario_responsavel=usuario_responsavel,
            descricao=descricao_log,
        )

        return processo

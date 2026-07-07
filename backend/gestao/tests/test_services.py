"""
Testes da Camada de Serviço — app gestao.

Cobre:
  - processo_service: geração de protocolo e distribuição Round-Robin.
  - diligencia_service: scatter-gather (concorrência de diligências) e status guards.

Cada TestCase usa o banco de testes isolado do Django (rollback por savepoint).
Os helpers de fixture são funções puras reutilizadas pelo test_api.py.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase

from cadastros.models import NivelPrioridade, Remetente
from gestao.models import Movimentacao, Processo, SolicitacaoDocumento
from gestao.services.diligencia_service import (
    DiligenciaService,
    StatusInvalidoError,
)
from gestao.services.processo_service import (
    DistribuicaoError,
    ProcessoService,
    gerar_numero_protocolo,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers de fixture (importados também por test_api.py)
# ---------------------------------------------------------------------------


def criar_prioridade(prazo_dias: int = 5, descricao: str = "Normal") -> NivelPrioridade:
    return NivelPrioridade.objects.create(descricao=descricao, prazo_dias=prazo_dias)


def criar_remetente(nome: str = "Remetente Teste") -> Remetente:
    return Remetente.objects.create(
        nome_razao_social=nome,
        tipo_pessoa=Remetente.TipoPessoa.FISICA,
    )


def criar_usuario(username: str, nome: str = "Usuário Teste"):
    partes = nome.split(maxsplit=1)
    return User.objects.create_user(
        username=username,
        password="senha123!@#",
        first_name=partes[0],
        last_name=partes[1] if len(partes) > 1 else "",
    )


def criar_processo(
    prioridade: NivelPrioridade,
    remetente: Remetente,
    status: str = Processo.Status.EM_ANALISE,
    seq: int = 1,
) -> Processo:
    """Cria um Processo com data fictícia de 2099 para não colidir com testes de protocolo."""
    return Processo.objects.create(
        numero_protocolo=f"2099-01-01-{seq:03d}",
        status=status,
        prioridade=prioridade,
        remetente=remetente,
    )


# ---------------------------------------------------------------------------
# Testes: gerar_numero_protocolo
# ---------------------------------------------------------------------------


class TestGerarNumeroProtocolo(TestCase):
    """Valida a geração do número de protocolo no formato AAAA-MM-DD-NNN."""

    def setUp(self):
        self.prioridade = criar_prioridade()
        self.remetente = criar_remetente()

    def test_primeiro_protocolo_do_dia_gera_001(self):
        """Sem processos no dia atual, deve gerar AAAA-MM-DD-001."""
        hoje = date.today().strftime("%Y-%m-%d")
        with transaction.atomic():
            numero = gerar_numero_protocolo()
        self.assertEqual(numero, f"{hoje}-001")

    def test_incrementa_sequencial_a_partir_do_existente(self):
        """Com processo do dia no banco, o sequencial deve incrementar."""
        hoje = date.today().strftime("%Y-%m-%d")
        Processo.objects.create(
            numero_protocolo=f"{hoje}-007",
            status=Processo.Status.AGUARDANDO_DISTRIBUICAO,
            prioridade=self.prioridade,
            remetente=self.remetente,
        )
        with transaction.atomic():
            numero = gerar_numero_protocolo()
        self.assertEqual(numero, f"{hoje}-008")

    def test_formato_aaaa_mm_dd_nnn(self):
        """O protocolo deve ter exatamente 4 segmentos separados por hífen."""
        with transaction.atomic():
            numero = gerar_numero_protocolo()
        partes = numero.split("-")
        self.assertEqual(len(partes), 4, f"Formato inválido: {numero}")
        ano, mes, dia, seq = partes
        self.assertEqual(len(ano), 4)
        self.assertEqual(len(mes), 2)
        self.assertEqual(len(dia), 2)
        self.assertEqual(len(seq), 3)


# ---------------------------------------------------------------------------
# Testes: ProcessoService.distribuir_em_lote (Round-Robin)
# ---------------------------------------------------------------------------


class TestDistribuirEmLote(TestCase):
    """Valida a matemática Round-Robin e as regras de negócio da distribuição."""

    def setUp(self):
        self.prioridade = criar_prioridade()
        self.remetente = criar_remetente()
        self.chefia = criar_usuario("chefia_dist", "Chefia Distribuição")

    def _processos(self, n: int) -> list[Processo]:
        return [
            criar_processo(self.prioridade, self.remetente, seq=i + 1)
            for i in range(n)
        ]

    def _procuradores(self, n: int):
        return [criar_usuario(f"proc_rr_{i}", f"Procurador RR {i}") for i in range(n)]

    # --- Matemática do Round-Robin ---

    def test_diferenca_maxima_de_1_entre_procuradores(self):
        """4 processos / 3 procuradores: diferença máxima de 1 processo (2-1-1)."""
        processos = self._processos(4)
        procuradores = self._procuradores(3)

        ProcessoService.distribuir_em_lote(
            processos_ids=[p.pk for p in processos],
            procuradores_ids=[u.pk for u in procuradores],
            usuario_responsavel=self.chefia,
        )

        contagens = [
            Processo.objects.filter(procurador_atribuido=u).count()
            for u in procuradores
        ]
        self.assertEqual(sum(contagens), 4)
        self.assertLessEqual(
            max(contagens) - min(contagens),
            1,
            f"Diferença acima de 1: {contagens}",
        )

    def test_distribuicao_exata_divisivel(self):
        """6 processos / 3 procuradores: deve ser exatamente 2 para cada."""
        processos = self._processos(6)
        procuradores = self._procuradores(3)

        ProcessoService.distribuir_em_lote(
            processos_ids=[p.pk for p in processos],
            procuradores_ids=[u.pk for u in procuradores],
            usuario_responsavel=self.chefia,
        )

        for proc in procuradores:
            count = Processo.objects.filter(procurador_atribuido=proc).count()
            self.assertEqual(count, 2, f"{proc.username} recebeu {count} processos, esperado 2")

    def test_um_procurador_recebe_todos(self):
        """Com 1 procurador, todos os processos vão para ele."""
        processos = self._processos(5)
        procurador = self._procuradores(1)[0]

        ProcessoService.distribuir_em_lote(
            processos_ids=[p.pk for p in processos],
            procuradores_ids=[procurador.pk],
            usuario_responsavel=self.chefia,
        )

        count = Processo.objects.filter(procurador_atribuido=procurador).count()
        self.assertEqual(count, 5)

    # --- Atualização de estado ---

    def test_status_atualizado_para_em_analise(self):
        """Após distribuição, todos os processos devem estar com status EM_ANALISE."""
        processos = self._processos(3)
        procuradores = self._procuradores(2)

        ProcessoService.distribuir_em_lote(
            processos_ids=[p.pk for p in processos],
            procuradores_ids=[u.pk for u in procuradores],
            usuario_responsavel=self.chefia,
        )

        for p in Processo.objects.filter(pk__in=[proc.pk for proc in processos]):
            self.assertEqual(p.status, Processo.Status.EM_ANALISE)

    def test_cria_movimentacao_distribuicao_para_cada_processo(self):
        """Deve existir exatamente 1 Movimentacao DISTRIBUICAO por processo."""
        processos = self._processos(2)
        procurador = self._procuradores(1)[0]

        ProcessoService.distribuir_em_lote(
            processos_ids=[p.pk for p in processos],
            procuradores_ids=[procurador.pk],
            usuario_responsavel=self.chefia,
        )

        for processo in processos:
            count = Movimentacao.objects.filter(
                processo=processo,
                tipo_evento=Movimentacao.TipoEvento.DISTRIBUICAO,
            ).count()
            self.assertEqual(count, 1)

    # --- Guards de erro ---

    def test_lista_vazia_procuradores_levanta_erro(self):
        processos = self._processos(2)
        with self.assertRaises(DistribuicaoError):
            ProcessoService.distribuir_em_lote(
                processos_ids=[p.pk for p in processos],
                procuradores_ids=[],
                usuario_responsavel=self.chefia,
            )

    def test_lista_vazia_processos_levanta_erro(self):
        procurador = self._procuradores(1)[0]
        with self.assertRaises(DistribuicaoError):
            ProcessoService.distribuir_em_lote(
                processos_ids=[],
                procuradores_ids=[procurador.pk],
                usuario_responsavel=self.chefia,
            )

    def test_processo_inexistente_levanta_erro(self):
        procurador = self._procuradores(1)[0]
        with self.assertRaises(DistribuicaoError):
            ProcessoService.distribuir_em_lote(
                processos_ids=[999_999],
                procuradores_ids=[procurador.pk],
                usuario_responsavel=self.chefia,
            )


# ---------------------------------------------------------------------------
# Testes: DiligenciaService — Scatter-Gather (concorrência de diligências)
# ---------------------------------------------------------------------------


class TestScatterGatherDiligencias(TestCase):
    """
    Valida a regra de concorrência: o Processo só volta para EM_ANALISE quando
    TODAS as diligências ativas do mesmo Processo estiverem concluídas.
    """

    def setUp(self):
        prioridade = criar_prioridade()
        remetente = criar_remetente()
        self.procurador = criar_usuario("proc_sg", "Procurador SG")
        self.chefia = criar_usuario("chefia_sg", "Chefia SG")

        # Processo começa EM_ANALISE
        self.processo = criar_processo(prioridade, remetente, seq=1)

        # Abre a primeira diligência via serviço (transição → EM_DILIGENCIA)
        self.diligencia_1 = DiligenciaService.criar_diligencia_em_lote(
            processo_id=self.processo.pk,
            usuario_logado=self.procurador,
            descricao_necessidade="Primeira necessidade para teste scatter-gather.",
            arquivos_em_memoria=[],
        )

        # Segunda diligência criada diretamente via ORM para isolar a regra
        # de scatter-gather da lógica de criação (que exige EM_ANALISE).
        mov2 = Movimentacao.objects.create(
            processo=self.processo,
            tipo_evento=Movimentacao.TipoEvento.DILIGENCIA_INICIADA,
            usuario_responsavel=self.procurador,
            descricao="Segunda necessidade para teste scatter-gather.",
        )
        self.diligencia_2 = SolicitacaoDocumento.objects.create(
            processo=self.processo,
            movimentacao_origem=mov2,
            descricao_necessidade="Segunda necessidade para teste scatter-gather.",
            status=SolicitacaoDocumento.Status.PENDENTE,
        )

    def test_concluir_primeira_mantem_processo_em_diligencia(self):
        """
        Conclui a diligência #1. O Processo DEVE continuar EM_DILIGENCIA
        porque a diligência #2 ainda está PENDENTE.
        """
        DiligenciaService.concluir_diligencia_manual(
            diligencia_id=self.diligencia_1.pk,
            usuario_logado=self.chefia,
            arquivos_em_memoria=[],
        )

        self.processo.refresh_from_db()
        self.assertEqual(
            self.processo.status,
            Processo.Status.EM_DILIGENCIA,
            "O Processo não deve sair de EM_DILIGENCIA enquanto há outra diligência ativa.",
        )

    def test_concluir_ambas_volta_processo_para_em_analise(self):
        """
        Conclui as diligências #1 e #2. O Processo DEVE voltar para EM_ANALISE
        porque não há mais nenhuma diligência PENDENTE ou ENVIADA.
        """
        DiligenciaService.concluir_diligencia_manual(
            diligencia_id=self.diligencia_1.pk,
            usuario_logado=self.chefia,
            arquivos_em_memoria=[],
        )
        DiligenciaService.concluir_diligencia_manual(
            diligencia_id=self.diligencia_2.pk,
            usuario_logado=self.chefia,
            arquivos_em_memoria=[],
        )

        self.processo.refresh_from_db()
        self.assertEqual(
            self.processo.status,
            Processo.Status.EM_ANALISE,
            "Com todas as diligências concluídas, o Processo deve voltar para EM_ANALISE.",
        )

    def test_diligencias_atualizadas_para_atendida(self):
        """Ambas as diligências devem estar com status ATENDIDA após a conclusão."""
        DiligenciaService.concluir_diligencia_manual(
            diligencia_id=self.diligencia_1.pk,
            usuario_logado=self.chefia,
            arquivos_em_memoria=[],
        )
        DiligenciaService.concluir_diligencia_manual(
            diligencia_id=self.diligencia_2.pk,
            usuario_logado=self.chefia,
            arquivos_em_memoria=[],
        )

        for d in [self.diligencia_1, self.diligencia_2]:
            d.refresh_from_db()
            self.assertEqual(d.status, SolicitacaoDocumento.Status.ATENDIDA)


# ---------------------------------------------------------------------------
# Testes: DiligenciaService — Status Guards (transações inválidas)
# ---------------------------------------------------------------------------


class TestStatusGuardsDiligencia(TestCase):
    """
    Valida que os status guards levantam StatusInvalidoError ao tentar
    transições inválidas.
    """

    def setUp(self):
        prioridade = criar_prioridade()
        remetente = criar_remetente()
        self.usuario = criar_usuario("usuario_guard", "Usuario Guard")
        self.processo = criar_processo(prioridade, remetente, seq=1)

        # Cria uma diligência e a conclui: ficará com status ATENDIDA
        diligencia = DiligenciaService.criar_diligencia_em_lote(
            processo_id=self.processo.pk,
            usuario_logado=self.usuario,
            descricao_necessidade="Diligência para testes de guard (mínimo 10 chars).",
            arquivos_em_memoria=[],
        )
        DiligenciaService.concluir_diligencia_manual(
            diligencia_id=diligencia.pk,
            usuario_logado=self.usuario,
            arquivos_em_memoria=[],
        )
        self.diligencia_atendida = diligencia

    def test_rejeitar_diligencia_atendida_levanta_status_invalido(self):
        """Tentar rejeitar uma diligência ATENDIDA deve levantar StatusInvalidoError."""
        with self.assertRaises(StatusInvalidoError):
            DiligenciaService.rejeitar_diligencia(
                diligencia_id=self.diligencia_atendida.pk,
                usuario_logado=self.usuario,
                motivo_rejeicao="Tentativa inválida.",
            )

    def test_concluir_diligencia_rejeitada_levanta_status_invalido(self):
        """Tentar concluir uma diligência REJEITADA deve levantar StatusInvalidoError."""
        # Recria o processo em EM_ANALISE para abrir nova diligência
        self.processo.status = Processo.Status.EM_ANALISE
        self.processo.save()

        nova = DiligenciaService.criar_diligencia_em_lote(
            processo_id=self.processo.pk,
            usuario_logado=self.usuario,
            descricao_necessidade="Nova diligência para testar rejeição de guard.",
            arquivos_em_memoria=[],
        )
        DiligenciaService.rejeitar_diligencia(
            diligencia_id=nova.pk,
            usuario_logado=self.usuario,
            motivo_rejeicao="Motivo de teste.",
        )

        with self.assertRaises(StatusInvalidoError):
            DiligenciaService.concluir_diligencia_manual(
                diligencia_id=nova.pk,
                usuario_logado=self.usuario,
                arquivos_em_memoria=[],
            )

    def test_abrir_diligencia_com_processo_em_diligencia_levanta_erro(self):
        """Abrir diligência em Processo já EM_DILIGENCIA deve levantar StatusInvalidoError."""
        prioridade = criar_prioridade(prazo_dias=3, descricao="Urgente")
        remetente = criar_remetente("Outro Remetente")
        processo_ocupado = criar_processo(
            prioridade, remetente,
            status=Processo.Status.EM_DILIGENCIA,
            seq=99,
        )

        with self.assertRaises(StatusInvalidoError):
            DiligenciaService.criar_diligencia_em_lote(
                processo_id=processo_ocupado.pk,
                usuario_logado=self.usuario,
                descricao_necessidade="Tentativa de abertura inválida.",
                arquivos_em_memoria=[],
            )

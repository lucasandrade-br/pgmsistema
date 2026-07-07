"""
Testes da Camada de API — app gestao.

Cobre:
  - ProcessoViewSet: listagem, autenticação e distribuir-lote.
  - DiligenciaViewSet: ações de criar, rejeitar e guardrails de autenticação.

Utiliza `force_authenticate` para isolar os testes do fluxo JWT,
testando apenas a lógica dos endpoints.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from gestao.models import Processo
from gestao.tests.test_services import (
    criar_prioridade,
    criar_processo,
    criar_remetente,
    criar_usuario,
)


# ---------------------------------------------------------------------------
# Testes: POST /api/v1/gestao/processos/distribuir-lote/
# ---------------------------------------------------------------------------


class TestDistribuirLoteEndpoint(APITestCase):
    URL = "/api/v1/gestao/processos/distribuir-lote/"

    def setUp(self):
        self.prioridade = criar_prioridade()
        self.remetente = criar_remetente()
        self.chefia = criar_usuario("chefia_api", "Chefia API")
        self.client.force_authenticate(user=self.chefia)

    # --- Validação de payload ---

    def test_payload_sem_procuradores_retorna_400(self):
        """Payload sem o campo procuradores_ids deve retornar HTTP 400."""
        response = self.client.post(
            self.URL,
            data={"processos_ids": [1, 2]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error_code"], "VALIDATION_FAILED")
        self.assertIn("procuradores_ids", response.data["details"])

    def test_payload_com_lista_procuradores_vazia_retorna_400(self):
        """Lista vazia de procuradores deve retornar HTTP 400."""
        response = self.client.post(
            self.URL,
            data={"processos_ids": [1], "procuradores_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error_code"], "VALIDATION_FAILED")

    def test_payload_com_lista_processos_vazia_retorna_400(self):
        """Lista vazia de processos deve retornar HTTP 400."""
        response = self.client.post(
            self.URL,
            data={"processos_ids": [], "procuradores_ids": [1]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_processos_inexistentes_retorna_400_com_error_code(self):
        """IDs de processos que não existem devem retornar HTTP 400 DISTRIBUICAO_ERROR."""
        procurador = criar_usuario("proc_api_err", "Procurador API Err")
        response = self.client.post(
            self.URL,
            data={"processos_ids": [999_999], "procuradores_ids": [procurador.pk]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error_code"], "DISTRIBUICAO_ERROR")

    # --- Fluxo de sucesso ---

    def test_distribuicao_valida_retorna_200_e_lista_processos(self):
        """Payload válido deve retornar HTTP 200 com a lista dos processos atualizados."""
        procurador = criar_usuario("proc_api_ok", "Procurador API OK")
        processo = criar_processo(
            self.prioridade, self.remetente,
            status=Processo.Status.EM_ANALISE, seq=1,
        )

        response = self.client.post(
            self.URL,
            data={
                "processos_ids": [processo.pk],
                "procuradores_ids": [procurador.pk],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], processo.pk)
        self.assertEqual(response.data[0]["status"], Processo.Status.EM_ANALISE)

    def test_distribuicao_atualiza_procurador_no_banco(self):
        """Após a distribuição, o campo procurador_atribuido deve estar salvo no banco."""
        procurador = criar_usuario("proc_bank_ok", "Procurador Banco OK")
        processo = criar_processo(
            self.prioridade, self.remetente,
            status=Processo.Status.EM_ANALISE, seq=2,
        )

        self.client.post(
            self.URL,
            data={
                "processos_ids": [processo.pk],
                "procuradores_ids": [procurador.pk],
            },
            format="json",
        )

        processo.refresh_from_db()
        self.assertEqual(processo.procurador_atribuido_id, procurador.pk)


# ---------------------------------------------------------------------------
# Testes: Autenticação (cobertura transversal)
# ---------------------------------------------------------------------------


class TestAutenticacaoEndpoints(APITestCase):
    """Garante que todos os endpoints principais requerem autenticação."""

    def test_listar_processos_sem_auth_retorna_401(self):
        response = self.client.get("/api/v1/gestao/processos/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_distribuir_lote_sem_auth_retorna_401(self):
        response = self.client.post(
            "/api/v1/gestao/processos/distribuir-lote/",
            data={},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_criar_diligencia_sem_auth_retorna_401(self):
        response = self.client.post(
            "/api/v1/gestao/diligencias/lote/",
            data={},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_token_invalido_retorna_401(self):
        """Token JWT forjado deve resultar em 401."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer token.invalido.aqui")
        response = self.client.get("/api/v1/gestao/processos/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Testes: GET /api/v1/gestao/processos/ (listagem paginada)
# ---------------------------------------------------------------------------


class TestListagemProcessos(APITestCase):
    def setUp(self):
        self.usuario = criar_usuario("usuario_lista", "Usuário Lista")
        self.client.force_authenticate(user=self.usuario)

    def test_listagem_retorna_200_com_envelope_paginado(self):
        """Deve retornar HTTP 200 com estrutura count/next/previous/results."""
        response = self.client.get("/api/v1/gestao/processos/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    def test_listagem_com_dados_retorna_processos(self):
        """Com processos no banco, a listagem deve retorná-los."""
        prioridade = criar_prioridade()
        remetente = criar_remetente()
        criar_processo(prioridade, remetente, seq=1)
        criar_processo(prioridade, remetente, seq=2)

        response = self.client.get("/api/v1/gestao/processos/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 2)


# ---------------------------------------------------------------------------
# Testes: POST /api/v1/gestao/diligencias/{id}/rejeitar/
# ---------------------------------------------------------------------------


class TestRejeitarDiligenciaEndpoint(APITestCase):
    def setUp(self):
        prioridade = criar_prioridade()
        remetente = criar_remetente()
        self.procurador = criar_usuario("proc_rej_api", "Procurador Rej API")
        self.chefia = criar_usuario("chefia_rej_api", "Chefia Rej API")
        self.client.force_authenticate(user=self.chefia)

        processo = criar_processo(prioridade, remetente, seq=1)

        # Importa o service aqui para criar a diligência diretamente
        from gestao.services.diligencia_service import DiligenciaService
        self.diligencia = DiligenciaService.criar_diligencia_em_lote(
            processo_id=processo.pk,
            usuario_logado=self.procurador,
            descricao_necessidade="Necessidade de teste para endpoint de rejeição.",
            arquivos_em_memoria=[],
        )

    def test_rejeitar_sem_motivo_retorna_400(self):
        """Rejeição sem motivo_rejeicao deve retornar HTTP 400."""
        url = f"/api/v1/gestao/diligencias/{self.diligencia.pk}/rejeitar/"
        response = self.client.post(url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("motivo_rejeicao", response.data["details"])

    def test_rejeitar_com_motivo_retorna_200(self):
        """Rejeição com motivo válido deve retornar HTTP 200."""
        url = f"/api/v1/gestao/diligencias/{self.diligencia.pk}/rejeitar/"
        response = self.client.post(
            url,
            data={"motivo_rejeicao": "Documentação insuficiente."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "REJEITADA")

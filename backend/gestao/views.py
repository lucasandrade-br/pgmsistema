"""
Views (Endpoints) do app gestao.

Responsabilidades exclusivas:
  1. Receber a requisição HTTP.
  2. Validar o payload via Serializer.
  3. Chamar o método correspondente na Camada de Serviço.
  4. Converter exceções de domínio em respostas HTTP padronizadas.
  5. Retornar o Response.

Nenhuma regra de negócio deve residir aqui.
"""

import json

from django.db import IntegrityError
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from gestao.filters import DiligenciaFilter, ProcessoFilter
from gestao.models import Anexo, Processo, SolicitacaoDocumento
from gestao.serializers import (
    AnexoUpdateSerializer,
    DiligenciaAprovarSerializer,
    DiligenciaConcluirSerializer,
    DiligenciaListSerializer,
    DiligenciaLoteCreateSerializer,
    DiligenciaMarcarSolicitadaSerializer,
    DiligenciaRejeitarSerializer,
    DistribuicaoLoteSerializer,
    ProcessoCreateSerializer,
    ProcessoTramitarSerializer,
    ProcessoUpdateSerializer,
    MovimentacaoSerializer,
    ProcessoSerializer,
    RedistribuicaoFeriasSerializer,
)
from gestao.services.diligencia_service import DiligenciaError, DiligenciaService, StatusInvalidoError
from gestao.services.movimentacao_service import MovimentacaoService, TipoEventoInvalidoError
from gestao.services.processo_service import DistribuicaoError, ProcessoService

# Grupos com visibilidade total sobre todos os processos
_GRUPOS_VISIBILIDADE_TOTAL = {"Protocolador-Chefe", "Procurador-Chefe", "Protocolo", "Cadastrante"}
# Grupos com visibilidade restrita aos próprios processos
_GRUPOS_VISIBILIDADE_PROPRIA = {"Procuradores", "Procurador-Analista"}


class AnexoViewSet(viewsets.GenericViewSet):
    """
    ViewSet minimal para atualização parcial de Anexos.
    Suporta apenas PATCH (soft-delete via ativo=False e edição de metadados).
    """

    from gestao.models import Anexo as _Anexo

    queryset           = _Anexo.objects.all()
    serializer_class   = AnexoUpdateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names  = ["patch", "head", "options"]

    def partial_update(self, request: Request, pk: int = None) -> Response:
        from gestao.models import Anexo as _Anexo
        try:
            anexo = _Anexo.objects.get(pk=pk)
        except _Anexo.DoesNotExist:
            return Response({"detail": "Anexo não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(anexo, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ProcessoViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para o recurso Processo.

    Rotas geradas automaticamente pelo DefaultRouter:
        GET    /api/v1/gestao/processos/           → list
        POST   /api/v1/gestao/processos/           → create
        GET    /api/v1/gestao/processos/{id}/      → retrieve
        PUT    /api/v1/gestao/processos/{id}/      → update
        PATCH  /api/v1/gestao/processos/{id}/      → partial_update
        DELETE /api/v1/gestao/processos/{id}/      → destroy

    Rota customizada:
        POST   /api/v1/gestao/processos/distribuir-lote/  → distribuir_lote
    """

    permission_classes = [IsAuthenticated]
    # Filtros avançados via ProcessoFilter (django-filter)
    filterset_class = ProcessoFilter

    # queryset base — substituído por get_queryset() para aplicar RLS
    queryset = Processo.objects.none()

    def get_queryset(self):
        """
        Aplica Row-Level Security baseada no grupo do usuário logado.

        Regras:
          - Superuser → todos os processos.
          - Grupos de chefia/protocolo (visibilidade total) → todos.
          - Procuradores e Analistas (visibilidade restrita) → apenas os
            processos atribuídos a eles OU sem procurador atribuído.
        """
        user = self.request.user
        base_qs = (
            Processo.objects.select_related(
                "prioridade",
                "remetente",
                "procurador_atribuido",
                "tipo_processo",
            )
            .prefetch_related("interessados")
            .order_by("-id")
        )

        if user.is_superuser:
            return base_qs

        grupos_usuario = set(user.groups.values_list("name", flat=True))

        if grupos_usuario & _GRUPOS_VISIBILIDADE_TOTAL:
            return base_qs

        # Visibilidade restrita: apenas processos explicitamente atribuídos ao usuário logado
        return base_qs.filter(procurador_atribuido=user)

    def get_serializer_class(self):
        """Retorna o serializer adequado para cada ação."""
        if self.action == "create":
            return ProcessoCreateSerializer
        if self.action in ("update", "partial_update"):
            return ProcessoUpdateSerializer
        return ProcessoSerializer

    def partial_update(self, request: Request, pk: int = None) -> Response:
        """
        PATCH /api/v1/gestao/processos/{id}/
        Atualização parcial dos metadados de um Processo.
        Retorna a representação completa (ProcessoSerializer) após o save.
        """
        processo = self.get_object()
        serializer = ProcessoUpdateSerializer(processo, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(
            ProcessoSerializer(updated, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def create(self, request: Request, *args, **kwargs) -> Response:
        """
        POST /api/v1/gestao/processos/
        Protocola um novo Processo (evento PROTOCOLO na Timeline).

        Aceita multipart/form-data.
        Campos de formulário: prioridade_id, remetente_id, interessados_ids[].
        Arquivos: campo 'arquivos' (múltiplos), com tipo_documento_id e
                  numero_documento opcionais para cada lote.
        """
        # RBAC: Trava de segurança do Backend
        user = request.user
        if not user.is_superuser:
            grupos_usuario = set(user.groups.values_list("name", flat=True))
            if not (grupos_usuario & _GRUPOS_VISIBILIDADE_TOTAL):
                return Response(
                    {"detail": "Acesso Negado: Seu perfil não tem permissão para protocolar novos processos."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = ProcessoCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error_code": "VALIDATION_FAILED",
                    "message": "A requisição contém dados inválidos.",
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        arquivos = _montar_arquivos(request)

        processo = ProcessoService.criar_processo_inicial(
            dados_gerais=serializer.validated_data,
            arquivos=arquivos,
            usuario_logado=request.user,
        )

        return Response(
            ProcessoSerializer(processo).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="distribuir-lote")
    def distribuir_lote(self, request: Request) -> Response:
        """
        POST /api/v1/gestao/processos/distribuir-lote/
        Distribui N processos entre M procuradores via Round-Robin.

        Payload:
            {
                "processos_ids":   [145, 146, 147],
                "procuradores_ids": [2, 5]
            }

        Respostas:
            200 OK           → lista dos Processos atualizados.
            400 Bad Request  → falha de validação ou regra de negócio violada.
            409 Conflict     → modificação concorrente detectada (IntegrityError).
        """
        serializer = DistribuicaoLoteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error_code": "VALIDATION_FAILED",
                    "message": "A requisição contém dados inválidos.",
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            processos = ProcessoService.distribuir_em_lote(
                processos_ids=serializer.validated_data["processos_ids"],
                procuradores_ids=serializer.validated_data["procuradores_ids"],
                usuario_responsavel=request.user,
            )
        except DistribuicaoError as exc:
            return Response(
                {
                    "error_code": "DISTRIBUICAO_ERROR",
                    "message": str(exc),
                    "details": {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            return Response(
                {
                    "error_code": "CONFLICT",
                    "message": (
                        "Um ou mais processos foram modificados simultaneamente. "
                        "Atualize a listagem e tente novamente."
                    ),
                    "details": {},
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            ProcessoSerializer(processos, many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="redistribuir-ferias")
    def redistribuir_ferias(self, request: Request) -> Response:
        """
        POST /api/v1/gestao/processos/redistribuir-ferias/
        Redistribui os processos ativos de um procurador em férias para
        outros procuradores via Round-Robin.

        Payload:
            {
                "procurador_origem_id": 5,
                "procuradores_destino_ids": [2, 8]
            }

        Respostas:
            200 OK          → lista dos Processos redistribuídos.
            400 Bad Request → validação ou nenhum processo ativo encontrado.
        """
        serializer = RedistribuicaoFeriasSerializer(data=request.data)
        if not serializer.is_valid():
            return _erro_validacao(serializer.errors)

        try:
            processos = ProcessoService.redistribuir_ferias(
                procurador_origem_id=serializer.validated_data["procurador_origem_id"],
                procuradores_destino_ids=serializer.validated_data["procuradores_destino_ids"],
                usuario_responsavel=request.user,
            )
        except DistribuicaoError as exc:
            return Response(
                {"error_code": "DISTRIBUICAO_ERROR", "message": str(exc), "details": {}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ProcessoSerializer(processos, many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="tramitar")
    def tramitar(self, request: Request, pk: int = None) -> Response:
        """
        POST /api/v1/gestao/processos/{id}/tramitar/
        Endpoint RPC para transição formal de estado do Processo.
        Garante criação da Movimentação correspondente (Event Sourcing).

        Payload:
            { "status": "CONCLUIDO", "motivo": "..." (opcional) }

        Respostas:
            200 OK          → Processo atualizado.
            400 Bad Request → status inválido.
            404 Not Found   → Processo não encontrado.
        """
        serializer = ProcessoTramitarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            processo = ProcessoService.tramitar_processo(
                processo_id=pk,
                novo_status=serializer.validated_data["status"],
                usuario_responsavel=request.user,
                motivo=serializer.validated_data.get("motivo", ""),
            )
        except Processo.DoesNotExist:
            return Response(
                {"detail": "Processo não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            ProcessoSerializer(processo, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="lembrete")
    def lembrete(self, request: Request, pk: int = None) -> Response:
        """
        POST /api/v1/gestao/processos/{id}/lembrete/
        Registra um lembrete de cobrança na Timeline do Processo.

        Sem payload obrigatório.

        Respostas:
            201 Created → Movimentacao de lembrete criada.
            404 Not Found → Processo não encontrado.
        """
        try:
            movimentacao = ProcessoService.enviar_lembrete(
                processo_id=pk,
                usuario_responsavel=request.user,
            )
        except Processo.DoesNotExist:
            return Response(
                {"error_code": "NOT_FOUND", "message": "Processo não encontrado.", "details": {}},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"id": movimentacao.pk, "tipo_evento": movimentacao.tipo_evento},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"], url_path="movimentacoes")
    def adicionar_movimentacao(self, request: Request, pk=None) -> Response:
        """
        GET  /api/v1/gestao/processos/{id}/movimentacoes/ — lista movimentações do processo
        POST /api/v1/gestao/processos/{id}/movimentacoes/ — adiciona nova movimentação

        Content-Type (POST): multipart/form-data
        Campos (POST):
            tipo_evento  str        — obrigatório; deve ser um TipoEvento válido.
            descricao    str        — despacho/observação (opcional).
            metadata     str (JSON) — array de metadados, um objeto por arquivo.
        Arquivos (POST):
            arquivos     File[]     — zero ou mais arquivos (multipart).

        Respostas:
            200 OK          → lista de movimentações (GET).
            201 Created     → movimentação criada; retorna id e tipo_evento (POST).
            400 Bad Request → tipo_evento inválido (POST).
            404 Not Found   → Processo não encontrado.
        """
        processo = self.get_object()  # levanta 404 automaticamente se inexistente

        if request.method == "GET":
            qs = (
                processo.movimentacoes
                .select_related("usuario_responsavel")
                .prefetch_related("anexos")
                .order_by("-data_criacao")
            )
            return Response(
                MovimentacaoSerializer(qs, many=True).data,
                status=status.HTTP_200_OK,
            )

        tipo_evento = request.data.get("tipo_evento", "")
        descricao   = request.data.get("descricao", "") or ""

        # Deserializa metadata: string JSON → lista de dicts
        raw_meta = request.data.get("metadata", "[]")
        try:
            metadata_list = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
            if not isinstance(metadata_list, list):
                metadata_list = []
        except (json.JSONDecodeError, ValueError, TypeError):
            metadata_list = []

        arquivos = request.FILES.getlist("arquivos")

        try:
            movimentacao = MovimentacaoService.adicionar_movimentacao(
                processo=processo,
                usuario=request.user,
                tipo_evento=tipo_evento,
                descricao=descricao,
                arquivos=arquivos,
                metadata_list=metadata_list,
            )
        except TipoEventoInvalidoError as exc:
            return Response(
                {
                    "error_code": "TIPO_EVENTO_INVALIDO",
                    "message":    str(exc),
                    "details":    {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "id":          movimentacao.pk,
                "tipo_evento": movimentacao.tipo_evento,
                "message":     "Movimentação adicionada com sucesso.",
            },
            status=status.HTTP_201_CREATED,
        )


def _montar_arquivos(request: Request) -> list[dict]:
    """
    Extrai arquivos do campo 'arquivos' e combina com metadata por-arquivo.

    O frontend envia 'metadata' como string JSON contendo um array de objetos,
    um por arquivo, na mesma ordem em que foram anexados no WorkspaceAnexos.

    Suporta o padrão Zip com `eh_nota`: entradas sem arquivo físico (notas
    de texto puras) são incluídas sem arquivo, usando o campo `observacao`.
    """
    arquivos = request.FILES.getlist("arquivos")

    metadata_list: list[dict] = []
    raw_meta = request.data.get("metadata", "[]")
    try:
        parsed = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
        if isinstance(parsed, list):
            metadata_list = parsed
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    if metadata_list:
        # Padrão Zip: itera sobre metadata_list; arquivos consumidos apenas para
        # entradas que não são nota (eh_nota == False ou ausente).
        result = []
        arquivo_idx = 0
        for meta in metadata_list:
            eh_nota = meta.get("eh_nota", False)
            arq = None
            if not eh_nota and arquivo_idx < len(arquivos):
                arq = arquivos[arquivo_idx]
                arquivo_idx += 1
            result.append({
                "arquivo":           arq,
                "tipo_documento_id": meta.get("categoria_documento_id") or None,
                "numero_documento":  meta.get("numero_documento") or None,
                "observacao":        meta.get("observacao") or None,
            })
        return result

    # Fallback: sem metadata, vincula todos os arquivos sem metadados (retrocompat)
    return [
        {
            "arquivo":           arquivo,
            "tipo_documento_id": None,
            "numero_documento":  None,
            "observacao":        None,
        }
        for arquivo in arquivos
    ]


def _erro_validacao(errors: dict) -> Response:
    return Response(
        {
            "error_code": "VALIDATION_FAILED",
            "message": "A requisição contém dados inválidos.",
            "details": errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _erro_negocio(exc: Exception, error_code: str = "DILIGENCIA_ERROR") -> Response:
    return Response(
        {
            "error_code": error_code,
            "message": str(exc),
            "details": {},
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


# ---------------------------------------------------------------------------
# DiligenciaViewSet
# ---------------------------------------------------------------------------


class DiligenciaViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet de ações customizadas para o ciclo de vida de Diligências.
    Expõe listagem (GET /diligencias/) e ações de transição de estado.

    Rotas registradas via DefaultRouter com prefix='diligencias':
        GET  /api/v1/gestao/diligencias/                  → list
        POST /api/v1/gestao/diligencias/lote/             → criar_em_lote
        POST /api/v1/gestao/diligencias/{id}/rejeitar/    → rejeitar
        POST /api/v1/gestao/diligencias/{id}/aprovar/     → aprovar
        POST /api/v1/gestao/diligencias/{id}/concluir/    → concluir
    """

    permission_classes = [IsAuthenticated]
    filterset_class    = DiligenciaFilter
    # Parsers explícitos: garante que o DRF aceita tanto JSON (ações sem arquivo)
    # quanto multipart/form-data (ações com upload de arquivos).
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.action == "list":
            return DiligenciaListSerializer
        return DiligenciaListSerializer  # fallback seguro; actions POST usam serializers próprios

    def get_queryset(self):
        """
        RLS para Diligências:
          - Superuser ou grupos de visibilidade total → todas as diligências.
          - Procurador comum → apenas diligências do seu processo atribuído.
        """
        base_qs = SolicitacaoDocumento.objects.select_related(
            "processo",
            "processo__procurador_atribuido",
        ).order_by("-id")

        user = self.request.user
        if user.is_superuser:
            return base_qs

        grupos_usuario = set(user.groups.values_list("name", flat=True))
        if grupos_usuario & _GRUPOS_VISIBILIDADE_TOTAL:
            return base_qs

        return base_qs.filter(processo__procurador_atribuido=user)

    @action(detail=False, methods=["post"], url_path="lote")
    def criar_em_lote(self, request: Request) -> Response:
        """
        POST /api/v1/gestao/diligencias/lote/
        Abre uma nova Diligência para um Processo.

        Content-Type: multipart/form-data
        Campos:    processo_id, descricao_necessidade
        Arquivos:  campo 'arquivos' (0 ou mais PDFs/docs)

        Respostas:
            201 Created     → SolicitacaoDocumento criada.
            400 Bad Request → validação ou status inválido do Processo.
        """
        serializer = DiligenciaLoteCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _erro_validacao(serializer.errors)

        try:
            diligencia = DiligenciaService.criar_diligencia_em_lote(
                processo_id=serializer.validated_data["processo_id"],
                usuario_logado=request.user,
                descricao_necessidade=serializer.validated_data["descricao_necessidade"],
                arquivos_em_memoria=_montar_arquivos(request),
            )
        except (StatusInvalidoError, DiligenciaError) as exc:
            return _erro_negocio(exc)

        return Response(
            {"id": diligencia.pk, "status": diligencia.status},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="rejeitar")
    def rejeitar(self, request: Request, pk: int = None) -> Response:
        """
        POST /api/v1/gestao/diligencias/{id}/rejeitar/
        Rejeita uma Diligência pendente, devolvendo o Processo para EM_ANALISE.

        Content-Type: application/json
        Payload: { "motivo_rejeicao": "..." }

        Respostas:
            200 OK          → Diligência rejeitada.
            400 Bad Request → validação ou transição de status inválida.
        """
        serializer = DiligenciaRejeitarSerializer(data=request.data)
        if not serializer.is_valid():
            return _erro_validacao(serializer.errors)

        try:
            diligencia = DiligenciaService.rejeitar_diligencia(
                diligencia_id=pk,
                usuario_logado=request.user,
                motivo_rejeicao=serializer.validated_data["motivo_rejeicao"],
            )
        except (StatusInvalidoError, DiligenciaError) as exc:
            return _erro_negocio(exc)

        return Response(
            {"id": diligencia.pk, "status": diligencia.status},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="aprovar")
    def aprovar(self, request: Request, pk: int = None) -> Response:
        """
        POST /api/v1/gestao/diligencias/{id}/aprovar/
        Aprova os anexos e enfileira o envio de e-mail externo via Cloud Tasks.

        Content-Type: application/json
        Payload:
            {
                "emails_destino": ["remetente@gov.br", "interessado@example.com"],
                "anexos_ids_selecionados": [10, 11]
            }

        Respostas:
            200 OK          → Diligência enviada; Cloud Tasks enfileirado.
            400 Bad Request → validação ou transição de status inválida.
        """
        serializer = DiligenciaAprovarSerializer(data=request.data)
        if not serializer.is_valid():
            return _erro_validacao(serializer.errors)

        try:
            diligencia = DiligenciaService.aprovar_e_enviar_email(
                diligencia_id=pk,
                usuario_logado=request.user,
                emails_destino=serializer.validated_data["emails_destino"],
                anexos_ids_selecionados=serializer.validated_data["anexos_ids_selecionados"],
            )
        except (StatusInvalidoError, DiligenciaError) as exc:
            return _erro_negocio(exc)

        return Response(
            {"id": diligencia.pk, "status": diligencia.status},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="concluir")
    def concluir(self, request: Request, pk: int = None) -> Response:
        """
        POST /api/v1/gestao/diligencias/{id}/concluir/
        Conclui manualmente uma Diligência com os documentos de resposta físicos.

        Content-Type: multipart/form-data
        Campos:   observacao_resolucao (opcional)
        Arquivos: campo 'arquivos' (0 ou mais ofícios de resposta)

        Respostas:
            200 OK          → Diligência concluída; Processo atualizado.
            400 Bad Request → validação ou transição de status inválida.
        """
        serializer = DiligenciaConcluirSerializer(data=request.data)
        if not serializer.is_valid():
            return _erro_validacao(serializer.errors)

        try:
            diligencia = DiligenciaService.concluir_diligencia_manual(
                diligencia_id=pk,
                usuario_logado=request.user,
                arquivos_em_memoria=_montar_arquivos(request),
                observacao_resolucao=serializer.validated_data.get("observacao_resolucao"),
            )
        except (StatusInvalidoError, DiligenciaError) as exc:
            return _erro_negocio(exc)

        return Response(
            {"id": diligencia.pk, "status": diligencia.status},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="marcar-solicitada")
    def marcar_solicitada(self, request, pk=None):
        serializer = DiligenciaMarcarSolicitadaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            diligencia = DiligenciaService.marcar_como_solicitada_manualmente(
                diligencia_id=pk,
                usuario_logado=request.user,
                observacao_contato=serializer.validated_data["observacao_contato"],
            )
        except (StatusInvalidoError, DiligenciaError) as exc:
            return _erro_negocio(exc)

        return Response(
            {"id": diligencia.pk, "status": diligencia.status},
            status=status.HTTP_200_OK,
        )


class CategoriaDocumentoViewSet(viewsets.ViewSet):
    """
    ViewSet auxiliar para buscar metadados de categorias (Tipos de Documento)
    relacionados aos anexos da gestão.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["get"], url_path="numeracoes")
    def numeracoes(self, request, pk=None):
        """
        GET /api/v1/gestao/categorias/{pk}/numeracoes/
        Retorna as últimas 4 numerações cadastradas no sistema para uma categoria específica.
        """
        anexos = (
            Anexo.objects.filter(tipo_documento_id=pk)
            .exclude(numero_documento__isnull=True)
            .exclude(numero_documento__exact="")
            .select_related("movimentacao")
            .order_by("-id")[:4]
        )

        resultados = [
            {
                "numeracao": anexo.numero_documento,
                "data_criacao": anexo.movimentacao.data_criacao.isoformat() if anexo.movimentacao else None,
            }
            for anexo in anexos
        ]

        return Response(resultados, status=status.HTTP_200_OK)


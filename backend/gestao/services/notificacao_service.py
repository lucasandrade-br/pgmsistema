"""
Camada de Serviço — Domínio: Notificações / Jobs Assíncronos

Responsável por enfileirar tarefas no Google Cloud Tasks para processamento
em background (envio de e-mails, geração de links com TTL, etc.).

Arquitetura (conforme knowledge/infraestrutura/jobs_assincronos.md):
  1. Este serviço monta o payload e cria uma tarefa na fila do Cloud Tasks.
  2. A API retorna imediatamente ao Vue.js (sem bloquear no SMTP).
  3. O Cloud Tasks faz um HTTP POST para /api/v1/internal/tasks/enviar_email/
     na nossa própria API Django, que executa o envio real.
  4. Em caso de falha no SMTP, o Cloud Tasks reexecuta automaticamente
     com backoff exponencial.

Ambiente de desenvolvimento:
  A função `enfileirar_tarefa_email` realiza apenas um `print` estruturado,
  simulando o enfileiramento. A integração real com a SDK do Google
  (`google-cloud-tasks`) será implementada na Sprint de Deploy/Cloud.

Segurança dos endpoints internos (futuro):
  Os endpoints /api/v1/internal/tasks/ serão protegidos via OIDC —
  apenas a Service Account do Cloud Tasks terá permissão IAM para invocá-los.
  Não usarão JWT de usuário.
"""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from gestao.models import Anexo

logger = logging.getLogger(__name__)


def executar_envio_email_diligencia(payload: dict) -> None:
    """
    Worker que processa o payload do Cloud Tasks, renderiza o HTML,
    anexa os arquivos físicos e dispara via SMTP.
    """
    emails_destino        = payload.get("emails_destino", [])
    numero_protocolo      = payload.get("numero_protocolo", "N/A")
    descricao_necessidade = payload.get("descricao_necessidade", "")
    anexos_ids            = payload.get("anexos_ids", [])

    if not emails_destino:
        logger.error("[Email Worker] Nenhum e-mail de destino informado no payload.")
        return

    # Renderiza o template HTML e gera o fallback em texto plano
    context = {
        "numero_protocolo":      numero_protocolo,
        "descricao_necessidade": descricao_necessidade,
    }
    html_content = render_to_string("emails/diligencia_email.html", context)
    text_content = strip_tags(html_content)

    assunto  = f"Notificação de Diligência - Processo {numero_protocolo}"
    remetente = settings.DEFAULT_FROM_EMAIL

    msg = EmailMultiAlternatives(
        subject=assunto,
        body=text_content,
        from_email=remetente,
        to=emails_destino,
    )
    msg.attach_alternative(html_content, "text/html")

    # Anexa os arquivos físicos selecionados
    if anexos_ids:
        for anexo in Anexo.objects.filter(id__in=anexos_ids, ativo=True):
            if anexo.arquivo:
                nome_arquivo = anexo.arquivo.name.split("/")[-1]
                msg.attach(nome_arquivo, anexo.arquivo.read(), "application/pdf")

    msg.send(fail_silently=False)
    logger.info("[Email Worker] E-mail enviado com sucesso para %s.", emails_destino)


def enfileirar_tarefa_email(payload: dict) -> None:
    """
    Enfileira uma tarefa de envio de e-mail no Google Cloud Tasks.

    Em produção, este método utilizará a SDK `google-cloud-tasks` para criar
    uma HttpRequest Task apontando para o endpoint interno da API:
        POST /api/v1/internal/tasks/enviar_email/

    Em desenvolvimento (implementação atual), simula o enfileiramento
    imprimindo o payload serializado e registrando no logger.

    Parâmetros:
        payload: Dicionário com os dados necessários para o processamento
                 assíncrono. Estrutura esperada:
                 {
                     "tipo_tarefa":         str   — identificador do tipo de job,
                     "diligencia_id":       int,
                     "processo_id":         int,
                     "numero_protocolo":    str,
                     "email_destino":       str,
                     "anexos_ids":          list[int],
                     "descricao_necessidade": str,
                     "aprovado_por_id":     int,
                     "aprovado_por_nome":   str,
                     "data_envio":          str  — ISO 8601,
                 }

    Não levanta exceções — falhas de enfileiramento são apenas logadas,
    pois não devem reverter a transação do banco de dados que já foi commitada.

    TODO (Sprint de Deploy):
        - Substituir o bloco de simulação pelo cliente real:
            from google.cloud import tasks_v2
            client = tasks_v2.CloudTasksClient()
            ...
        - Adicionar CLOUD_TASKS_QUEUE_NAME e CLOUD_TASKS_SERVICE_URL ao .env.
        - Configurar autenticação OIDC na task para o endpoint interno.
    """
    tipo_tarefa = payload.get("tipo_tarefa", "DESCONHECIDA")

    # -----------------------------------------------------------------------
    # SIMULAÇÃO — remover na Sprint de Deploy e substituir pela SDK real
    # -----------------------------------------------------------------------
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    print(
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║         [DEV] SIMULAÇÃO — Google Cloud Tasks                 ║\n"
        "╠══════════════════════════════════════════════════════════════╣\n"
        f"║  Fila:    pgm-email-queue                                    ║\n"
        f"║  Tarefa:  {tipo_tarefa:<50} ║\n"
        f"║  Destino: POST /api/v1/internal/tasks/enviar_email/          ║\n"
        "╠══════════════════════════════════════════════════════════════╣\n"
        f"{payload_json}\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
    )

    logger.info(
        "[Cloud Tasks - DEV] Tarefa simulada enfileirada. "
        "tipo=%s diligencia_id=%s processo=%s destino=%s",
        tipo_tarefa,
        payload.get("diligencia_id"),
        payload.get("numero_protocolo"),
        payload.get("emails_destino"),
    )
    # -----------------------------------------------------------------------
    # FIM DA SIMULAÇÃO
    # -----------------------------------------------------------------------

    # Em ambiente de desenvolvimento, executa o envio SMTP de forma síncrona
    # para validar o template e as credenciais sem precisar do emulador GCP.
    if settings.DEBUG:
        print(">> [DEV] Iniciando disparo síncrono via SMTP configurado...")
        executar_envio_email_diligencia(payload)

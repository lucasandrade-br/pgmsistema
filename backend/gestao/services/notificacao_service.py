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

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from gestao.models import Anexo

logger = logging.getLogger(__name__)


def _enviar_diligencia(payload: dict) -> None:
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


def _enviar_redefinicao_senha(payload: dict) -> None:
    """
    Renderiza e despacha o e-mail de redefinição de senha via SMTP.
    """
    email_destino    = payload.get("email_destino", [])
    usuario_nome     = payload.get("usuario_nome", "")
    reset_link       = payload.get("reset_link", "")
    minutos_validade = payload.get("minutos_validade", 15)

    context = {
        "usuario_nome":     usuario_nome,
        "reset_link":       reset_link,
        "minutos_validade": minutos_validade,
        "titulo_cabecalho": "Redefinição de Senha",
    }
    html_content = render_to_string("emails/redefinicao_senha.html", context)
    text_content = strip_tags(html_content)

    msg = EmailMultiAlternatives(
        subject="Redefinição de Senha - PGM",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=email_destino,
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)
    logger.info("[Email Worker] E-mail de redefinição enviado com sucesso para %s.", email_destino)


def _enviar_compartilhamento_autos(payload: dict) -> None:
    """
    Renderiza e despacha o e-mail com link de acesso aos autos digitais.
    """
    email_destino    = payload.get("email_destino", [])
    numero_protocolo = payload.get("numero_protocolo", "")
    link_acesso      = payload.get("link_acesso", "")

    context = {
        "numero_protocolo": numero_protocolo,
        "link_acesso":      link_acesso,
        "titulo_cabecalho": "Acesso aos Autos Digitais",
    }
    html_content = render_to_string("emails/compartilhamento_autos.html", context)
    text_content = strip_tags(html_content)

    msg = EmailMultiAlternatives(
        subject=f"Autos Digitais - Processo {numero_protocolo}",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=email_destino,
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)
    logger.info("[Email Worker] E-mail de compartilhamento de autos enviado para %s.", email_destino)


def _enviar_compartilhamento_autos_lote(payload: dict) -> None:
    """
    Renderiza e despacha um único e-mail consolidado com os links de todos os
    autos digitais gerados em lote.
    """
    email_destino = payload.get("email_destino", [])
    processos     = payload.get("processos", [])   # lista de {numero, link}

    context = {
        "processos":        processos,
        "quantidade":       len(processos),
        "titulo_cabecalho": "Autos Digitais em Lote",
    }
    html_content = render_to_string("emails/compartilhamento_autos_lote.html", context)
    text_content = strip_tags(html_content)

    msg = EmailMultiAlternatives(
        subject=f"Autos Digitais — {len(processos)} processo(s)",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=email_destino,
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)
    logger.info(
        "[Email Worker] E-mail de autos em lote enviado para %s (%d processo(s)).",
        email_destino,
        len(processos),
    )


def _enviar_atribuicao_lote(payload: dict) -> None:
    """
    Renderiza e despacha um único e-mail por procurador com a lista dos
    processos recebidos na distribuição em lote.
    """
    email_destino   = payload.get("email_destino", [])
    procurador_nome = payload.get("procurador_nome", "")
    processos       = payload.get("processos", [])
    link_sistema    = payload.get("link_sistema", "")

    context = {
        "procurador_nome":   procurador_nome,
        "processos":         processos,
        "quantidade":        len(processos),
        "link_sistema":      link_sistema,
        "titulo_cabecalho": "Nova Atribuição de Processos",
    }
    html_content = render_to_string("emails/atribuicao_lote.html", context)
    text_content = strip_tags(html_content)

    msg = EmailMultiAlternatives(
        subject=f"Você recebeu {len(processos)} novo(s) processo(s) para análise",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=email_destino,
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)
    logger.info(
        "[Email Worker] E-mail de atribuição em lote enviado para %s (%d processo(s)).",
        email_destino,
        len(processos),
    )


def _enviar_cobranca_atrasos(payload: dict) -> None:
    """
    Renderiza e despacha o e-mail de cobrança de prazos vencidos.
    Acionado pelo Job de Cobrança (Cloud Scheduler 3x/semana).
    """
    email_destino   = payload.get("email_destino", [])
    procurador_nome = payload.get("procurador_nome", "")
    processos       = payload.get("processos", [])
    link_sistema    = payload.get("link_sistema", "")

    context = {
        "procurador_nome":   procurador_nome,
        "processos":         processos,
        "quantidade":        len(processos),
        "link_sistema":      link_sistema,
        "titulo_cabecalho": "Aviso de Prazos Vencidos",
    }
    html_content = render_to_string("emails/cobranca_atrasos.html", context)
    text_content = strip_tags(html_content)

    msg = EmailMultiAlternatives(
        subject=f"Atenção: Você possui {len(processos)} processo(s) em atraso",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=email_destino,
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)
    logger.info(
        "[Email Worker] E-mail de cobrança de atrasos enviado para %s (%d processo(s)).",
        email_destino,
        len(processos),
    )


def _enviar_cobranca_chefia(payload: dict) -> None:
    """
    Renderiza e despacha o relatório gerencial de atrasos para a Chefia.
    Um único e-mail agrega todos os procuradores em atraso.
    """
    emails_destino = payload.get("emails_destino", [])
    agrupamento    = payload.get("agrupamento", {})
    link_sistema   = payload.get("link_sistema", "")

    context = {
        "agrupamento":      agrupamento,
        "link_sistema":     link_sistema,
        "titulo_cabecalho": "Relatório Gerencial de Atrasos",
    }
    html_content = render_to_string("emails/cobranca_chefia.html", context)
    text_content = strip_tags(html_content)

    msg = EmailMultiAlternatives(
        subject="Relatório Gerencial: Processos em Atraso",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=emails_destino,
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)
    logger.info(
        "[Email Worker] Relatório gerencial de atrasos enviado para %d destinatário(s) da Chefia.",
        len(emails_destino),
    )


def _enviar_conclusao_diligencia(payload: dict) -> None:
    """
    Renderiza e despacha o e-mail de conclusão manual de diligência para o
    procurador atribuído ao processo.
    """
    email_destino         = payload.get("email_destino", [])
    procurador_nome       = payload.get("procurador_nome", "")
    numero_protocolo      = payload.get("numero_protocolo", "")
    diligencia_id         = payload.get("diligencia_id", "")
    descricao_necessidade = payload.get("descricao_necessidade", "")
    observacao_resolucao  = payload.get("observacao_resolucao", "")
    nova_data_limite      = payload.get("nova_data_limite")
    link_sistema          = payload.get("link_sistema", "")

    context = {
        "procurador_nome":       procurador_nome,
        "numero_protocolo":      numero_protocolo,
        "diligencia_id":         diligencia_id,
        "descricao_necessidade": descricao_necessidade,
        "observacao_resolucao":  observacao_resolucao,
        "nova_data_limite":      nova_data_limite,
        "link_sistema":          link_sistema,
        "titulo_cabecalho":      "Diligência Concluída",
    }
    html_content = render_to_string("emails/diligencia_concluida_email.html", context)
    text_content = strip_tags(html_content)

    msg = EmailMultiAlternatives(
        subject=f"Diligência #{diligencia_id} concluída - Processo {numero_protocolo}",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=email_destino,
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)
    logger.info(
        "[Email Worker] E-mail de conclusão de diligência enviado para %s.",
        email_destino,
    )


def worker_processar_email(payload: dict) -> None:
    """
    Dispatcher principal do worker de e-mail.

    Roteia a execução para o handler correto de acordo com o `tipo_tarefa`
    presente no payload. Novos tipos de e-mail devem ser registrados aqui.

    Tipos suportados:
        - ``ENVIAR_EMAIL_DILIGENCIA``: notificação de pendência de diligência.
    """
    tipo_tarefa = payload.get("tipo_tarefa", "")

    _handlers = {
        "ENVIAR_EMAIL_DILIGENCIA": _enviar_diligencia,
        "REDEFINIR_SENHA":         _enviar_redefinicao_senha,
        "COMPARTILHAR_AUTOS":       _enviar_compartilhamento_autos,
        "COMPARTILHAR_AUTOS_LOTE":  _enviar_compartilhamento_autos_lote,
        "ATRIBUICAO_LOTE":          _enviar_atribuicao_lote,
        "COBRANCA_ATRASOS":        _enviar_cobranca_atrasos,
        "COBRANCA_CHEFIA":         _enviar_cobranca_chefia,
        "CONCLUSAO_DILIGENCIA":    _enviar_conclusao_diligencia,
    }

    handler = _handlers.get(tipo_tarefa)
    if handler:
        handler(payload)
    else:
        logger.warning(
            "[Email Worker] tipo_tarefa desconhecido ou não suportado: '%s'. Payload ignorado.",
            tipo_tarefa,
        )


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
    # Executa o envio SMTP de forma síncrona.
    # TODO (Sprint de Deploy): substituir pelo cliente real do Cloud Tasks para
    # processamento assíncrono em produção (ver docstring acima).
    worker_processar_email(payload)

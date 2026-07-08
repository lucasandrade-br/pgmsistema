from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.models import CustomUser, PasswordResetToken
from gestao.services.notificacao_service import enfileirar_tarefa_email

# TTL do token de redefinição de senha (em minutos).
# Mantido como constante nomeada para facilitar auditoria e ajuste futuro.
_TOKEN_TTL_MINUTES = 15


class TokenInvalidoError(Exception):
    """
    Levantada quando o token de redefinição é inexistente, já utilizado
    ou expirado (mais antigo que _TOKEN_TTL_MINUTES minutos).
    A mensagem propositalmente genérica evita vazar informações ao cliente.
    """

    default_message = "Token inválido ou expirado."

    def __init__(self, message: str = default_message):
        super().__init__(message)


def request_password_reset(email: str) -> None:
    """
    Inicia o fluxo de redefinição de senha para o e-mail informado.

    Proteção contra enumeração de e-mails (OWASP A01 / CWE-204):
    Se o e-mail NÃO existir na base, a função retorna None silenciosamente —
    sem levantar exceção, sem alterar o código HTTP da view. O atacante não
    consegue distinguir um e-mail existente de um inexistente pela resposta.

    Fluxo quando o e-mail EXISTE:
    1. Invalida todos os tokens pendentes anteriores do usuário (is_used=True).
    2. Cria um novo PasswordResetToken.
    3. Simula o envio de e-mail via print (substituir por Cloud Tasks no deploy).

    Parâmetros:
        email: E-mail buscado na base. Case-insensitive via __iexact.
    """
    try:
        user = CustomUser.objects.get(email__iexact=email)
    except CustomUser.DoesNotExist:
        # Retorno silencioso — não levanta erro (anti-enumeração)
        return

    # Invalida tokens anteriores pendentes para este usuário
    PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)

    # Cria o novo token (UUID gerado automaticamente pelo default do campo)
    reset_token = PasswordResetToken.objects.create(user=user)

    reset_link = f"http://localhost:5173/redefinir-senha?token={reset_token.token}"
    payload = {
        "tipo_tarefa":      "REDEFINIR_SENHA",
        "email_destino":    [user.email],
        "usuario_nome":     user.first_name or user.username,
        "reset_link":       reset_link,
        "minutos_validade": _TOKEN_TTL_MINUTES,
    }
    enfileirar_tarefa_email(payload)


@transaction.atomic
def confirm_password_reset(token_str: str, new_password: str) -> None:
    """
    Confirma a redefinição de senha validando o token e atualizando a senha.

    Envolvida em `transaction.atomic()`: a mudança de senha e a invalidação
    do token ocorrem na mesma transação — se qualquer operação falhar, nenhuma
    alteração persiste no banco.

    Validações (ordem de falha segura):
    1. Token não encontrado → TokenInvalidoError
    2. Token já utilizado   → TokenInvalidoError
    3. Token expirado (> 15 min) → TokenInvalidoError

    Parâmetros:
        token_str:    UUID do token como string (vindo da requisição HTTP).
        new_password: Nova senha em texto puro (Django faz o hash).

    Levanta:
        TokenInvalidoError — em qualquer cenário inválido.
    """
    try:
        reset_token = (
            PasswordResetToken.objects
            .select_related("user")
            .select_for_update()  # Bloqueia a linha durante a transação
            .get(token=token_str)
        )
    except (PasswordResetToken.DoesNotExist, ValueError):
        # ValueError cobre UUIDs mal-formados passados como token_str
        raise TokenInvalidoError()

    if reset_token.is_used:
        raise TokenInvalidoError()

    # Verifica o TTL: created_at deve ser mais recente que N minutos atrás
    expiration_limit = timezone.now() - timedelta(minutes=_TOKEN_TTL_MINUTES)
    if reset_token.created_at < expiration_limit:
        raise TokenInvalidoError()

    # Token válido — altera a senha e invalida o token atomicamente
    user = reset_token.user
    user.set_password(new_password)
    user.save(update_fields=["password"])

    reset_token.is_used = True
    reset_token.save(update_fields=["is_used"])

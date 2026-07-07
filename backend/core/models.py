import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Modelo de usuário customizado do sistema PGM.
    Estende o AbstractUser do Django adicionando campos
    específicos de negócio diretamente na tabela de usuários,
    eliminando a necessidade de uma tabela Profile separada.
    """

    # Hash do PIN de autorização (argon2). Usado para validar
    # transições críticas de workflow (finalizar, arquivar, rejeitar).
    # Armazenado como None até o usuário definir seu PIN.
    pin_autorizacao = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="PIN de autorização (hash)",
    )

    telefone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Telefone",
    )

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def __str__(self):
        return self.get_full_name() or self.username


class PasswordResetToken(models.Model):
    """
    Token de uso único para redefinição de senha.

    Regras de segurança:
    - TTL de 15 minutos (validado na camada de serviço via `created_at`).
    - `is_used` impede reutilização mesmo dentro do TTL.
    - `token` é um UUID v4 gerado pelo banco; nunca exposto no admin list.
    - Tokens anteriores do mesmo usuário são invalidados ao gerar um novo
      (função `request_password_reset`), impedindo acúmulo de tokens ativos.
    """

    user = models.ForeignKey(
        "core.CustomUser",
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
        verbose_name="Usuário",
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
        verbose_name="Token",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    is_used = models.BooleanField(default=False, verbose_name="Utilizado")

    class Meta:
        verbose_name = "Token de Redefinição de Senha"
        verbose_name_plural = "Tokens de Redefinição de Senha"
        ordering = ["-created_at"]

    def __str__(self):
        status = "usado" if self.is_used else "ativo"
        return f"Token [{status}] – {self.user.username}"

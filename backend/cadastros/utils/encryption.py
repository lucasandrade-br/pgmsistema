"""
Utilitários de criptografia para campos sensíveis (LGPD).

Estratégia:
  - Criptografia: Fernet (AES-128-CBC + HMAC-SHA256) — protege valor em repouso no DB.
  - Hash de busca: HMAC-SHA256 determinístico — permite busca exata sem expor o valor.

Campos afetados no modelo Remetente: doc, telefone.
"""

import hmac as _hmac
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY não configurado. "
            "Adicione a variável ao arquivo .env."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str) -> str:
    """Criptografa `value` com Fernet. Retorna o token base64 como str."""
    if not value:
        return value
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """
    Descriptografa um token Fernet.
    Se o valor não for um token válido (ex.: dado legado em plaintext),
    retorna o próprio valor sem lançar exceção.
    """
    if not value:
        return value
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        return value  # graceful fallback para valores legado


def make_hash(value: str) -> str:
    """
    HMAC-SHA256 determinístico para busca exata.
    Normaliza o valor (strip + lower) antes de hashear para consistência.
    """
    if not value:
        return ""
    key = settings.SEARCH_HASH_KEY
    if not key:
        raise RuntimeError(
            "SEARCH_HASH_KEY não configurado. "
            "Adicione a variável ao arquivo .env."
        )
    normalizado = value.strip().lower()
    return _hmac.new(
        key.encode() if isinstance(key, str) else key,
        normalizado.encode(),
        hashlib.sha256,
    ).hexdigest()

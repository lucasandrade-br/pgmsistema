from django.db import models


class Remetente(models.Model):
    class TipoPessoa(models.TextChoices):
        FISICA = "FISICA", "Física"
        JURIDICA = "JURIDICA", "Jurídica"
        ORGAO_PUBLICO = "ORGAO_PUBLICO", "Órgão Público"

    nome_razao_social = models.CharField(
        max_length=255,
        verbose_name="Nome / Razão Social",
    )
    doc = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="CPF / CNPJ (criptografado)",
    )
    doc_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Hash do documento (busca)",
    )
    email = models.EmailField(
        null=True,
        blank=True,
        verbose_name="E-mail",
    )
    telefone = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Telefone (criptografado)",
    )
    telefone_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Hash do telefone (busca)",
    )
    tipo_pessoa = models.CharField(
        max_length=20,
        choices=TipoPessoa.choices,
        verbose_name="Tipo de Pessoa",
    )

    class Meta:
        verbose_name = "Remetente"
        verbose_name_plural = "Remetentes"
        ordering = ["nome_razao_social"]

    def __str__(self):
        return self.nome_razao_social


class TipoDocumento(models.Model):
    descricao = models.CharField(
        max_length=255,
        verbose_name="Descrição",
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
    )

    class Meta:
        verbose_name = "Tipo de Documento"
        verbose_name_plural = "Tipos de Documento"
        ordering = ["descricao"]

    def __str__(self):
        return self.descricao


class NivelPrioridade(models.Model):
    descricao = models.CharField(
        max_length=100,
        verbose_name="Descrição",
    )
    prazo_dias = models.IntegerField(
        verbose_name="Prazo (dias)",
    )

    class Meta:
        verbose_name = "Nível de Prioridade"
        verbose_name_plural = "Níveis de Prioridade"
        ordering = ["prazo_dias"]

    def __str__(self):
        return f"{self.descricao} ({self.prazo_dias} dias)"

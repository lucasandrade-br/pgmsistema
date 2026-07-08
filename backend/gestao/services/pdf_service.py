"""
Motor de Autos Digitais — GeradorAutosService.

Responsabilidade:
  1. Gerar uma capa PDF com os metadados do Processo (reportlab).
  2. Converter anexos de imagem (JPG/PNG) para PDF em memória (Pillow).
  3. Fundir todos os PDFs numa única stream em memória (pypdf).
  4. Persistir o resultado no Cloud Storage via ContentFile.
  5. Criar e retornar a instância de LinkCompartilhamento.

Nenhuma operação em disco: tudo via io.BytesIO para compatibilidade com
qualquer backend de storage (local, GCS, S3, Azure Blob, etc.).
"""

import io

from django.core.files.base import ContentFile
from django.utils import timezone

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors


class GeradorAutosService:

    # ── Geração da Capa ───────────────────────────────────────────────────────

    @staticmethod
    def _gerar_capa_pdf(processo) -> io.BytesIO:
        import os
        from django.conf import settings
        from reportlab.platypus import Image
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=2.5 * cm,
            leftMargin=3 * cm,
            rightMargin=3 * cm,
        )
        elements = []

        # ── 1. Estilos Institucionais (Times-Roman) ───────────────────────────
        estilo_orgao = ParagraphStyle(
            "Orgao",
            fontName="Times-Bold",
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=0.2 * cm,
        )
        estilo_suborgao = ParagraphStyle(
            "SubOrgao",
            fontName="Times-Roman",
            fontSize=12,
            alignment=TA_CENTER,
            spaceAfter=1.5 * cm,
        )
        estilo_titulo = ParagraphStyle(
            "TituloFormal",
            fontName="Times-Bold",
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=1.5 * cm,
        )

        # ── 2. Brasão do Município ────────────────────────────────────────────
        # Tenta buscar o brasão na pasta static do projeto.
        # Caso o arquivo não exista ainda, ignora graciosamente para não quebrar a geração.
        caminho_brasao = os.path.join(settings.BASE_DIR, 'static', 'img', 'brasao.png')
        if os.path.exists(caminho_brasao):
            img = Image(caminho_brasao, width=3 * cm, height=3 * cm)
            elements.append(img)
            elements.append(Spacer(1, 0.5 * cm))

        # ── 3. Cabeçalho Institucional ────────────────────────────────────────
        elements.append(Paragraph("PROCURADORIA GERAL DA VITÓRIA DE SANTO ANTÃO", estilo_orgao))
        elements.append(Paragraph("ESTADO DE PERNAMBUCO", estilo_suborgao))

        # ── 4. Título da Capa ─────────────────────────────────────────────────
        elements.append(Paragraph("AUTOS DIGITAIS DO PROCESSO", estilo_titulo))

        # ── 5. Tabela de Metadados (Estilo Clean / Jurídico) ──────────────────
        dados = [
            ["Nº Protocolo:",   processo.numero_protocolo],
            ["Nº Origem:",      processo.numero_origem or "—"],
            ["Nº SEI:",         processo.numero_sei or "—"],
            ["Remetente:",      str(processo.remetente) if processo.remetente else "—"],
            ["Tipo:",           str(processo.tipo_processo) if processo.tipo_processo else "—"],
            ["Data de Emissão:", timezone.now().strftime("%d/%m/%Y às %H:%M")],
        ]

        estilo_tabela = TableStyle([
            ("FONTNAME",      (0, 0), (0, -1), "Times-Bold"),
            ("FONTNAME",      (1, 0), (1, -1), "Times-Roman"),
            ("FONTSIZE",      (0, 0), (-1, -1), 12),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ])

        tabela = Table(dados, colWidths=[4 * cm, 12 * cm], style=estilo_tabela)
        elements.append(tabela)

        doc.build(elements)
        buffer.seek(0)
        return buffer

    # ── Conversão de Imagem → PDF ─────────────────────────────────────────────

    @staticmethod
    def _converter_imagem_para_pdf(conteudo_bytes: bytes) -> io.BytesIO:
        """
        Converte uma imagem (JPEG/PNG) em bytes para um PDF de página única.
        Retorna um BytesIO posicionado no início.
        """
        imagem = Image.open(io.BytesIO(conteudo_bytes)).convert("RGB")
        buffer = io.BytesIO()
        imagem.save(buffer, format="PDF")
        buffer.seek(0)
        return buffer

    # ── Motor de Fusão e Persistência ─────────────────────────────────────────

    @classmethod
    def gerar_e_salvar_autos(cls, processo) -> "LinkCompartilhamento":
        """
        Gera o PDF integral do processo (capa + anexos) e persiste no storage.

        Fluxo:
          1. Cria PdfWriter e adiciona a capa gerada pelo reportlab.
          2. Itera sobre os Anexos ativos do processo ordenados por id.
          3. Para cada anexo:
             - Lê o arquivo em memória (sem tocar no disco).
             - Se for imagem → converte para PDF via Pillow.
             - Se for PDF → usa direto.
             - Adiciona as páginas ao PdfWriter (ignora PDFs corrompidos).
          4. Serializa o PdfWriter em BytesIO e salva via ContentFile,
             compatível com qualquer backend de Cloud Storage.
          5. Retorna a instância criada de LinkCompartilhamento.
        """
        from gestao.models import Anexo, LinkCompartilhamento  # importação local para evitar ciclo

        writer = PdfWriter()

        # 1. Capa
        capa_buffer = cls._gerar_capa_pdf(processo)
        writer.append(PdfReader(capa_buffer))

        # 2. Anexos ativos, na ordem de inserção
        anexos = (
            Anexo.objects.filter(processo=processo, ativo=True)
            .exclude(arquivo="")
            .exclude(arquivo__isnull=True)
            .order_by("id")
        )

        for anexo in anexos:
            try:
                conteudo  = anexo.arquivo.read()
                extensao  = anexo.arquivo.name.rsplit(".", 1)[-1].lower()

                if extensao in ("jpg", "jpeg", "png"):
                    pdf_buffer = cls._converter_imagem_para_pdf(conteudo)
                else:
                    pdf_buffer = io.BytesIO(conteudo)

                writer.append(PdfReader(pdf_buffer))
            except Exception:
                # PDF/imagem corrompido — continua sem interromper a geração
                continue

        # 3. Serializar em memória
        saida = io.BytesIO()
        writer.write(saida)
        saida.seek(0)

        # 4. Criar link e persistir via ContentFile (Cloud Storage safe)
        nome_arquivo = f"autos_{processo.numero_protocolo}.pdf"
        link = LinkCompartilhamento(processo=processo)
        link.arquivo_gerado.save(
            nome_arquivo,
            ContentFile(saida.read()),
            save=True,
        )

        return link

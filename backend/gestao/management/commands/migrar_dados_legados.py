import hmac
import hashlib
from cryptography.fernet import Fernet

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction, connections
from django.utils import timezone
from django.contrib.auth import get_user_model

# Importe os seus models exatos aqui. Ajuste os caminhos conforme sua estrutura.
from cadastros.models import NivelPrioridade, TipoDocumento, Remetente
from gestao.models import Anexo, Processo, Movimentacao, SolicitacaoDocumento

User = get_user_model()

class Command(BaseCommand):
    help = 'Executa o ETL (Extract, Transform, Load) do sistema legado para a nova arquitetura.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Iniciando o túnel no tempo... Lendo banco legado."))

        usuario_sistema, _ = User.objects.get_or_create(
            username='sistema_migracao',
            defaults={'first_name': 'Sistema', 'last_name': 'Legado', 'email': 'migracao@pgm.local'}
        )

        try:
            with connections['legado'].cursor() as cursor:
                # ---------------------------------------------------------
                # 1. MIGRAÇÃO DE USUÁRIOS
                # ---------------------------------------------------------
                self.stdout.write("Migrando Usuários...")
                cursor.execute("SELECT id, username, first_name, last_name, email, is_active FROM auth_user")
                for row in cursor.fetchall():
                    User.objects.get_or_create(
                        id=row[0],
                        defaults={
                            'username': row[1], 'first_name': row[2],
                            'last_name': row[3], 'email': row[4], 'is_active': row[5]
                        }
                    )

                # ---------------------------------------------------------
                # 2. MIGRAÇÃO DE PRIORIDADES E TIPOS DE DOCUMENTO
                # ---------------------------------------------------------
                self.stdout.write("Migrando Dicionários (Prioridades e Tipos)...")
                
                # CORREÇÃO: Usamos 'descricao' tanto no SELECT quanto no defaults
                cursor.execute("SELECT id, descricao, prazo_dias FROM gestao_nivelprioridade")
                for row in cursor.fetchall():
                    # Ajuste aqui para o nome exato do campo no seu model NOVO
                    NivelPrioridade.objects.get_or_create(id=row[0], defaults={'descricao': row[1], 'prazo_dias': row[2]})

                cursor.execute("SELECT id, descricao, ativo FROM gestao_tipodocumento")
                for row in cursor.fetchall():
                    TipoDocumento.objects.get_or_create(id=row[0], defaults={'descricao': row[1], 'ativo': bool(row[2])})

                # ---------------------------------------------------------
                # 3. MIGRAÇÃO DE REMETENTES (COM CRIPTOGRAFIA)
                # ---------------------------------------------------------
                self.stdout.write("Migrando Remetentes (Aplicando Criptografia Fernet)...")
                fernet = Fernet(settings.FIELD_ENCRYPTION_KEY)
                
                cursor.execute("SELECT id, nome_razao_social, cpf_cnpj, telefone, email, tipo_remetente FROM gestao_remetente")
                for row in cursor.fetchall():
                    remetente_id, nome, cpf_cnpj, telefone, email, tipo_antigo = row

                    # De->Para do Tipo de Pessoa
                    mapa_tipo = {'Pessoa Física': 'FISICA', 'Pessoa Jurídica': 'JURIDICA', 'Órgão Público': 'ORGAO_PUBLICO'}
                    tipo_novo = mapa_tipo.get(tipo_antigo, 'FISICA')

                    # Criptografia: cpf_cnpj
                    doc_cripto = fernet.encrypt(cpf_cnpj.encode()).decode() if cpf_cnpj else None
                    doc_hash = hmac.new(settings.SEARCH_HASH_KEY.encode(), cpf_cnpj.encode(), hashlib.sha256).hexdigest() if cpf_cnpj else None

                    # Criptografia: telefone
                    tel_cripto = fernet.encrypt(telefone.encode()).decode() if telefone else None
                    tel_hash = hmac.new(settings.SEARCH_HASH_KEY.encode(), telefone.encode(), hashlib.sha256).hexdigest() if telefone else None

                    Remetente.objects.get_or_create(
                        id=remetente_id,
                        defaults={
                            'nome_razao_social': nome,
                            'tipo_pessoa': tipo_novo,
                            'email': email,
                            'doc': doc_cripto,
                            'doc_hash': doc_hash,
                            'telefone': tel_cripto,
                            'telefone_hash': tel_hash,
                        }
                    )

                # ---------------------------------------------------------
                # 4. MIGRAÇÃO DE PROCESSOS E TIMELINE (O CORAÇÃO)
                # ---------------------------------------------------------
                self.stdout.write("Migrando Processos e reconstruindo a Timeline...")
                # Adapte o nome da tabela (gestao_documento) conforme o banco antigo
                cursor.execute("""
                    SELECT 
                        id, protocolo, status, remetente_id, tipo_documento_id, prioridade_id,
                        num_doc_origem, data_doc_origem, observacoes_protocolo,
                        procurador_atribuido_id, data_atribuicao, data_limite,
                        protocolado_por_id, data_recebimento, data_finalizacao,
                        finalizado_por_id, obs_finalizacao
                    FROM gestao_documento
                """)
                processos_legados = cursor.fetchall()

                # ---------------------------------------------------------
                # 5. INTERESSADOS (M2M: gestao_documento_interessados)
                # ---------------------------------------------------------
                self.stdout.write("Lendo Interessados...")
                cursor.execute("SELECT documento_id, remetente_id FROM gestao_documento_interessados")
                interessados_por_doc = {}
                for row in cursor.fetchall():
                    interessados_por_doc.setdefault(row[0], []).append(row[1])

                # ---------------------------------------------------------
                # 6. DILIGÊNCIAS (gestao_solicitacaodocumento)
                # ---------------------------------------------------------
                self.stdout.write("Lendo Diligências...")
                cursor.execute("""
                    SELECT id, documento_id, procurador_id, descricao_necessidade,
                           status, data_solicitacao, analisado_por_id, observacao_chefia, data_resposta
                    FROM gestao_solicitacaodocumento
                    ORDER BY documento_id, data_solicitacao
                """)
                diligencias_por_doc = {}
                for row in cursor.fetchall():
                    diligencias_por_doc.setdefault(row[1], []).append(row)

                # ---------------------------------------------------------
                # 7. ANEXOS (gestao_anexo)
                # ---------------------------------------------------------
                self.stdout.write("Lendo Anexos...")
                cursor.execute("""
                    SELECT id, documento_id, arquivo, nome_original, tipo_anexo,
                           tipo_documento_id, numero_documento, usuario_upload_id,
                           data_upload, ativo, descricao, solicitacao_diligencia_id
                    FROM gestao_anexo
                    WHERE ativo = 1
                    ORDER BY documento_id, data_upload
                """)
                anexos_por_doc = {}
                for row in cursor.fetchall():
                    anexos_por_doc.setdefault(row[1], []).append(row)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao ler banco legado: {e}"))
            return

        sucesso, erros = 0, 0

        def _aw(dt):
            """Converte datetime naive → aware usando TIME_ZONE do settings. Retorna None se dt for None."""
            if dt is None:
                return None
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt

        # Cada processo tem sua própria transação isolada com savepoint.
        # Assim, um erro em um processo não envenena os demais.
        for p in processos_legados:
            protocolo = p[1]  # disponível no log de erro mesmo se o unpack falhar
            try:
                with transaction.atomic(using='default'):
                    (
                        p_id, protocolo, status_antigo, rem_id, tipo_id, prio_id,
                        num_origem, dt_origem, obs_prot, proc_atrib_id, dt_atrib, dt_limite,
                        prot_por_id, dt_receb, dt_finalizacao, fin_por_id, obs_fin
                    ) = p

                    # DE->PARA Status
                    mapa_status = {
                        'Aguardando Distribuição': Processo.Status.AGUARDANDO_DISTRIBUICAO,
                        'Em Análise': Processo.Status.EM_ANALISE,
                        'Análise Concluída': Processo.Status.CONCLUIDO,
                        'Aguardando Confirmação': Processo.Status.CONCLUIDO,
                        'Devolvido pela Análise': Processo.Status.DEVOLVIDO,
                        'Arquivado': Processo.Status.ARQUIVADO,
                        'Finalizado': Processo.Status.ARQUIVADO,
                        'Em Diligência': Processo.Status.EM_DILIGENCIA,
                    }
                    status_novo = mapa_status.get(status_antigo, Processo.Status.EM_ANALISE)

                    # 4.1 Criar o Processo
                    processo = Processo.objects.create(
                        id=p_id,  # Mantemos o ID original para preservar anexos/relacionamentos
                        numero_protocolo=protocolo,
                        status=status_novo,
                        remetente_id=rem_id,
                        tipo_processo_id=tipo_id,
                        prioridade_id=prio_id,
                        numero_origem=(num_origem or "")[:50],  # legado: max_length=100; novo: max_length=50
                        data_origem=dt_origem,
                        observacoes=obs_prot or "",
                        procurador_atribuido_id=proc_atrib_id,
                        data_atribuicao=_aw(dt_atrib),
                        data_limite=dt_limite
                    )

                    # 4.2 Construir a Timeline (Event Sourcing)

                    # Evento 1: PROTOCOLO (Obrigatório)
                    mov_prot = Movimentacao.objects.create(
                        processo=processo,
                        tipo_evento=Movimentacao.TipoEvento.PROTOCOLO,
                        usuario_responsavel_id=prot_por_id or usuario_sistema.id,
                        descricao="Processo protocolado (Migração)."
                    )
                    # Bypass do auto_now_add para manter a data histórica
                    Movimentacao.objects.filter(id=mov_prot.id).update(data_criacao=_aw(dt_receb))

                    # Evento 2: DISTRIBUIÇÃO
                    if dt_atrib:
                        mov_dist = Movimentacao.objects.create(
                            processo=processo,
                            tipo_evento=Movimentacao.TipoEvento.DISTRIBUICAO,
                            usuario_responsavel_id=prot_por_id or usuario_sistema.id,
                            descricao="Distribuído via migração do sistema legado."
                        )
                        Movimentacao.objects.filter(id=mov_dist.id).update(data_criacao=_aw(dt_atrib))

                    # Evento 3: CONCLUSÃO
                    mov_fim = None
                    if status_antigo == 'Finalizado' or dt_finalizacao:
                        mov_fim = Movimentacao.objects.create(
                            processo=processo,
                            tipo_evento=Movimentacao.TipoEvento.CONCLUSAO,
                            usuario_responsavel_id=fin_por_id or usuario_sistema.id,
                            descricao=obs_fin or "Processo concluído no sistema legado."
                        )
                        Movimentacao.objects.filter(id=mov_fim.id).update(data_criacao=_aw(dt_finalizacao) or timezone.now())

                    # 4.3 Interessados (M2M)
                    for rem_int_id in interessados_por_doc.get(p_id, []):
                        processo.interessados.add(rem_int_id)

                    # 4.4 Diligências (SolicitacaoDocumento + Movimentacoes de timeline)
                    # mapa: legacy solicitacao_id → Movimentacao DILIGENCIA_INICIADA
                    # usado na seção 4.5 para ancorar anexos de diligência
                    map_sol_mov = {}
                    mapa_status_dil = {
                        'Pendente':  SolicitacaoDocumento.Status.PENDENTE,
                        'Enviada':   SolicitacaoDocumento.Status.ENVIADA,
                        'Atendida':  SolicitacaoDocumento.Status.ATENDIDA,
                        'Rejeitada': SolicitacaoDocumento.Status.REJEITADA,
                    }
                    for dil in diligencias_por_doc.get(p_id, []):
                        (dil_id, _, proc_id_dil, descricao_dil,
                         status_dil, dt_sol, analisado_id, obs_chefia, dt_resposta) = dil

                        mov_dil = Movimentacao.objects.create(
                            processo=processo,
                            tipo_evento=Movimentacao.TipoEvento.DILIGENCIA_INICIADA,
                            usuario_responsavel_id=proc_id_dil or usuario_sistema.id,
                            descricao=descricao_dil,
                        )
                        Movimentacao.objects.filter(id=mov_dil.id).update(data_criacao=_aw(dt_sol) or timezone.now())
                        map_sol_mov[dil_id] = mov_dil

                        status_dil_novo = mapa_status_dil.get(status_dil, SolicitacaoDocumento.Status.PENDENTE)
                        sol = SolicitacaoDocumento.objects.create(
                            processo=processo,
                            movimentacao_origem=mov_dil,
                            descricao_necessidade=descricao_dil,
                            status=status_dil_novo,
                            observacao_chefia=obs_chefia or "",
                            data_conclusao=_aw(dt_resposta),
                        )
                        # Bypass do auto_now_add para manter a data histórica
                        SolicitacaoDocumento.objects.filter(id=sol.id).update(
                            data_solicitacao=_aw(dt_sol) or timezone.now()
                        )

                        # Se a diligência foi resolvida, cria o evento de fechamento
                        if status_dil == 'Atendida' and dt_resposta:
                            mov_dil_res = Movimentacao.objects.create(
                                processo=processo,
                                tipo_evento=Movimentacao.TipoEvento.DILIGENCIA_RESOLVIDA,
                                usuario_responsavel_id=analisado_id or usuario_sistema.id,
                                descricao=obs_chefia or "Diligência resolvida (Migração).",
                            )
                            Movimentacao.objects.filter(id=mov_dil_res.id).update(data_criacao=_aw(dt_resposta))

                    # 4.5 Anexos (ancorados na Movimentacao correta)
                    for anx in anexos_por_doc.get(p_id, []):
                        (anx_id, _, arquivo, nome_orig, tipo_anx, tipo_doc_id,
                         num_doc, user_upload_id, dt_upload, ativo_anx,
                         descricao_anx, sol_id) = anx

                        # Regra de ancoragem: qual Movimentacao recebe este anexo?
                        if tipo_anx == 'INICIAL':
                            mov_anc = mov_prot
                        elif tipo_anx == 'RESPOSTA':
                            mov_anc = mov_fim if mov_fim else mov_prot
                        elif tipo_anx == 'DILIGENCIA' and sol_id and sol_id in map_sol_mov:
                            mov_anc = map_sol_mov[sol_id]
                        else:
                            mov_anc = mov_prot  # fallback seguro

                        Anexo.objects.create(
                            movimentacao=mov_anc,
                            processo=processo,
                            arquivo=arquivo,      # path legado; arquivos físicos migrar separadamente
                            tipo_anexo=tipo_anx,
                            tipo_documento_id=tipo_doc_id,
                            numero_documento=num_doc,
                            ativo=bool(ativo_anx),
                            observacao=descricao_anx,
                        )

                sucesso += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erro no proc {protocolo}: {e}"))
                erros += 1

        self.stdout.write(self.style.SUCCESS(f"ETL Concluído! Sucesso: {sucesso} | Erros: {erros}"))
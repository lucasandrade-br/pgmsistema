<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter }      from 'vue-router'
import { useToast }                 from 'primevue/usetoast'
import { useConfirm }               from 'primevue/useconfirm'
import Button                       from 'primevue/button'
import ConfirmDialog                from 'primevue/confirmdialog'
import Dialog                       from 'primevue/dialog'
import InputText                    from 'primevue/inputtext'
import Menu                         from 'primevue/menu'
import Select                       from 'primevue/select'
import SelectButton                 from 'primevue/selectbutton'
import Skeleton                     from 'primevue/skeleton'
import Tag                          from 'primevue/tag'
import Textarea                     from 'primevue/textarea'
import ModalEdicaoProcesso          from '@/components/processos/ModalEdicaoProcesso.vue'
import WorkspaceAnexos              from '@/components/shared/WorkspaceAnexos.vue'
import VisualizadorPDFPadrao        from '@/components/shared/VisualizadorPDFPadrao.vue'
import GerenciadorDiligencias       from '@/components/shared/GerenciadorDiligencias.vue'
import api                          from '@/services/api'
import { useAuthStore }             from '@/stores/auth'

const route     = useRoute()
const router    = useRouter()
const toast     = useToast()
const confirm   = useConfirm()
const authStore = useAuthStore()

// Tipos de documento carregados da API (substitui mock estático)
const tiposDocumento    = ref([])
const tipoAnexoOpcoes   = [
  { label: 'Inicial',    value: 'INICIAL'    },
  { label: 'Resposta',   value: 'RESPOSTA'   },
  { label: 'Diligência', value: 'DILIGENCIA' },
  { label: 'Outros',     value: 'OUTROS'     },
]

// Dados reativos
const processo      = ref(null)
const movimentacoes = ref([])
const loading       = ref(false)

// ══════════════════ Estado da UI ══════════════════════════    
const exibirModalDados         = ref(false)
const exibirModalAnexo         = ref(false)
const exibirModalEdicaoAnexo   = ref(false)
const exibirModalEdicaoProcesso = ref(false)
const isTimelineOpen           = ref(true)
const selectedAnexo            = ref(null)
const diligenciaEmFoco         = ref(null)
const menuAcoes                = ref(null)
const anexosNovaMovimentacao   = ref([])
const procuradores             = ref([])
const isSubmittingAnexo        = ref(false)
const isSavingEdicao           = ref(false)
const tipoMovimentacao         = ref('Anexo')

// ══════════════════ Autos Digitais ══════════════════════════
const gerandoAutos          = ref(false)
const modalAutosVisivel     = ref(false)
const linkCompartilhamento  = ref('')
const emailDestino          = ref('')
const enviandoEmail         = ref(false)
const descricaoDiligencia      = ref('')
const dadosEdicaoAnexo         = ref({ categoria: null, numeracao: '', observacao: '', tipoAnexo: '' })

// Monta a URL absoluta do PDF combinando o domínio do backend com o path relativo da API
const viewerUrlCompleta = computed(() => {
  const url = selectedAnexo.value?.url
  if (!url) return null
  if (url.startsWith('http') || url.startsWith('blob:')) return url
  const baseUrl = api.defaults.baseURL?.replace(/\/api\/v1\/?$/, '') || 'http://localhost:8000'
  return `${baseUrl}${url}`
})

// Coleta todos os anexos físicos (com URL) de todas as movimentações do processo
const anexosGlobais = computed(() => {
  const todos = []
  movimentacoes.value.forEach(m => {
    if (m.anexos) todos.push(...m.anexos.filter(a => a.url))
  })
  return todos
})

// ══════════════════ RBAC e Validações ══════════════════════════    
const _CHEFIAS = ['Protocolador-Chefe', 'Procurador-Chefe', 'Procurador-Analista']

const currentUser    = computed(() => authStore.user ?? { id: null, username: null, grupos: [], is_superuser: false })
const isSuperUser    = computed(() => !!currentUser.value.is_superuser)
const isChefiaOrSuper = computed(() => _CHEFIAS.some(c => currentUser.value.grupos?.includes(c)) || isSuperUser.value)
const isOwnerOrSuper  = computed(() => {
  if (isSuperUser.value) return true
  if (!currentUser.value.id || !processo.value?.procurador_atribuido) return false
  return Number(currentUser.value.id) === Number(processo.value.procurador_atribuido)
})

const hasResposta = computed(() =>
  // Varre os anexos para identificar se há uma RESPOSTA (seja PDF ou Nota de Texto)
  movimentacoes.value.some(m => m.anexos && m.anexos.some(a => a.tipo_anexo === 'RESPOSTA'))
)

const canDistribuir = computed(() =>
  (['AGUARDANDO_DISTRIBUICAO', 'DEVOLVIDO'].includes(processo.value?.status) && isChefiaOrSuper.value) || isSuperUser.value
)

const canConcluirAnalise = computed(() =>
  (['EM_ANALISE', 'REJEITADO'].includes(processo.value?.status) && isOwnerOrSuper.value && hasResposta.value) || isSuperUser.value
)

const canConfirmarRejeitar = computed(() =>
  (processo.value?.status === 'CONCLUIDO' && isChefiaOrSuper.value) || isSuperUser.value
)

// ══════════════════ Tramitações e Ações Diretas ══════════════════════════
const exibirModalDistribuicao = ref(false)
const procuradorSelecionado   = ref(null)
const isSubmittingAcao        = ref(false)

async function abrirModalDistribuicao() {
  try {
    const res = await api.get('auth/procuradores/')
    procuradores.value = res.data?.results ?? res.data ?? []
    procuradorSelecionado.value = null
    exibirModalDistribuicao.value = true
  } catch {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível carregar os procuradores.' })
  }
}

const exibirModalTramitacao = ref(false)
const dadosTramitacao       = ref({ status: '', titulo: '', motivo: '' })

function abrirModalTramitacao(novoStatus, titulo) {
  dadosTramitacao.value = { status: novoStatus, titulo: titulo, motivo: '' }
  exibirModalTramitacao.value = true
}

async function confirmarTramitacao() {
  loading.value = true
  try {
    await api.post(`gestao/processos/${processo.value.id}/tramitar/`, {
      status: dadosTramitacao.value.status,
      motivo: dadosTramitacao.value.motivo,
    })
    toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Ação executada com sucesso.', life: 3000 })
    exibirModalTramitacao.value = false
    await carregarProcesso()
  } catch {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível executar a ação.', life: 5000 })
  } finally {
    loading.value = false
  }
}

async function salvarDistribuicao() {
  if (!procuradorSelecionado.value) return
  isSubmittingAcao.value = true
  try {
    // Reutiliza a inteligência do backend que calcula prazo e gera Movimentação
    await api.post('gestao/processos/distribuir-lote/', {
      processos_ids:    [processo.value.id],
      procuradores_ids: [procuradorSelecionado.value]
    })
    toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Processo atribuído com sucesso.' })
    exibirModalDistribuicao.value = false
    setTimeout(async () => { await carregarProcesso() }, 300)
  } catch {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao distribuir o processo.' })
  } finally {
    isSubmittingAcao.value = false
  }
}

// ══════════════════ Menu Secundário (Kebab) ══════════════════════════    
const itensMenuSecundario = computed(() => {
  const p = processo.value
  if (!p) return []
  const items = []

  if (p.status === 'EM_ANALISE' && isOwnerOrSuper.value) {
    items.push({
      label:   'Devolver',
      icon:    'pi pi-undo',
      command: () => abrirModalTramitacao('DEVOLVIDO', 'Devolver Processo')
    })
  }

  if (!['ARQUIVADO', 'REJEITADO'].includes(p.status) && isChefiaOrSuper.value) {
    items.push({
      label:   'Arquivar',
      icon:    'pi pi-folder',
      command: () => abrirModalTramitacao('ARQUIVADO', 'Arquivar Processo')
    })
  }

  if (['ARQUIVADO', 'FINALIZADO'].includes(p.status) && isChefiaOrSuper.value) {
    items.push({
      label:   'Desarquivar',
      icon:    'pi pi-folder-open',
      command: () => abrirModalTramitacao('EM_ANALISE', 'Desarquivar Processo')
    })
  }

  if ((!['ARQUIVADO', 'CONCLUIDO', 'REJEITADO'].includes(p.status) && isChefiaOrSuper.value) || isSuperUser.value) {
    items.push({
      label:   'Editar Dados',
      icon:    'pi pi-pencil',
      command: () => { exibirModalEdicaoProcesso.value = true }
    })
  }

  items.push({
    label:   'Gerar Autos Digitais',
    icon:    'pi pi-file-pdf',
    command: () => gerarAutos()
  })

  return items
})

function toggleMenuAcoes(event) {
  menuAcoes.value.toggle(event)
}

// ══════════════════ Carregamento de Dados ══════════════════════════
async function carregarProcesso() {
  loading.value = true
  try {
    const id = route.params.id
    const [processoRes, movimentacoesRes] = await Promise.all([
      api.get(`gestao/processos/${id}/`),
      api.get(`gestao/processos/${id}/movimentacoes/`),
    ])
    processo.value      = processoRes.data
    movimentacoes.value = movimentacoesRes.data
    // Auto-seleciona o primeiro anexo da movimentação mais recente (topo da lista)
    selectedAnexo.value = null
    for (const item of movimentacoes.value) {
      if (item.anexos?.length) {
        selectedAnexo.value = item.anexos[0]
        break
      }
    }
  } catch (err) {
    if (err.response?.status === 404) {
      toast.add({
        severity: 'error',
        summary:  'Acesso Negado',
        detail:   'Processo não encontrado ou você não tem permissão para visualizá-lo.',
        life:     5000,
      })
      router.replace('/')
    } else {
      toast.add({
        severity: 'error',
        summary:  'Erro ao carregar',
        detail:   'Não foi possível carregar os dados do processo.',
        life:     5000,
      })
    }
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  carregarProcesso()
  try {
    const tipoDocRes = await api.get('cadastros/tipos-documento/')
    tiposDocumento.value = tipoDocRes.data.results ?? tipoDocRes.data
  } catch { /* silencioso */ }
})

// Helpers
function formatarData(iso) {
  if (!iso) return '-'
  const [ano, mes, dia] = iso.substring(0, 10).split('-')
  return `${dia}/${mes}/${ano}`
}

function formatarDataHora(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function statusSeverity(status) {
  const map = {
    AGUARDANDO_DISTRIBUICAO: 'secondary',
    DEVOLVIDO:               'danger',
    EM_ANALISE:              'info',
    EM_DILIGENCIA:           'warn',
    CONCLUIDO:               'success',
    ARQUIVADO:               'secondary',
    REJEITADO:               'danger',
  }
  return map[status] ?? 'secondary'
}

function tipoEventoIcon(tipo) {
  const map = {
    PROTOCOLO:            'pi-file',
    DISTRIBUICAO:         'pi-user-plus',
    CONCLUSAO:            'pi-check-circle',
    REJEICAO:             'pi-times-circle',
    DILIGENCIA_INICIADA:  'pi-exclamation-triangle',
    DILIGENCIA_RESOLVIDA: 'pi-check',
    ARQUIVAMENTO:         'pi-folder',
    DESARQUIVAMENTO:      'pi-folder-open',
    DEVOLUCAO:            'pi-undo',
    ANEXO_ARQUIVO:        'pi-paperclip',
    OBSERVACAO_SIMPLES:   'pi-comment',
  }
  return map[tipo] ?? 'pi-circle'
}

// ══════════════════ Nova Movimentação: Workspace de Anexos ══════════════════════════
async function salvarMovimentacao() {
  // Validação: diligência exige descrição
  if (tipoMovimentacao.value === 'Iniciar Diligência' && !descricaoDiligencia.value.trim()) {
    toast.add({
      severity: 'warn',
      summary:  'Campo obrigatório',
      detail:   'Descreva a necessidade da diligência antes de salvar.',
      life:     3000,
    })
    return
  }

  // Validação: ao menos um documento no carrinho
  if (!anexosNovaMovimentacao.value.length) {
    toast.add({
      severity: 'warn',
      summary:  'Nenhum documento',
      detail:   'Adicione ao menos um documento antes de salvar.',
      life:     3000,
    })
    return
  }

  const formData     = new FormData()
  const metadataList = []

  // Tipo do evento
  formData.append(
    'tipo_evento',
    tipoMovimentacao.value === 'Iniciar Diligência' ? 'DILIGENCIA_INICIADA' : 'ANEXO_ARQUIVO',
  )

  // Descrição opcional (obrigatória para diligência, já validado acima)
  if (descricaoDiligencia.value.trim()) {
    formData.append('descricao', descricaoDiligencia.value.trim())
  }

  // Padrão "Zip" flexível: inclui notas de texto (sem arquivo) e PDFs
  anexosNovaMovimentacao.value.forEach(anexo => {
    if (anexo.arquivo) formData.append('arquivos', anexo.arquivo)
    metadataList.push({
      eh_nota:                !anexo.arquivo,
      categoria_documento_id: anexo.categoria?.id ?? null,
      numero_documento:       (anexo.numeracao !== '—' ? anexo.numeracao : '') || '',
      observacao:             anexo.texto ?? '',
    })
  })
  formData.append('metadata', JSON.stringify(metadataList))

  isSubmittingAnexo.value = true
  try {
    await api.post(`gestao/processos/${processo.value.id}/movimentacoes/`, formData)

    toast.add({
      severity: 'success',
      summary:  'Movimentação salva!',
      detail:   'Os documentos foram adicionados ao processo.',
      life:     4000,
    })

    // Reseta formulário e fecha modal
    anexosNovaMovimentacao.value = []
    exibirModalAnexo.value       = false
    tipoMovimentacao.value       = 'Anexo'
    descricaoDiligencia.value    = ''

    // Recarrega a timeline para refletir a nova movimentação
    await carregarProcesso()
  } catch {
    toast.add({
      severity: 'error',
      summary:  'Erro ao salvar',
      detail:   'Não foi possível registrar a movimentação.',
      life:     5000,
    })
  } finally {
    isSubmittingAnexo.value = false
  }
}

// ══════════════════ Edição de Metadados do Processo ════════════════════════
// ══════════════════ Edição e Exclusão de Anexo ══════════════════════════════
function abrirGerenciador(diligencia) {
  selectedAnexo.value    = null
  diligenciaEmFoco.value = diligencia
}

function recarregarAposDiligencia() {
  diligenciaEmFoco.value = null
  carregarProcesso()
}

function abrirModalEdicao() {
  if (!selectedAnexo.value) return
  dadosEdicaoAnexo.value = {
    categoria:  selectedAnexo.value.tipo_documento_id ?? null,
    numeracao:  selectedAnexo.value.numero_documento ?? '',
    observacao: selectedAnexo.value.observacao ?? '',
    tipoAnexo:  selectedAnexo.value.tipo_anexo ?? '',
  }
  exibirModalEdicaoAnexo.value = true
}

async function salvarEdicaoAnexo() {
  isSavingEdicao.value = true
  try {
    await api.patch(`gestao/anexos/${selectedAnexo.value.id}/`, {
      tipo_documento:  dadosEdicaoAnexo.value.categoria ?? null,
      tipo_anexo:      dadosEdicaoAnexo.value.tipoAnexo || undefined,
      numero_documento: dadosEdicaoAnexo.value.numeracao,
      observacao:       dadosEdicaoAnexo.value.observacao,
    })
    exibirModalEdicaoAnexo.value = false
    toast.add({
      severity: 'success',
      summary:  'Anexo atualizado',
      detail:   'Os metadados foram salvos com sucesso.',
      life:     4000,
    })
    await carregarProcesso()
  } catch {
    toast.add({
      severity: 'error',
      summary:  'Erro ao salvar',
      detail:   'Não foi possível atualizar os dados do anexo.',
      life:     5000,
    })
  } finally {
    isSavingEdicao.value = false
  }
}

async function gerarAutos() {
  gerandoAutos.value = true
  try {
    const { data } = await api.post(`gestao/processos/${processo.value.id}/gerar-link/`)
    linkCompartilhamento.value = `${window.location.origin}/autos/${data.token}`
    modalAutosVisivel.value = true
  } catch {
    toast.add({
      severity: 'error',
      summary:  'Erro',
      detail:   'Não foi possível gerar os autos digitais. Tente novamente.',
      life:     5000,
    })
  } finally {
    gerandoAutos.value = false
  }
}

function copiarLink() {
  navigator.clipboard.writeText(linkCompartilhamento.value).then(() => {
    toast.add({
      severity: 'success',
      summary:  'Copiado!',
      detail:   'Link copiado para a área de transferência.',
      life:     3000,
    })
  })
}

function enviarWhatsApp() {
  const texto = encodeURIComponent(
    'Segue o link de acesso aos autos digitais do processo. O link é válido por 30 dias: ' +
    linkCompartilhamento.value
  )
  window.open(`https://api.whatsapp.com/send?text=${texto}`, '_blank')
}

async function enviarEmailAutos() {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(emailDestino.value)) {
    toast.add({
      severity: 'warn',
      summary:  'E-mail inválido',
      detail:   'Informe um endereço de e-mail válido antes de enviar.',
      life:     3000,
    })
    return
  }
  enviandoEmail.value = true
  try {
    await api.post(`gestao/processos/${processo.value.id}/enviar-link-autos/`, {
      email: emailDestino.value,
      link:  linkCompartilhamento.value,
    })
    toast.add({
      severity: 'success',
      summary:  'E-mail enviado!',
      detail:   `O link foi enviado para ${emailDestino.value}.`,
      life:     4000,
    })
    emailDestino.value = ''
  } catch {
    toast.add({
      severity: 'error',
      summary:  'Erro ao enviar',
      detail:   'Não foi possível enviar o e-mail. Tente novamente.',
      life:     5000,
    })
  } finally {
    enviandoEmail.value = false
  }
}

function confirmarExclusao() {
  if (!selectedAnexo.value) return
  confirm.require({
    message:     'Tem certeza que deseja remover este anexo?',
    header:      'Confirmar Exclusão',
    icon:        'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await api.patch(`gestao/anexos/${selectedAnexo.value.id}/`, { ativo: false })
        toast.add({
          severity: 'success',
          summary:  'Anexo removido',
          detail:   'O documento foi removido da movimentação.',
          life:     4000,
        })
        // Exclusão otimista: remove localmente para feedback instantâneo
        const idRemovido = selectedAnexo.value.id
        for (const mov of movimentacoes.value) {
          if (mov.anexos) {
            const index = mov.anexos.findIndex(a => a.id === idRemovido)
            if (index !== -1) { mov.anexos.splice(index, 1); break }
          }
        }
        selectedAnexo.value = null
        carregarProcesso() // background sync sem await — UI já atualizada
      } catch {
        toast.add({
          severity: 'error',
          summary:  'Erro ao remover',
          detail:   'Não foi possível remover o anexo.',
          life:     5000,
        })
      }
    },
  })
}
</script>

<template>
  <!-- ══════════════════ ESTADO DE CARREGAMENTO ══════════════════════════ -->
  <div
    v-if="loading"
    class="-m-6 flex flex-col h-[calc(100vh-4rem)] overflow-hidden"
  >
    <!-- Topbar skeleton -->
    <div class="shrink-0 bg-gray-100 border-b border-gray-300 px-4 py-2.5 flex items-center justify-between">
      <Skeleton width="55%" height="2rem" border-radius="0.375rem" />
      <div class="flex gap-2">
        <Skeleton width="6rem" height="2rem" border-radius="0.375rem" />
        <Skeleton width="2.25rem" height="2.25rem" border-radius="50%" />
        <Skeleton width="2.25rem" height="2.25rem" border-radius="50%" />
      </div>
    </div>
    <!-- Split-screen skeleton -->
    <div class="flex flex-1 overflow-hidden">
      <Skeleton width="20rem" height="100%" border-radius="0" />
      <Skeleton class="flex-1" height="100%" border-radius="0" />
    </div>
  </div>

  <!-- ══════════════════ WORKSPACE PRINCIPAL ══════════════════════════════ -->
  <div
    v-else-if="processo"
    class="-m-6 flex flex-col h-[calc(100vh-4rem)] overflow-hidden"
  >

    <!-- ══════════════════ SUBCABEÇALHO IMERSIVO ══════════════════════════ -->
    <div class="shrink-0 w-full bg-gray-100 border-b border-gray-300 px-4 py-2.5 flex items-center justify-between gap-4">

      <!-- Lado esquerdo: botão de toggle da timeline + dados resumidos -->
      <div class="flex items-center min-w-0">
        <Button
          :icon="isTimelineOpen ? 'pi pi-angle-double-left' : 'pi pi-bars'"
          text
          rounded
          severity="secondary"
          size="small"
          class="mr-2 shrink-0"
          @click="isTimelineOpen = !isTimelineOpen"
          :title="isTimelineOpen ? 'Recolher Timeline' : 'Expandir Timeline'"
        />
        <div
          class="flex items-center gap-2 cursor-pointer hover:bg-gray-200 px-2 py-1.5 rounded transition-colors min-w-0"
          title="Clique para ver os detalhes completos do processo"
          @click="exibirModalDados = true"
        >
          <div class="min-w-0">
            <!-- Linha 1: protocolo | tipo | status ▾ -->
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-mono font-bold text-gray-900 text-sm shrink-0">
                {{ processo.numero_protocolo }}
              </span>
              <span class="text-gray-300 shrink-0">|</span>
              <span class="text-gray-700 text-sm font-medium truncate">
                {{ processo.tipo_processo_descricao }} - {{ processo.numero_origem }}
              </span>
              <span class="text-gray-300 shrink-0">|</span>
              <span class="text-gray-500 text-sm shrink-0">Status:</span>
              <Tag
                :value="processo.status_display"
                :severity="statusSeverity(processo.status)"
                class="!text-xs !py-0.5 shrink-0"
              />
              <i class="pi pi-angle-down text-gray-400 text-xs shrink-0" />
            </div>
            <!-- Linha 2: interessados -->
            <div class="text-xs text-gray-500 mt-0.5 truncate">
              Interessado(s): {{ processo.interessados_info?.map(i => i.nome).join(', ') }}
            </div>
          </div>
        </div>
      </div>

      <!-- Lado direito: ações condicionais por RBAC -->
      <div class="flex items-center gap-2 shrink-0">

        <!-- Botão de distribuição: só chefias em processos sem procurador -->
        <Button
          v-if="canDistribuir"
          label="Distribuir / Assumir"
          severity="info"
          size="small"
          icon="pi pi-users"
          @click="abrirModalDistribuicao"
        />

        <!-- Botão de conclusão: só o analista dono do processo -->
        <Button
          v-if="canConcluirAnalise"
          label="Concluir Análise"
          severity="success"
          size="small"
          icon="pi pi-check"
          @click="abrirModalTramitacao('CONCLUIDO', 'Concluir Análise')"
        />

        <!-- Botões de homologação: só em status CONCLUÍDO para perfis chefia -->
        <Button
          v-if="canConfirmarRejeitar"
          label="Rejeitar"
          severity="danger"
          outlined
          size="small"
          icon="pi pi-times"
          @click="abrirModalTramitacao('REJEITADO', 'Rejeitar Análise')"
        />
        <Button
          v-if="canConfirmarRejeitar"
          label="Homologar"
          severity="success"
          size="small"
          icon="pi pi-check-circle"
          @click="abrirModalTramitacao('FINALIZADO', 'Homologar Análise')"
        />

        <!-- Anexar: abre o modal de nova movimentação com WorkspaceAnexos -->
        <Button
          icon="pi pi-paperclip"
          label="Anexar Arquivo"
          rounded
          severity="contrast"
          size="small"
          title="Adicionar Movimentação"
          @click="exibirModalAnexo = true"
        />

        <!-- Kebab menu: ações secundárias (Devolver, Arquivar, Editar...) -->
        <Button
          v-if="itensMenuSecundario.length > 0"
          icon="pi pi-ellipsis-v"
          rounded
          text
          severity="secondary"
          size="small"
          aria-haspopup="true"
          aria-controls="overlay_menu_acoes"
          @click="toggleMenuAcoes"
        />

        <!-- Voltar -->
        <Button
          icon="pi pi-home"
          rounded
          text
          severity="secondary"
          size="small"
          title="Voltar"
          @click="router.back()"
        />
      </div>

    </div>

    <!-- ══════════════════ ÁREA PRINCIPAL — SPLIT SCREEN ═════════════════ -->
    <div class="flex flex-1 overflow-hidden bg-white">

      <!-- ── Sidebar Esquerda: Timeline de cards (colapsável) ──────────────── -->
      <div
        :class="[
          'shrink-0 bg-gray-50 transition-all duration-300 ease-in-out overflow-hidden flex flex-col',
          isTimelineOpen ? 'w-80 border-r border-gray-200 opacity-100' : 'w-0 border-r-0 opacity-0'
        ]"
      >
        <!-- Largura fixa interna: evita reflow de texto durante a animação -->
        <div class="w-80 p-4 h-full overflow-y-auto shrink-0">

          <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 px-1">
            Movimentações
          </h3>

          <div
            v-for="item in movimentacoes"
            :key="item.id"
            :class="[
              'mb-3 p-3 rounded-r-md border-l-4 shadow-sm',
              item.diligencia_info?.status === 'PENDENTE' || item.diligencia_info?.status === 'ENVIADA'
                ? 'bg-amber-50/40 border-amber-400'
                : 'bg-white border-gray-200',
            ]"
          >
            <!-- Cabeçalho do card: tipo de evento -->
            <div class="flex items-center gap-2 mb-1">
              <i :class="`pi ${tipoEventoIcon(item.tipo_evento)} text-sm text-gray-400`" />
              <span class="font-semibold text-sm text-gray-800">{{ item.tipo_evento_display }}</span>
              <Button
                v-if="item.diligencia_info && ['PENDENTE', 'ENVIADA'].includes(item.diligencia_info.status) && isChefiaOrSuper"
                icon="pi pi-cog"
                text rounded
                severity="warning"
                size="small"
                title="Gerenciar Diligência"
                class="ml-auto"
                @click="abrirGerenciador(item.diligencia_info)"
              />
            </div>

            <!-- Data -->
            <p class="text-xs text-gray-400">{{ formatarDataHora(item.data_criacao) }}</p>

            <!-- Iteração de anexos -->
            <div v-if="item.anexos?.length" class="mt-3 flex flex-col gap-1.5">
              <div
                v-for="anexo in item.anexos"
                :key="anexo.id"
                @click="selectedAnexo = anexo; diligenciaEmFoco = null"
                :class="[
                  'flex items-center gap-2 rounded px-2 py-1.5 text-xs cursor-pointer transition-colors border',
                  selectedAnexo?.id === anexo.id
                    ? 'bg-blue-50 border-blue-200 text-blue-700 font-medium'
                    : 'bg-gray-50 border-gray-100 text-gray-600 hover:bg-gray-100 hover:border-gray-300'
                ]"
              >
                <i :class="['pi pi-file-pdf shrink-0', selectedAnexo?.id === anexo.id ? 'text-red-500' : 'text-red-400']" />
                <span class="truncate">{{ anexo.nome }}</span>
                <i v-if="selectedAnexo?.id === anexo.id" class="pi pi-eye ml-auto text-blue-400" />
              </div>
            </div>

            <!-- Descrição opcional -->
            <p v-if="item.descricao" class="text-xs text-gray-500 mt-2 leading-snug">
              {{ item.descricao }}
            </p>

          </div>
        </div>
      </div>

      <!-- ── Área Direita: Visualizador de Documento ou Gerenciador de Diligência ── -->
      <VisualizadorPDFPadrao
        v-if="!diligenciaEmFoco"
        :arquivoNome="selectedAnexo?.nome"
        :viewerUrl="viewerUrlCompleta"
        :textoNota="viewerUrlCompleta ? null : (selectedAnexo?.observacao || null)"
        class="flex-1 h-full border-none rounded-none"
        @editar="abrirModalEdicao"
        @excluir="confirmarExclusao"
      />
      <GerenciadorDiligencias
        v-else-if="diligenciaEmFoco"
        :diligencia="diligenciaEmFoco"
        :processo="processo"
        :anexos-globais="anexosGlobais"
        class="flex-1 h-full"
        @sucesso="recarregarAposDiligencia"
      />
    </div>

    <!-- Menu popup de análises secundárias (Kebab) -->
    <Menu
      ref="menuAcoes"
      id="overlay_menu_acoes"
      :model="itensMenuSecundario"
      :popup="true"
    />

    <!-- ══════════════════ MODAL DE DETALHES ══════════════════════════ -->
    <Dialog
      v-model:visible="exibirModalDados"
      modal
      header="Detalhes do Processo"
      :style="{ width: '52rem' }"
      :breakpoints="{ '960px': '90vw', '640px': '95vw' }"
    >
      <div>

        <div class="grid grid-cols-2 gap-0 pt-2">

          <!-- ── Coluna Esquerda: metadados do processo ──────────────────── -->
          <dl class="pr-6 flex flex-col gap-4 text-sm">

            <div>
              <dt class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Status</dt>
              <dd class="mt-1">
                <Tag :value="processo.status_display" :severity="statusSeverity(processo.status)" />
              </dd>
            </div>

            <div>
              <dt class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Nº Documento de Origem</dt>
              <dd class="mt-1 font-medium text-gray-800">{{ processo.numero_origem ?? '—' }}</dd>
            </div>

            <div>
              <dt class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Número SEI</dt>
              <dd class="mt-1 font-medium text-gray-800">{{ processo.numero_sei || '—' }}</dd>
            </div>

            <div>
              <dt class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Tipo de Processo</dt>
              <dd class="mt-1 font-medium text-gray-800">{{ processo.tipo_processo_descricao ?? '—' }}</dd>
            </div>
            <div>
              <dt class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Prioridade</dt>
              <dd class="mt-1 font-medium text-gray-800">{{ processo.prioridade_descricao ?? '—' }}</dd>
            </div>
            <div>
              <dt class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Procurador Responsável</dt>
              <dd class="mt-1 font-medium text-gray-800">{{ processo.procurador_nome ?? '—' }}</dd>
            </div>

            <div>
              <dt class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Atribuído em</dt>
              <dd class="mt-1 font-medium text-gray-800">{{ formatarDataHora(processo.data_atribuicao) }}</dd>
            </div>

            <div>
              <dt class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Prazo</dt>
              <dd class="mt-1 font-medium text-gray-800">
                {{ processo.prazo_dias != null ? `${processo.prazo_dias} dias` : '—' }}
                <span class="text-gray-400 font-normal ml-1">
                  ({{ formatarData(processo.data_limite) }})
                </span>
              </dd>
            </div>

            <div>
              <dt class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Respondido em</dt>
              <dd class="mt-1 font-medium text-gray-800">{{ formatarDataHora(processo.data_resposta_procurador) }}</dd>
            </div>

            <div>
              <dt class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Observações</dt>
              <dd class="mt-1 text-gray-700 leading-relaxed">{{ processo.observacoes ?? '—' }}</dd>
            </div>

          </dl>

          <!-- ── Coluna Direita: remetente e interessados ─────────────────────────── -->
          <div class="pl-6 border-l border-gray-200 flex flex-col gap-6 text-sm">

            <!-- Remetente Principal -->
            <div>
              <h4 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Remetente Principal
              </h4>
              <p class="font-semibold text-gray-900">{{ processo.remetente_nome }}</p>
              <p v-if="processo.remetente_email" class="text-gray-500 text-xs mt-1">
                <i class="pi pi-envelope text-gray-300 mr-1" />{{ processo.remetente_email }}
              </p>
              <p v-if="processo.remetente_telefone" class="text-gray-500 text-xs mt-1">
                <i class="pi pi-phone text-gray-300 mr-1" />{{ processo.remetente_telefone }}
              </p>
              <p class="text-gray-400 text-xs mt-1.5">{{ processo.remetente_tipo }}</p>
            </div>

            <!-- Interessados -->
            <div>
              <h4 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Interessado(s)
              </h4>

              <template v-if="processo.interessados_info?.length">
                <div
                  v-for="(int, idx) in processo.interessados_info"
                  :key="idx"
                  :class="idx > 0 ? 'mt-4 pt-4 border-t border-gray-100' : ''"
                >
                  <p class="font-semibold text-gray-900">{{ int.nome }}</p>
                  <p v-if="int.email" class="text-gray-500 text-xs mt-1">
                    <i class="pi pi-envelope text-gray-300 mr-1" />{{ int.email }}
                  </p>
                  <p v-if="int.telefone" class="text-gray-500 text-xs mt-1">
                    <i class="pi pi-phone text-gray-300 mr-1" />{{ int.telefone }}
                  </p>
                  <p class="text-gray-400 text-xs mt-1.5">{{ int.tipo }}</p>
                </div>
              </template>

              <p v-else class="text-gray-400 text-xs">Nenhum interessado cadastrado.</p>
            </div>

          </div>
        </div>
      </div>
    </Dialog>

    <!--  MODAL DE NOVA MOVIMENTAÇÃO  -->
    <!--
      maximizable + 90vw garantem que o WorkspaceAnexos tenha altura
      suficiente para leitura confortável do PDF no visualizador.
    -->
    <Dialog
      v-model:visible="exibirModalAnexo"
      modal
      maximizable
      header="Adicionar Movimentação"
      :style="{ width: '90vw', maxWidth: '1400px' }"
      :breakpoints="{ '640px': '98vw' }"
    >
      <!-- Seletor de tipo de movimentação -->
      <div class="mb-4 pb-4 border-b border-gray-100 flex flex-col gap-3">
        <SelectButton
          v-model="tipoMovimentacao"
          :options="['Anexo', 'Iniciar Diligência']"
        />
        <Textarea
          v-if="tipoMovimentacao === 'Iniciar Diligência'"
          v-model="descricaoDiligencia"
          :rows="3"
          placeholder="Descreva a necessidade da diligência..."
          class="w-full"
        />
      </div>

      <!-- Corpo: WorkspaceAnexos reutilizável -->
      <WorkspaceAnexos v-model="anexosNovaMovimentacao" />

      <!-- Rodapé do modal -->
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button
            label="Cancelar"
            text
            severity="secondary"
            @click="exibirModalAnexo = false"
          />
          <Button
            label="Salvar Movimentação"
            severity="success"
            icon="pi pi-check"
            :loading="isSubmittingAnexo"
            @click="salvarMovimentacao"
          />
        </div>
      </template>
    </Dialog>

    <!-- ══════════════════ MODAL DE EDIÇÃO DE ANEXO ═══════════════ -->
    <Dialog
      v-model:visible="exibirModalEdicaoAnexo"
      modal
      header="Editar Metadados do Anexo"
      :style="{ width: '32rem' }"
      :breakpoints="{ '640px': '95vw' }"
    >
      <div class="flex flex-col gap-5 pt-2">

        <!-- Tipo do Anexo -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Tipo do Anexo
          </label>
          <Select
            v-model="dadosEdicaoAnexo.tipoAnexo"
            :options="tipoAnexoOpcoes"
            optionLabel="label"
            optionValue="value"
            placeholder="Selecione o tipo"
            class="w-full"
          />
        </div>

        <!-- Categoria -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Categoria
          </label>
          <Select
            v-model="dadosEdicaoAnexo.categoria"
            :options="tiposDocumento"
            optionLabel="descricao"
            optionValue="id"
            placeholder="Selecione a categoria"
            class="w-full"
          />
        </div>

        <!-- Numeração -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Numeração
          </label>
          <InputText
            v-model="dadosEdicaoAnexo.numeracao"
            placeholder="Ex: 001/2026"
            class="w-full"
          />
        </div>

        <!-- Observações -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Observações
          </label>
          <Textarea
            v-model="dadosEdicaoAnexo.observacao"
            rows="3"
            placeholder="Observações sobre o documento..."
            class="w-full resize-none"
          />
        </div>

      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <Button
            label="Cancelar"
            text
            severity="secondary"
            @click="exibirModalEdicaoAnexo = false"
          />
          <Button
            label="Salvar"
            icon="pi pi-check"
            severity="primary"
            :loading="isSavingEdicao"
            @click="salvarEdicaoAnexo"
          />
        </div>
      </template>
    </Dialog>

    <!-- ConfirmDialog global: usado por confirmarExclusao() -->
    <ConfirmDialog />

    <!-- ════════════════ MODAL DE EDIÇÃO DO PROCESSO ════════════════ -->
    <ModalEdicaoProcesso
      v-model:visible="exibirModalEdicaoProcesso"
      :processo="processo"
      @sucesso="carregarProcesso"
    />

    <!-- ════════════════ MODAL DE DISTRIBUIÇÃO ════════════════ -->
    <Dialog
      v-model:visible="exibirModalDistribuicao"
      modal
      header="Distribuir Processo"
      :style="{ width: '30rem' }"
    >
      <div class="flex flex-col gap-2 pt-2">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Selecione o Procurador Responsável
        </label>
        <Select
          v-model="procuradorSelecionado"
          :options="procuradores || []"
          optionLabel="safe_label"
          optionValue="id"
          placeholder="Selecione..."
          filter
          class="w-full"
        >
          <template #option="slotProps">
            {{ slotProps.option.nome || slotProps.option.username || slotProps.option.safe_label }}
          </template>
        </Select>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <Button label="Cancelar" text severity="secondary" @click="exibirModalDistribuicao = false" />
          <Button label="Confirmar Atribuição" icon="pi pi-check" severity="primary" :loading="isSubmittingAcao" @click="salvarDistribuicao" />
        </div>
      </template>
    </Dialog>

    <!-- ════════════════ MODAL DE AUTOS DIGITAIS ════════════════ -->
    <Dialog
      v-model:visible="modalAutosVisivel"
      modal
      header="Autos Digitais Gerados"
      :style="{ width: '34rem' }"
      :breakpoints="{ '640px': '95vw' }"
    >
      <div class="flex flex-col gap-5 pt-2">
        <p class="text-sm text-gray-600 leading-relaxed">
          O processo foi unificado com sucesso em um único PDF.
          Este link expirará em <strong>30 dias</strong>.
        </p>

        <InputText
          :value="linkCompartilhamento"
          readonly
          class="w-full font-mono text-xs select-all"
          @focus="$event.target.select()"
        />

        <div class="flex gap-2 justify-end">
          <Button
            label="Copiar Link"
            icon="pi pi-copy"
            severity="secondary"
            @click="copiarLink"
          />
          <Button
            label="WhatsApp"
            icon="pi pi-whatsapp"
            severity="success"
            @click="enviarWhatsApp"
          />
        </div>

        <hr class="border-gray-200">

        <!-- Envio por e-mail -->
        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wider -mb-2">Enviar por E-mail</p>
        <div class="flex gap-2">
          <InputText
            v-model="emailDestino"
            placeholder="Digite o e-mail do destinatário..."
            class="flex-1"
            type="email"
          />
          <Button
            label="Enviar"
            icon="pi pi-envelope"
            severity="primary"
            :loading="enviandoEmail"
            @click="enviarEmailAutos"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end">
          <Button
            label="Fechar"
            text
            severity="secondary"
            @click="modalAutosVisivel = false"
          />
        </div>
      </template>
    </Dialog>

    <!-- ════════════════ MODAL DE TRAMITAÇÃO COM MOTIVO ════════════════ -->
    <Dialog
      v-model:visible="exibirModalTramitacao"
      modal
      :header="dadosTramitacao.titulo"
      :style="{ width: '32rem' }"
    >
      <div class="flex flex-col gap-3 pt-2">
        <p class="text-sm text-gray-600">
          Adicione uma observação ou justificativa para esta ação (Opcional).
        </p>
        <Textarea
          v-model="dadosTramitacao.motivo"
          rows="4"
          placeholder="Digite sua observação..."
          class="w-full"
          autofocus
        />
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button label="Cancelar" text severity="secondary" @click="exibirModalTramitacao = false" />
          <Button
            label="Confirmar"
            icon="pi pi-check"
            :severity="dadosTramitacao.status === 'REJEITADO' ? 'danger' : 'primary'"
            :loading="loading"
            @click="confirmarTramitacao"
          />
        </div>
      </template>
    </Dialog>

  </div>
</template>

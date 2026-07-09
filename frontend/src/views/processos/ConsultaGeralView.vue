<script setup>
import { ref, onActivated, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { useAuthStore } from '@/stores/auth'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import MultiSelect from 'primevue/multiselect'
import DatePicker from 'primevue/datepicker' // ou Calendar dependendo da versão do PrimeVue
import Dialog from 'primevue/dialog'
import Checkbox from 'primevue/checkbox'
import Tag from 'primevue/tag'
import api from '@/services/api'

const router = useRouter()
const toast = useToast()
const authStore = useAuthStore()

const processos = ref([])
const totalRecords = ref(0)
const loading = ref(false)

// Dados para os Selects
const tiposDocumento = ref([])
const procuradores = ref([])
const statusOpcoes = [
  { label: 'Aguardando Distribuição', value: 'AGUARDANDO_DISTRIBUICAO' },
  { label: 'Em Análise', value: 'EM_ANALISE' },
  { label: 'Em Diligência', value: 'EM_DILIGENCIA' },
  { label: 'Devolvido', value: 'DEVOLVIDO' },
  { label: 'Concluído', value: 'CONCLUIDO' },
  { label: 'Finalizado', value: 'FINALIZADO' },
  { label: 'Rejeitado', value: 'REJEITADO' },
  { label: 'Arquivado', value: 'ARQUIVADO' },
]

// RBAC: Filtro de procurador só aparece para Chefia/Superuser
const _CHEFIAS = ['Protocolador-Chefe', 'Procurador-Chefe', 'Procurador-Analista']
const currentUser = computed(() => authStore.user ?? { grupos: [], is_superuser: false })
const isChefiaOrSuper = computed(() => 
  _CHEFIAS.some(c => currentUser.value.grupos?.includes(c)) || !!currentUser.value.is_superuser
)

// Estado dos Filtros
const filtros = ref({
  numeracao: '',
  envolvido: '',
  data_inicio: null,
  data_fim: null,
  status: [],
  tipo_processo: null,
  procurador_atribuido: null
})

// ── Helpers ────────────────────────────────────────────────────────
function formatarDataISO(data) {
  if (!data) return null
  const d = new Date(data)
  return d.toISOString().split('T')[0]
}

function formatarDataBR(iso) {
  if (!iso) return '—'
  const [ano, mes, dia] = iso.substring(0, 10).split('-')
  return `${dia}/${mes}/${ano}`
}

function formatarInteressados(infoList) {
  if (!infoList || infoList.length === 0) return '—'
  const nomes = infoList.map(i => i.nome)
  return nomes.length > 2 ? `${nomes[0]}, ${nomes[1]}...` : nomes.join(', ')
}

function statusSeverity(status) {
  const map = {
    AGUARDANDO_DISTRIBUICAO: 'secondary',
    EM_ANALISE: 'info',
    EM_DILIGENCIA: 'warn',
    CONCLUIDO: 'success',
    FINALIZADO: 'success',
    ARQUIVADO: 'secondary',
    REJEITADO: 'danger',
    DEVOLVIDO: 'danger',
  }
  return map[status] ?? 'secondary'
}

// ── Funções de Busca e Limpeza ─────────────────────────────────────
function limparFiltros() {
  filtros.value = {
    numeracao: '', envolvido: '', data_inicio: null, data_fim: null,
    status: [], tipo_processo: null, procurador_atribuido: null
  }
  carregarProcessos(1)
}

function realizarBusca() {
  carregarProcessos(1)
}

async function carregarProcessos(page = 1) {
  loading.value = true
  try {
    // Monta os query parameters ignorando campos vazios
    const params = new URLSearchParams()
    params.append('page', page)

    if (filtros.value.numeracao) params.append('numeracao', filtros.value.numeracao)
    if (filtros.value.envolvido) params.append('envolvido', filtros.value.envolvido)
    if (filtros.value.data_inicio) params.append('data_inicio', formatarDataISO(filtros.value.data_inicio))
    if (filtros.value.data_fim) params.append('data_fim', formatarDataISO(filtros.value.data_fim))
    if (filtros.value.tipo_processo) params.append('tipo_processo', filtros.value.tipo_processo)
    if (filtros.value.procurador_atribuido) params.append('procurador_atribuido', filtros.value.procurador_atribuido)
    
    // Status (array para string separada por vírgula)
    if (filtros.value.status && filtros.value.status.length > 0) {
      params.append('status__in', filtros.value.status.join(','))
    }

    const { data } = await api.get(`gestao/processos/?${params.toString()}`)
    processos.value = data.results ?? data
    totalRecords.value = data.count ?? processos.value.length
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro na busca', detail: 'Falha ao buscar processos.', life: 5000 })
  } finally {
    loading.value = false
  }
}

function onPage(event) {
  carregarProcessos(event.page + 1)
}

// ── Init ───────────────────────────────────────────────────────────
onMounted(async () => {
  carregarProcessos(1)
  try {
    const resTipos = await api.get('cadastros/tipos-documento/')
    tiposDocumento.value = resTipos.data.results ?? resTipos.data
    
    if (isChefiaOrSuper.value) {
      const resProc = await api.get('auth/procuradores/')
      procuradores.value = resProc.data.results ?? resProc.data
    }
  } catch (e) {
    console.error('Erro ao carregar dados auxiliares', e)
  }
})

// Atualiza dados silenciosamente ao retornar de uma rota de detalhe
onActivated(() => carregarProcessos(1))

// ══════════════════ Geração de Autos em Lote ═══════════════════

const LIMITE_LOTE = 10
const modoLote    = ref(false)
const selecaoLote = ref(new Map()) // Map<id, processoData> — persiste entre mudanças de filtro

const selecaoCount      = computed(() => selecaoLote.value.size)
const resultadosSucesso = computed(() => resultadosLote.value.filter(r => !r.erro))
const resultadosErro    = computed(() => resultadosLote.value.filter(r =>  r.erro))

// Quando ativo, a tabela exibe somente os processos marcados (sem chamar o backend)
const verApenasSelecao  = ref(false)
const processosExibidos = computed(() =>
  verApenasSelecao.value
    ? Array.from(selecaoLote.value.values())
    : processos.value
)

// Progresso de geração
const modalProgressoVisivel = ref(false)
const progressoAtual        = ref(0)
const progressoTotal        = ref(0)
const resultadosLote        = ref([])

// Modal de resultado
const modalResultadoLote = ref(false)
const emailDestinoLote   = ref('')
const enviandoEmailLote  = ref(false)

function toggleModoLote() {
  modoLote.value = !modoLote.value
  if (!modoLote.value) {
    selecaoLote.value  = new Map()
    verApenasSelecao.value = false
  }
}

function toggleSelecaoProcesso(proc) {
  const map = new Map(selecaoLote.value)
  if (map.has(proc.id)) {
    map.delete(proc.id)
  } else if (map.size < LIMITE_LOTE) {
    map.set(proc.id, proc)
  } else {
    toast.add({
      severity: 'warn',
      summary:  'Limite atingido',
      detail:   `Máximo de ${LIMITE_LOTE} processos por geração.`,
      life:     3000,
    })
    return
  }
  selecaoLote.value = map
}

function isProcessoSelecionado(id) {
  return selecaoLote.value.has(id)
}

function acessarProcesso(proc) {
  if (modoLote.value) {
    // No modo lote: abre em nova aba para não perder a seleção.
    // sessionStorage não é compartilhado entre abas, por isso depositamos
    // o token em localStorage._new_tab_token antes de abrir.
    // O auth store da nova aba consome essa chave de uso único na hidratação.
    const token = localStorage.getItem('token') || sessionStorage.getItem('token')
    if (token) {
      localStorage.setItem('_new_tab_token', token)
      // Safety-net: remove caso a nova aba não consiga consumir
      setTimeout(() => localStorage.removeItem('_new_tab_token'), 10_000)
    }
    const resolved = router.resolve({ name: 'detalhes-processo', params: { id: proc.id } })
    window.open(resolved.href, '_blank', 'noopener,noreferrer')
  } else {
    router.push({ name: 'detalhes-processo', params: { id: proc.id } })
  }
}

async function confirmarGeracaoLote() {
  const lista = Array.from(selecaoLote.value.values())
  progressoTotal.value        = lista.length
  progressoAtual.value        = 0
  resultadosLote.value        = []
  // Limpa modo lote antes de processar para liberar a UI
  modoLote.value              = false
  selecaoLote.value           = new Map()
  modalProgressoVisivel.value = true

  for (const proc of lista) {
    try {
      const { data } = await api.post(`gestao/processos/${proc.id}/gerar-link/`)
      resultadosLote.value.push({
        id:               proc.id,
        numero_protocolo: proc.numero_protocolo,
        numero_origem:    proc.numero_origem,
        link:             `${window.location.origin}/autos/${data.token}`,
        url_download:     data.url_publica || null,
        erro:             null,
      })
    } catch {
      resultadosLote.value.push({
        id:               proc.id,
        numero_protocolo: proc.numero_protocolo,
        numero_origem:    proc.numero_origem,
        link:             null,
        url_download:     null,
        erro:             'Falha ao gerar',
      })
    }
    progressoAtual.value++
  }

  modalProgressoVisivel.value = false
  modalResultadoLote.value    = true
}

function copiarLinkItem(link) {
  navigator.clipboard.writeText(link).then(() => {
    toast.add({ severity: 'success', summary: 'Copiado!', detail: 'Link copiado.', life: 2000 })
  })
}

function baixarItem(url) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

function copiarTodosLinks() {
  const texto = resultadosLote.value
    .filter(r => r.link)
    .map(r => `${r.numero_origem || r.numero_protocolo}: ${r.link}`)
    .join('\n')
  navigator.clipboard.writeText(texto).then(() => {
    toast.add({ severity: 'success', summary: 'Copiado!', detail: 'Todos os links copiados.', life: 3000 })
  })
}

function enviarWhatsAppLote() {
  const itens = resultadosLote.value
    .filter(r => r.link)
    .map(r => `• ${r.numero_origem || r.numero_protocolo}: ${r.link}`)
    .join('\n')
  const texto = encodeURIComponent(
    `Autos Digitais — ${resultadosSucesso.value.length} processo(s):\n\n${itens}\n\nLinks válidos por 30 dias.`
  )
  window.open(`https://api.whatsapp.com/send?text=${texto}`, '_blank')
}

async function enviarEmailLote() {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(emailDestinoLote.value)) {
    toast.add({ severity: 'warn', summary: 'E-mail inválido', detail: 'Informe um endereço válido.', life: 3000 })
    return
  }
  const processosOk = resultadosLote.value
    .filter(r => r.link)
    .map(r => ({ numero: r.numero_origem || r.numero_protocolo, link: r.link }))
  if (!processosOk.length) return

  enviandoEmailLote.value = true
  try {
    await api.post('gestao/processos/enviar-autos-lote-email/', {
      email:     emailDestinoLote.value,
      processos: processosOk,
    })
    toast.add({
      severity: 'success',
      summary:  'E-mail enviado!',
      detail:   `${processosOk.length} link(s) enviados para ${emailDestinoLote.value}.`,
      life:     4000,
    })
    emailDestinoLote.value = ''
  } catch {
    toast.add({ severity: 'error', summary: 'Erro ao enviar', detail: 'Não foi possível enviar o e-mail.', life: 5000 })
  } finally {
    enviandoEmailLote.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-6 p-6">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-gray-900">Consulta Geral</h1>
        <p class="text-sm text-gray-500 mt-0.5">Busque e filtre todos os processos do sistema.</p>
      </div>
      <Button
        :label="modoLote ? 'Cancelar Seleção' : 'Gerar Autos em Lote'"
        :icon="modoLote ? 'pi pi-times' : 'pi pi-file-pdf'"
        :severity="modoLote ? 'danger' : 'primary'"
        outlined
        size="small"
        @click="toggleModoLote"
      />
    </div>

    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex flex-col gap-4">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase">Numeração (Prot / Orig / SEI)</label>
          <InputText v-model="filtros.numeracao" placeholder="Ex: 2026-001 ou SEI" @keyup.enter="realizarBusca" />
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase">Envolvido (Nome)</label>
          <InputText v-model="filtros.envolvido" placeholder="Remetente ou Interessado" @keyup.enter="realizarBusca" />
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase">Período (Início)</label>
          <DatePicker v-model="filtros.data_inicio" dateFormat="dd/mm/yy" placeholder="Selecione..." showIcon />
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase">Período (Fim)</label>
          <DatePicker v-model="filtros.data_fim" dateFormat="dd/mm/yy" placeholder="Selecione..." showIcon />
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase">Tipo de Processo</label>
          <Select v-model="filtros.tipo_processo" :options="tiposDocumento" optionLabel="descricao" optionValue="id" placeholder="Todos" showClear />
        </div>

        <div class="flex flex-col gap-1.5 lg:col-span-2">
          <label class="text-xs font-semibold text-gray-500 uppercase">Status</label>
          <MultiSelect v-model="filtros.status" :options="statusOpcoes" optionLabel="label" optionValue="value" placeholder="Qualquer status" :maxSelectedLabels="3" class="w-full" />
        </div>

        <div v-if="isChefiaOrSuper" class="flex flex-col gap-1.5">
          <label class="text-xs font-semibold text-gray-500 uppercase">Procurador</label>
          <Select v-model="filtros.procurador_atribuido" :options="procuradores" optionLabel="nome" optionValue="id" placeholder="Qualquer procurador" showClear />
        </div>

      </div>

      <div class="flex justify-end gap-2 pt-2 border-t border-gray-50 mt-2">
        <Button label="Limpar Filtros" icon="pi pi-filter-slash" text severity="secondary" @click="limparFiltros" />
        <Button label="Buscar Processos" icon="pi pi-search" severity="primary" @click="realizarBusca" :loading="loading" />
      </div>
    </div>

    <!-- Banner de seleção: visível apenas no modo lote -->
    <div
      v-if="modoLote"
      class="flex items-center justify-between bg-blue-50 border border-blue-200 rounded-xl px-5 py-3"
    >
      <div class="flex items-center gap-3 text-sm text-blue-800">
        <i class="pi pi-check-square text-blue-500" />
        <span>
          <strong>{{ selecaoCount }}</strong> de <strong>{{ LIMITE_LOTE }}</strong> processos selecionados
          <span v-if="selecaoCount === LIMITE_LOTE" class="ml-2 text-xs text-blue-600 font-medium">(limite atingido)</span>
        </span>
      </div>
      <div class="flex items-center gap-2">
        <Button
          :label="verApenasSelecao ? 'Ver todos os resultados' : `Ver ${selecaoCount} selecionado(s)`"
          :icon="verApenasSelecao ? 'pi pi-list' : 'pi pi-eye'"
          severity="secondary"
          size="small"
          outlined
          :disabled="selecaoCount === 0"
          @click="verApenasSelecao = !verApenasSelecao"
        />
        <Button
          label="Confirmar Geração"
          icon="pi pi-file-pdf"
          severity="primary"
          size="small"
          :disabled="selecaoCount === 0"
          @click="confirmarGeracaoLote"
        />
      </div>
    </div>

    <div class="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <DataTable
        :value="processosExibidos"
        :loading="loading && !verApenasSelecao"
        :lazy="!verApenasSelecao"
        :paginator="!verApenasSelecao"
        :rows="20"
        :totalRecords="totalRecords"
        @page="onPage"
        paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
        currentPageReportTemplate="{first}–{last} de {totalRecords} processos"
        :rowHover="true"
        stripedRows
        emptyMessage="Nenhum processo encontrado com os filtros informados."
        class="text-sm"
      >
        <!-- Coluna de seleção: visível apenas no modo Gerar em Lote -->
        <Column v-if="modoLote" style="width: 3.5rem; min-width: 3.5rem">
          <template #body="{ data }">
            <Checkbox
              :modelValue="isProcessoSelecionado(data.id)"
              :binary="true"
              @update:modelValue="() => toggleSelecaoProcesso(data)"
            />
          </template>
        </Column>

        <Column header="Nº Origem / SEI" style="min-width: 12rem">
          <template #body="{ data }">
            <div class="flex flex-col">
              <span class="text-gray-800 font-medium">{{ data.numero_origem || '—' }}</span>
              <span v-if="data.numero_sei" class="text-xs text-gray-500 mt-0.5" title="Número SEI">
                {{ data.numero_sei }}
              </span>
            </div>
          </template>
        </Column>

        <Column field="tipo_processo_descricao" header="Tipo" style="min-width: 12rem">
          <template #body="{ data }"><span class="text-gray-700">{{ data.tipo_processo_descricao ?? '—' }}</span></template>
        </Column>

        <Column header="Interessados" style="min-width: 14rem">
          <template #body="{ data }"><span class="text-gray-700">{{ formatarInteressados(data.interessados_info) }}</span></template>
        </Column>

        <Column field="status" header="Status" style="min-width: 10rem">
          <template #body="{ data }"><Tag :value="data.status_display" :severity="statusSeverity(data.status)" class="text-xs" /></template>
        </Column>

        <Column header="Ações" style="min-width: 4rem; text-align: right" alignFrozen="right">
          <template #body="{ data }">
            <Button
              label="Acessar"
              icon="pi pi-folder-open"
              text
              class="!bg-blue-50 hover:!bg-blue-100 !text-blue-700 !text-xs font-medium !py-1.5 !px-3 rounded-lg transition-colors"
              :title="modoLote ? 'Abrir em nova aba (seleção não será perdida)' : `Acessar processo ${data.numero_protocolo}`"
              @click="acessarProcesso(data)"
            />
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- ════ MODAL: PROGRESSO DE GERAÇÃO ════ -->
    <Dialog
      v-model:visible="modalProgressoVisivel"
      modal
      :closable="false"
      header="Gerando Autos Digitais..."
      :style="{ width: '32rem' }"
    >
      <div class="flex flex-col gap-5 py-2">
        <div class="flex items-center gap-3">
          <i class="pi pi-spin pi-spinner text-blue-500 text-lg" />
          <span class="text-sm text-gray-700">
            Processando <strong>{{ progressoAtual }} de {{ progressoTotal }}</strong> processos...
          </span>
        </div>
        <!-- Barra de progresso manual -->
        <div class="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
          <div
            class="h-3 rounded-full bg-blue-500 transition-all duration-500"
            :style="{ width: progressoTotal ? ((progressoAtual / progressoTotal) * 100) + '%' : '0%' }"
          />
        </div>
        <p class="text-xs text-gray-400 text-center">Por favor, aguarde e não feche esta página.</p>
      </div>
    </Dialog>

    <!-- ════ MODAL: RESULTADO EM LOTE ════ -->
    <Dialog
      v-model:visible="modalResultadoLote"
      modal
      header="Autos Digitais Gerados em Lote"
      :style="{ width: '44rem' }"
      :breakpoints="{ '640px': '95vw' }"
    >
      <div class="flex flex-col gap-5 pt-2">

        <!-- Resumo -->
        <div class="text-sm text-gray-700">
          <span class="font-semibold text-green-700">{{ resultadosSucesso.length }}</span> gerado(s) com sucesso
          <template v-if="resultadosErro.length">
            · <span class="font-semibold text-red-600">{{ resultadosErro.length }}</span> com falha
          </template>
        </div>

        <!-- Lista de resultados -->
        <div class="flex flex-col gap-2 max-h-52 overflow-y-auto pr-1">
          <div
            v-for="r in resultadosLote"
            :key="r.id"
            class="flex items-center justify-between p-3 rounded-lg border"
            :class="r.erro ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200'"
          >
            <div class="flex items-center gap-2 min-w-0">
              <i :class="['pi text-sm shrink-0', r.erro ? 'pi-times-circle text-red-500' : 'pi-check-circle text-green-500']" />
              <span class="text-sm font-medium text-gray-800">
                {{ r.numero_origem || r.numero_protocolo }}
              </span>
              <span v-if="r.erro" class="text-xs text-red-500 ml-1">· {{ r.erro }}</span>
            </div>
            <div v-if="r.link" class="flex items-center gap-1 shrink-0">
              <Button
                icon="pi pi-copy"
                text
                rounded
                size="small"
                severity="secondary"
                title="Copiar link"
                @click="copiarLinkItem(r.link)"
              />
              <Button
                v-if="r.url_download"
                icon="pi pi-download"
                text
                rounded
                size="small"
                severity="info"
                title="Baixar PDF"
                @click="baixarItem(r.url_download)"
              />
            </div>
          </div>
        </div>

        <!-- Ações em lote -->
        <div class="flex flex-wrap gap-2 pt-2 border-t border-gray-100">
          <Button
            label="Copiar todos os links"
            icon="pi pi-copy"
            severity="secondary"
            size="small"
            :disabled="!resultadosSucesso.length"
            @click="copiarTodosLinks"
          />
          <Button
            label="WhatsApp"
            icon="pi pi-whatsapp"
            severity="success"
            size="small"
            :disabled="!resultadosSucesso.length"
            @click="enviarWhatsAppLote"
          />
        </div>

        <!-- Envio por e-mail -->
        <div class="flex flex-col gap-2">
          <p class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Enviar por E-mail</p>
          <div class="flex gap-2">
            <InputText
              v-model="emailDestinoLote"
              placeholder="E-mail do destinatário..."
              type="email"
              class="flex-1"
            />
            <Button
              label="Enviar"
              icon="pi pi-envelope"
              severity="primary"
              size="small"
              :loading="enviandoEmailLote"
              :disabled="!resultadosSucesso.length"
              @click="enviarEmailLote"
            />
          </div>
        </div>

      </div>

      <template #footer>
        <div class="flex justify-end">
          <Button label="Fechar" text severity="secondary" @click="modalResultadoLote = false" />
        </div>
      </template>
    </Dialog>

  </div>
</template>
<script setup>
import { ref, onActivated, onMounted, computed } from 'vue'
import { useRouter }     from 'vue-router'
import { useToast }      from 'primevue/usetoast'
import Button      from 'primevue/button'
import Column      from 'primevue/column'
import DataTable   from 'primevue/datatable'
import Dialog      from 'primevue/dialog'
import InputText   from 'primevue/inputtext'
import Select      from 'primevue/select'
import Tag         from 'primevue/tag'
import api         from '@/services/api'
import GerenciadorDiligencias from '@/components/shared/GerenciadorDiligencias.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const toast  = useToast()
const authStore = useAuthStore()

// ── RBAC: Controle de Acesso ────────────────────────────────────────────────
const currentUser = computed(() => authStore.user ?? { grupos: [], is_superuser: false })
const _CHEFIAS = ['Protocolador-Chefe', 'Procurador-Chefe', 'Procurador-Analista']
const isChefiaOrSuper = computed(() =>
  _CHEFIAS.some(c => currentUser.value.grupos?.includes(c)) || !!currentUser.value.is_superuser
)

// ── Estado da tabela ────────────────────────────────────────────────────
const diligencias  = ref([])
const loading      = ref(false)
const totalRecords = ref(0)
const filtros      = ref({ numeracao: '', status: null })

// ── Estado do modal In-Place ────────────────────────────────────────────
const modalVisivel        = ref(false)
const processoSelecionado = ref(null)
const diligenciaAtual     = ref(null)
const loadingModal        = ref(false)

// ── Opções de status ────────────────────────────────────────────────────
const opcoesStatus = [
  { label: 'Pendente',  value: 'PENDENTE'  },
  { label: 'Enviada',   value: 'ENVIADA'   },
  { label: 'Atendida',  value: 'ATENDIDA'  },
  { label: 'Rejeitada', value: 'REJEITADA' },
]

// ── Helpers ─────────────────────────────────────────────────────────────────
function formatarData(iso) {
  if (!iso) return '—'
  const [ano, mes, dia] = iso.substring(0, 10).split('-')
  return `${dia}/${mes}/${ano}`
}

function calcularDiasEspera(dataSolicitacao, status) {
  // Se já foi resolvida, não contamos mais o tempo de espera
  if (['ATENDIDA', 'REJEITADA'].includes(status)) return null
  if (!dataSolicitacao) return null

  // Extraímos apenas a data "YYYY-MM-DD" e comparamos com a meia-noite de hoje
  const dataBase = new Date(dataSolicitacao.substring(0, 10) + 'T00:00:00')
  const hoje = new Date()
  hoje.setHours(0, 0, 0, 0)

  const diffTime = hoje - dataBase
  const dias = Math.floor(diffTime / (1000 * 60 * 60 * 24))

  return dias >= 0 ? dias : 0
}

function statusSeverity(status) {
  const map = { PENDENTE: 'warn', ENVIADA: 'info', ATENDIDA: 'success', REJEITADA: 'danger' }
  return map[status] ?? 'secondary'
}

function statusLabel(status) {
  const map = { PENDENTE: 'Pendente', ENVIADA: 'Enviada', ATENDIDA: 'Atendida', REJEITADA: 'Rejeitada' }
  return map[status] ?? status
}

// ── Filtros ─────────────────────────────────────────────────────────────────
function realizarBusca() { carregarDiligencias(1) }

function limparFiltros() {
  filtros.value = { numeracao: '', status: null }
  carregarDiligencias(1)
}

// ── Carga da listagem ────────────────────────────────────────────────────
async function carregarDiligencias(page = 1) {
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.append('page', page)

    if (filtros.value.numeracao?.trim()) params.append('numeracao', filtros.value.numeracao.trim())

    // Padrão: lista apenas PENDENTE e ENVIADA; usuário pode filtrar ATENDIDA/REJEITADA
    if (filtros.value.status) {
      params.append('status', filtros.value.status)
    } else {
      params.append('status__in', 'PENDENTE,ENVIADA')
    }

    const { data } = await api.get(`gestao/diligencias/?${params.toString()}`)
    diligencias.value  = data.results ?? data
    totalRecords.value = data.count    ?? diligencias.value.length
  } catch {
    toast.add({ severity: 'error', summary: 'Erro ao carregar', detail: 'Não foi possível buscar as diligências.', life: 4000 })
    diligencias.value = []
  } finally {
    loading.value = false
  }
}

function onPage(event) { carregarDiligencias(event.page + 1) }

// ── Abrir gerenciador (fetch do processo) ─────────────────────────────────
async function abrirGerenciador(diligencia) {
  loadingModal.value    = true
  modalVisivel.value    = true
  diligenciaAtual.value = diligencia
  processoSelecionado.value = null

  try {
    const { data } = await api.get(`gestao/processos/${diligencia.processo_id}/`)
    processoSelecionado.value = data
  } catch {
    modalVisivel.value = false
  } finally {
    loadingModal.value = false
  }
}

onMounted(() => carregarDiligencias(1))

// Atualiza dados silenciosamente ao retornar de uma rota de detalhe
onActivated(() => carregarDiligencias(1))
</script>

<template>
  <div class="p-6 flex flex-col gap-6">

    <!-- Cabeçalho -->
    <div>
      <h1 class="text-xl font-bold text-gray-900">Controle de Diligências</h1>
      <p class="text-sm text-gray-400 mt-0.5">Painel centralizado de diligências em aberto.</p>
    </div>

    <!-- Barra de filtros -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex flex-col md:flex-row gap-3 items-center">
      <div class="w-full md:w-64">
        <InputText
          v-model="filtros.numeracao"
          placeholder="Protocolo, Origem ou SEI..."
          class="w-full text-sm"
          @keyup.enter="realizarBusca"
        />
      </div>

      <div class="w-full md:w-56">
        <Select
          v-model="filtros.status"
          :options="opcoesStatus"
          optionLabel="label"
          optionValue="value"
          placeholder="Pendente + Enviada"
          showClear
          class="w-full text-sm"
          @change="realizarBusca"
        />
      </div>

      <div class="flex gap-2 w-full md:w-auto md:ml-auto mt-2 md:mt-0">
        <Button
          v-if="filtros.numeracao || filtros.status"
          icon="pi pi-filter-slash"
          text
          severity="secondary"
          size="small"
          title="Limpar filtros"
          @click="limparFiltros"
        />
        <Button
          icon="pi pi-search"
          label="Buscar"
          severity="primary"
          size="small"
          :loading="loading"
          class="w-full md:w-auto"
          @click="realizarBusca"
        />
      </div>
    </div>

    <!-- Tabela -->
    <div class="bg-white rounded-xl border border-gray-100 overflow-hidden">
      <DataTable
        :value="diligencias"
        :loading="loading"
        lazy
        :paginator="true"
        :rows="20"
        :totalRecords="totalRecords"
        @page="onPage"
        paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
        currentPageReportTemplate="{first}–{last} de {totalRecords} diligências"
        :rowHover="true"
        stripedRows
        responsiveLayout="scroll"
        class="text-sm"
        emptyMessage="Nenhuma diligência encontrada."
      >
        <!-- Nº Origem / SEI -->
        <Column header="Nº Origem / SEI" style="min-width: 10rem">
          <template #body="{ data }">
            <div class="flex flex-col gap-0.5">
              <span class="text-gray-800 font-medium text-xs">
                {{ data.numero_origem || '—' }}
              </span>
              <span v-if="data.numero_sei" class="text-xs text-gray-400 flex items-center gap-1">
                {{ data.numero_sei }}
              </span>
            </div>
          </template>
        </Column>

        <!-- Descrição -->
        <Column header="Descrição da Necessidade" style="min-width: 14rem">
          <template #body="{ data }">
            <p class="truncate max-w-xs text-sm text-gray-700" :title="data.descricao_necessidade">
              {{ data.descricao_necessidade || '—' }}
            </p>
          </template>
        </Column>

        <!-- Data + dias de espera -->
        <Column header="Data da Solicitação" style="min-width: 12rem">
          <template #body="{ data }">
            <div class="flex flex-col gap-0.5">
              <span class="text-sm text-gray-700">{{ formatarData(data.data_solicitacao) }}</span>
              
              <span
                v-if="calcularDiasEspera(data.data_solicitacao, data.status) !== null"
                class="text-xs font-medium flex items-center mt-0.5"
                :class="calcularDiasEspera(data.data_solicitacao, data.status) > 0 ? 'text-red-500' : 'text-amber-500'"
              >
                <i class="pi pi-clock mr-1" style="font-size: 0.7rem"></i>
                {{ calcularDiasEspera(data.data_solicitacao, data.status) === 0
                   ? 'Solicitada hoje'
                   : `${calcularDiasEspera(data.data_solicitacao, data.status)} dia(s) em aberto`
                }}
              </span>
            </div>
          </template>
        </Column>

        <!-- Status -->
        <Column header="Status" style="min-width: 8rem">
          <template #body="{ data }">
            <Tag :value="statusLabel(data.status)" :severity="statusSeverity(data.status)" class="text-xs" />
          </template>
        </Column>

        <!-- Ações -->
        <Column header="Ações" style="min-width: 12rem; text-align: right" alignFrozen="right">
          <template #body="{ data }">
            <div class="flex gap-1 justify-end">
              <Button
                label="Acessar"
                icon="pi pi-folder-open"
                text
                class="!bg-blue-50 hover:!bg-blue-100 !text-blue-700 !text-xs font-medium !py-1.5 !px-3 rounded-lg transition-colors"
                :title="`Acessar processo ${data.numero_protocolo}`"
                @click="router.push({ name: 'detalhes-processo', params: { id: data.processo_id } })"
              />
              <Button
                v-if="['PENDENTE', 'ENVIADA'].includes(data.status) && isChefiaOrSuper"
                label="Gerenciar"
                icon="pi pi-cog"
                outlined
                size="small"
                @click="abrirGerenciador(data)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- Modal In-Place -->
    <Dialog
      v-model:visible="modalVisivel"
      modal
      header=" "
      :style="{ width: '50vw' }"
      :breakpoints="{ '960px': '75vw', '641px': '100vw' }"
    >
      <div v-if="loadingModal" class="p-6 flex justify-center">
        <i class="pi pi-spin pi-spinner text-3xl text-blue-500" />
      </div>
      <GerenciadorDiligencias
        v-else-if="processoSelecionado && diligenciaAtual"
        :diligencia="diligenciaAtual"
        :processo="processoSelecionado"
        :anexos-globais="processoSelecionado.anexos || []"
        @sucesso="() => { modalVisivel = false; carregarDiligencias() }"
      />
    </Dialog>

  </div>
</template>

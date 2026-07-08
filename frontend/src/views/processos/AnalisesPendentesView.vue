<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const router    = useRouter()
const route     = useRoute()
const toast     = useToast()
const authStore = useAuthStore()

const currentUser    = computed(() => authStore.user ?? { grupos: [], is_superuser: false })
const _CHEFIAS       = ['Protocolador-Chefe', 'Procurador-Chefe', 'Procurador-Analista']
const isChefiaOrSuper = computed(() =>
  _CHEFIAS.some(c => currentUser.value.grupos?.includes(c)) || !!currentUser.value.is_superuser
)
// ── Estado dos Filtros ───────────────────────────────────────────────────────
const filtros = ref({
  numeracao: '',
  envolvido: '',
  status: null
})

// Opções dinâmicas de status para a fila de análises
const statusOpcoes = computed(() => {
  const base = [
    { label: 'Em Análise', value: 'EM_ANALISE' },
    { label: 'Em Diligência', value: 'EM_DILIGENCIA' },
    { label: 'Rejeitado', value: 'REJEITADO' }
  ]
  if (isChefiaOrSuper.value) {
    base.push({ label: 'Concluído', value: 'CONCLUIDO' })
  }
  return base
})

function realizarBusca() {
  carregarProcessos(1)
}

function limparFiltros() {
  filtros.value = { numeracao: '', envolvido: '', status: null }
  carregarProcessos(1)
}

const processos    = ref([])
const totalRecords = ref(0)
const loading      = ref(false)

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatarInteressados(infoList) {
  if (!infoList || infoList.length === 0) return '—'
  const nomes = infoList.map(i => i.nome)
  return nomes.length > 2 ? `${nomes[0]}, ${nomes[1]}...` : nomes.join(', ')
}

function statusSeverity(status) {
  const map = {
    AGUARDANDO_DISTRIBUICAO: 'secondary',
    EM_ANALISE:              'info',
    EM_DILIGENCIA:           'warn',
    CONCLUIDO:               'success',
    ARQUIVADO:               'secondary',
    REJEITADO:               'danger',
    DEVOLVIDO:               'danger',
  }
  return map[status] ?? 'secondary'
}

/**
 * Formata uma data ISO (yyyy-mm-dd ou ISO 8601) para DD/MM/AAAA.
 * Retorna '—' quando o valor estiver ausente.
 */
function formatarData(iso) {
  if (!iso) return '—'
  const [ano, mes, dia] = iso.substring(0, 10).split('-')
  return `${dia}/${mes}/${ano}`
}




/**
 * Ordena a lista de processos:
 * 1º por prioridade de status (Chefia vê Concluído no topo; demais veem Rejeitado primeiro)
 * 2º dentro do mesmo status, pela data_limite crescente (urgência → prazo menor = mais urgente)
 *    Processos sem data_limite ficam no final do bloco.
 */
function ordenarProcessos(lista) {
  const ordemChefia = {
    CONCLUIDO:               0,
    REJEITADO:               1,
    EM_ANALISE:              2,
    EM_DILIGENCIA:           3,
    DEVOLVIDO:               4,
    ARQUIVADO:               5,
    AGUARDANDO_DISTRIBUICAO: 6,
  }
  const ordemProcurador = {
    REJEITADO:               0,
    EM_ANALISE:              1,
    EM_DILIGENCIA:           2,
    DEVOLVIDO:               3,
    ARQUIVADO:               4,
    AGUARDANDO_DISTRIBUICAO: 5,
    CONCLUIDO:               6,
  }
  const ordem = isChefiaOrSuper.value ? ordemChefia : ordemProcurador

  return [...lista].sort((a, b) => {
    const pa = ordem[a.status] ?? 99
    const pb = ordem[b.status] ?? 99
    if (pa !== pb) return pa - pb
    // Mesmo status → crescente por data_limite; null vai para o final
    if (!a.data_limite && !b.data_limite) return 0
    if (!a.data_limite) return 1
    if (!b.data_limite) return -1
    return a.data_limite.localeCompare(b.data_limite) // 'YYYY-MM-DD' compara corretamente como string
  })
}

/**
 * Define classes CSS dinâmicas para a linha da tabela (Tr)
 * - Verde para processos concluídos
 * - Vermelho para processos com data limite ultrapassada
 */
function rowClass(data) {
  if (!data) return ''
  
  if (data.status === 'CONCLUIDO') {
    return '!bg-green-50/60 hover:!bg-green-100/60'
  }
  
  if (data.data_limite && !['CONCLUIDO', 'ARQUIVADO'].includes(data.status)) {
    // Pega a data atual no formato YYYY-MM-DD para comparação direta e segura
    const hoje = new Date().toISOString().split('T')[0]
    if (data.data_limite < hoje) {
      return '!bg-red-50/60 hover:!bg-red-100/60'
    }
  }
  
  return ''
}

// ── Carregamento de dados ────────────────────────────────────────────────────
async function carregarProcessos(page = 1) {
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.append('page', page)

    // Filtros de texto
    if (filtros.value.numeracao) params.append('numeracao', filtros.value.numeracao)
    if (filtros.value.envolvido) params.append('envolvido', filtros.value.envolvido)

    // Lógica de Status: se escolheu um específico, usa ele. Se não, usa a base.
    if (filtros.value.status) {
      params.append('status', filtros.value.status)
    } else {
      let baseStatuses = 'EM_ANALISE,REJEITADO'
      if (isChefiaOrSuper.value) baseStatuses += ',CONCLUIDO'
      params.append('status__in', baseStatuses)
    }

    const { data } = await api.get(`gestao/processos/?${params.toString()}`)
    
    processos.value    = ordenarProcessos(data.results ?? [])
    totalRecords.value = data.count ?? processos.value.length
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: 'Erro ao carregar',
      detail: 'Não foi possível buscar as análises pendentes.',
      life: 4000,
    })
  } finally {
    loading.value = false
  }
}

// ── Paginação lazy ───────────────────────────────────────────────────────────
// O PrimeVue DataTable em modo lazy emite @page com `event.page` (0-indexed).
// O DRF PageNumberPagination usa ?page=N (1-indexed) → somamos 1.
function onPage(event) {
  carregarProcessos(event.page + 1)
}

onMounted(() => {
  if (route.query.status) {
    filtros.value.status = route.query.status
  }
  carregarProcessos(1)
})

// Atualiza dados silenciosamente ao retornar de uma rota de detalhe
onActivated(() => carregarProcessos(1))
</script>

<template>
  <div class="flex flex-col gap-6">

    <!-- Cabeçalho da página -->
    <div>
      <h1 class="text-xl font-bold text-gray-900">Análises Pendentes</h1>
      <p class="text-sm text-gray-500 mt-0.5">Processos aguardando análise do procurador.</p>
    </div>
    <!-- Barra de Filtros Rápidos -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex flex-col md:flex-row gap-3 items-center">
      <div class="w-full md:w-64">
        <InputText 
          v-model="filtros.numeracao" 
          placeholder="Buscar Numeração..." 
          class="w-full text-sm" 
          @keyup.enter="realizarBusca" 
        />
      </div>
      <div class="w-full md:w-64">
        <InputText 
          v-model="filtros.envolvido" 
          placeholder="Remetente ou Interessado..." 
          class="w-full text-sm" 
          @keyup.enter="realizarBusca" 
        />
      </div>
      <div class="w-full md:w-56">
        <Select 
          v-model="filtros.status" 
          :options="statusOpcoes" 
          optionLabel="label" 
          optionValue="value" 
          placeholder="Filtrar por Status" 
          class="w-full text-sm" 
          showClear 
          @change="realizarBusca"
        />
      </div>
      
      <div class="flex gap-2 w-full md:w-auto md:ml-auto mt-2 md:mt-0">
        <Button 
          v-if="filtros.numeracao || filtros.envolvido || filtros.status" 
          icon="pi pi-filter-slash" 
          text 
          severity="secondary" 
          size="small"
          @click="limparFiltros" 
          title="Limpar filtros"
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
    <!-- Card da tabela -->
    <div class="bg-white rounded-xl border border-gray-100 overflow-hidden">
      <DataTable
        :value="processos"
        :loading="loading"
        lazy
        :paginator="true"
        :rows="20"
        :totalRecords="totalRecords"
        @page="onPage"
        paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
        currentPageReportTemplate="{first}–{last} de {totalRecords} processos"
        :rowHover="true"
        :rowClass="rowClass"
        stripedRows
        responsiveLayout="scroll"
        emptyMessage="Nenhum processo em análise encontrado."
        class="text-sm"
      >
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
          <template #body="{ data }">
            <span class="text-gray-700">{{ data.tipo_processo_descricao ?? '—' }}</span>
          </template>
        </Column>

        <Column header="Interessados" style="min-width: 14rem">
          <template #body="{ data }">
            <span class="text-gray-700">{{ formatarInteressados(data.interessados_info) }}</span>
          </template>
        </Column>

        <Column field="data_limite" header="Data Limite" style="min-width: 9rem">
          <template #body="{ data }">
            <span :class="['font-medium', !data.data_limite && 'text-gray-400']">
              {{ formatarData(data.data_limite) }}
            </span>
          </template>
        </Column>

        <Column field="status" header="Status" style="min-width: 9rem">
          <template #body="{ data }">
            <Tag :value="data.status_display" :severity="statusSeverity(data.status)" class="text-xs shadow-sm" />
          </template>
        </Column>

        <Column header="Ações" style="min-width: 5rem; text-align: right" alignFrozen="right">
          <template #body="{ data }">
            <Button
              label="Acessar"
              icon="pi pi-folder-open"
              text
              class="!bg-blue-50 hover:!bg-blue-100 !text-blue-700 !text-xs font-medium !py-1.5 !px-3 rounded-lg transition-colors"
              :title="`Acessar processo ${data.numero_protocolo}`"
              @click="router.push({ name: 'detalhes-processo', params: { id: data.id } })"
            />
          </template>
        </Column>

      </DataTable>
    </div>

  </div>
</template>

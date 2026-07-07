<script setup>
import { ref, onMounted, computed } from 'vue'
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
</script>

<template>
  <div class="flex flex-col gap-6 p-6">
    <div>
      <h1 class="text-xl font-bold text-gray-900">Consulta Geral</h1>
      <p class="text-sm text-gray-500 mt-0.5">Busque e filtre todos os processos do sistema.</p>
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

    <div class="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
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
        stripedRows
        emptyMessage="Nenhum processo encontrado com os filtros informados."
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
              :title="`Acessar processo ${data.numero_protocolo}`"
              @click="router.push({ name: 'detalhes-processo', params: { id: data.id } })"
            />
          </template>
        </Column>
      </DataTable>
    </div>
  </div>
</template>
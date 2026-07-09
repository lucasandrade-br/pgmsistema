<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import Button      from 'primevue/button'
import Column      from 'primevue/column'
import DataTable   from 'primevue/datatable'
import MultiSelect from 'primevue/multiselect'
import Tag         from 'primevue/tag'
import Toolbar     from 'primevue/toolbar'
import api         from '@/services/api'

const router = useRouter()
const toast  = useToast()

// ── Estado ────────────────────────────────────────────────────────────────────
const processos              = ref([])
const processosSelecionados  = ref([])
const procuradores           = ref([])
const procuradoresSelecionados = ref([])
const isLoading              = ref(false)
const isSubmitting           = ref(false)

// ── Computed ──────────────────────────────────────────────────────────────────
const canDistribuir = computed(
  () => processosSelecionados.value.length > 0 && procuradoresSelecionados.value.length > 0,
)

const labelBotao = computed(() => {
  const n = processosSelecionados.value.length
  return n > 0
    ? `Distribuir ${n} Processo${n !== 1 ? 's' : ''}`
    : 'Distribuir Processos'
})
// Top-4 procuradores com maior tempo sem atribuição (já vem ordenado pela API)
const filaDistribuicao = computed(() => procuradores.value.slice(0, 4))

// Procuradores selecionados mantendo a ordem da API (idle-time order)
const procuradoresSelecionadosOrdenados = computed(() => {
  const selectedIds = new Set(procuradoresSelecionados.value.map(p => p.id))
  return procuradores.value.filter(p => selectedIds.has(p.id))
})

// Simula o round-robin e retorna a quantidade de processos por procurador
const previewDistribuicao = computed(() => {
  const n = processosSelecionados.value.length
  const lista = procuradoresSelecionadosOrdenados.value
  const m = lista.length
  if (n === 0 || m === 0) return []
  const base  = Math.floor(n / m)
  const extra = n % m
  return lista.map((p, i) => ({
    nome:       p.nome,
    quantidade: base + (i < extra ? 1 : 0),
  }))
})
// ── Carregamento de dados ──────────────────────────────────────────────────────
async function carregarDados() {
  isLoading.value = true
  try {
    const [resProcessos, resProcuradores] = await Promise.all([
      // Filtra apenas processos que ainda aguardam distribuição
      api.get('gestao/processos/?status__in=AGUARDANDO_DISTRIBUICAO,DEVOLVIDO'),
      // Lista os usuários do grupo "Procuradores" ativos
      api.get('auth/procuradores/'),
    ])

    // Suporte a resposta paginada (results) ou array direto
    processos.value    = resProcessos.data.results ?? resProcessos.data
    procuradores.value = resProcuradores.data
  } catch {
    toast.add({
      severity: 'error',
      summary:  'Erro ao carregar dados',
      detail:   'Não foi possível carregar a lista de processos ou procuradores.',
      life:     5000,
    })
  } finally {
    isLoading.value = false
  }
}

onMounted(carregarDados)

// Atualiza dados silenciosamente ao retornar de uma rota de detalhe
onActivated(carregarDados)

// ── Distribuição ──────────────────────────────────────────────────────────────
async function submitDistribuicao() {
  const processosIds    = processosSelecionados.value.map(p => p.id)
  const procuradoresIds = procuradoresSelecionados.value.map(u => u.id)

  isSubmitting.value = true
  try {
    await api.post('gestao/processos/distribuir-lote/', {
      processos_ids:    processosIds,
      procuradores_ids: procuradoresIds,
    })

    toast.add({
      severity: 'success',
      summary:  'Distribuição realizada!',
      detail:   `${processosIds.length} processo(s) distribuído(s) com sucesso.`,
      life:     5000,
    })

    // Limpa seleção e recarrega a tabela com os processos restantes
    processosSelecionados.value = []
    await carregarDados()
  } catch (err) {
    const detail =
      err.response?.data?.message ??
      err.response?.data?.detail ??
      'Verifique os dados e tente novamente.'
    toast.add({ severity: 'error', summary: 'Erro na distribuição', detail, life: 6000 })
  } finally {
    isSubmitting.value = false
  }
}

// ── Helpers de exibição ───────────────────────────────────────────────────────
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

function prioridadeSeverity(prazo_dias) {
  if (prazo_dias == null) return 'secondary'
  if (prazo_dias <= 5)   return 'danger'
  if (prazo_dias <= 15)  return 'warn'
  return 'secondary'
}

function formatarData(data) {
  if (!data) return '—'
  const [y, m, d] = data.split('-')
  return `${d}/${m}/${y}`
}
</script>

<template>
  <div class="p-6 flex flex-col gap-6">

    <!-- ── Título da página ────────────────────────────────────────────────── -->
    <div>
      <h1 class="text-xl font-bold text-gray-900">Distribuição em Lote</h1>
      <p class="text-sm text-gray-400 mt-0.5">
        Selecione os processos e os procuradores de destino. A distribuição usa Round-Robin automático.
      </p>
    </div>

    <!-- ── Toolbar de controle ─────────────────────────────────────────────── -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
      <!-- Fila de distribuição: top-4 com maior tempo sem atribuição -->
      <div v-if="filaDistribuicao.length" class="mb-3 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-gray-500">
        <span class="flex items-center gap-1 font-semibold text-gray-600">
          <i class="pi pi-sort-amount-up text-gray-400" />
          Fila de distribuição:
        </span>
        <template v-for="(p, i) in filaDistribuicao" :key="p.id">
          <span class="text-gray-700">{{ i + 1 }}. {{ p.nome }}</span>
          <span v-if="i < filaDistribuicao.length - 1" class="text-gray-300">|</span>
        </template>
      </div>
      <Toolbar class="border-0 p-0 bg-transparent">

        <template #start>
          <!--
            MultiSelect de procuradores.
            display="chip" exibe cada selecionado como uma tag removível,
            melhorando a leitura quando há múltiplos procuradores escolhidos.
          -->
          <MultiSelect
            v-model="procuradoresSelecionados"
            :options="procuradores"
            optionLabel="nome"
            placeholder="Selecione os Procuradores de destino"
            filter
            filterPlaceholder="Buscar procurador..."
            display="chip"
            class="w-full md:w-[28rem]"
            :loading="isLoading"
            :disabled="isLoading"
          />
        </template>

        <template #end>
          <Button
            :label="labelBotao"
            icon="pi pi-send"
            :disabled="!canDistribuir || isSubmitting"
            :loading="isSubmitting"
            @click="submitDistribuicao"
          />
        </template>

      </Toolbar>
    </div>

    <!-- ── Preview de distribuição ───────────────────────────────────────────── -->
    <Transition name="fade">
      <div
        v-if="previewDistribuicao.length"
        class="bg-blue-50 border border-blue-100 rounded-xl p-4"
      >
        <p class="text-xs font-semibold text-blue-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <i class="pi pi-eye" /> Preview da distribuição
        </p>
        <div class="flex flex-wrap gap-3">
          <div
            v-for="(item, i) in previewDistribuicao"
            :key="item.nome"
            class="flex items-center gap-2 bg-white border border-blue-100 rounded-lg px-3 py-2 text-sm shadow-sm"
          >
            <span class="text-xs font-bold text-blue-300">{{ i + 1 }}.</span>
            <span class="font-medium text-gray-800">{{ item.nome }}</span>
            <span class="ml-1 bg-blue-100 text-blue-700 text-xs font-semibold px-2 py-0.5 rounded-full">
              {{ item.quantidade }}&nbsp;processo{{ item.quantidade !== 1 ? 's' : '' }}
            </span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ── Tabela de processos ─────────────────────────────────────────────── -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <DataTable
        :value="processos"
        v-model:selection="processosSelecionados"
        dataKey="id"
        paginator
        :rows="50"
        :rowsPerPageOptions="[10, 20, 50]"
        paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
        :loading="isLoading"
        stripedRows
        class="w-full"
      >

        <!-- Estado vazio -->
        <template #empty>
          <div class="py-12 flex flex-col items-center gap-2 text-gray-400">
            <i class="pi pi-inbox text-4xl text-gray-300" />
            <span class="text-sm">Nenhum processo aguardando distribuição.</span>
          </div>
        </template>

        <!-- ── Colunas ──────────────────────────────────────────────────────── -->

        <!-- Checkbox de seleção múltipla -->
        <Column selectionMode="multiple" headerStyle="width: 3rem" />

        <!-- Protocolo -->
        <Column field="numero_origem" header="Nº Origem" sortable>
          <template #body="{ data }">
            <span class="font-mono text-sm font-semibold text-gray-800">
              {{ data.numero_origem || '—' }}
            </span>
          </template>
        </Column>

        <!-- Tipo de Processo (campo adicionado ao serializer nesta sprint) -->
        <Column field="tipo_processo_descricao" header="Tipo de Processo" sortable>
          <template #body="{ data }">
            <span class="text-sm text-gray-700">
              {{ data.tipo_processo_descricao ?? '—' }}
            </span>
          </template>
        </Column>

        <!-- Interessados -->
        <Column header="Interessados">
          <template #body="{ data }">
            <span class="text-sm text-gray-700">{{ formatarInteressados(data.interessados_info) }}</span>
          </template>
        </Column>

        <!-- Prioridade com Tag colorida -->
        <Column field="prioridade_descricao" header="Prioridade" sortable>
          <template #body="{ data }">
            <Tag
              :value="data.prioridade_descricao"
              :severity="prioridadeSeverity(data.prazo_dias)"
              class="text-xs"
            />
          </template>
        </Column>

        <!-- Status -->
        <Column field="status" header="Status" sortable>
          <template #body="{ data }">
            <Tag :value="data.status_display" :severity="statusSeverity(data.status)" class="text-xs" />
          </template>
        </Column>

        <!-- Ações -->
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

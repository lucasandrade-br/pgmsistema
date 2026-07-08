<script setup>
import { computed, onMounted, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button      from 'primevue/button'
import Dropdown    from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import api         from '@/services/api'

const toast = useToast()

// ── Estado ────────────────────────────────────────────────────────────────────
const procuradores          = ref([])
const origemSelecionada     = ref(null)
const destinosSelecionados  = ref([])
const loading               = ref(false)
const carregando            = ref(false)

// ── Computed ──────────────────────────────────────────────────────────────────
const procuradoresDestinoDisponiveis = computed(() => {
  if (!origemSelecionada.value) return procuradores.value
  return procuradores.value.filter((p) => p.id !== origemSelecionada.value.id)
})

const podeExecutar = computed(
  () => origemSelecionada.value && destinosSelecionados.value.length > 0,
)

// ── Carregamento ──────────────────────────────────────────────────────────────
async function carregarProcuradores() {
  carregando.value = true
  try {
    const { data } = await api.get('auth/procuradores/')
    procuradores.value = data
  } catch {
    toast.add({
      severity: 'error',
      summary:  'Erro ao carregar',
      detail:   'Não foi possível carregar a lista de procuradores.',
      life:     5000,
    })
  } finally {
    carregando.value = false
  }
}

onMounted(carregarProcuradores)

// Limpa destinos quando a origem muda (evita selecionar a mesma pessoa dos dois lados)
function onOrigemChange() {
  destinosSelecionados.value = destinosSelecionados.value.filter(
    (d) => d.id !== origemSelecionada.value?.id,
  )
}

// ── Ação principal ────────────────────────────────────────────────────────────
async function executarRedistribuicao() {
  if (!podeExecutar.value) return

  loading.value = true
  try {
    const { data } = await api.post('gestao/processos/redistribuir-ferias/', {
      procurador_origem_id:     origemSelecionada.value.id,
      procuradores_destino_ids: destinosSelecionados.value.map((d) => d.id),
    })

    const total = Array.isArray(data) ? data.length : (data.redistribuidos ?? '?')

    toast.add({
      severity: 'success',
      summary:  'Redistribuição concluída!',
      detail:   `${total} processo(s) redistribuído(s) com sucesso via Round-Robin.`,
      life:     6000,
    })

    // Limpa o formulário
    origemSelecionada.value    = null
    destinosSelecionados.value = []
  } catch (err) {
    const detail =
      err.response?.data?.message ??
      err.response?.data?.detail ??
      'Verifique os dados e tente novamente.'
    toast.add({
      severity: 'error',
      summary:  'Erro na redistribuição',
      detail,
      life:     7000,
    })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="p-6 flex justify-center">
    <div class="w-full max-w-xl">

      <!-- ── Cabeçalho ─────────────────────────────────────────────────── -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold text-gray-800">Redistribuição de Processos</h1>
        <p class="text-sm text-gray-500 mt-1">
          Transfira a carga de um procurador em férias ou afastamento para outros
          membros da equipe. A distribuição é feita automaticamente via Round-Robin.
        </p>
      </div>

      <!-- ── Card principal ────────────────────────────────────────────── -->
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">

        <!-- Bloco Origem -->
        <div class="p-6 border-b border-gray-100">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
              <i class="pi pi-user text-red-600" />
            </div>
            <div>
              <p class="font-semibold text-gray-800 text-sm">Procurador de Origem</p>
              <p class="text-xs text-gray-400">Quem sairá de férias / afastamento</p>
            </div>
          </div>

          <Dropdown
            v-model="origemSelecionada"
            :options="procuradores"
            option-label="nome"
            placeholder="Selecione quem sairá..."
            :loading="carregando"
            :disabled="carregando"
            class="w-full"
            filter
            @change="onOrigemChange"
          />
        </div>

        <!-- Seta visual de separação -->
        <div class="flex items-center justify-center py-3 bg-gray-50 border-b border-gray-100">
          <div class="flex items-center gap-2 text-gray-400 text-sm font-medium">
            <i class="pi pi-arrow-down text-base" />
            <span>os processos serão distribuídos para</span>
            <i class="pi pi-arrow-down text-base" />
          </div>
        </div>

        <!-- Bloco Destinos -->
        <div class="p-6">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
              <i class="pi pi-users text-blue-600" />
            </div>
            <div>
              <p class="font-semibold text-gray-800 text-sm">Procuradores de Destino</p>
              <p class="text-xs text-gray-400">Quem absorverá os processos (Round-Robin)</p>
            </div>
          </div>

          <MultiSelect
            v-model="destinosSelecionados"
            :options="procuradoresDestinoDisponiveis"
            option-label="nome"
            placeholder="Selecione quem receberá os processos..."
            display="chip"
            :loading="carregando"
            :disabled="carregando || !origemSelecionada"
            class="w-full"
            filter
          />

          <p v-if="!origemSelecionada" class="text-xs text-gray-400 mt-2">
            <i class="pi pi-info-circle mr-1" />
            Selecione primeiro o procurador de origem.
          </p>
        </div>

        <!-- Resumo / Preview -->
        <div
          v-if="origemSelecionada && destinosSelecionados.length"
          class="mx-6 mb-4 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm"
        >
          <p class="font-semibold text-amber-800 mb-1">
            <i class="pi pi-info-circle mr-1" />
            Resumo da operação
          </p>
          <p class="text-amber-700">
            Todos os processos ativos de
            <strong>{{ origemSelecionada.nome }}</strong>
            serão redistribuídos entre
            <strong>{{ destinosSelecionados.length }} procurador(es)</strong>
            selecionado(s).
          </p>
        </div>

        <!-- Botão de ação -->
        <div class="px-6 pb-6">
          <Button
            label="Executar Redistribuição"
            icon="pi pi-sync"
            severity="danger"
            :loading="loading"
            :disabled="!podeExecutar"
            class="w-full"
            @click="executarRedistribuicao"
          />
        </div>

      </div>
    </div>
  </div>
</template>

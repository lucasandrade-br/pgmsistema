<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const authStore = useAuthStore()

// ── RBAC ──────────────────────────────────────────────────────────────────────────────────
const _CHEFIA = ['Procurador-Chefe', 'Protocolador-Chefe']

const isChefia = computed(() => {
  const u = authStore.user
  if (!u) return false
  if (u.is_superuser) return true
  return _CHEFIA.some(g => u.grupos?.includes(g))
})

const isCadastrante = computed(() =>
  !isChefia.value && authStore.user?.grupos?.includes('Cadastrante')
)

const isProcurador = computed(() =>
  !isChefia.value && !isCadastrante.value && !!authStore.user
)

// ── Métricas ──────────────────────────────────────────────────────────────────────────────────
const loading  = ref(true)
const metricas = ref({ pendentes: 0, diligencias: 0, aguardando: 0, concluidos: 0 })

async function carregarResumo() {
  loading.value = true
  try {
    const { data } = await api.get('gestao/dashboard/resumo/')
    metricas.value = data
  } catch {
    // silencia erros de rede; os valores padrão (zero) já estão no ref
  } finally {
    loading.value = false
  }
}

onMounted(carregarResumo)
</script>

<template>
  <div class="flex flex-col gap-6">

    <!-- Título -->
    <div>
      <h1 class="text-xl font-bold text-gray-900">Painel de Controle</h1>
      <p class="text-sm text-gray-400 mt-0.5">
        Olá, <span class="font-medium text-gray-600">{{ authStore.user?.first_name || authStore.user?.username }}</span>.
        Aqui está o resumo do dia.
      </p>
    </div>

    <!-- Grid de cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">

      <!-- Card: Processos Pendentes -->
      <div
        v-if="isChefia || isProcurador"
        class="flex flex-col bg-white border border-gray-200 shadow-sm rounded-lg overflow-hidden"
      >
        <div class="flex-1 flex flex-col items-center justify-center p-8">
          <span v-if="loading" class="text-6xl font-light text-gray-300">...</span>
          <span v-else class="text-6xl font-light text-gray-800">{{ metricas.pendentes }}</span>
          <span class="text-sm text-gray-500 mt-2">Processos Pendentes</span>
        </div>
        <RouterLink
          to="/analises-pendentes"
          class="w-full bg-blue-900 hover:bg-blue-950 text-white text-xs font-medium py-2.5 flex items-center justify-center gap-2 transition-colors"
        >
          Acessar meus processos <i class="pi pi-arrow-circle-right" />
        </RouterLink>
      </div>

      <!-- Card: Diligências em Aberto -->
      <div
        v-if="isChefia || isProcurador"
        class="flex flex-col bg-white border border-gray-200 shadow-sm rounded-lg overflow-hidden"
      >
        <div class="flex-1 flex flex-col items-center justify-center p-8">
          <span v-if="loading" class="text-6xl font-light text-gray-300">...</span>
          <span v-else class="text-6xl font-light text-gray-800">{{ metricas.diligencias }}</span>
          <span class="text-sm text-gray-500 mt-2">Diligências em Aberto</span>
        </div>
        <RouterLink
          to="/diligencias"
          class="w-full bg-blue-900 hover:bg-blue-950 text-white text-xs font-medium py-2.5 flex items-center justify-center gap-2 transition-colors"
        >
          Ver Diligências <i class="pi pi-arrow-circle-right" />
        </RouterLink>
      </div>

      <!-- Card: Aguardando Distribuição (chefia) -->
      <div
        v-if="isChefia"
        class="flex flex-col bg-white border border-gray-200 shadow-sm rounded-lg overflow-hidden"
      >
        <div class="flex-1 flex flex-col items-center justify-center p-8">
          <span v-if="loading" class="text-6xl font-light text-gray-300">...</span>
          <span v-else class="text-6xl font-light text-gray-800">{{ metricas.aguardando }}</span>
          <span class="text-sm text-gray-500 mt-2">Aguardando Distribuição</span>
        </div>
        <RouterLink
          to="/processos/distribuicao"
          class="w-full bg-blue-900 hover:bg-blue-950 text-white text-xs font-medium py-2.5 flex items-center justify-center gap-2 transition-colors"
        >
          Ver Lista <i class="pi pi-arrow-circle-right" />
        </RouterLink>
      </div>

      <!-- Card: Análises Concluídas (chefia) -->
      <div
        v-if="isChefia"
        class="flex flex-col bg-white border border-gray-200 shadow-sm rounded-lg overflow-hidden"
      >
        <div class="flex-1 flex flex-col items-center justify-center p-8">
          <span v-if="loading" class="text-6xl font-light text-gray-300">...</span>
          <span v-else class="text-6xl font-light text-gray-800">{{ metricas.concluidos }}</span>
          <span class="text-sm text-gray-500 mt-2">Análises Concluídas</span>
        </div>
        <RouterLink
          :to="{ name: 'analises-pendentes', query: { status: 'CONCLUIDO' } }"
          class="w-full bg-blue-900 hover:bg-blue-950 text-white text-xs font-medium py-2.5 flex items-center justify-center gap-2 transition-colors"
        >
          Monitorar <i class="pi pi-arrow-circle-right" />
        </RouterLink>
      </div>

      <!-- Card: Cadastrar Processo (chefia + cadastrante) -->
      <div
        v-if="isChefia || isCadastrante"
        class="flex flex-col bg-white border border-gray-200 shadow-sm rounded-lg overflow-hidden"
      >
        <div class="flex-1 flex flex-col items-center justify-center p-8">
          <i class="pi pi-plus-circle text-5xl text-blue-600" />
          <span class="text-sm text-gray-500 mt-3">Novo Cadastro</span>
        </div>
        <RouterLink
          to="/processos/novo"
          class="w-full bg-blue-900 hover:bg-blue-950 text-white text-xs font-medium py-2.5 flex items-center justify-center gap-2 transition-colors"
        >
          Protocolar Novo Processo <i class="pi pi-arrow-circle-right" />
        </RouterLink>
      </div>

    </div>
  </div>
</template>

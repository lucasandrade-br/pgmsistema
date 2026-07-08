<script setup>
import { ref, computed, onMounted } from 'vue'
import Chart from 'primevue/chart'
import api from '@/services/api'

// ── Estado ──────────────────────────────────────────────────────────────────
const loading          = ref(true)
const dadosGerenciais  = ref(null)

// ── Fetch ────────────────────────────────────────────────────────────────────
async function carregarDados() {
  loading.value = true
  try {
    const { data } = await api.get('gestao/dashboard/gerencial/')
    dadosGerenciais.value = data
  } finally {
    loading.value = false
  }
}

onMounted(carregarDados)

// ── KPIs (atalhos) ───────────────────────────────────────────────────────────
const kpis = computed(() => dadosGerenciais.value?.kpis ?? {})

// ── Gráfico de Carga de Trabalho ─────────────────────────────────────────────
const chartCargaData = computed(() => {
  const carga = dadosGerenciais.value?.carga_trabalho ?? []
  return {
    labels: carga.map((p) => p.nome),
    datasets: [
      {
        label: 'No Prazo',
        backgroundColor: '#031e6b',
        data: carga.map((p) => p.no_prazo),
        yAxisID: 'y',
        order: 1,
      },
      {
        label: 'Em Atraso',
        backgroundColor: '#6a6f7a',
        data: carga.map((p) => p.em_atraso),
        yAxisID: 'y',
        order: 1,
      },
      {
        label: 'Diligências',
        backgroundColor: '#faad32',
        data: carga.map((p) => p.diligencias),
        yAxisID: 'y',
        order: 1,
      },
      {
        type: 'line',
        label: 'Tempo Médio (dias)',
        borderColor: '#25b01a',
        backgroundColor: 'rgba(50,240,36,0.06)',
        borderWidth: 2,
        pointBackgroundColor: '#25b01a',
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        pointRadius: 3,
        tension: 0.3,
        fill: false,
        spanGaps: true,
        yAxisID: 'y2',
        order: 0,
        data: carga.map((p) => p.tempo_medio_dias),
      },
    ],
  }
})

const chartCargaOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: { mode: 'index', intersect: false },
  },
  scales: {
    x: { stacked: true, grid: { display: false } },
    y: {
      stacked: true,
      beginAtZero: true,
      ticks: { stepSize: 1 },
      title: { display: true, text: 'Qtd. Processos', color: '#6b7280' },
    },
    y2: {
      type: 'linear',
      position: 'right',
      beginAtZero: true,
      title: { display: true, text: 'Dias', color: '#6b7280' },
      ticks: { color: '#6b7280' },
      grid: { drawOnChartArea: false },
    },
  },
}

// ── Produtividade (termômetro) ────────────────────────────────────────────────
const produtividade = computed(() => dadosGerenciais.value?.produtividade ?? {})

const prodIsPositivo = computed(
  () => produtividade.value.concluidos_30d >= produtividade.value.media_mensal_ano,
)

const prodPercentual = computed(() => {
  const media = produtividade.value.media_mensal_ano
  if (!media) return 100
  return Math.min(
    Math.round((produtividade.value.concluidos_30d / media) * 100),
    150,
  )
})
</script>

<template>
  <div class="p-6 space-y-6">

    <!-- ── Cabeçalho ──────────────────────────────────────────────────────── -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">Painel Gerencial</h1>
        <p class="text-sm text-gray-500 mt-0.5">Visão consolidada da equipe em tempo real</p>
      </div>
      <button
        @click="carregarDados"
        :disabled="loading"
        class="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 disabled:opacity-50 transition-colors"
      >
        <i :class="['pi pi-refresh', loading && 'animate-spin']" />
        Atualizar
      </button>
    </div>

    <!-- ── KPI Cards ─────────────────────────────────────────────────────── -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

      <!-- Fila de distribuição -->
      <div class="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4 shadow-sm">
        <div class="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
          <i class="pi pi-inbox text-blue-600 text-xl" />
        </div>
        <div>
          <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Fila de Distribuição</p>
          <p v-if="!loading" class="text-3xl font-bold text-gray-800 leading-tight">
            {{ kpis.total_fila ?? '—' }}
          </p>
          <div v-else class="h-8 w-16 bg-gray-200 rounded animate-pulse mt-1" />
        </div>
      </div>

      <!-- Em Análise -->
      <div class="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4 shadow-sm">
        <div class="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
          <i class="pi pi-file-edit text-indigo-600 text-xl" />
        </div>
        <div>
          <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Em Análise</p>
          <p v-if="!loading" class="text-3xl font-bold text-gray-800 leading-tight">
            {{ kpis.em_analise ?? '—' }}
          </p>
          <div v-else class="h-8 w-16 bg-gray-200 rounded animate-pulse mt-1" />
        </div>
      </div>

      <!-- Gargalo Diligências -->
      <div class="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4 shadow-sm">
        <div class="w-12 h-12 rounded-full bg-yellow-100 flex items-center justify-center flex-shrink-0">
          <i class="pi pi-exclamation-triangle text-yellow-600 text-xl" />
        </div>
        <div>
          <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Gargalo Diligências</p>
          <p v-if="!loading" class="text-3xl font-bold text-gray-800 leading-tight">
            {{ kpis.gargalo_diligencia ?? '—' }}
          </p>
          <div v-else class="h-8 w-16 bg-gray-200 rounded animate-pulse mt-1" />
        </div>
      </div>

      <!-- Tempo Médio de Conclusão -->
      <div class="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4 shadow-sm">
        <div class="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
          <i class="pi pi-stopwatch text-green-600 text-xl" />
        </div>
        <div>
          <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Tempo Médio</p>
          <p v-if="!loading" class="text-3xl font-bold text-gray-800 leading-tight">
            <template v-if="kpis.tempo_medio_conclusao != null">
              {{ kpis.tempo_medio_conclusao }}<span class="text-base font-normal text-gray-400 ml-1">dias</span>
            </template>
            <span v-else class="text-lg text-gray-400">Sem dados</span>
          </p>
          <div v-else class="h-8 w-16 bg-gray-200 rounded animate-pulse mt-1" />
        </div>
      </div>

    </div>

    <!-- ── Linha 2: Carga + Produtividade ─────────────────────────────────── -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">

      <!-- Gráfico de Carga de Trabalho (ocupa 2/3) -->
      <div class="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h2 class="text-sm font-semibold text-gray-700 mb-4">Carga de Trabalho por Procurador</h2>

        <div v-if="loading" class="h-64 bg-gray-100 rounded animate-pulse" />

        <div v-else-if="!dadosGerenciais?.carga_trabalho?.length"
             class="h-64 flex items-center justify-center text-gray-400 text-sm">
          Nenhum procurador com processos ativos.
        </div>

        <div v-else class="h-64">
          <Chart
            type="bar"
            :data="chartCargaData"
            :options="chartCargaOptions"
            class="h-full w-full"
          />
        </div>

        <!-- Legenda de referência -->
        <div class="flex gap-4 mt-3 justify-center text-xs text-gray-500">
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-sm bg-blue-700" /> No Prazo
          </span>
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-sm bg-slate-500" /> Em Atraso
          </span>
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-sm bg-[#faad32]" /> Diligências
          </span>
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-0.5 bg-[#32f024]" style="border-radius:2px" />
            <span class="inline-block w-2 h-2 rounded-full bg-slate-900 -ml-1.5" />
            Tempo Médio (dias)
          </span>
        </div>
      </div>

      <!-- Termômetro de Produtividade (ocupa 1/3) -->
      <div class="bg-white rounded-xl border border-gray-200 p-5 shadow-sm flex flex-col">
        <h2 class="text-sm font-semibold text-gray-700 mb-1">Termômetro de Produtividade</h2>
        <p class="text-xs text-gray-400 mb-5">Últimos 30 dias vs Média Mensal Anual</p>

        <div v-if="loading" class="flex-1 flex flex-col gap-3">
          <div class="h-6 bg-gray-200 rounded animate-pulse" />
          <div class="h-4 bg-gray-200 rounded animate-pulse w-3/4" />
          <div class="h-16 bg-gray-100 rounded animate-pulse mt-4" />
        </div>

        <template v-else-if="dadosGerenciais">
          <!-- Valor principal -->
          <div class="text-center mb-4">
            <p class="text-5xl font-bold"
               :class="prodIsPositivo ? 'text-green-600' : 'text-red-600'">
              {{ produtividade.concluidos_30d }}
            </p>
            <p class="text-sm text-gray-500 mt-1">concluídos nos últimos 30 dias</p>
          </div>

          <!-- Barra de progresso -->
          <div class="mb-3">
            <div class="flex justify-between text-xs text-gray-500 mb-1">
              <span>0</span>
              <span>Meta: {{ produtividade.media_mensal_ano }}/mês</span>
            </div>
            <div class="w-full bg-gray-100 rounded-full h-4 overflow-hidden">
              <div
                class="h-4 rounded-full transition-all duration-700"
                :class="prodIsPositivo ? 'bg-green-500' : 'bg-red-500'"
                :style="{ width: Math.min(prodPercentual, 100) + '%' }"
              />
            </div>
            <p class="text-xs text-center mt-1"
               :class="prodIsPositivo ? 'text-green-600' : 'text-red-600'">
              {{ prodPercentual }}% da meta mensal
            </p>
          </div>

          <!-- Badge de status -->
          <div
            class="mt-auto rounded-lg p-3 text-center text-sm font-semibold"
            :class="prodIsPositivo
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-red-50 text-red-700 border border-red-200'"
          >
            <i :class="['pi mr-1', prodIsPositivo ? 'pi-arrow-up' : 'pi-arrow-down']" />
            {{ prodIsPositivo ? 'Acima da média' : 'Abaixo da média' }}
            <span class="block text-xs font-normal mt-0.5">
              Média anual: {{ produtividade.media_mensal_ano }} proc/mês
            </span>
          </div>
        </template>

      </div>
    </div>

  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import FormularioEnvolvido from '@/components/shared/FormularioEnvolvido.vue'
import api from '@/services/api'

const toast = useToast()

// ── Estado ───────────────────────────────────────────────────────────────────
const envolvidos    = ref([])
const isLoading     = ref(false)
const termoBusca    = ref('')

const modalVisivel    = ref(false)
const envolvidoEdicao = ref(null)   // null = criação, object = edição

// ── Carregar lista ────────────────────────────────────────────────────────────
async function carregar() {
  isLoading.value = true
  try {
    const params = {}
    if (termoBusca.value.trim()) params.search = termoBusca.value.trim()
    const { data } = await api.get('cadastros/remetentes/', { params })
    // A API pode retornar objeto paginado ou array direto
    envolvidos.value = Array.isArray(data) ? data : (data.results ?? [])
  } catch {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível carregar os envolvidos.', life: 4000 })
  } finally {
    isLoading.value = false
  }
}

onMounted(carregar)

// ── Busca ─────────────────────────────────────────────────────────────────────
let debounceTimer = null
function onBusca() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(carregar, 350)
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function abrirCriar() {
  envolvidoEdicao.value = null
  modalVisivel.value    = true
}

function abrirEditar(envolvido) {
  envolvidoEdicao.value = envolvido
  modalVisivel.value    = true
}

function onSalvo() {
  modalVisivel.value = false
  carregar()
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const tipoSeverity = { FISICA: 'info', JURIDICA: 'success', ORGAO_PUBLICO: 'warn' }
const tipoLabel    = { FISICA: 'Física', JURIDICA: 'Jurídica', ORGAO_PUBLICO: 'Órgão Público' }

/**
 * Mascara parcialmente um valor sensível para exibição.
 * Mantém os primeiros 2 e os últimos 2 dígitos; oculta o restante com '*'.
 * Remove não-dígitos antes de aplicar para evitar vazar máscara formatada.
 * Ex.: "123.456.789-09" → "12*****09"
 */
function mascarar(valor) {
  if (!valor) return '—'
  const digitos = valor.replace(/\D/g, '')
  if (digitos.length <= 4) return '*'.repeat(digitos.length)
  return digitos.slice(0, 2) + '*'.repeat(digitos.length - 4) + digitos.slice(-2)
}
</script>

<template>
  <div class="flex flex-col gap-6">

    <!-- Cabeçalho -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-900">Gestão de Envolvidos</h1>
        <p class="text-sm text-gray-400 mt-0.5">Remetentes e interessados cadastrados no sistema.</p>
      </div>
      <Button
        label="Novo Envolvido"
        icon="pi pi-plus"
        @click="abrirCriar"
      />
    </div>

    <!-- Card de listagem -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">

      <!-- Barra de busca -->
      <div class="mb-4 flex gap-2">
        <InputText
          v-model="termoBusca"
          placeholder="Buscar por nome, e-mail, CPF/CNPJ..."
          class="w-full max-w-sm"
          @input="onBusca"
        />
        <Button
          icon="pi pi-refresh"
          severity="secondary"
          text
          v-tooltip.top="'Recarregar'"
          @click="carregar"
        />
      </div>

      <DataTable
        :value="envolvidos"
        :loading="isLoading"
        stripedRows
        responsiveLayout="scroll"
        emptyMessage="Nenhum envolvido encontrado."
        class="text-sm"
      >
        <Column field="nome_razao_social" header="Nome / Razão Social" sortable />

        <Column header="Tipo" style="width: 160px">
          <template #body="{ data }">
            <Tag
              :value="tipoLabel[data.tipo_pessoa] ?? data.tipo_pessoa"
              :severity="tipoSeverity[data.tipo_pessoa] ?? 'secondary'"
            />
          </template>
        </Column>

        <Column field="doc" header="CPF / CNPJ" style="width: 180px">
          <template #body="{ data }">
            <span class="font-mono text-sm tracking-wider">{{ mascarar(data.doc) }}</span>
          </template>
        </Column>

        <Column field="email" header="E-mail" />

        <Column field="telefone" header="Telefone" style="width: 160px">
          <template #body="{ data }">
            <span class="font-mono text-sm tracking-wider">{{ mascarar(data.telefone) }}</span>
          </template>
        </Column>

        <Column header="" style="width: 80px; text-align: right">
          <template #body="{ data }">
            <Button
              icon="pi pi-pencil"
              severity="secondary"
              text
              size="small"
              v-tooltip.left="'Editar'"
              @click="abrirEditar(data)"
            />
          </template>
        </Column>
      </DataTable>

    </div>

    <!-- Modal de cadastro / edição -->
    <Dialog
      v-model:visible="modalVisivel"
      :header="envolvidoEdicao ? 'Editar Envolvido' : 'Novo Envolvido'"
      modal
      :style="{ width: '480px' }"
      :draggable="false"
    >
      <FormularioEnvolvido
        :remetente="envolvidoEdicao"
        @salvo="onSalvo"
      />
    </Dialog>

  </div>
</template>

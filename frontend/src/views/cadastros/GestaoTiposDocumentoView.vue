<script setup>
import { onMounted, ref } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import FormularioTipoDocumento from '@/components/shared/FormularioTipoDocumento.vue'
import api from '@/services/api'

// ── Estado ───────────────────────────────────────────────────────────────────
const tipos      = ref([])
const listaBase  = ref([])   // cache para filtro local sem nova chamada
const isLoading  = ref(false)
const termoBusca = ref('')

const modalVisivel = ref(false)
const tipoEdicao   = ref(null)   // null = criação, object = edição

// ── Carregar lista ────────────────────────────────────────────────────────────
async function carregar() {
  isLoading.value = true
  try {
    const { data } = await api.get('cadastros/tipos-documento/', {
      params: { incluir_inativos: 'true' },
    })
    listaBase.value = Array.isArray(data) ? data : (data.results ?? [])
    aplicarFiltro()
  } catch {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível carregar os tipos de documento.', life: 4000 })
  } finally {
    isLoading.value = false
  }
}

function aplicarFiltro() {
  const termo = termoBusca.value.trim().toLowerCase()
  tipos.value = termo
    ? listaBase.value.filter(t => t.descricao.toLowerCase().includes(termo))
    : listaBase.value
}

onMounted(carregar)

// ── Busca local (sem re-fetch) ────────────────────────────────────────────────
let debounceTimer = null
function onBusca() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(aplicarFiltro, 200)
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function abrirCriar() {
  tipoEdicao.value   = null
  modalVisivel.value = true
}

function abrirEditar(tipo) {
  tipoEdicao.value   = tipo
  modalVisivel.value = true
}

function onSalvo() {
  modalVisivel.value = false
  carregar()
}
</script>

<template>
  <div class="flex flex-col gap-6">

    <!-- Cabeçalho -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-900">Tipos de Documento</h1>
        <p class="text-sm text-gray-400 mt-0.5">Categorias de documentos aceitos no protocolo.</p>
      </div>
      <Button label="Novo Tipo" icon="pi pi-plus" @click="abrirCriar" />
    </div>

    <!-- Card de listagem -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">

      <!-- Barra de busca -->
      <div class="mb-4 flex gap-2">
        <InputText
          v-model="termoBusca"
          placeholder="Buscar por descrição..."
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
        :value="tipos"
        :loading="isLoading"
        stripedRows
        responsiveLayout="scroll"
        emptyMessage="Nenhum tipo de documento encontrado."
        class="text-sm"
      >
        <Column field="descricao" header="Descrição" sortable />

        <Column header="Situação" style="width: 130px">
          <template #body="{ data }">
            <Tag
              :value="data.ativo ? 'Ativo' : 'Inativo'"
              :severity="data.ativo ? 'success' : 'secondary'"
            />
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
      :header="tipoEdicao ? 'Editar Tipo de Documento' : 'Novo Tipo de Documento'"
      modal
      :style="{ width: '420px' }"
      :draggable="false"
    >
      <FormularioTipoDocumento
        :tipo="tipoEdicao"
        @salvo="onSalvo"
      />
    </Dialog>

  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'
import Button from 'primevue/button'
import api from '@/services/api'

// ── Props e emits ─────────────────────────────────────────────────────────────
const props = defineProps({
  /** Objeto TipoDocumento existente (modo edição). null = modo criação. */
  tipo: { type: Object, default: null },
})
const emit = defineEmits(['salvo'])

const toast     = useToast()
const isLoading = ref(false)

// ── Estado do formulário ──────────────────────────────────────────────────────
const formDescricao = ref(props.tipo?.descricao ?? '')
const formAtivo     = ref(props.tipo?.ativo ?? true)

// Quando o componente é reutilizado (modo edição → criação e vice-versa)
// os valores precisam reagir à troca de prop
watch(() => props.tipo, (novoTipo) => {
  formDescricao.value = novoTipo?.descricao ?? ''
  formAtivo.value     = novoTipo?.ativo     ?? true
}, { immediate: false })

// ── Salvar ────────────────────────────────────────────────────────────────────
async function salvar() {
  if (!formDescricao.value.trim()) {
    toast.add({ severity: 'warn', summary: 'Campo obrigatório', detail: 'Informe a descrição do tipo.', life: 3000 })
    return
  }

  isLoading.value = true
  try {
    const payload = { descricao: formDescricao.value.trim(), ativo: formAtivo.value }
    let response
    if (props.tipo?.id) {
      response = await api.patch(`cadastros/tipos-documento/${props.tipo.id}/`, payload)
      toast.add({ severity: 'success', summary: 'Atualizado', detail: 'Tipo de documento atualizado.', life: 3000 })
    } else {
      response = await api.post('cadastros/tipos-documento/', payload)
      toast.add({ severity: 'success', summary: 'Criado', detail: 'Tipo de documento cadastrado.', life: 3000 })
    }
    emit('salvo', response.data)
  } catch (err) {
    const erros = err.response?.data
    const detail =
      erros?.descricao?.[0] ??
      erros?.detail ??
      'Verifique os dados e tente novamente.'
    toast.add({ severity: 'error', summary: 'Erro ao salvar', detail, life: 5000 })
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-4">

    <!-- Descrição -->
    <div class="flex flex-col gap-1.5">
      <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
        Descrição <span class="text-red-500">*</span>
      </label>
      <InputText
        v-model="formDescricao"
        placeholder="Ex.: Ofício, Requerimento, Contrato..."
        class="w-full"
        autofocus
        @keyup.enter="salvar"
      />
    </div>

    <!-- Ativo / Inativo -->
    <div class="flex items-center gap-3">
      <ToggleSwitch v-model="formAtivo" inputId="form-tipo-ativo" />
      <label for="form-tipo-ativo" class="text-sm text-gray-700 cursor-pointer select-none">
        {{ formAtivo ? 'Ativo — aparece nas listas de seleção' : 'Inativo — oculto nas listas de seleção' }}
      </label>
    </div>

    <!-- Ação -->
    <div class="flex justify-end pt-2">
      <Button
        :label="tipo?.id ? 'Atualizar' : 'Cadastrar Tipo'"
        icon="pi pi-check"
        severity="success"
        :loading="isLoading"
        @click="salvar"
      />
    </div>

  </div>
</template>

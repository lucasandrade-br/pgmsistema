<script setup>
import { computed, ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import SelectButton from 'primevue/selectbutton'
import InputText from 'primevue/inputtext'
import InputMask from 'primevue/inputmask'
import Button from 'primevue/button'
import api from '@/services/api'

// ── Props e emits ──────────────────────────────────────────────────────────────
const props = defineProps({
  /** Objeto Remetente existente (modo edição). null = modo criação. */
  remetente: { type: Object, default: null },
})
const emit = defineEmits(['salvo'])

const toast      = useToast()
const isLoading  = ref(false)

// ── Opções do SelectButton tipo_pessoa ────────────────────────────────────────
const tipoOpcoes = [
  { label: 'Física',        value: 'FISICA'        },
  { label: 'Jurídica',      value: 'JURIDICA'      },
  { label: 'Órgão Público', value: 'ORGAO_PUBLICO' },
]

// ── Estado do formulário ──────────────────────────────────────────────────────
const form = ref({
  tipo_pessoa:       props.remetente?.tipo_pessoa       ?? 'FISICA',
  nome_razao_social: props.remetente?.nome_razao_social ?? '',
  doc:               props.remetente?.doc               ?? '',
  email:             props.remetente?.email             ?? '',
  telefone:          props.remetente?.telefone          ?? '',
})

// ── Placeholder dinâmico para o campo doc ─────────────────────────────────────
const docLabel = computed(() => {
  if (form.value.tipo_pessoa === 'FISICA')        return 'CPF'
  if (form.value.tipo_pessoa === 'JURIDICA')      return 'CNPJ'
  return 'Identificação do Órgão'
})
const docPlaceholder = computed(() => {
  if (form.value.tipo_pessoa === 'FISICA')        return '000.000.000-00'
  if (form.value.tipo_pessoa === 'JURIDICA')      return '00.000.000/0000-00'
  return 'Nº do órgão público'
})

// Máscara para InputMask (FISICA e JURIDICA)
const docMask = computed(() => {
  if (form.value.tipo_pessoa === 'FISICA')   return '999.999.999-99'
  if (form.value.tipo_pessoa === 'JURIDICA') return '99.999.999/9999-99'
  return null
})

// Limpa o doc ao trocar de tipo para evitar valor incompatível com a nova máscara
watch(() => form.value.tipo_pessoa, () => { form.value.doc = '' })

// ── Validação básica ─────────────────────────────────────────────────────────
function validar() {
  if (!form.value.nome_razao_social.trim()) {
    toast.add({ severity: 'warn', summary: 'Campo obrigatório', detail: 'Informe o nome/razão social.', life: 3000 })
    return false
  }
  if (!form.value.doc.trim()) {
    toast.add({ severity: 'warn', summary: 'Campo obrigatório', detail: `Informe o ${docLabel.value}.`, life: 3000 })
    return false
  }
  return true
}

// ── Salvar ────────────────────────────────────────────────────────────────────
async function salvar() {
  if (!validar()) return

  isLoading.value = true
  try {
    let response
    if (props.remetente?.id) {
      response = await api.patch(`cadastros/remetentes/${props.remetente.id}/`, form.value)
    } else {
      response = await api.post('cadastros/remetentes/', form.value)
    }

    // Adiciona alias 'nome' para compatibilidade com o AutoComplete (optionLabel="nome")
    const entidade = { ...response.data, nome: response.data.nome_razao_social }

    toast.add({ severity: 'success', summary: 'Salvo!', detail: 'Envolvido cadastrado com sucesso.', life: 3000 })
    emit('salvo', entidade)
  } catch (err) {
    const erros = err.response?.data
    const detail =
      erros?.nome_razao_social?.[0] ??
      erros?.doc?.[0] ??
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

    <!-- Tipo de pessoa -->
    <div class="flex flex-col gap-1.5">
      <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
        Tipo de Pessoa <span class="text-red-500">*</span>
      </label>
      <SelectButton
        v-model="form.tipo_pessoa"
        :options="tipoOpcoes"
        optionLabel="label"
        optionValue="value"
        :allowEmpty="false"
        class="w-full"
      />
    </div>

    <!-- Nome / Razão Social -->
    <div class="flex flex-col gap-1.5">
      <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
        {{ form.tipo_pessoa === 'FISICA' ? 'Nome Completo' : 'Razão Social' }}
        <span class="text-red-500">*</span>
      </label>
      <InputText
        v-model="form.nome_razao_social"
        placeholder="Nome completo ou razão social"
        class="w-full"
      />
    </div>

    <!-- CPF / CNPJ / Identificação -->
    <div class="flex flex-col gap-1.5">
      <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
        {{ docLabel }} <span class="text-red-500">*</span>
      </label>
      <!-- FISICA e JURIDICA: InputMask com máscara específica -->
      <InputMask
        v-if="docMask"
        v-model="form.doc"
        :mask="docMask"
        :placeholder="docPlaceholder"
        class="w-full"
      />
      <!-- ORGAO_PUBLICO: sem formato fixo -->
      <InputText
        v-else
        v-model="form.doc"
        :placeholder="docPlaceholder"
        class="w-full"
      />
    </div>

    <!-- E-mail -->
    <div class="flex flex-col gap-1.5">
      <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
        E-mail
      </label>
      <InputText
        v-model="form.email"
        type="email"
        placeholder="contato@exemplo.com.br"
        class="w-full"
      />
    </div>

    <!-- Telefone -->
    <div class="flex flex-col gap-1.5">
      <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
        Telefone
      </label>
      <InputText
        v-model="form.telefone"
        placeholder="(00) 00000-0000"
        class="w-full"
      />
    </div>

    <!-- Ação -->
    <div class="flex justify-end pt-2">
      <Button
        :label="remetente?.id ? 'Atualizar' : 'Cadastrar Envolvido'"
        icon="pi pi-check"
        severity="success"
        :loading="isLoading"
        @click="salvar"
      />
    </div>

  </div>
</template>

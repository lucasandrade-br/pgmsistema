<script setup>
import { ref, computed, watch } from 'vue'
import { useToast }   from 'primevue/usetoast'
import Button         from 'primevue/button'
import DatePicker     from 'primevue/datepicker'
import Dialog         from 'primevue/dialog'
import InputText      from 'primevue/inputtext'
import MultiSelect    from 'primevue/multiselect'
import Select         from 'primevue/select'
import Textarea       from 'primevue/textarea'
import ToggleSwitch   from 'primevue/toggleswitch'
import api            from '@/services/api'

const props = defineProps({
  visible: { type: Boolean, required: true },
  processo: { type: Object, required: true },
})
const emit = defineEmits(['update:visible', 'sucesso'])
const toast = useToast()

// Evita o erro de transição do Vue em versões mais antigas
const visibleLocal = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const isSubmitting = ref(false)
const isLoadingDados = ref(false)
const dependenciasCarregadas = ref(false)

const tiposDocumento = ref([])
const prioridades    = ref([])
const procuradores   = ref([])
const remetentes     = ref([])

const form = ref({
  prioridade:           null,
  tipo_processo:        null,
  remetente:            null,
  interessados:         [],
  procurador_atribuido: null,
  numero_origem:        '',
  numero_sei:           '',
  data_origem:          null,
  data_limite:          null,
  observacoes:          '',
  notificar_remetente:  false,
})

// ── BLINDAGEM MÁXIMA: Garante array e cria uma 'safe_label' para o PrimeVue não travar ──
function extrairEBlindarArray(resposta, chavesDeBusca) {
  let arr = []
  if (resposta && resposta.data) {
    if (Array.isArray(resposta.data)) arr = resposta.data
    else if (Array.isArray(resposta.data.results)) arr = resposta.data.results
    else if (Array.isArray(resposta.data.data)) arr = resposta.data.data
  }
  
  return arr.map(item => {
    let labelEncontrada = 'Sem Nome/Descrição'
    for (const chave of chavesDeBusca) {
      if (item[chave]) {
        labelEncontrada = item[chave]
        break
      }
    }
    return { ...item, safe_label: labelEncontrada }
  })
}

async function carregarDependenciasDaApi() {
  if (dependenciasCarregadas.value) return 
  
  isLoadingDados.value = true
  try {
    const noop = () => ({ data: [] })
    const [tipoRes, priorRes, procRes, remRes] = await Promise.all([
      api.get('cadastros/tipos-documento/').catch(noop),
      api.get('cadastros/niveis-prioridade/').catch(noop),
      api.get('auth/procuradores/').catch(noop),
      api.get('cadastros/remetentes/?page_size=500').catch(noop),
    ])

    // Extrai e blinda cada lista procurando a propriedade correta
    tiposDocumento.value = extrairEBlindarArray(tipoRes,  ['descricao', 'nome'])
    prioridades.value    = extrairEBlindarArray(priorRes, ['descricao', 'nome'])
    procuradores.value   = extrairEBlindarArray(procRes,  ['nome', 'username'])
    remetentes.value     = extrairEBlindarArray(remRes,   ['nome_razao_social', 'nome', 'razao_social'])

    dependenciasCarregadas.value = true
  } catch (error) {
    toast.add({ severity: 'warn', summary: 'Aviso', detail: 'Alguns menus podem estar vazios.', life: 3000 })
  } finally {
    isLoadingDados.value = false
  }
}

watch(() => props.visible, async (aberto) => {
  if (!aberto) return

  await carregarDependenciasDaApi()
  const p = props.processo

    let interessadosIds = []
  
  // Extrai da lista principal ou da info, forçando a conversão para Número Inteiro
  if (p.interessados && Array.isArray(p.interessados) && p.interessados.length > 0) {
    interessadosIds = p.interessados.map(item => Number(typeof item === 'object' ? item.id : item))
  } else if (p.interessados_info && Array.isArray(p.interessados_info)) {
    interessadosIds = p.interessados_info.map(item => Number(item.id))
  }
  
  // Filtra para garantir que não vai nenhum valor quebrado (NaN) para o componente
  interessadosIds = interessadosIds.filter(id => id && !isNaN(id))

  form.value = {
    prioridade:           p.prioridade?.id ?? p.prioridade ?? null,
    tipo_processo:        p.tipo_processo?.id ?? p.tipo_processo ?? null,
    remetente:            p.remetente?.id ?? p.remetente ?? null,
    interessados:         interessadosIds,
    procurador_atribuido: p.procurador_atribuido?.id ?? p.procurador_atribuido ?? null,
    numero_origem:        p.numero_origem ?? '',
    numero_sei:           p.numero_sei ?? '',
    data_origem:          p.data_origem ? new Date(p.data_origem) : null,
    data_limite:          p.data_limite ? new Date(p.data_limite) : null,
    observacoes:          p.observacoes ?? '',
    notificar_remetente:  p.notificar_remetente ?? false,
  }
})

async function salvar() {
  isSubmitting.value = true
  try {
    const toISO = date => date ? new Date(date).toISOString().split('T')[0] : null
    
    await api.patch(`gestao/processos/${props.processo.id}/`, {
      ...form.value,
      data_origem: toISO(form.value.data_origem),
      data_limite: toISO(form.value.data_limite),
    })

    toast.add({ severity: 'success', summary: 'Atualizado', detail: 'Dados salvos com sucesso.', life: 3000 })
    
    visibleLocal.value = false // Fecha a tela PRIMEIRO (Evita o erro de transição)
    
    // Aguarda o modal fechar para só então recarregar o processo no pai
    setTimeout(() => {
      emit('sucesso')
    }, 400)
    
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível salvar os dados.', life: 5000 })
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visibleLocal"
    modal
    header="Editar Dados do Processo"
    :style="{ width: '56rem' }"
    :breakpoints="{ '960px': '92vw', '640px': '98vw' }"
  >
    <div v-if="isLoadingDados" class="flex flex-col items-center justify-center p-10 gap-3">
      <i class="pi pi-spin pi-spinner text-3xl text-gray-400"></i>
      <p class="text-sm text-gray-500">Preparando formulário...</p>
    </div>

    <div v-else class="grid grid-cols-2 gap-x-6 gap-y-5 pt-2">
      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Nº Origem</label>
        <InputText v-model="form.numero_origem" placeholder="Ex.: 001/2026" class="w-full" />
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Número SEI</label>
        <InputText v-model="form.numero_sei" placeholder="Ex.: SEI-XXX/2026" class="w-full" />
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Tipo de Processo</label>
        <Select v-model="form.tipo_processo" :options="tiposDocumento" optionLabel="safe_label" optionValue="id" placeholder="Selecione..." filter class="w-full" />
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Prioridade</label>
        <Select v-model="form.prioridade" :options="prioridades" optionLabel="safe_label" optionValue="id" placeholder="Selecione..." class="w-full" />
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Procurador</label>
        <Select v-model="form.procurador_atribuido" :options="procuradores" optionLabel="safe_label" optionValue="id" placeholder="Selecione..." filter class="w-full" />
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Data Origem</label>
        <DatePicker v-model="form.data_origem" dateFormat="dd/mm/yy" class="w-full" />
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Data Limite</label>
        <DatePicker v-model="form.data_limite" dateFormat="dd/mm/yy" class="w-full" />
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Remetente Principal</label>
        <Select v-model="form.remetente" :options="remetentes" optionLabel="safe_label" optionValue="id" placeholder="Selecione..." filter class="w-full" />
      </div>

      <div class="flex flex-col gap-1 justify-center mt-4">
        <div class="flex items-center gap-3">
          <ToggleSwitch v-model="form.notificar_remetente" />
          <span class="text-sm font-semibold text-gray-600 uppercase">Notificar Remetente</span>
        </div>
      </div>

      <div class="col-span-2 flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Interessados</label>
        <MultiSelect v-model="form.interessados" :options="remetentes" optionLabel="safe_label" optionValue="id" placeholder="Adicionar interessados..." filter display="chip" class="w-full" />
      </div>

      <div class="col-span-2 flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Observações</label>
        <Textarea v-model="form.observacoes" rows="3" class="w-full" />
      </div>
    </div>

    <template #footer>
      <Button label="Cancelar" text severity="secondary" @click="visibleLocal = false" />
      <Button label="Salvar Alterações" icon="pi pi-check" severity="primary" :loading="isSubmitting" @click="salvar" />
    </template>
  </Dialog>
</template>
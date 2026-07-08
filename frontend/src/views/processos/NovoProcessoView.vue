<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import AutoComplete from 'primevue/autocomplete'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import WorkspaceAnexos from '@/components/shared/WorkspaceAnexos.vue'
import FormularioEnvolvido from '@/components/shared/FormularioEnvolvido.vue'
import api from '@/services/api'

const toast  = useToast()
const router = useRouter()

// ── Estado do formulário ──────────────────────────────────────────────────────
const remetente         = ref(null)   // objeto Remetente selecionado
const interessados      = ref([])     // array de objetos Remetente
const prioridade        = ref(null)   // objeto NivelPrioridade selecionado
const tipoProcesso      = ref(null)   // objeto TipoDocumento selecionado
const numeroOrigem      = ref('')
const numeroSei         = ref('')
const observacoes       = ref('')
const dataOrigem        = ref(null)   // Date string YYYY-MM-DD (campo sem UI por enquanto)
const notificarRemetente = ref(false) // flag de notificação ao remetente
const isSubmitting      = ref(false)  // bloqueia duplo-clique durante o POST
const listaAnexos       = ref([])
// ── Modal de cadastro de envolvido ─────────────────────────────────────────────────────────────────
const modalEnvolvidoVisivel = ref(false)
const alvoCadastro          = ref('remetente')  // 'remetente' | 'interessado'

function abrirModalCadastro(alvo) {
  alvoCadastro.value          = alvo
  modalEnvolvidoVisivel.value = true
}

function onEnvolvidoSalvo(novaEntidade) {
  if (alvoCadastro.value === 'remetente') {
    remetente.value = novaEntidade
  } else {
    // Evita duplicata na lista de interessados
    if (!interessados.value.some(i => i.id === novaEntidade.id)) {
      interessados.value = [...interessados.value, novaEntidade]
    }
  }
  modalEnvolvidoVisivel.value = false
}
// ── Sugestões dos AutoCompletes ───────────────────────────────────────────────
const sugestoesRemetentes   = ref([])
const sugestoesInteressados = ref([])

// ── Listas cacheáveis (carregadas uma vez no mount) ───────────────────────────
const tiposDocumento = ref([])
const prioridades    = ref([])

// ── Utilitário de debounce ────────────────────────────────────────────────────
// Evita chamadas à API a cada tecla digitada; dispara apenas após `delay` ms
// de inatividade. Complementa o :delay nativo do AutoComplete do PrimeVue.
function criarDebounce(fn, delay = 350) {
  let timer = null
  return function (...args) {
    clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

// ── Funções de busca (AutoComplete) ───────────────────────────────────────────

const buscarRemetentes = criarDebounce(async (event) => {
  const query = (event.query ?? '').trim()
  if (!query) {
    sugestoesRemetentes.value = []
    return
  }
  try {
    const { data } = await api.get(`cadastros/remetentes/?search=${encodeURIComponent(query)}`)
    sugestoesRemetentes.value = data.results ?? data
  } catch {
    sugestoesRemetentes.value = []
  }
})

const buscarInteressados = criarDebounce(async (event) => {
  const query = (event.query ?? '').trim()
  if (!query) {
    sugestoesInteressados.value = []
    return
  }
  try {
    const { data } = await api.get(`cadastros/remetentes/?search=${encodeURIComponent(query)}`)
    sugestoesInteressados.value = data.results ?? data
  } catch {
    sugestoesInteressados.value = []
  }
})

// ── Carregamento inicial das listas cacheáveis ────────────────────────────────
onMounted(async () => {
  try {
    const [tiposResp, priorsResp] = await Promise.all([
      api.get('cadastros/tipos-documento/'),
      api.get('cadastros/niveis-prioridade/'),
    ])
    tiposDocumento.value = tiposResp.data.results ?? tiposResp.data
    // Monta label composto para exibição na lista de prioridades
    prioridades.value = (priorsResp.data.results ?? priorsResp.data).map(p => ({
      ...p,
      label: `${p.descricao} (${p.prazo_dias} dias)`,
    }))
  } catch {
    toast.add({
      severity: 'warn',
      summary: 'Aviso',
      detail: 'Não foi possível carregar tipos de processo e prioridades.',
      life: 4000,
    })
  }
})

// ── Submissão ─────────────────────────────────────────────────────────────────
async function submitProcesso() {
  // ── 1. Validação ─────────────────────────────────────────────────────────
  if (!remetente.value) {
    toast.add({ severity: 'warn', summary: 'Campo obrigatório', detail: 'Selecione o remetente principal.', life: 3000 })
    return
  }
  if (!prioridade.value) {
    toast.add({ severity: 'warn', summary: 'Campo obrigatório', detail: 'Selecione a prioridade.', life: 3000 })
    return
  }
  if (!listaAnexos.value.length) {
    toast.add({ severity: 'warn', summary: 'Documento obrigatório', detail: 'Inclua ao menos um documento antes de protocolar.', life: 3000 })
    return
  }

  // ── 2. FormData — campos globais ─────────────────────────────────────────
  const formData = new FormData()

  formData.append('remetente_id',  remetente.value.id)
  formData.append('prioridade_id', prioridade.value.id)

  if (tipoProcesso.value?.id)    formData.append('tipo_processo_id', tipoProcesso.value.id)
  if (numeroOrigem.value.trim()) formData.append('numero_origem',    numeroOrigem.value.trim())
  if (numeroSei.value.trim())    formData.append('numero_sei',        numeroSei.value.trim())
  if (observacoes.value.trim())  formData.append('observacoes',      observacoes.value.trim())
  if (dataOrigem.value)          formData.append('data_origem',      dataOrigem.value)  // YYYY-MM-DD

  formData.append('notificar_remetente', notificarRemetente.value ? 'true' : 'false')

  // M2M: múltiplos appends com a mesma chave → Django QueryDict.getlist()
  interessados.value.forEach(i => formData.append('interessados_ids', i.id))

  // ── 3. Estratégia do "Zip" (arquivos ↔ metadata por índice) ──────────────
  //   Cada File ocupa o índice i em 'arquivos'; metadataList[i] carrega
  //   os metadados correspondentes. O backend combina por posição em
  //   _montar_arquivos(). Anexos modo 'editor' (sem arquivo físico) são
  //   pulados neste ciclo — suporte previsto para sprint futura.
  const metadataList = []

  listaAnexos.value.forEach(anexo => {
    if (!anexo.arquivo) return  // modo 'editor' — sem arquivo físico

    // Propriedades exatas conforme WorkspaceAnexos.vue:
    //   arquivo  → File object
    //   categoria → string (mock); .id = undefined → null até usar API de TipoDocumento
    //   numeracao → string (pode ser '—' se não informado)
    formData.append('arquivos', anexo.arquivo)

    metadataList.push({
      categoria_documento_id: anexo.categoria?.id ?? null,
      numero_documento:       (anexo.numeracao !== '—' ? anexo.numeracao : '') || '',
      observacao:             '',
    })
  })

  // JSON.stringify antes do append — o backend faz json.loads(request.data.get('metadata'))
  formData.append('metadata', JSON.stringify(metadataList))

  // ── 4. POST para a API ───────────────────────────────────────────────────
  //   NÃO definir 'Content-Type' manualmente: o navegador gera o boundary
  //   multipart/form-data automaticamente ao detectar um FormData.
  isSubmitting.value = true
  try {
    const { data } = await api.post('gestao/processos/', formData)

    const protocolo = data.numero_protocolo ?? 'gerado com sucesso'
    toast.add({
      severity: 'success',
      summary:  'Protocolo gerado!',
      detail:   `Processo ${protocolo} criado com sucesso.`,
      life:     5000,
    })
    router.push('/')
  } catch (err) {
    const detail =
      err.response?.data?.message ??
      err.response?.data?.detail ??
      'Verifique os dados e tente novamente.'
    toast.add({ severity: 'error', summary: 'Erro ao protocolar', detail, life: 6000 })
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="p-6 flex flex-col gap-6">

    <!-- Título da página -->
    <div>
      <h1 class="text-xl font-bold text-gray-900">Protocolar Novo Processo</h1>
      <p class="text-sm text-gray-400 mt-0.5">Preencha os dados e adicione os documentos abaixo.</p>
    </div>

    <!-- ── Card superior: metadados do processo ──────────────────────────────── -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-5">
        Dados do Processo
      </h2>

      <!-- Linha 1: Remetente + Interessados -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">

        <!-- Remetente Principal -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Remetente Principal <span class="text-red-500">*</span>
          </label>
          <div class="flex gap-2 items-start">
            <AutoComplete
              v-model="remetente"
              :suggestions="sugestoesRemetentes"
              optionLabel="nome"
              forceSelection
              placeholder="Digite para buscar..."
              class="flex-1"
              inputClass="w-full"
              @complete="buscarRemetentes"
            />
            <Button
              icon="pi pi-plus"
              severity="secondary"
              text
              v-tooltip.top="'Cadastrar novo remetente'"
              @click="abrirModalCadastro('remetente')"
            />
          </div>
        </div>

        <!-- Interessados -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Interessados
          </label>
          <div class="flex gap-2 items-start">
            <AutoComplete
              v-model="interessados"
              :suggestions="sugestoesInteressados"
              optionLabel="nome"
              multiple
              placeholder="Busque secretarias/órgãos..."
              class="flex-1"
              inputClass="w-full"
              @complete="buscarInteressados"
            />
            <Button
              icon="pi pi-plus"
              severity="secondary"
              text
              v-tooltip.top="'Cadastrar novo interessado'"
              @click="abrirModalCadastro('interessado')"
            />
          </div>
        </div>

      </div>

      <!-- Linha 2: Tipo de Processo + Número de Origem + Prioridade -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">

        <!-- Tipo de Processo -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Tipo de Processo
          </label>
          <Select
            v-model="tipoProcesso"
            :options="tiposDocumento"
            optionLabel="descricao"
            filter
            filterPlaceholder="Buscar tipo..."
            placeholder="Selecione o tipo"
            class="w-full"
          />
        </div>

        <!-- Número de Origem -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Nº de Origem
          </label>
          <InputText
            v-model="numeroOrigem"
            placeholder="Ex.: OF-123/2026"
            class="w-full"
          />
        </div>

        <!-- Número SEI -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Número SEI
          </label>
          <InputText
            v-model="numeroSei"
            placeholder="Ex.: SEI-0123456/2026"
            class="w-full"
          />
        </div>

        <!-- Prioridade -->
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Prioridade <span class="text-red-500">*</span>
          </label>
          <Select
            v-model="prioridade"
            :options="prioridades"
            optionLabel="label"
            placeholder="Selecione a prioridade"
            class="w-full"
          />
        </div>

      </div>

      <!-- Linha 3: Observações (largura total) -->
      <div class="mt-4">
        <div class="flex flex-col gap-1.5">
          <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Observações
          </label>
          <Textarea
            v-model="observacoes"
            :rows="3"
            placeholder="Informações adicionais sobre o processo..."
            class="w-full text-sm"
          />
        </div>
      </div>

    </div>

    <!-- ── Card inferior: workspace de documentos ───────────────────────────── -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-5">
        Documentos
      </h2>
      <WorkspaceAnexos v-model="listaAnexos" />
    </div>

    <!-- ── Ação final ────────────────────────────────────────────────────────── -->
    <div class="flex justify-end pb-6">
      <Button
        label="Salvar Movimentação / Protocolar"
        icon="pi pi-save"
        severity="success"
        size="large"
        :loading="isSubmitting"
        :disabled="isSubmitting"
        @click="submitProcesso"
      />
    </div>

    <!-- ── Modal: cadastro rápido de envolvido ──────────────────────────────── -->
    <Dialog
      v-model:visible="modalEnvolvidoVisivel"
      :header="alvoCadastro === 'remetente' ? 'Cadastrar Remetente' : 'Cadastrar Interessado'"
      modal
      :style="{ width: '480px' }"
      :closable="true"
      :draggable="false"
    >
      <FormularioEnvolvido @salvo="onEnvolvidoSalvo" />
    </Dialog>

  </div>
</template>

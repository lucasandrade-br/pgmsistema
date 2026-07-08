<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import SelectButton          from 'primevue/selectbutton'
import Select                from 'primevue/select'
import InputText             from 'primevue/inputtext'
import Textarea             from 'primevue/textarea'
import Button               from 'primevue/button'
import VisualizadorPDFPadrao from './VisualizadorPDFPadrao.vue'
import api                   from '@/services/api'

// ── v-model ──────────────────────────────────────────────────────────────────
const props = defineProps({
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const toast = useToast()

// ── Estado da área de preparação ─────────────────────────────────────────────
const modoOpcoes = [
  { label: 'PDF',    value: 'pdf'    },
  { label: 'Editor', value: 'editor' },
]
const modo           = ref('pdf')
const categoriaAtual = ref(null)
const numeracaoAtual = ref('')
const textoEditor    = ref('')
const arquivoAtual   = ref(null)
const viewerUrl      = ref(null)   // URL exibida no iframe/visualizador
const fileInputRef   = ref(null)

// ── Dados: Categorias de documento carregadas da API ─────────────────────────
const categorias = ref([])

onMounted(async () => {
  try {
    const res = await api.get('cadastros/tipos-documento/')
    categorias.value = res.data
  } catch {
    // fallback silencioso: lista fica vazia, dropdown mostra placeholder
  }
})

const ultimasNumeracoes = ref([])

function formatarData(iso) {
  if (!iso) return '—'
  const [ano, mes, dia] = iso.substring(0, 10).split('-')
  return `${dia}/${mes}/${ano}`
}

watch(categoriaAtual, async (novaCategoria) => {
  ultimasNumeracoes.value = []
  if (!novaCategoria?.id) return
  try {
    const res = await api.get(`gestao/categorias/${novaCategoria.id}/numeracoes/`)
    const records = res.data?.results ?? res.data ?? []
    ultimasNumeracoes.value = records.map(r => ({
      numeracao: r.numero_documento || r.numeracao,
      upload: r.data_criacao || r.upload || r.data,
    })).slice(0, 4)
  } catch (err) {
    console.error('Erro ao buscar numerações', err)
  }
})

// ── Gerenciamento de Blob URLs (evitar vazamento de memória) ──────────────────
const blobUrls = []

function criarBlobUrl(file) {
  const url = URL.createObjectURL(file)
  blobUrls.push(url)
  return url
}

onUnmounted(() => {
  blobUrls.forEach(url => URL.revokeObjectURL(url))
})

// ── Handlers de arquivo ───────────────────────────────────────────────────────
function abrirSeletor() {
  fileInputRef.value?.click()
}

function processarArquivo(file) {
  if (!file) return

  // Validação de tipo: aceita somente PDF e imagens JPEG/PNG
  const EXTENSOES = ['pdf', 'jpg', 'jpeg', 'png']
  const MIMETYPES = ['application/pdf', 'image/jpeg', 'image/png']
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''

  if (!EXTENSOES.includes(ext) || !MIMETYPES.includes(file.type)) {
    toast.add({
      severity: 'warn',
      summary:  'Tipo não permitido',
      detail:   `"${file.name}" não é permitido. Use PDF, JPG, JPEG ou PNG.`,
      life:     4000,
    })
    return
  }

  arquivoAtual.value = file
  viewerUrl.value    = criarBlobUrl(file)
}
function limparArquivoSelecionado() {
  arquivoAtual.value = null
  viewerUrl.value = null
  if (fileInputRef.value) {
    fileInputRef.value.value = '' // Reseta o input nativo para permitir selecionar o mesmo arquivo novamente
  }
}
function onFileChange(e) {
  processarArquivo(e.target.files[0])
  e.target.value = ''   // permite re-selecionar o mesmo arquivo
}

function onDrop(e) {
  processarArquivo(e.dataTransfer.files[0])
}

// ── Incluir anexo na lista ────────────────────────────────────────────────────
function incluir() {
  if (!categoriaAtual.value) {
    toast.add({ severity: 'warn', summary: 'Campo obrigatório', detail: 'Selecione a categoria do documento.', life: 3000 })
    return
  }
  if (modo.value === 'pdf' && !arquivoAtual.value) {
    toast.add({ severity: 'warn', summary: 'Arquivo obrigatório', detail: 'Selecione um arquivo PDF antes de incluir.', life: 3000 })
    return
  }

  const novoAnexo = {
    id: Date.now(),
    categoria: categoriaAtual.value,
    numeracao: numeracaoAtual.value.trim() || '—',
    arquivo: arquivoAtual.value,
    previewUrl: viewerUrl.value,
    texto: textoEditor.value,
    modo: modo.value,
  }

  emit('update:modelValue', [...props.modelValue, novoAnexo])

  // Limpar área de preparação (a previewUrl do anexo salvo permanece válida)
  categoriaAtual.value = null
  numeracaoAtual.value = ''
  textoEditor.value    = ''
  arquivoAtual.value   = null
  viewerUrl.value      = null
}

// ── Ações sobre itens da lista ────────────────────────────────────────────────
function visualizarAnexo(anexo) {
  if (anexo.previewUrl) viewerUrl.value = anexo.previewUrl
}

function removerAnexo(id) {
  const anexo = props.modelValue.find(a => a.id === id)
  // Se o visualizador estava mostrando este anexo, limpar
  if (viewerUrl.value && viewerUrl.value === anexo?.previewUrl) {
    viewerUrl.value = null
  }
  emit('update:modelValue', props.modelValue.filter(a => a.id !== id))
}
</script>

<template>
  <div class="grid grid-cols-12 gap-6">

    <!-- ═══════════════════════════════════════════════════════════════════════ -->
    <!-- Coluna Esquerda — Área de Preparação (8/12)                            -->
    <!-- ═══════════════════════════════════════════════════════════════════════ -->
    <div class="col-span-12 lg:col-span-8 flex flex-col gap-5 lg:border-r lg:border-gray-200 lg:pr-6">

      <!-- Topo: toggle de modo -->
      <div class="flex items-center gap-6 flex-wrap">
        <SelectButton
          v-model="modo"
          :options="modoOpcoes"
          optionLabel="label"
          optionValue="value"
        />
      </div>

      <!-- ── Área de Upload (modo PDF) ──────────────────────────────────────── -->
      <div v-if="modo === 'pdf'">
        <div
          class="border-2 border-dashed rounded-lg p-8 flex flex-col items-center justify-center gap-2 transition-colors"
          :class="arquivoAtual ? 'border-blue-400 bg-blue-50/40' : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50 cursor-pointer'"
          @click="!arquivoAtual && abrirSeletor()"
          @dragover.prevent
          @drop.prevent="onDrop"
        >
          <template v-if="!arquivoAtual">
            <i class="pi pi-cloud-upload text-4xl text-gray-400" />
            <p class="text-sm font-semibold text-gray-600">Anexar Documento</p>
            <p class="text-xs text-gray-400">Arraste ou clique para escolher</p>
          </template>

          <template v-else>
            <i class="pi pi-file-pdf text-4xl text-red-500" />
            <p class="text-sm font-semibold text-blue-900 text-center break-all px-4">
              {{ arquivoAtual.name }}
            </p>
            <div class="flex items-center gap-3 mt-3">
              <Button 
                label="Trocar" 
                icon="pi pi-refresh" 
                size="small" 
                outlined 
                severity="secondary"
                @click.stop="abrirSeletor" 
              />
              <Button 
                label="Remover" 
                icon="pi pi-trash" 
                size="small" 
                outlined 
                severity="danger"
                @click.stop="limparArquivoSelecionado" 
              />
            </div>
          </template>
        </div>
        
        <input
          ref="fileInputRef"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          class="hidden"
          @change="onFileChange"
        />
      </div>

      <!-- ── Editor de Texto (modo Editor) ──────────────────────────────────── -->
      <!--
        TODO: substituir <Textarea> pelo componente <Editor> do PrimeVue
              após instalar a dependência: npm install quill
              import Editor from 'primevue/editor'
      -->
      <div v-else>
        <Textarea
          v-model="textoEditor"
          :rows="8"
          autoResize
          placeholder="Digite o conteúdo do documento..."
          class="w-full text-sm"
        />
      </div>

      <!-- ── Metadados + Tabela (grid 2 colunas) ───────────────────────────── -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">

        <!-- Coluna esquerda: Categoria, Numeração e Botão -->
        <div class="flex flex-col gap-4">
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Categoria do Documento <span class="text-red-500">*</span>
            </label>
            <Select
              v-model="categoriaAtual"
              :options="categorias"
              optionLabel="descricao"
              placeholder="Selecione a categoria"
              class="w-full text-sm"
            />
          </div>

          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Numeração
            </label>
            <InputText
              v-model="numeracaoAtual"
              placeholder="*Apenas recomendação"
              class="w-full text-sm"
            />
          </div>

          <!-- Botão movido para baixo dos inputs -->
          <div class="flex justify-end mt-2">
            <Button
              label="Incluir Documento"
              icon="pi pi-plus"
              class="w-full"
              style="background-color: #1e40af; border-color: #1e40af;"
              @click="incluir"
            />
          </div>
        </div>

        <!-- Coluna direita: últimas numerações desta categoria -->
        <div>
          <p class="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
            Últimas numerações desta categoria
          </p>
          <div class="border border-gray-200 rounded-lg overflow-hidden h-[164px]">
            <table v-if="ultimasNumeracoes.length > 0" class="w-full text-xs">
              <thead class="bg-gray-50 text-gray-500 border-b border-gray-200">
                <tr>
                  <th class="text-left px-3 py-2 font-semibold">Numeração</th>
                  <th class="text-left px-3 py-2 font-semibold">Upload</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, index) in ultimasNumeracoes"
                  :key="index"
                  class="border-t border-gray-100 hover:bg-gray-50 transition-colors"
                >
                  <td class="px-3 py-2 font-mono text-gray-700">{{ row.numeracao || '—' }}</td>
                  <td class="px-3 py-2 text-gray-500">{{ formatarData(row.upload) }}</td>
                </tr>
              </tbody>
            </table>
            <!-- Estado Vazio -->
            <div v-else class="h-full flex items-center justify-center p-4 text-center text-xs text-gray-400 bg-gray-50">
              Ainda não existem arquivos dessa categoria.
            </div>
          </div>
        </div>

      </div>

      <!-- ── Visualizador de PDF (Com Scroll Interno) ────────────────────────── -->
      <div v-if="arquivoAtual || viewerUrl" class="mt-4 flex flex-col gap-2">
        
        <!-- Título padronizado do lado de fora da rolagem -->
        <p class="text-xs font-medium text-gray-500 uppercase tracking-wider">
          Visualizar Prévia
        </p>
        
        <!-- Caixa com o Scroll e o Visualizador -->
        <div class="border border-gray-200 rounded-lg bg-gray-50 h-[400px] overflow-y-auto flex flex-col">
          <VisualizadorPDFPadrao
            :arquivoNome="arquivoAtual?.name ?? 'Visualização'"
            :viewerUrl="viewerUrl"
            class="w-full flex-1"
          />
        </div>
        
      </div>

    </div>

    <!-- ═══════════════════════════════════════════════════════════════════════ -->
    <!-- Coluna Direita — Lista de Anexos (4/12)                                -->
    <!-- ═══════════════════════════════════════════════════════════════════════ -->
    <div class="col-span-12 lg:col-span-4">

      <h3 class="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
        Lista de Anexos
        <span
          class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-xs font-bold"
        >
          {{ modelValue.length }}
        </span>
      </h3>

      <!-- Estado vazio -->
      <div
        v-if="!modelValue.length"
        class="flex flex-col items-center justify-center py-12 text-gray-300 border-2 border-dashed border-gray-200 rounded-xl"
      >
        <i class="pi pi-paperclip text-3xl mb-2" />
        <p class="text-xs">Nenhum anexo adicionado</p>
      </div>

      <!-- Cards de anexos adicionados -->
      <div
        v-for="anexo in modelValue"
        :key="anexo.id"
        class="bg-slate-50 p-4 rounded-md mb-3 flex justify-between items-start border border-gray-100 hover:border-slate-300 transition-colors"
      >
        <!-- Dados do card -->
        <div class="min-w-0 flex-1">
          <p class="font-semibold text-gray-800 text-sm truncate">
            {{ anexo.categoria?.descricao || 'Sem Categoria' }}
            <span v-if="anexo.numeracao && anexo.numeracao !== '—'" class="font-normal text-gray-500">
              - {{ anexo.numeracao }}
            </span>
          </p>
          <p class="text-xs text-gray-400 mt-0.5 truncate">
            <span v-if="anexo.arquivo">{{ anexo.arquivo.name }}</span>
            <span v-else>Nota de Texto</span>
          </p>
          <div class="flex flex-wrap gap-1 mt-1.5">
            <span
              v-if="anexo.modo === 'editor'"
              class="inline-block text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-medium"
            >
              Texto
            </span>
          </div>
        </div>

        <!-- Ações do card -->
        <div class="flex gap-0.5 ml-3 shrink-0">
          <button
            class="p-1.5 rounded-md text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
            :title="`Visualizar: ${anexo.categoria}`"
            @click="visualizarAnexo(anexo)"
          >
            <i class="pi pi-eye text-sm" />
          </button>
          <button
            class="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
            :title="`Remover: ${anexo.categoria}`"
            @click="removerAnexo(anexo.id)"
          >
            <i class="pi pi-trash text-sm" />
          </button>
        </div>
      </div>

    </div>

  </div>
</template>

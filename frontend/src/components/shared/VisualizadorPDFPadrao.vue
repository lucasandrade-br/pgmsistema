<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useToast }                from 'primevue/usetoast'
import Button                      from 'primevue/button'
import VuePdfEmbed                 from 'vue-pdf-embed'
import api                         from '@/services/api'

const props = defineProps({
  arquivoNome:    { type: String, default: 'Documento Sem Nome' },
  categoriaAnexo: { type: String, default: null },
  numeracaoAnexo: { type: String, default: null },
  viewerUrl:      { type: String, default: null },
  textoNota:      { type: String, default: null },
})

// Linha de título exibida na topbar: "PARECER | 1050/2026"
const tituloTopbar = computed(() => {
  const parts = [
    props.categoriaAnexo?.toUpperCase() || null,
    props.numeracaoAnexo || null,
  ].filter(Boolean)
  return parts.length ? parts.join(' | ') : (props.arquivoNome || 'Documento Sem Nome')
})

const emit = defineEmits(['editar', 'excluir'])

const toast          = useToast()
const localBlobUrl   = ref(null)
const isLoadingPdf   = ref(false)
const escala         = ref(1.0)
const scrollContainer = ref(null)
const baseWidth      = ref(0)

// Captura a largura do contêiner ao montar; lê novamente na primeira renderização
// do PDF caso o componente tenha sido criado com display:none (ex: dentro de modal)
onMounted(() => {
  baseWidth.value = scrollContainer.value?.clientWidth || 800
})

// Largura em pixels passada ao VuePdfEmbed — mudança dispara re-render vetorial
const pdfWidth = computed(() =>
  baseWidth.value ? Math.round(baseWidth.value * escala.value) : undefined
)

// Rastreia blob URLs criadas por nós para gerenciar a memória corretamente
let _ownedBlobUrl = null

function _releaseOwnedBlob() {
  if (_ownedBlobUrl) {
    URL.revokeObjectURL(_ownedBlobUrl)
    _ownedBlobUrl = null
  }
}

// ── Ações da Topbar ───────────────────────────────────────────────────────────
function zoomIn()  { escala.value = Math.min(escala.value + 0.1, 3.0) }
function zoomOut() { escala.value = Math.max(escala.value - 0.1, 0.5) }

function baixarPdf() {
  if (!localBlobUrl.value) return
  const a    = document.createElement('a')
  a.href     = localBlobUrl.value
  a.download = props.arquivoNome
  a.click()
}

function imprimirPdf() {
  if (!localBlobUrl.value) return
  const popup = window.open(localBlobUrl.value)
  popup?.addEventListener('load', () => popup.print())
}

// Chamado por @rendered, @loading-failed e @rendering-failed do VuePdfEmbed
function onPdfRendered() {
  // Se baseWidth ainda não foi capturado (ex: componente montado oculto),
  // lê agora para que os botões de zoom funcionem corretamente a partir daqui
  if (!baseWidth.value && scrollContainer.value) {
    baseWidth.value = scrollContainer.value.clientWidth || 800
  }
}

// ── Fetch do PDF como Blob (bypassa X-Frame-Options) ─────────────────────────
async function carregarPdf(url) {
  _releaseOwnedBlob()

  if (!url) {
    localBlobUrl.value = null
    isLoadingPdf.value = false
    return
  }

  // Inicia feedback de carregamento
  isLoadingPdf.value = true

  // Blob local (ex: preview de arquivo arrastado no WorkspaceAnexos) — usa direto
  if (url.startsWith('blob:')) {
    localBlobUrl.value = url
    isLoadingPdf.value = false  // libera o overlay; VuePdfEmbed renderiza progressivamente
    return
  }

  // URL remota — fetch autenticado via Axios (JWT no header)
  try {
    const response     = await api.get(url, { responseType: 'blob' })
    _ownedBlobUrl      = URL.createObjectURL(response.data)
    localBlobUrl.value = _ownedBlobUrl
    isLoadingPdf.value = false  // libera o overlay; VuePdfEmbed renderiza progressivamente
  } catch {
    toast.add({
      severity: 'error',
      summary:  'Erro ao carregar documento',
      detail:   'Não foi possível obter o arquivo. Tente novamente.',
      life:     5000,
    })
    localBlobUrl.value = null
    isLoadingPdf.value = false
  }
}

// Recarrega sempre que a URL da prop mudar
watch(() => props.viewerUrl, (newUrl) => carregarPdf(newUrl), { immediate: true })

// Libera apenas as blob URLs que criamos (não as passadas externamente)
onUnmounted(_releaseOwnedBlob)
</script>

<template>
  <div class="flex flex-col h-full bg-gray-100 overflow-hidden rounded-lg border border-gray-200">

    <!-- ── Topbar ─────────────────────────────────────────────────────────── -->
    <div class="shrink-0 bg-white border-b border-gray-200 px-4 py-2 flex items-center justify-between">
      <div class="flex items-center gap-2 min-w-0">
        <i class="pi pi-file-pdf text-red-500 shrink-0" />
        <span class="text-sm font-medium text-gray-700 truncate">
          {{ tituloTopbar }}
        </span>
      </div>
      <div class="flex items-center gap-0.5 shrink-0 ml-4">
        <Button
          icon="pi pi-search-minus" text size="small" title="Reduzir zoom"
          class="text-gray-500" :disabled="!localBlobUrl || !!textoNota"
          @click="zoomOut"
        />
        <Button
          icon="pi pi-search-plus" text size="small" title="Ampliar zoom"
          class="text-gray-500" :disabled="!localBlobUrl || !!textoNota"
          @click="zoomIn"
        />
        <Button
          v-if="!textoNota"
          icon="pi pi-download" text size="small" title="Baixar"
          class="text-gray-500" :disabled="!localBlobUrl"
          @click="baixarPdf"
        />
        <Button
          v-if="!textoNota"
          icon="pi pi-print" text size="small" title="Imprimir"
          class="text-gray-500" :disabled="!localBlobUrl"
          @click="imprimirPdf"
        />
        <Button
          icon="pi pi-pencil" text size="small" title="Editar"
          class="text-gray-500"
          @click="$emit('editar')"
        />
        <Button
          icon="pi pi-trash" text size="small" title="Excluir"
          severity="danger"
          @click="$emit('excluir')"
        />
      </div>
    </div>

    <!-- ── Área de Exibição ───────────────────────────────────────────────── -->
    <div class="flex-1 relative overflow-hidden">

      <!-- Spinner overlay: cobre o conteúdo durante fetch e rendering do VuePdfEmbed -->
      <Transition name="pdf-fade">
        <div
          v-if="isLoadingPdf"
          class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-slate-100/90 backdrop-blur-sm"
        >
          <i class="pi pi-spin pi-spinner text-4xl text-blue-400" />
          <p class="mt-3 text-sm text-gray-400">Carregando documento...</p>
        </div>
      </Transition>

      <!-- PDF: scroll contínuo com todas as páginas; zoom via re-render vetorial (:width prop) -->
      <div
        v-if="localBlobUrl"
        ref="scrollContainer"
        class="overflow-auto w-full h-full bg-slate-200/50 p-4 md:p-8"
      >
        <VuePdfEmbed
          :source="localBlobUrl"
          :width="pdfWidth"
          class="mx-auto shadow-lg bg-white transition-all duration-200 ease-out"
          @rendered="onPdfRendered"
          @loading-failed="onPdfRendered"
          @rendering-failed="onPdfRendered"
        />
      </div>

      <!-- Nota de texto: renderiza como folha A4 sem necessidade de PDF -->
      <div
        v-else-if="textoNota"
        class="w-full h-full bg-slate-200/50 flex justify-center p-4 md:p-8 overflow-auto"
      >
        <div class="w-full max-w-3xl bg-white shadow-lg p-10 md:p-14" style="min-height: 800px">
          <p class="whitespace-pre-wrap text-gray-800 leading-relaxed text-sm font-serif">{{ textoNota }}</p>
        </div>
      </div>

      <!-- Estado vazio -->
      <div
        v-else-if="!isLoadingPdf"
        class="w-full h-full flex flex-col items-center justify-center gap-3 bg-white"
      >
        <i class="pi pi-file-pdf text-6xl text-gray-200" />
        <p class="text-sm text-gray-400 font-medium">Nenhum documento selecionado</p>
      </div>

    </div>

  </div>
</template>

<style scoped>
.pdf-fade-enter-active,
.pdf-fade-leave-active {
  transition: opacity 0.2s ease;
}
.pdf-fade-enter-from,
.pdf-fade-leave-to {
  opacity: 0;
}
</style>


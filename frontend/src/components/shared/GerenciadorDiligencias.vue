<script setup>
import { ref }          from 'vue'
import { useToast }     from 'primevue/usetoast'
import Button           from 'primevue/button'
import Checkbox         from 'primevue/checkbox'
import Chips            from 'primevue/chips'
import Dialog           from 'primevue/dialog'
import Tag              from 'primevue/tag'
import Textarea         from 'primevue/textarea'
import api              from '@/services/api'
import WorkspaceAnexos  from '@/components/shared/WorkspaceAnexos.vue'

// ── Props / Emits ──────────────────────────────────────────────────────────────
const props = defineProps({
  diligencia:    { type: Object, required: true },
  processo:      { type: Object, default: () => ({}) },
  anexosGlobais: { type: Array,  default: () => [] },
})
const emit = defineEmits(['sucesso'])

const toast = useToast()

// ── Estado local ──────────────────────────────────────────────────────────────
const exibirModalContato      = ref(false)
const observacaoContato       = ref('')
const exibirModalRejeitar     = ref(false)
const motivoRejeicao          = ref('')
const exibirModalConcluir     = ref(false)
const observacaoConclusao     = ref('')
const anexosConclusao         = ref([])
const isLoading               = ref(false)
const isSubmittingConclusao   = ref(false)

// ── Estado do modal de E-mail ────────────────────────────────────────────────
const exibirModalEmail        = ref(false)
const isSubmittingEmail       = ref(false)
const emailsSugeridos         = ref([])
const emailsSelecionados      = ref([])
const emailsAvulsos           = ref([])
const anexosSelecionados      = ref([])

// ── Mapeamento de severidade do Tag pelo status ───────────────────────────────
const severidadeStatus = {
  PENDENTE:  'warn',
  ENVIADA:   'info',
  CONCLUIDA: 'success',
  REJEITADA: 'danger',
}

// ── Ações ─────────────────────────────────────────────────────────────────────
// ── Ações ─────────────────────────────────────────────────────────────────────
function abrirModalEmail() {
  const sugeridos = []
  const p = props.processo
  if (p?.remetente_email) {
    sugeridos.push({ label: `Remetente: ${p.remetente_nome}`, email: p.remetente_email })
  }
  if (p?.interessados_info) {
    p.interessados_info.forEach(int => {
      if (int.email) sugeridos.push({ label: `Interessado: ${int.nome}`, email: int.email })
    })
  }
  emailsSugeridos.value    = sugeridos
  emailsSelecionados.value = []
  emailsAvulsos.value      = []
  anexosSelecionados.value = []
  exibirModalEmail.value   = true
}

async function enviarEmail() {
  const emailsDestino = [...emailsSelecionados.value, ...emailsAvulsos.value]

  if (emailsDestino.length === 0) {
    toast.add({ severity: 'warn', summary: 'Destinatário', detail: 'Informe ao menos um e-mail.', life: 3000 })
    return
  }
  if (anexosSelecionados.value.length === 0) {
    toast.add({ severity: 'warn', summary: 'Anexos', detail: 'Selecione ao menos um anexo para enviar.', life: 3000 })
    return
  }

  isSubmittingEmail.value = true
  try {
    await api.post(`gestao/diligencias/${props.diligencia.id}/aprovar/`, {
      emails_destino:          emailsDestino,
      anexos_ids_selecionados: anexosSelecionados.value,
    })
    exibirModalEmail.value = false
    toast.add({
      severity: 'success',
      summary:  'E-mail Enfileirado',
      detail:   'A diligência foi aprovada e o e-mail será enviado.',
      life:     4000,
    })
    emit('sucesso')
  } catch (err) {
    const msg = err.response?.data?.error || 'Erro ao enviar o e-mail.'
    toast.add({ severity: 'error', summary: 'Erro', detail: msg, life: 5000 })
  } finally {
    isSubmittingEmail.value = false
  }
}

async function marcarSolicitada() {
  if (observacaoContato.value.trim().length < 5) {
    toast.add({
      severity: 'warn',
      summary:  'Campo obrigatório',
      detail:   'A observação deve ter ao menos 5 caracteres.',
      life:     4000,
    })
    return
  }

  isLoading.value = true
  try {
    await api.post(`gestao/diligencias/${props.diligencia.id}/marcar-solicitada/`, {
      observacao_contato: observacaoContato.value,
    })
    exibirModalContato.value = false
    observacaoContato.value  = ''
    toast.add({
      severity: 'success',
      summary:  'Sucesso',
      detail:   'Diligência marcada como solicitada.',
      life:     4000,
    })
    emit('sucesso')
  } catch (err) {
    const msg = err.response?.data?.error || 'Erro ao marcar a diligência.'
    toast.add({ severity: 'error', summary: 'Erro', detail: msg, life: 5000 })
  } finally {
    isLoading.value = false
  }
}

async function rejeitar() {
  if (motivoRejeicao.value.trim().length < 5) {
    toast.add({
      severity: 'warn',
      summary:  'Campo obrigatório',
      detail:   'O motivo da rejeição deve ter ao menos 5 caracteres.',
      life:     4000,
    })
    return
  }

  isLoading.value = true
  try {
    await api.post(`gestao/diligencias/${props.diligencia.id}/rejeitar/`, {
      motivo_rejeicao: motivoRejeicao.value,
    })
    exibirModalRejeitar.value = false
    motivoRejeicao.value      = ''
    toast.add({
      severity: 'success',
      summary:  'Diligência rejeitada',
      detail:   'A operação foi registrada.',
      life:     4000,
    })
    emit('sucesso')
  } catch (err) {
    const msg = err.response?.data?.error || 'Erro ao rejeitar a diligência.'
    toast.add({ severity: 'error', summary: 'Erro', detail: msg, life: 5000 })
  } finally {
    isLoading.value = false
  }
}

async function concluirDiligencia() {
  if (anexosConclusao.value.length === 0) {
    toast.add({
      severity: 'warn',
      summary:  'Sem itens',
      detail:   'Adicione ao menos um documento ou nota de texto para concluir.',
      life:     4000,
    })
    return
  }

  isSubmittingConclusao.value = true
  try {
    const formData = new FormData()
    formData.append('observacao_resolucao', observacaoConclusao.value)

    const metadataList = []
    for (const anexo of anexosConclusao.value) {
      if (anexo.arquivo) formData.append('arquivos', anexo.arquivo)
      metadataList.push({
        eh_nota:                !anexo.arquivo,
        categoria_documento_id: anexo.categoria?.id ?? null,
        numero_documento:       (anexo.numeracao !== '—' ? anexo.numeracao : '') || '',
        observacao:             anexo.texto ?? '',
      })
    }
    formData.append('metadata', JSON.stringify(metadataList))

    await api.post(
      `gestao/diligencias/${props.diligencia.id}/concluir/`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )

    exibirModalConcluir.value   = false
    observacaoConclusao.value   = ''
    anexosConclusao.value       = []
    toast.add({
      severity: 'success',
      summary:  'Diligência concluída',
      detail:   'Os documentos foram registrados com sucesso.',
      life:     4000,
    })
    emit('sucesso')
  } catch (err) {
    const msg = err.response?.data?.error || 'Erro ao concluir a diligência.'
    toast.add({ severity: 'error', summary: 'Erro', detail: msg, life: 5000 })
  } finally {
    isSubmittingConclusao.value = false
  }
}
</script>

<template>
  <div v-bind="$attrs" class="w-full h-full bg-slate-100 flex items-center justify-center p-8 overflow-auto">
    <div class="bg-white shadow-xl rounded-xl border border-gray-200 w-full max-w-3xl p-8">

      <!-- Cabeçalho ─────────────────────────────────────────────────────────── -->
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-bold text-gray-800">Gerenciar Diligência</h2>
        <Tag
          :value="diligencia.status"
          :severity="severidadeStatus[diligencia.status] ?? 'secondary'"
        />
      </div>

      <!-- Corpo: Descrição da Necessidade ──────────────────────────────────── -->
      <div class="bg-gray-50 rounded-lg border border-gray-200 p-5 mb-8">
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Descrição da Necessidade
        </p>
        <p class="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
          {{ diligencia.descricao_necessidade || '—' }}
        </p>
      </div>

      <!-- Rodapé: Botões de Ação ───────────────────────────────────────────── -->
      <div class="flex flex-wrap gap-3">
        <Button
          label="Enviar por E-mail"
          icon="pi pi-envelope"
          outlined
          @click="abrirModalEmail"
        />
        <Button
          label="Marcar como Solicitada"
          icon="pi pi-phone"
          severity="info"
          @click="exibirModalContato = true"
        />
        <Button
          label="Concluir / Receber Arquivos"
          icon="pi pi-paperclip"
          severity="success"
          @click="exibirModalConcluir = true"
        />
        <Button
          label="Rejeitar"
          icon="pi pi-times"
          severity="danger"
          text
          @click="exibirModalRejeitar = true"
        />
      </div>
    </div>
  </div>

  <!-- ── Modal: Concluir Diligência ───────────────────────────────────────────────── -->
  <Dialog
    v-model:visible="exibirModalConcluir"
    modal
    maximizable
    header="Concluir Diligência"
    :style="{ width: '90vw', maxWidth: '1400px' }"
  >
    <div class="flex flex-col gap-4">
      <Textarea
        v-model="observacaoConclusao"
        rows="3"
        maxlength="50"
        placeholder="Observações sobre a conclusão (Opcional)"
        class="w-full"
      />
      <div class="flex justify-end">
        <small class="text-xs text-gray-400">{{ observacaoConclusao.length }} / 50</small>
      </div>
      <WorkspaceAnexos v-model="anexosConclusao" />
    </div>

    <template #footer>
      <Button
        label="Cancelar"
        text
        severity="secondary"
        @click="exibirModalConcluir = false"
      />
      <Button
        label="Confirmar Conclusão"
        icon="pi pi-check"
        severity="success"
        :loading="isSubmittingConclusao"
        @click="concluirDiligencia"
      />
    </template>
  </Dialog>

  <!-- ── Modal: Marcar como Solicitada ──────────────────────────────────────── -->
  <Dialog
    v-model:visible="exibirModalContato"
    modal
    header="Marcar como Solicitada Manualmente"
    :style="{ width: '32rem' }"
  >
    <div class="flex flex-col gap-3">
      <p class="text-sm text-gray-600">
        Informe como o contato foi realizado (ex.: telefone, WhatsApp, presencialmente).
      </p>
      <Textarea
        v-model="observacaoContato"
        rows="4"
        maxlength="50"
        placeholder="Descreva brevemente o meio de contato e o que foi combinado..."
        class="w-full"
        autofocus
      />
      <div class="flex justify-end">
        <small class="text-xs text-gray-400">{{ observacaoContato.length }} / 50</small>
      </div>
    </div>

    <template #footer>
      <Button
        label="Cancelar"
        text
        severity="secondary"
        @click="exibirModalContato = false"
      />
      <Button
        label="Confirmar"
        icon="pi pi-check"
        severity="info"
        :loading="isLoading"
        @click="marcarSolicitada"
      />
    </template>
  </Dialog>

  <!-- ── Modal: Rejeitar ────────────────────────────────────────────────────── -->
  <Dialog
    v-model:visible="exibirModalRejeitar"
    modal
    header="Rejeitar Diligência"
    :style="{ width: '32rem' }"
  >
    <div class="flex flex-col gap-3">
      <p class="text-sm text-gray-600">
        Informe o motivo da rejeição desta diligência.
      </p>
      <Textarea
        v-model="motivoRejeicao"
        rows="4"
        maxlength="50"
        placeholder="Ex.: Documento não localizado, solicitação indevida..."
        class="w-full"
        autofocus
      />
      <div class="flex justify-end">
        <small class="text-xs text-gray-400">{{ motivoRejeicao.length }} / 50</small>
      </div>
    </div>

    <template #footer>
      <Button
        label="Cancelar"
        text
        severity="secondary"
        @click="exibirModalRejeitar = false"
      />
      <Button
        label="Confirmar Rejeição"
        icon="pi pi-times"
        severity="danger"
        :loading="isLoading"
        @click="rejeitar"
      />
    </template>
  </Dialog>

  <!-- ── Modal: Enviar por E-mail ────────────────────────────────────────────────── -->
  <Dialog
    v-model:visible="exibirModalEmail"
    modal
    header="Enviar Diligência por E-mail"
    :style="{ width: '45rem' }"
  >
    <div class="flex flex-col gap-6 pt-2">

      <!-- Destinatários -->
      <div>
        <h3 class="text-sm font-semibold text-gray-700 mb-3 border-b pb-1">Destinatários</h3>
        <div v-if="emailsSugeridos.length" class="flex flex-col gap-2 mb-4">
          <div
            v-for="sugestao in emailsSugeridos"
            :key="sugestao.email"
            class="flex items-center gap-2"
          >
            <Checkbox
              v-model="emailsSelecionados"
              :inputId="sugestao.email"
              :value="sugestao.email"
            />
            <label :for="sugestao.email" class="text-sm text-gray-600 cursor-pointer">
              <strong>{{ sugestao.label }}</strong> ({{ sugestao.email }})
            </label>
          </div>
        </div>
        <p class="text-xs text-gray-500 mb-1">Outros E-mails (Pressione Enter após digitar):</p>
        <Chips
          v-model="emailsAvulsos"
          separator=","
          class="w-full"
          placeholder="exemplo@email.com"
        />
      </div>

      <!-- Documentos a Enviar -->
      <div>
        <h3 class="text-sm font-semibold text-gray-700 mb-3 border-b pb-1">Documentos a Enviar</h3>
        <div class="max-h-60 overflow-y-auto flex flex-col gap-2 border border-gray-200 rounded p-3 bg-gray-50">
          <div
            v-for="anexo in anexosGlobais"
            :key="anexo.id"
            class="flex items-center gap-2 bg-white p-2 rounded border border-gray-100 shadow-sm"
          >
            <Checkbox
              v-model="anexosSelecionados"
              :inputId="'anexo-' + anexo.id"
              :value="anexo.id"
            />
            <i class="pi pi-file-pdf text-red-500" />
            <label
              :for="'anexo-' + anexo.id"
              class="text-sm text-gray-700 cursor-pointer flex-1 truncate"
            >
              {{ anexo.nome }}
              <span class="text-gray-400 text-xs ml-1">({{ anexo.tipo_anexo || 'Documento' }})</span>
            </label>
          </div>
          <p v-if="!anexosGlobais.length" class="text-sm text-gray-400 text-center py-4">
            Nenhum arquivo físico disponível no processo.
          </p>
        </div>
      </div>

    </div>

    <template #footer>
      <Button label="Cancelar" text severity="secondary" @click="exibirModalEmail = false" />
      <Button
        label="Aprovar e Enviar"
        icon="pi pi-send"
        severity="primary"
        :loading="isSubmittingEmail"
        @click="enviarEmail"
      />
    </template>
  </Dialog>
</template>

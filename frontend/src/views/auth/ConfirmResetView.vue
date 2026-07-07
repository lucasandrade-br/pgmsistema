<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import Password from 'primevue/password'
import Button from 'primevue/button'
import api from '@/services/api'

const route     = useRoute()
const router    = useRouter()
const toast     = useToast()

const newPassword = ref('')
const isLoading   = ref(false)
let   resetToken  = null

onMounted(() => {
  resetToken = route.query.token ?? null

  if (!resetToken) {
    // Link sem token → redireciona ao login com aviso
    toast.add({
      severity: 'warn',
      summary: 'Link inválido',
      detail: 'O link de redefinição é inválido. Solicite um novo.',
      life: 5000,
    })
    router.replace({ name: 'login' })
  }
})

async function handleConfirm() {
  if (!newPassword.value || newPassword.value.length < 8) {
    toast.add({
      severity: 'warn',
      summary: 'Atenção',
      detail: 'A senha deve ter no mínimo 8 caracteres.',
      life: 3000,
    })
    return
  }

  isLoading.value = true
  try {
    await api.post('auth/password-reset/confirm/', {
      token: resetToken,
      new_password: newPassword.value,
    })

    toast.add({
      severity: 'success',
      summary: 'Senha redefinida!',
      detail: 'Sua senha foi alterada com sucesso. Faça o login.',
      life: 4000,
    })
    router.push({ name: 'login' })
  } catch (err) {
    // 400 → token inválido, expirado ou já utilizado
    const detail = err.response?.status === 400
      ? (err.response.data?.detail ?? 'Token inválido ou expirado. Solicite um novo link.')
      : 'Erro ao conectar ao servidor. Tente novamente.'

    toast.add({ severity: 'error', summary: 'Erro', detail, life: 5000 })
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex">

    <!-- ── Lado Esquerdo: Branding (desktop only) ───────────────────────── -->
    <div class="hidden lg:flex lg:w-1/2 bg-slate-900 text-white flex-col justify-center items-start p-16">
      <p class="text-sm font-semibold tracking-widest text-slate-400 uppercase mb-6">
        Procuradoria Geral do Município
      </p>
      <h1 class="text-5xl font-bold leading-tight mb-4">
        PGM<span class="text-blue-400">Sistema</span>
      </h1>
      <p class="text-lg text-slate-300 leading-relaxed max-w-sm">
        Gestão Inteligente de Processos Jurídicos para a administração pública municipal.
      </p>
    </div>

    <!-- ── Lado Direito: Formulário ─────────────────────────────────────── -->
    <div class="w-full lg:w-1/2 flex items-center justify-center bg-white px-8">
      <div class="w-full max-w-md">

        <div class="mb-8">
          <h2 class="text-2xl font-bold text-gray-900">Definir Nova Senha</h2>
          <p class="mt-1 text-sm text-gray-500">
            Escolha uma senha segura para sua conta.
          </p>
        </div>

        <form @submit.prevent="handleConfirm" class="flex flex-col gap-4" novalidate>

          <div class="flex flex-col gap-1.5">
            <label for="new-password" class="text-sm font-medium text-gray-700">
              Nova senha
            </label>
            <Password
              id="new-password"
              v-model="newPassword"
              placeholder="Mínimo 8 caracteres"
              :feedback="true"
              toggleMask
              autocomplete="new-password"
              class="w-full"
              inputClass="w-full"
            />
          </div>

          <Button
            type="submit"
            label="Salvar Nova Senha"
            :loading="isLoading"
            class="w-full mt-2"
          />

          <div class="text-center">
            <RouterLink
              to="/login"
              class="text-sm text-gray-500 hover:text-gray-800 transition-colors"
            >
              ← Voltar ao Login
            </RouterLink>
          </div>

        </form>
      </div>
    </div>

  </div>
</template>

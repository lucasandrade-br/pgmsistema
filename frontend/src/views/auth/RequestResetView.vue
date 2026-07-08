<script setup>
import { ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import api from '@/services/api'

const toast     = useToast()
const email     = ref('')
const isLoading = ref(false)

async function handleRequest() {
  if (!email.value) {
    toast.add({ severity: 'warn', summary: 'Atenção', detail: 'Informe seu e-mail.', life: 3000 })
    return
  }

  isLoading.value = true
  try {
    // O backend sempre retorna 200, independente de o e-mail existir ou não
    // (anti-enumeração). A view replica esse comportamento no Toast.
    await api.post('auth/password-reset/request/', { email: email.value })
  } catch {
    // Ignorado propositalmente: a UX não deve revelar se o e-mail existe
  } finally {
    isLoading.value = false
  }

  // Toast de sucesso SEMPRE exibido (mesmo se o e-mail não existir)
  toast.add({
    severity: 'success',
    summary: 'Instruções enviadas',
    detail: 'Se o e-mail constar em nossa base, você receberá um link em breve.',
    life: 6000,
  })
  email.value = ''
}
</script>

<template>
  <div class="min-h-screen flex">

    <!-- ── Lado Esquerdo: Branding (desktop only) ───────────────────────── -->
    <div class="hidden lg:flex lg:w-1/2 bg-slate-900 text-white flex-col justify-center items-start p-16">
      <p class="text-sm font-semibold tracking-widest text-slate-400 uppercase mb-6">
        Procuradoria-Geral do Município
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
          <h2 class="text-2xl font-bold text-gray-900">Recuperar Senha</h2>
          <p class="mt-1 text-sm text-gray-500">
            Informe seu e-mail e enviaremos as instruções de acesso.
          </p>
        </div>

        <form @submit.prevent="handleRequest" class="flex flex-col gap-4" novalidate>

          <div class="flex flex-col gap-1.5">
            <label for="email" class="text-sm font-medium text-gray-700">E-mail</label>
            <InputText
              id="email"
              v-model="email"
              type="email"
              placeholder="seu@email.com"
              autocomplete="email"
              class="w-full"
            />
          </div>

          <Button
            type="submit"
            label="Enviar Instruções"
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

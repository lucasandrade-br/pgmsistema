<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { useAuthStore } from '@/stores/auth'
import Checkbox  from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import Password  from 'primevue/password'
import Button    from 'primevue/button'

const router    = useRouter()
const toast     = useToast()
const authStore = useAuthStore()

const username   = ref('')
const password   = ref('')
const rememberMe = ref(false)
const isLoading  = ref(false)

async function handleLogin() {
  if (!username.value || !password.value) {
    toast.add({ severity: 'warn', summary: 'Atenção', detail: 'Preencha usuário e senha.', life: 3000 })
    return
  }

  isLoading.value = true
  try {
    await authStore.login({ username: username.value, password: password.value }, rememberMe.value)
    router.push({ name: 'home' })
  } catch (err) {
    const detail = err.response?.status === 401
      ? 'Usuário ou senha incorretos.'
      : 'Erro ao conectar ao servidor. Tente novamente.'
    toast.add({ severity: 'error', summary: 'Erro de autenticação', detail, life: 4000 })
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
      <div class="mt-12 flex flex-col gap-3 text-sm text-slate-400">
        <span class="flex items-center gap-2">
          <i class="pi pi-shield text-blue-400" /> Controle de acesso por perfil
        </span>
        <span class="flex items-center gap-2">
          <i class="pi pi-history text-blue-400" /> Timeline completa de movimentações
        </span>
        <span class="flex items-center gap-2">
          <i class="pi pi-send text-blue-400" /> Fluxo automatizado de diligências
        </span>
      </div>
    </div>

    <!-- ── Lado Direito: Formulário ─────────────────────────────────────── -->
    <div class="w-full lg:w-1/2 flex items-center justify-center bg-white px-8">
      <div class="w-full max-w-md">

        <!-- Cabeçalho do formulário -->
        <div class="mb-8">
          <h2 class="text-2xl font-bold text-gray-900">Bem-vindo(a)!</h2>
          <p class="mt-1 text-sm text-gray-500">Entre com suas credenciais para acessar o sistema.</p>
        </div>

        <!-- Formulário -->
        <form @submit.prevent="handleLogin" class="flex flex-col gap-4" novalidate>

          <div class="flex flex-col gap-1.5">
            <label for="username" class="text-sm font-medium text-gray-700">Usuário</label>
            <InputText
              id="username"
              v-model="username"
              placeholder="Digite seu usuário"
              autocomplete="username"
              class="w-full"
            />
          </div>

          <div class="flex flex-col gap-1.5">
            <label for="password" class="text-sm font-medium text-gray-700">Senha</label>
            <Password
              id="password"
              v-model="password"
              placeholder="Digite sua senha"
              :feedback="false"
              toggleMask
              autocomplete="current-password"
              class="w-full"
              inputClass="w-full"
            />
          </div>

          <!-- Lembrar-me -->
          <div class="flex items-center gap-2">
            <Checkbox inputId="remember" v-model="rememberMe" :binary="true" />
            <label for="remember" class="text-sm text-gray-700 cursor-pointer select-none">
              Lembrar meu acesso
            </label>
          </div>

          <Button
            type="submit"
            label="Entrar"
            :loading="isLoading"
            class="w-full mt-2"
          />

          <div class="text-center">
            <RouterLink
              to="/esqueci-a-senha"
              class="text-sm text-gray-500 hover:text-gray-800 transition-colors"
            >
            Esqueceu sua senha?
            </RouterLink>
          </div>

        </form>
      </div>
    </div>

  </div>
</template>

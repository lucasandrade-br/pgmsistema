<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Menu from 'primevue/menu'

const router = useRouter()
const authStore = useAuthStore()

// ── Estado do Layout ────────────────────────────────────────────────────────
const isPinned = ref(typeof window !== 'undefined' && window.innerWidth >= 768)
const isHovered = ref(false)
const isExpanded = computed(() => isPinned.value || isHovered.value)

function toggleSidebar() { isPinned.value = !isPinned.value }
function closeSidebar() { isPinned.value = false }

// ── Estado do Usuário e RBAC ──────────────────────────────────────────────
const currentUser = computed(() => authStore.user ?? {})

function hasAccess(roles) {
  if (!roles || roles.length === 0) return true
  const userRoles = currentUser.value.grupos || []
  if (currentUser.value.is_superuser) return true
  return roles.some(role => userRoles.includes(role))
}

// ── Menu Suspenso do Usuário ────────────────────────────────────────────────
const menuUsuario = ref(null)

function toggleMenuUsuario(event) {
  menuUsuario.value.toggle(event)
}

const opcoesMenuUsuario = ref([
  {
    label: 'Redefinir Senha',
    icon: 'pi pi-key',
    command: () => { authStore.logout(); router.push('/esqueci-a-senha') }
  },
  {
    separator: true
  },
  {
    label: 'Sair',
    icon: 'pi pi-power-off',
    command: () => {
      authStore.logout()
      router.push('/login')
    }
  }
])

// ── Itens de Navegação Categorizados ────────────────────────────────────────
const navItems = [
  { icon: 'pi-home',            label: 'Início',              to: '/' },  
  { heading: 'Fluxo Operacional' },
  { icon: 'pi-inbox',           label: 'Análises Pendentes',  to: '/analises-pendentes' },
  { icon: 'pi-arrows-h',        label: 'Distribuição', to: '/processos/distribuicao', roles: ['Protocolador-Chefe', 'Procurador-Chefe', 'Procurador-Analista'] },
  { icon: 'pi-file-edit',       label: 'Diligências',          to: '/diligencias' },

  { heading: 'Gerencial' },
  { icon: 'pi-plus-circle',     label: 'Novo Processo',       to: '/processos/novo', roles: ['Protocolador-Chefe', 'Procurador-Chefe', 'Protocolo', 'Cadastrante'] },
  { icon: 'pi-search',          label: 'Consulta Geral',       to: '/consulta-geral' },

  { heading: 'Administração', roles: ['Procurador-Chefe', 'Protocolador-Chefe'] },
  { icon: 'pi-users',           label: 'Usuários',             to: '/usuarios', roles: ['Procurador-Chefe', 'Protocolador-Chefe'] },
  { icon: 'pi-cog',             label: 'Configurações',        to: '/configuracoes', roles : ['Protocolador-Chefe'] }
]
</script>

<template>
  <!-- ═══════════════════════════ TOPBAR ════════════════════════════════════ -->
  <header class="fixed top-0 w-full z-50 bg-white border-b border-gray-200">
    <div class="h-16 flex items-center justify-between px-4">

      <!-- Esquerda: hambúrguer + logomarca -->
      <div class="flex items-center gap-3">
        <button
          @click="toggleSidebar"
          class="p-2 rounded-md text-gray-500 hover:bg-gray-100 transition-colors"
          aria-label="Abrir/fechar menu"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none"
            viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <span class="text-lg font-semibold tracking-tight text-gray-800">
          PGM<span class="text-blue-600 font-bold">Sistema</span>
        </span>
      </div>

      <!-- Direita: sino + usuário -->
      <div class="flex items-center gap-4">
        <button
          class="relative p-2 rounded-md text-gray-500 hover:bg-gray-100 transition-colors"
          aria-label="Notificações"
        >
          <i class="pi pi-bell text-lg" />
          <span class="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full ring-2 ring-white" />
        </button>

        <div
          class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer hover:bg-gray-50 rounded-lg px-2 py-1 transition-colors"
          @click="toggleMenuUsuario"
        >
          <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white">
            <i class="pi pi-user text-sm" />
          </div>
          <div class="hidden md:flex flex-col leading-tight">
            <span class="font-medium text-gray-800">{{ currentUser.first_name || currentUser.username || 'Usuário' }}</span>
            <span class="text-xs text-gray-500">{{ currentUser.grupos?.[0] || 'Colaborador' }}</span>
          </div>
          <i class="pi pi-chevron-down text-xs text-gray-400 hidden md:block" />
        </div>
        <Menu ref="menuUsuario" :model="opcoesMenuUsuario" :popup="true" />
      </div>

    </div>
  </header>

  <!-- ═══════════════════════ OVERLAY (mobile) ══════════════════════════════ -->
  <transition name="fade">
    <div
      v-if="isPinned"
      class="fixed inset-0 z-30 bg-black/30 md:hidden"
      @click="closeSidebar"
    />
  </transition>

  <!-- ══════════════════════════ SIDEBAR ════════════════════════════════════ -->
  <!--
    Largura  → isExpanded: w-64 (expandida) | w-16 (mini, só ícones)
    Posição  → isPinned:
                 true  → translate-x-0  (visível mobile + desktop)
                 false → -translate-x-full md:translate-x-0
                         (escondida no mobile; mini visível no desktop)
    Conteúdo → overflow-hidden garante que labels não "vazem" enquanto a
               sidebar está colapsada; transition-all anima width + transform.
  -->
  <aside
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
    :class="[
      'fixed left-0 top-16 h-[calc(100vh-4rem)] z-40',
      'bg-white border-r border-gray-200 overflow-hidden',
      'transition-all duration-300 ease-in-out',
      isExpanded ? 'w-64' : 'w-16',
      isPinned ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
    ]"
  >
    <nav class="flex flex-col gap-0.5 p-2 pt-4">
      <template v-for="item in navItems" :key="item.to ?? item.heading ?? '__sep__'">

        <!-- Título de seção (heading) -->
        <template v-if="item.heading && hasAccess(item.roles)">
          <p
            v-if="isExpanded"
            class="text-[11px] font-semibold text-slate-400 uppercase tracking-widest px-3 pt-4 pb-1"
            >
            {{ item.heading }}
          </p>
          <hr v-else class="my-2 border-gray-200" />
        </template>

        <!-- Item de navegação com RBAC -->
        <RouterLink
          v-else-if="hasAccess(item.roles)"
          :to="item.to"
          :title="!isExpanded ? item.label : undefined"
          :class="[
            'flex items-center py-2.5 rounded-lg text-sm text-gray-600 font-medium',
            'hover:bg-blue-50 hover:text-blue-700 transition-colors group',
            isExpanded ? 'gap-3 px-3' : 'justify-center px-0',
          ]"
          @click="closeSidebar"
        >
          <!-- Ícone: sempre visível -->
          <i
            :class="`pi ${item.icon} flex-shrink-0 text-base text-gray-400 group-hover:text-blue-600`"
          />
          <!-- Label: fade + clip quando mini.
               max-w-0 + opacity-0 colapsa sem quebrar o layout do ícone. -->
          <span
            :class="[
              'overflow-hidden whitespace-nowrap transition-all duration-200',
              isExpanded ? 'max-w-xs opacity-100' : 'max-w-0 opacity-0',
            ]"
          >{{ item.label }}</span>
        </RouterLink>

      </template>
    </nav>
  </aside>

  <!-- ═════════════════════ CONTEÚDO PRINCIPAL ══════════════════════════════ -->
  <!--
    pt-16   → compensa a Topbar fixa (4rem).
    md:pl-* → segue APENAS isPinned (não isHovered), para que o layout não
              "pule" quando o usuário apenas passa o mouse sobre a sidebar.
              isPinned=true  → md:pl-64 (reserva espaço para sidebar aberta)
              isPinned=false → md:pl-16 (reserva espaço para sidebar mini)
  -->
  <main
    :class="[
      'min-h-screen bg-slate-50 pt-16 transition-all duration-300',
      isPinned ? 'md:pl-64' : 'md:pl-16',
    ]"
  >
    <div class="p-6">
      <!-- Rotas filhas (definidas no router como children de /) são
           renderizadas aqui pelo Vue Router. -->
      <RouterView />
    </div>
  </main>
</template>

<style scoped>
/* Transição de opacidade do overlay mobile */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>


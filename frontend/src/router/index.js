import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Lazy-load de todas as views (code splitting automático pelo Vite)
const AppLayout              = () => import('@/layouts/AppLayout.vue')
const HomeView               = () => import('@/views/HomeView.vue')
const LoginView              = () => import('@/views/auth/LoginView.vue')
const RequestResetView       = () => import('@/views/auth/RequestResetView.vue')
const ConfirmResetView       = () => import('@/views/auth/ConfirmResetView.vue')
const AnalisesPendentesView  = () => import('@/views/processos/AnalisesPendentesView.vue')
const DetalhesProcessoView   = () => import('@/views/processos/DetalhesProcessoView.vue')
const NovoProcessoView       = () => import('@/views/processos/NovoProcessoView.vue')
const GestaoEnvolvidosView   = () => import('@/views/cadastros/GestaoEnvolvidosView.vue')
const NotFoundView           = () => import('@/views/NotFoundView.vue')

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // ── Rotas públicas (sem autenticação) ─────────────────────────────────
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { requiresAuth: false },
    },
    {
      path: '/esqueci-a-senha',
      name: 'request-reset',
      component: RequestResetView,
      meta: { requiresAuth: false },
    },
    {
      path: '/redefinir-senha',
      name: 'confirm-reset',
      component: ConfirmResetView,
      meta: { requiresAuth: false },
    },

    // ── Rotas protegidas (envolvidas pelo AppLayout) ───────────────────────
    {
      path: '/',
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'home',
          component: HomeView,
        },
        {
          path: 'analises-pendentes',
          name: 'analises-pendentes',
          component: AnalisesPendentesView,
          // sem meta.roles — acesso comum a todos os grupos autenticados
        },
        {
          path: 'processos/detalhes/:id',
          name: 'detalhes-processo',
          component: DetalhesProcessoView,
        },
        {
          path: 'processos/novo',
          name: 'novo-processo',
          component: NovoProcessoView,
          meta: {
            roles: ['Protocolador-Chefe', 'Procurador-Chefe', 'Protocolo', 'Cadastrante'],
          },
        },
        {
          path: 'processos/distribuicao',
          name: 'distribuicao-lote',
          component: () => import('@/views/processos/DistribuicaoLoteView.vue'),
          meta: {
            roles: ['Protocolador-Chefe', 'Procurador-Chefe'],
          },
        },
        {
          path: '/consulta-geral',
          name: 'consulta-geral',
          component: () => import('@/views/processos/ConsultaGeralView.vue'),
          meta: { requiresAuth: true }
        },
        {
          path: '/diligencias',
          name: 'diligencias',
          component: () => import('@/views/processos/ListagemDiligenciasView.vue'),
        },
        {
          path: 'painel-gerencial',
          name: 'painel-gerencial',
          component: () => import('@/views/PainelGerencialView.vue'),
          meta: {
            roles: ['Procurador-Chefe', 'Protocolador-Chefe'],
          },
        },
        {
          path: 'redistribuicao',
          name: 'redistribuicao',
          component: () => import('@/views/processos/RedistribuicaoView.vue'),
          meta: {
            roles: ['Procurador-Chefe', 'Protocolador-Chefe'],
          },
        },
        {
          path: '/cadastros/envolvidos',
          name: 'gestao-envolvidos',
          component: GestaoEnvolvidosView,
          meta: {
            roles: ['Protocolador-Chefe', 'Procurador-Chefe', 'Protocolo', 'Cadastrante'],
          },
        },
      ],
    },

    // ── Rotas públicas — sem AppLayout e sem autenticação ─────────────────
    {
      path: '/autos/:token',
      name: 'autos-publicos',
      component: () => import('@/views/AutosPublicosView.vue'),
      meta: { requiresAuth: false },
    },

    // ── Catch-all: qualquer rota não mapeada → 404 ────────────────────────
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: NotFoundView,
    },
  ],
})

// ── Navigation Guard global ───────────────────────────────────────────────
router.beforeEach((to) => {
  const authStore = useAuthStore()
  const user = authStore.user || { grupos: [], is_superuser: false }
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)

  // 1. Autenticação
  if (requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login' }
  }

  if (to.name === 'login' && authStore.isAuthenticated) {
    return { name: 'home' }
  }

  // 2. RBAC Centralizado: verifica meta.roles da rota (ou de qualquer ancestral)
  const roles = to.matched.flatMap((record) => record.meta.roles ?? [])
  if (roles.length > 0) {
    if (user.is_superuser) return // superuser passa sempre

    const hasAccess = roles.some((role) => user.grupos?.includes(role))
    if (!hasAccess) {
      console.warn(`RBAC: acesso bloqueado. Exigido: [${roles}]. Usuário: [${user.grupos}]`)
      return { path: '/', query: { error: 'acesso_negado' } }
    }
  }
})

export default router


import axios from 'axios'
// Import estático no topo: o ES Module já está resolvido quando os
// callbacks dos interceptors executam. Não há circular dep em runtime
// porque useAuthStore() só é CHAMADO dentro das funções, não na carga
// do módulo — momento em que auth.js também já importou api.js.
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1/',
  timeout: 10000,
})

// ── Request Interceptor ──────────────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

// ── Response Interceptor ─────────────────────────────────────────────────────
// Em respostas 401 (Unauthorized), desloga o usuário automaticamente.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
    }
    return Promise.reject(error)
  },
)

export default api


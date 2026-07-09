import { defineStore } from 'pinia'
import api from '@/services/api'

// Decodifica o payload do JWT sem biblioteca extra.
// Retorna null se o token for nulo ou malformado.
function _decodeUser(token) {
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return { id: payload.user_id, username: payload.username ?? null, grupos: payload.grupos ?? [] }
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => {
    // ── Suporte a abertura em nova aba ───────────────────────────────────────
    // Quando outra aba abre esta via window.open, ela deposita o token em
    // localStorage._new_tab_token antes de chamar window.open.
    // Aqui consumimos essa chave de uso único e armazenamos no sessionStorage
    // desta aba para que refreshes subsequentes também funcionem.
    const newTabToken = localStorage.getItem('_new_tab_token')
    if (newTabToken) {
      localStorage.removeItem('_new_tab_token')   // consume imediatamente
      sessionStorage.setItem('token', newTabToken) // persiste para esta aba
    }

    // Hidratação: ao recarregar a página (F5) o token é restaurado do
    // storage escolhido durante o login.
    //   localStorage   → "Lembrar meu acesso" marcado (persiste entre abas e fechamentos)
    //   sessionStorage → sessão da aba atual (perdido ao fechar o browser)
    const token =
      localStorage.getItem('token') ??
      sessionStorage.getItem('token') ??
      null

    return {
      token,
      user: _decodeUser(token),  // restaura dados do usuário direto do payload do JWT
    }
  },

  getters: {
    isAuthenticated: (state) => !!state.token,
  },

  actions: {
    /**
     * Autentica o usuário contra o backend Django/SimpleJWT.
     *
     * @param {{ username: string, password: string }} credentials
     * @param {boolean} rememberMe  true → localStorage (persiste); false → sessionStorage
     * @throws {Error} com a mensagem de erro da API em caso de falha
     */
    async login(credentials, rememberMe = false) {
      const { data } = await api.post('auth/token/', credentials)

      const token = data.access
      this.token = token
      this.user  = _decodeUser(token) ?? { username: credentials.username }

      // Persisteência controlada pelo checkbox "Lembrar meu acesso".
      // Nota de segurança (OWASP A02/A03): localStorage é acessível via JS
      // e suscetível a XSS. Aceitável como trade-off deliberado de UX;
      // mitigado pelo CSP da aplicação e pela ausência de eval/innerHTML.
      if (rememberMe) {
        localStorage.setItem('token', token)
      } else {
        sessionStorage.setItem('token', token)
      }
    },

    /**
     * Desloga o usuário: limpa state + ambos os storages.
     * Chamado pelo Response Interceptor do Axios em respostas 401.
     */
    logout() {
      this.token = null
      this.user  = null
      localStorage.removeItem('token')
      sessionStorage.removeItem('token')
      window.location.href = '/login'
    },
  },
})

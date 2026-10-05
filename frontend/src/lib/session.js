import { reactive } from 'vue'

const TOKEN_KEY = 'paveda_token'

export const session = reactive({
  token: localStorage.getItem(TOKEN_KEY),
  user: null,
})

export function setToken(token) {
  session.token = token
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearSession() {
  session.token = null
  session.user = null
  localStorage.removeItem(TOKEN_KEY)
}

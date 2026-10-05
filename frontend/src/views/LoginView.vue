<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { API_BASE } from '../lib/api'

const route = useRoute()

const ERRORS = {
  not_authorized: 'is not enabled. Ask an administrator to add you.',
  email_not_verified: 'Your Google e-mail address is not verified.',
  invalid_state: 'The login session expired, please try again.',
  google_error: 'Google sign-in failed, please try again.',
  access_denied: 'Sign-in was cancelled.',
}

const error = computed(() => {
  const code = route.query.error
  if (!code) return null
  if (code === 'not_authorized') return `The address ${route.query.email || ''} ${ERRORS.not_authorized}`
  return ERRORS[code] || `Login error: ${code}`
})

function login() {
  if (route.query.redirect) sessionStorage.setItem('paveda_redirect', route.query.redirect)
  window.location.href = `${API_BASE}/auth/login`
}
</script>

<template>
  <div class="d-flex justify-content-center pt-5">
    <div class="card shadow-sm login-card w-100 mt-5">
      <div class="card-body p-4 text-center">
        <h1 class="h4 mb-1">PaVeDa</h1>
        <p class="text-muted mb-4">Excel Manager</p>
        <div v-if="error" class="alert alert-danger text-start small">{{ error }}</div>
        <button class="btn btn-primary w-100" @click="login"><i class="bi bi-google me-2"></i>Sign in with Google</button>
      </div>
    </div>
  </div>
</template>

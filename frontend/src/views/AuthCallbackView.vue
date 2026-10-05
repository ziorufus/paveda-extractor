<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { setToken } from '../lib/session'

const router = useRouter()

onMounted(() => {
  const token = new URLSearchParams(window.location.hash.slice(1)).get('token')
  if (!token) {
    router.replace({ name: 'login', query: { error: 'google_error' } })
    return
  }
  setToken(token)
  const redirect = sessionStorage.getItem('paveda_redirect') || '/'
  sessionStorage.removeItem('paveda_redirect')
  router.replace(redirect)
})
</script>

<template>
  <div class="text-center text-muted pt-5"><span class="spinner-border spinner-border-sm me-2"></span>Signing in…</div>
</template>

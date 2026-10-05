<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearSession, session } from './lib/session'

const router = useRouter()
const route = useRoute()
const menuOpen = ref(false)

watch(() => route.fullPath, () => (menuOpen.value = false))

function logout() {
  clearSession()
  router.push({ name: 'login' })
}
</script>

<template>
  <nav v-if="session.user" class="navbar navbar-expand-md navbar-dark bg-dark mb-4">
    <div class="container">
      <RouterLink class="navbar-brand" :to="{ name: 'projects' }">PaVeDa <small>Excel Manager</small></RouterLink>
      <button class="navbar-toggler" type="button" aria-label="Toggle navigation" @click="menuOpen = !menuOpen">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" :class="{ show: menuOpen }">
        <ul class="navbar-nav me-auto">
          <li class="nav-item">
            <RouterLink class="nav-link" active-class="active" :to="{ name: 'projects' }" exact-active-class="active">
              <i class="bi bi-translate me-1"></i>Languages
            </RouterLink>
          </li>
          <template v-if="session.user.is_admin">
            <li class="nav-item">
              <RouterLink class="nav-link" active-class="active" :to="{ name: 'users' }"><i class="bi bi-people me-1"></i>Users</RouterLink>
            </li>
            <li class="nav-item">
              <RouterLink class="nav-link" active-class="active" :to="{ name: 'sets' }"><i class="bi bi-collection me-1"></i>Sets</RouterLink>
            </li>
            <li class="nav-item">
              <RouterLink class="nav-link" active-class="active" :to="{ name: 'export' }"><i class="bi bi-box-arrow-down me-1"></i>ValPaL export</RouterLink>
            </li>
          </template>
        </ul>
        <div class="d-flex align-items-center gap-3 text-light">
          <span class="small">
            <i class="bi bi-person-circle me-1"></i>{{ session.user.name || session.user.email }}
            <span v-if="session.user.is_admin" class="badge text-bg-warning ms-1">admin</span>
          </span>
          <button class="btn btn-outline-light btn-sm" @click="logout"><i class="bi bi-box-arrow-right me-1"></i>Log out</button>
        </div>
      </div>
    </div>
  </nav>

  <main class="container pb-5">
    <RouterView />
  </main>
</template>

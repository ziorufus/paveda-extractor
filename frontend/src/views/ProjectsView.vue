<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import VersionStatus from '../components/VersionStatus.vue'
import { api } from '../lib/api'
import { formatDate } from '../lib/format'
import { session } from '../lib/session'

const router = useRouter()
const projects = ref([])
const loading = ref(true)
const error = ref('')
const filter = ref('')

const isAdmin = computed(() => session.user.is_admin)

const visible = computed(() => {
  const query = filter.value.trim().toLowerCase()
  if (!query) return projects.value
  return projects.value.filter((project) =>
    [project.name, project.language_id, project.glottocode, project.family, project.contributors]
      .filter(Boolean)
      .some((value) => value.toLowerCase().includes(query)),
  )
})

async function load() {
  loading.value = true
  try {
    projects.value = await api.get('/projects')
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function remove(project) {
  if (!confirm(`Delete "${project.name}" and all its ${project.version_count} versions? This cannot be undone.`)) return
  try {
    await api.delete(`/projects/${project.id}`)
    projects.value = projects.value.filter((item) => item.id !== project.id)
  } catch (err) {
    error.value = err.message
  }
}

function open(project) {
  router.push({ name: 'project', params: { id: project.id } })
}

onMounted(load)
</script>

<template>
  <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
    <h1 class="h3 mb-0 me-auto">Languages</h1>
    <input v-model="filter" type="search" class="form-control w-auto" placeholder="Search…" />
    <RouterLink v-if="isAdmin" class="btn btn-primary" :to="{ name: 'project-new' }"><i class="bi bi-plus-lg me-1"></i>New language</RouterLink>
  </div>

  <div v-if="error" class="alert alert-danger">{{ error }}</div>

  <div v-if="loading" class="text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading…</div>
  <div v-else-if="!projects.length" class="alert alert-info">
    {{ isAdmin ? 'No languages yet.' : 'No languages have been assigned to you yet. Ask an administrator.' }}
  </div>
  <div v-else class="card shadow-sm">
    <div class="table-responsive">
      <table class="table table-hover mb-0">
        <thead class="table-light">
          <tr>
            <th>Name</th>
            <th>ID</th>
            <th class="d-none d-lg-table-cell">Family</th>
            <th class="d-none d-md-table-cell">Contributors</th>
            <th class="text-center">Versions</th>
            <th>Last upload</th>
            <th v-if="isAdmin" class="text-center d-none d-md-table-cell" title="Assigned users"><i class="bi bi-people"></i></th>
            <th v-if="isAdmin"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="project in visible" :key="project.id" class="clickable-row" @click="open(project)">
            <td class="fw-semibold">{{ project.name }}</td>
            <td><code>{{ project.language_id }}</code></td>
            <td class="d-none d-lg-table-cell">{{ project.family || '—' }}</td>
            <td class="d-none d-md-table-cell small">{{ project.contributors || '—' }}</td>
            <td class="text-center">{{ project.version_count }}</td>
            <td>
              <template v-if="project.latest_version">
                <div class="small">{{ formatDate(project.latest_version.created_at) }}</div>
                <VersionStatus :version="project.latest_version" />
              </template>
              <span v-else class="text-muted small">never</span>
            </td>
            <td v-if="isAdmin" class="text-center d-none d-md-table-cell">{{ project.user_ids.length }}</td>
            <td v-if="isAdmin" class="table-actions" @click.stop>
              <RouterLink class="btn btn-sm btn-outline-secondary me-1" :to="{ name: 'project-edit', params: { id: project.id } }" title="Edit">
                <i class="bi bi-pencil"></i>
              </RouterLink>
              <button class="btn btn-sm btn-outline-danger" title="Delete" @click="remove(project)"><i class="bi bi-trash"></i></button>
            </td>
          </tr>
          <tr v-if="!visible.length">
            <td colspan="8" class="text-muted text-center">No match</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

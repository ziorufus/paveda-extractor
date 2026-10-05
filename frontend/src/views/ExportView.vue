<script setup>
import { computed, onMounted, ref } from 'vue'
import CheckList from '../components/CheckList.vue'
import LogViewer from '../components/LogViewer.vue'
import { api } from '../lib/api'
import { formatDate } from '../lib/format'

const sets = ref([])
const projects = ref([])
const selected = ref([])
const loading = ref(true)
const exporting = ref(false)
const error = ref('')
const errorLog = ref('')
const activeSet = ref(null)

// Mirrors the backend: the latest version whose conversion did not fail
function exportableVersion(project) {
  return project.versions.find((version) => version.success !== false) || null
}

const items = computed(() =>
  projects.value.map((project) => {
    const version = exportableVersion(project)
    const latest = project.versions[0]
    return {
      id: project.id,
      label: project.name,
      sublabel: version ? `v${version.number} · ${formatDate(version.created_at)}` : 'no usable version',
      disabled: !version,
      warning: version && latest && latest.id !== version.id ? `latest upload (v${latest.number}) failed` : '',
    }
  }),
)

const exportableIds = computed(() => new Set(items.value.filter((item) => !item.disabled).map((item) => item.id)))

async function load() {
  try {
    const [setList, projectList] = await Promise.all([api.get('/sets'), api.get('/projects')])
    sets.value = setList
    projects.value = await Promise.all(
      projectList.map(async (project) => ({ ...project, versions: project.version_count ? await api.get(`/projects/${project.id}/versions`) : [] })),
    )
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

function applySet(projectSet) {
  activeSet.value = projectSet.id
  selected.value = projectSet.project_ids.filter((id) => exportableIds.value.has(id))
}

const skippedInSet = computed(() => {
  const projectSet = sets.value.find((item) => item.id === activeSet.value)
  if (!projectSet) return []
  return projectSet.project_ids.filter((id) => !exportableIds.value.has(id)).map((id) => projects.value.find((p) => p.id === id)?.name)
})

async function runExport() {
  exporting.value = true
  error.value = ''
  errorLog.value = ''
  try {
    await api.downloadPost('/export', { project_ids: selected.value }, 'valpal-export.zip')
  } catch (err) {
    error.value = err.message
    errorLog.value = err.detail?.log || ''
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <h1 class="h3 mb-1">ValPaL export</h1>
  <p class="text-muted small">
    Converts the latest valid Excel version of each selected language and downloads the ZIP package with the CSV files, the log and a summary.
  </p>

  <div v-if="loading" class="text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading…</div>

  <template v-else>
    <div class="card shadow-sm mb-3">
      <div class="card-header">Sets</div>
      <div class="card-body">
        <div v-if="sets.length" class="d-flex flex-wrap gap-2">
          <button
            v-for="projectSet in sets"
            :key="projectSet.id"
            type="button"
            class="btn btn-sm"
            :class="activeSet === projectSet.id ? 'btn-primary' : 'btn-outline-primary'"
            :title="projectSet.description || ''"
            @click="applySet(projectSet)"
          >
            {{ projectSet.name }} <span class="badge text-bg-light ms-1">{{ projectSet.project_ids.length }}</span>
          </button>
        </div>
        <div v-else class="small text-muted">No sets defined. <RouterLink :to="{ name: 'sets' }">Create one</RouterLink>.</div>
        <div v-if="skippedInSet.length" class="small text-warning-emphasis mt-2">
          <i class="bi bi-exclamation-triangle me-1"></i>Not selected (no usable version): {{ skippedInSet.join(', ') }}
        </div>
      </div>
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-header">Languages</div>
      <div class="card-body">
        <CheckList v-model="selected" :items="items" empty-text="No languages" @update:model-value="activeSet = null" />
      </div>
    </div>

    <button class="btn btn-primary" :disabled="!selected.length || exporting" @click="runExport">
      <span v-if="exporting" class="spinner-border spinner-border-sm me-1"></span>
      <i v-else class="bi bi-file-zip me-1"></i>Generate ZIP ({{ selected.length }} languages)
    </button>
    <span v-if="exporting" class="small text-muted ms-2">Running the conversion, this may take a few minutes…</span>

    <div v-if="error" class="alert alert-danger mt-3">{{ error }}</div>
    <LogViewer v-if="errorLog" :log="errorLog" />
  </template>
</template>

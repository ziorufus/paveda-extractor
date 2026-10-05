<script setup>
import { computed, onMounted, ref } from 'vue'
import AppModal from '../components/AppModal.vue'
import LogViewer from '../components/LogViewer.vue'
import VersionStatus from '../components/VersionStatus.vue'
import { api } from '../lib/api'
import { formatDate, formatSize, userLabel } from '../lib/format'
import { session } from '../lib/session'

const props = defineProps({ id: { type: String, required: true } })

const project = ref(null)
const versions = ref([])
const error = ref('')
const loading = ref(true)

const fileInput = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)
const uploadResult = ref(null)

const logVersion = ref(null)

const isAdmin = computed(() => session.user.is_admin)

const metadata = computed(() => {
  if (!project.value) return []
  const p = project.value
  return [
    ['Language ID', p.language_id],
    ['Glottocode', p.glottocode],
    ['Glottolog name', p.glottolog_name],
    ['Family', p.family],
    ['ISO 639-3', p.iso639p3code],
    ['Macroarea', p.macroarea],
    ['Coordinates', p.latitude && p.longitude ? `${p.latitude}, ${p.longitude}` : null],
    ['Contributors', p.contributors],
  ]
})

async function load() {
  loading.value = true
  try {
    ;[project.value, versions.value] = await Promise.all([
      api.get(`/projects/${props.id}`),
      api.get(`/projects/${props.id}/versions`),
    ])
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function upload() {
  if (!selectedFile.value) return
  const form = new FormData()
  form.append('file', selectedFile.value)
  uploading.value = true
  uploadResult.value = null
  error.value = ''
  try {
    const version = await api.upload(`/projects/${props.id}/versions`, form)
    uploadResult.value = version
    versions.value = [version, ...versions.value]
    selectedFile.value = null
    fileInput.value.value = ''
  } catch (err) {
    error.value = err.message
  } finally {
    uploading.value = false
  }
}

async function showLog(version) {
  try {
    logVersion.value = version.log !== undefined ? version : await api.get(`/versions/${version.id}`)
  } catch (err) {
    error.value = err.message
  }
}

async function download(path) {
  try {
    await api.download(path)
  } catch (err) {
    error.value = err.message
  }
}

async function remove(version) {
  if (!confirm(`Delete version ${version.number} (${version.original_filename})? This cannot be undone.`)) return
  try {
    await api.delete(`/versions/${version.id}`)
    versions.value = versions.value.filter((item) => item.id !== version.id)
    if (uploadResult.value?.id === version.id) uploadResult.value = null
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <nav aria-label="breadcrumb">
    <ol class="breadcrumb">
      <li class="breadcrumb-item"><RouterLink :to="{ name: 'projects' }">Languages</RouterLink></li>
      <li class="breadcrumb-item active">{{ project?.name || '…' }}</li>
    </ol>
  </nav>

  <div v-if="error" class="alert alert-danger alert-dismissible">
    {{ error }}
    <button type="button" class="btn-close" @click="error = ''"></button>
  </div>
  <div v-if="loading" class="text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading…</div>

  <template v-if="project">
    <div class="d-flex align-items-center gap-2 mb-3">
      <h1 class="h3 mb-0 me-auto">{{ project.name }}</h1>
      <RouterLink v-if="isAdmin" class="btn btn-outline-secondary" :to="{ name: 'project-edit', params: { id: project.id } }">
        <i class="bi bi-pencil me-1"></i>Edit
      </RouterLink>
    </div>

    <div class="row g-3 mb-4">
      <div class="col-lg-5">
        <div class="card shadow-sm h-100">
          <div class="card-header">Language</div>
          <div class="card-body">
            <dl class="row mb-0 small">
              <template v-for="[label, value] in metadata" :key="label">
                <dt class="col-sm-4">{{ label }}</dt>
                <dd class="col-sm-8">{{ value || '—' }}</dd>
              </template>
            </dl>
          </div>
        </div>
      </div>
      <div class="col-lg-7">
        <div class="card shadow-sm h-100">
          <div class="card-header">Upload a new version</div>
          <div class="card-body">
            <p class="small text-muted">
              The file is checked with the conversion script and stored as a new version, together with the log.
            </p>
            <form class="d-flex flex-wrap gap-2" @submit.prevent="upload">
              <input
                ref="fileInput"
                type="file"
                class="form-control flex-grow-1 w-auto"
                accept=".xlsx,.xlsm,.xls"
                :disabled="uploading"
                @change="selectedFile = $event.target.files[0] || null"
              />
              <button class="btn btn-primary" :disabled="!selectedFile || uploading">
                <span v-if="uploading" class="spinner-border spinner-border-sm me-1"></span>
                <i v-else class="bi bi-upload me-1"></i>Upload
              </button>
            </form>
            <div v-if="uploading" class="small text-muted mt-2">Running the conversion, this may take a while…</div>
            <div
              v-if="uploadResult"
              class="alert mt-3 mb-0 d-flex align-items-center gap-2"
              :class="uploadResult.success === false ? 'alert-danger' : uploadResult.error_count ? 'alert-warning' : 'alert-success'"
            >
              <span class="me-auto">
                Version {{ uploadResult.number }} saved.
                <template v-if="uploadResult.success === false">The conversion failed.</template>
                <template v-else>{{ uploadResult.error_count }} errors, {{ uploadResult.warning_count }} warnings.</template>
              </span>
              <button class="btn btn-sm btn-light" @click="showLog(uploadResult)">View log</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <h2 class="h5">History</h2>
    <div v-if="!versions.length" class="alert alert-light border">No versions uploaded yet.</div>
    <div v-else class="card shadow-sm">
      <div class="table-responsive">
        <table class="table mb-0">
          <thead class="table-light">
            <tr>
              <th>#</th>
              <th>Date</th>
              <th>Uploaded by</th>
              <th>File</th>
              <th>Check</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="version in versions" :key="version.id">
              <td class="fw-semibold">v{{ version.number }}</td>
              <td class="small">{{ formatDate(version.created_at) }}</td>
              <td class="small">{{ version.user ? userLabel(version.user) : version.success === null ? '—' : 'Deleted user' }}</td>
              <td class="small">{{ version.original_filename }} <span class="text-muted">({{ formatSize(version.file_size) }})</span></td>
              <td><VersionStatus :version="version" /></td>
              <td class="table-actions">
                <button class="btn btn-sm btn-outline-secondary me-1" title="View log" @click="showLog(version)"><i class="bi bi-eye"></i></button>
                <button class="btn btn-sm btn-outline-secondary me-1" title="Download log" @click="download(`/versions/${version.id}/log`)">
                  <i class="bi bi-file-text"></i>
                </button>
                <button class="btn btn-sm btn-outline-secondary" title="Download Excel" @click="download(`/versions/${version.id}/excel`)">
                  <i class="bi bi-file-earmark-excel"></i>
                </button>
                <button v-if="isAdmin" class="btn btn-sm btn-outline-danger ms-1" title="Delete version" @click="remove(version)">
                  <i class="bi bi-trash"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </template>

  <AppModal v-if="logVersion" :title="`${project.name} — v${logVersion.number} log`" size="xl" @close="logVersion = null">
    <LogViewer :log="logVersion.log" />
    <template #footer>
      <button class="btn btn-outline-secondary" @click="download(`/versions/${logVersion.id}/log`)"><i class="bi bi-download me-1"></i>Download</button>
      <button class="btn btn-secondary" @click="logVersion = null">Close</button>
    </template>
  </AppModal>
</template>

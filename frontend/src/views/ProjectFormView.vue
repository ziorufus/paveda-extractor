<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import CheckList from '../components/CheckList.vue'
import { api } from '../lib/api'

const props = defineProps({ id: { type: String, default: null } })
const router = useRouter()

const FIELDS = [
  { key: 'name', label: 'Name', required: true, col: 6 },
  { key: 'language_id', label: 'Language ID (CLDF)', required: true, col: 3, help: 'Usually the Glottocode' },
  { key: 'excel_filename', label: 'File key', col: 3, help: 'Leave empty to generate it from the name' },
  { key: 'glottocode', label: 'Glottocode', col: 3 },
  { key: 'glottolog_name', label: 'Glottolog name', col: 5 },
  { key: 'iso639p3code', label: 'ISO 639-3 code', col: 4 },
  { key: 'family', label: 'Family', col: 4 },
  { key: 'macroarea', label: 'Macroarea', col: 4 },
  { key: 'latitude', label: 'Latitude', col: 2 },
  { key: 'longitude', label: 'Longitude', col: 2 },
  { key: 'contributors', label: 'Contributors', col: 12 },
]

const form = reactive(Object.fromEntries(FIELDS.map((field) => [field.key, ''])))
const userIds = ref([])
const users = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')

const isNew = computed(() => !props.id)

const userItems = computed(() =>
  users.value.map((user) => ({
    id: user.id,
    label: user.name || user.email,
    sublabel: user.name ? user.email : '',
    warning: user.is_admin ? 'admin, sees everything anyway' : '',
  })),
)

async function load() {
  try {
    users.value = await api.get('/users')
    if (!isNew.value) {
      const project = await api.get(`/projects/${props.id}`)
      for (const field of FIELDS) form[field.key] = project[field.key] ?? ''
      userIds.value = project.user_ids
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  const payload = { ...form, user_ids: userIds.value }
  try {
    const project = isNew.value ? await api.post('/projects', payload) : await api.patch(`/projects/${props.id}`, payload)
    router.push({ name: 'project', params: { id: project.id } })
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <nav aria-label="breadcrumb">
    <ol class="breadcrumb">
      <li class="breadcrumb-item"><RouterLink :to="{ name: 'projects' }">Languages</RouterLink></li>
      <li v-if="!isNew" class="breadcrumb-item">
        <RouterLink :to="{ name: 'project', params: { id } }">{{ form.name || '…' }}</RouterLink>
      </li>
      <li class="breadcrumb-item active">{{ isNew ? 'New' : 'Edit' }}</li>
    </ol>
  </nav>

  <h1 class="h3 mb-3">{{ isNew ? 'New language' : `Edit ${form.name}` }}</h1>

  <div v-if="error" class="alert alert-danger">{{ error }}</div>
  <div v-if="loading" class="text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading…</div>

  <form v-else @submit.prevent="save">
    <div class="card shadow-sm mb-3">
      <div class="card-body row g-3">
        <div v-for="field in FIELDS" :key="field.key" :class="`col-md-${field.col}`">
          <label class="form-label" :for="`field-${field.key}`">
            {{ field.label }}<span v-if="field.required" class="text-danger">*</span>
          </label>
          <input :id="`field-${field.key}`" v-model="form[field.key]" class="form-control" :required="field.required" />
          <div v-if="field.help" class="form-text">{{ field.help }}</div>
        </div>
      </div>
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-header">Assigned users</div>
      <div class="card-body">
        <p class="small text-muted">These users can see this language, browse its history and upload new versions.</p>
        <CheckList v-model="userIds" :items="userItems" empty-text="No users" />
      </div>
    </div>

    <div class="d-flex gap-2">
      <button class="btn btn-primary" :disabled="saving">
        <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>Save
      </button>
      <button type="button" class="btn btn-outline-secondary" @click="router.back()">Cancel</button>
    </div>
  </form>
</template>

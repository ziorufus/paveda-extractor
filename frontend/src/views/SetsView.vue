<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import AppModal from '../components/AppModal.vue'
import CheckList from '../components/CheckList.vue'
import { api } from '../lib/api'

const sets = ref([])
const projects = ref([])
const loading = ref(true)
const error = ref('')

const editing = ref(null)
const form = reactive({ name: '', description: '', project_ids: [] })
const formError = ref('')
const saving = ref(false)

const projectItems = computed(() => projects.value.map((project) => ({ id: project.id, label: project.name, sublabel: project.language_id })))
const projectNames = computed(() => Object.fromEntries(projects.value.map((project) => [project.id, project.name])))

async function load() {
  try {
    ;[sets.value, projects.value] = await Promise.all([api.get('/sets'), api.get('/projects')])
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

function openForm(projectSet = {}) {
  editing.value = projectSet
  form.name = projectSet.name || ''
  form.description = projectSet.description || ''
  form.project_ids = [...(projectSet.project_ids || [])]
  formError.value = ''
}

async function save() {
  saving.value = true
  formError.value = ''
  try {
    if (editing.value.id) {
      const updated = await api.patch(`/sets/${editing.value.id}`, form)
      sets.value = sets.value.map((item) => (item.id === updated.id ? updated : item))
    } else {
      sets.value = [...sets.value, await api.post('/sets', form)].sort((a, b) => a.name.localeCompare(b.name))
    }
    editing.value = null
  } catch (err) {
    formError.value = err.message
  } finally {
    saving.value = false
  }
}

async function remove(projectSet) {
  if (!confirm(`Delete the set "${projectSet.name}"? The languages themselves are not affected.`)) return
  try {
    await api.delete(`/sets/${projectSet.id}`)
    sets.value = sets.value.filter((item) => item.id !== projectSet.id)
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <div class="d-flex align-items-center mb-3">
    <h1 class="h3 mb-0 me-auto">Sets</h1>
    <button class="btn btn-primary" @click="openForm()"><i class="bi bi-plus-lg me-1"></i>New set</button>
  </div>
  <p class="text-muted small">Sets are groups of languages that can be pre-selected in one click when creating the ValPaL export.</p>

  <div v-if="error" class="alert alert-danger">{{ error }}</div>
  <div v-if="loading" class="text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading…</div>
  <div v-else-if="!sets.length" class="alert alert-light border">No sets yet.</div>

  <div class="row g-3">
    <div v-for="projectSet in sets" :key="projectSet.id" class="col-md-6 col-xl-4">
      <div class="card shadow-sm h-100">
        <div class="card-body">
          <div class="d-flex align-items-start mb-2">
            <h2 class="h5 mb-0 me-auto">{{ projectSet.name }}</h2>
            <button class="btn btn-sm btn-outline-secondary me-1" title="Edit" @click="openForm(projectSet)"><i class="bi bi-pencil"></i></button>
            <button class="btn btn-sm btn-outline-danger" title="Delete" @click="remove(projectSet)"><i class="bi bi-trash"></i></button>
          </div>
          <p v-if="projectSet.description" class="small text-muted">{{ projectSet.description }}</p>
          <div class="d-flex flex-wrap gap-1">
            <span v-for="id in projectSet.project_ids" :key="id" class="badge text-bg-light border">{{ projectNames[id] }}</span>
            <span v-if="!projectSet.project_ids.length" class="small text-muted">Empty</span>
          </div>
        </div>
        <div class="card-footer small text-muted">{{ projectSet.project_ids.length }} languages</div>
      </div>
    </div>
  </div>

  <AppModal v-if="editing" :title="editing.id ? `Edit ${editing.name}` : 'New set'" size="lg" @close="editing = null">
    <form id="set-form" @submit.prevent="save">
      <div v-if="formError" class="alert alert-danger">{{ formError }}</div>
      <div class="mb-3">
        <label class="form-label" for="set-name">Name<span class="text-danger">*</span></label>
        <input id="set-name" v-model="form.name" class="form-control" required />
      </div>
      <div class="mb-3">
        <label class="form-label" for="set-description">Description</label>
        <textarea id="set-description" v-model="form.description" class="form-control" rows="2"></textarea>
      </div>
      <label class="form-label">Languages</label>
      <CheckList v-model="form.project_ids" :items="projectItems" empty-text="No languages" />
    </form>
    <template #footer>
      <button type="button" class="btn btn-outline-secondary" @click="editing = null">Cancel</button>
      <button type="submit" form="set-form" class="btn btn-primary" :disabled="saving">
        <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>Save
      </button>
    </template>
  </AppModal>
</template>

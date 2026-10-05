<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import AppModal from '../components/AppModal.vue'
import CheckList from '../components/CheckList.vue'
import { api } from '../lib/api'
import { formatDate } from '../lib/format'
import { session } from '../lib/session'

const users = ref([])
const projects = ref([])
const loading = ref(true)
const error = ref('')

const editing = ref(null) // null = closed, {} = new user, user object = edit
const form = reactive({ email: '', name: '', is_admin: false, project_ids: [] })
const formError = ref('')
const saving = ref(false)

const projectItems = computed(() => projects.value.map((project) => ({ id: project.id, label: project.name, sublabel: project.language_id })))
const projectNames = computed(() => Object.fromEntries(projects.value.map((project) => [project.id, project.name])))

async function load() {
  try {
    ;[users.value, projects.value] = await Promise.all([api.get('/users'), api.get('/projects')])
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

function openForm(user = {}) {
  editing.value = user
  form.email = user.email || ''
  form.name = user.name || ''
  form.is_admin = user.is_admin || false
  form.project_ids = [...(user.project_ids || [])]
  formError.value = ''
}

async function save() {
  saving.value = true
  formError.value = ''
  try {
    if (editing.value.id) {
      const updated = await api.patch(`/users/${editing.value.id}`, form)
      users.value = users.value.map((user) => (user.id === updated.id ? updated : user))
      if (updated.id === session.user.id) session.user = updated
    } else {
      users.value = [...users.value, await api.post('/users', form)]
    }
    editing.value = null
  } catch (err) {
    formError.value = err.message
  } finally {
    saving.value = false
  }
}

async function remove(user) {
  if (!confirm(`Delete ${user.email}? They will no longer be able to log in.`)) return
  try {
    await api.delete(`/users/${user.id}`)
    users.value = users.value.filter((item) => item.id !== user.id)
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <div class="d-flex align-items-center mb-3">
    <h1 class="h3 mb-0 me-auto">Users</h1>
    <button class="btn btn-primary" @click="openForm()"><i class="bi bi-person-plus me-1"></i>New user</button>
  </div>
  <p class="text-muted small">Only the e-mail addresses listed here can log in with Google.</p>

  <div v-if="error" class="alert alert-danger">{{ error }}</div>
  <div v-if="loading" class="text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading…</div>

  <div v-else class="card shadow-sm">
    <div class="table-responsive">
      <table class="table mb-0">
        <thead class="table-light">
          <tr>
            <th>Name</th>
            <th>E-mail</th>
            <th>Role</th>
            <th>Languages</th>
            <th class="d-none d-md-table-cell">Last login</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td class="fw-semibold">{{ user.name || '—' }}</td>
            <td>{{ user.email }}</td>
            <td>
              <span v-if="user.is_owner" class="badge text-bg-dark" title="First administrator">owner</span>
              <span v-else-if="user.is_admin" class="badge text-bg-warning">admin</span>
              <span v-else class="badge text-bg-light border">user</span>
            </td>
            <td class="small">
              <span v-if="user.is_admin" class="text-muted">all</span>
              <span v-else-if="!user.project_ids.length" class="text-muted">none</span>
              <span v-else :title="user.project_ids.map((id) => projectNames[id]).join(', ')">
                {{ user.project_ids.map((id) => projectNames[id]).slice(0, 3).join(', ') }}<template v-if="user.project_ids.length > 3"> +{{ user.project_ids.length - 3 }}</template>
              </span>
            </td>
            <td class="small d-none d-md-table-cell">{{ formatDate(user.last_login_at) }}</td>
            <td class="table-actions">
              <button class="btn btn-sm btn-outline-secondary me-1" title="Edit" @click="openForm(user)"><i class="bi bi-pencil"></i></button>
              <button
                class="btn btn-sm btn-outline-danger"
                title="Delete"
                :disabled="user.is_owner || user.id === session.user.id"
                @click="remove(user)"
              >
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <AppModal v-if="editing" :title="editing.id ? `Edit ${editing.email}` : 'New user'" size="lg" @close="editing = null">
    <form id="user-form" @submit.prevent="save">
      <div v-if="formError" class="alert alert-danger">{{ formError }}</div>
      <div class="row g-3 mb-3">
        <div class="col-md-6">
          <label class="form-label" for="user-email">E-mail (Google account)<span class="text-danger">*</span></label>
          <input id="user-email" v-model="form.email" type="email" class="form-control" required />
        </div>
        <div class="col-md-6">
          <label class="form-label" for="user-name">Name</label>
          <input id="user-name" v-model="form.name" class="form-control" placeholder="Taken from Google if empty" />
        </div>
      </div>
      <div class="form-check form-switch mb-3">
        <input id="user-admin" v-model="form.is_admin" class="form-check-input" type="checkbox" :disabled="editing.is_owner" />
        <label class="form-check-label" for="user-admin">
          Administrator
          <small v-if="editing.is_owner" class="text-muted">(the first administrator cannot be demoted)</small>
        </label>
      </div>
      <label class="form-label">Assigned languages</label>
      <div v-if="form.is_admin" class="form-text mb-2">Administrators see all languages regardless of this list.</div>
      <CheckList v-model="form.project_ids" :items="projectItems" empty-text="No languages" />
    </form>
    <template #footer>
      <button type="button" class="btn btn-outline-secondary" @click="editing = null">Cancel</button>
      <button type="submit" form="user-form" class="btn btn-primary" :disabled="saving">
        <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>Save
      </button>
    </template>
  </AppModal>
</template>

import { createRouter, createWebHistory } from 'vue-router'
import { api, onUnauthorized } from './lib/api'
import { session } from './lib/session'

import AuthCallbackView from './views/AuthCallbackView.vue'
import ExportView from './views/ExportView.vue'
import LoginView from './views/LoginView.vue'
import ProjectDetailView from './views/ProjectDetailView.vue'
import ProjectFormView from './views/ProjectFormView.vue'
import ProjectsView from './views/ProjectsView.vue'
import SetsView from './views/SetsView.vue'
import UsersView from './views/UsersView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/auth/callback', name: 'auth-callback', component: AuthCallbackView, meta: { public: true } },
    { path: '/', name: 'projects', component: ProjectsView },
    { path: '/projects/new', name: 'project-new', component: ProjectFormView, meta: { admin: true } },
    { path: '/projects/:id', name: 'project', component: ProjectDetailView, props: true },
    { path: '/projects/:id/edit', name: 'project-edit', component: ProjectFormView, props: true, meta: { admin: true } },
    { path: '/users', name: 'users', component: UsersView, meta: { admin: true } },
    { path: '/sets', name: 'sets', component: SetsView, meta: { admin: true } },
    { path: '/export', name: 'export', component: ExportView, meta: { admin: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  if (!session.token) return { name: 'login', query: { redirect: to.fullPath } }
  if (!session.user) {
    try {
      session.user = await api.get('/auth/me')
    } catch {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }
  if (to.meta.admin && !session.user.is_admin) return { name: 'projects' }
  return true
})

onUnauthorized(() => {
  if (!router.currentRoute.value.meta.public) router.push({ name: 'login' })
})

export default router

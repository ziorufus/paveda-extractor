import { clearSession, session } from './session'

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

let unauthorizedHandler = () => {}

export function onUnauthorized(handler) {
  unauthorizedHandler = handler
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(formatDetail(detail))
    this.status = status
    this.detail = detail
  }
}

function formatDetail(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    // FastAPI validation errors
    return detail.map((item) => `${(item.loc || []).filter((part) => part !== 'body').join('.')}: ${item.msg}`).join('; ')
  }
  if (detail && detail.message) return detail.message
  return 'Unexpected error'
}

async function request(method, path, { json, form, raw = false } = {}) {
  const headers = {}
  if (session.token) headers.Authorization = `Bearer ${session.token}`
  let body
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  } else if (form) {
    body = form
  }

  let response
  try {
    response = await fetch(API_BASE + path, { method, headers, body })
  } catch {
    throw new ApiError(0, `Cannot reach the server at ${API_BASE}`)
  }

  if (response.status === 401) {
    clearSession()
    unauthorizedHandler()
  }
  if (!response.ok) {
    let detail = response.statusText
    try {
      detail = (await response.json()).detail ?? detail
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, detail)
  }
  if (raw) return response
  if (response.status === 204) return null
  return response.json()
}

function filenameFromResponse(response, fallback) {
  const header = response.headers.get('Content-Disposition') || ''
  const encoded = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (encoded) return decodeURIComponent(encoded[1])
  const plain = header.match(/filename="?([^";]+)"?/i)
  return plain ? plain[1] : fallback
}

async function download(method, path, options = {}, fallbackName = 'download') {
  const response = await request(method, path, { ...options, raw: true })
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filenameFromResponse(response, fallbackName)
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, json) => request('POST', path, { json }),
  patch: (path, json) => request('PATCH', path, { json }),
  delete: (path) => request('DELETE', path),
  upload: (path, formData) => request('POST', path, { form: formData }),
  download: (path, fallbackName) => download('GET', path, {}, fallbackName),
  downloadPost: (path, json, fallbackName) => download('POST', path, { json }, fallbackName),
}

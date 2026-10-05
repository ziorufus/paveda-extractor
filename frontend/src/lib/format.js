const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export function formatDate(value) {
  return value ? dateFormat.format(new Date(value)) : '—'
}

export function formatSize(bytes) {
  if (bytes == null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function userLabel(user) {
  if (!user) return 'Deleted user'
  return user.name || user.email
}

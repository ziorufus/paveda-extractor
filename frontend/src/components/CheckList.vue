<script setup>
import { computed, ref, useId } from 'vue'

// items: [{ id, label, sublabel?, disabled?, warning? }]
const props = defineProps({
  items: { type: Array, required: true },
  emptyText: { type: String, default: 'Nothing to show' },
})
const selected = defineModel({ type: Array, default: () => [] })

const filter = ref('')
const uid = useId()

const visible = computed(() => {
  const query = filter.value.trim().toLowerCase()
  if (!query) return props.items
  return props.items.filter((item) => `${item.label} ${item.sublabel || ''}`.toLowerCase().includes(query))
})

function toggle(id, checked) {
  const set = new Set(selected.value)
  checked ? set.add(id) : set.delete(id)
  selected.value = props.items.filter((item) => set.has(item.id)).map((item) => item.id)
}

function selectVisible(checked) {
  const set = new Set(selected.value)
  for (const item of visible.value) {
    if (item.disabled) continue
    checked ? set.add(item.id) : set.delete(item.id)
  }
  selected.value = props.items.filter((item) => set.has(item.id)).map((item) => item.id)
}
</script>

<template>
  <div class="border rounded">
    <div class="d-flex gap-2 p-2 border-bottom bg-light rounded-top">
      <input v-model="filter" type="search" class="form-control form-control-sm" placeholder="Filter…" />
      <button type="button" class="btn btn-sm btn-outline-secondary text-nowrap" @click="selectVisible(true)">All</button>
      <button type="button" class="btn btn-sm btn-outline-secondary text-nowrap" @click="selectVisible(false)">None</button>
    </div>
    <div class="check-list px-2 py-1">
      <div v-for="item in visible" :key="item.id" class="form-check my-1">
        <input
          :id="`check-${uid}-${item.id}`"
          class="form-check-input"
          type="checkbox"
          :disabled="item.disabled"
          :checked="selected.includes(item.id)"
          @change="toggle(item.id, $event.target.checked)"
        />
        <label class="form-check-label" :class="{ 'text-muted': item.disabled }" :for="`check-${uid}-${item.id}`">
          {{ item.label }}
          <small v-if="item.sublabel" class="text-muted ms-1">{{ item.sublabel }}</small>
          <small v-if="item.warning" class="text-warning-emphasis ms-1"><i class="bi bi-exclamation-triangle"></i> {{ item.warning }}</small>
        </label>
      </div>
      <div v-if="!visible.length" class="text-muted small py-2">{{ emptyText }}</div>
    </div>
    <div class="small text-muted px-2 py-1 border-top">{{ selected.length }} selected</div>
  </div>
</template>

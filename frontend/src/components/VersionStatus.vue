<script setup>
defineProps({ version: { type: Object, required: true } })
</script>

<template>
  <span v-if="version.success === false" class="badge text-bg-danger" title="The conversion raised an exception">
    <i class="bi bi-x-circle me-1"></i>failed
  </span>
  <span v-else-if="version.success === null" class="badge text-bg-secondary" title="Imported at first startup, never checked">
    imported
  </span>
  <template v-else>
    <span v-if="version.error_count" class="badge text-bg-warning me-1">{{ version.error_count }} errors</span>
    <span v-if="version.warning_count" class="badge text-bg-light border me-1">{{ version.warning_count }} warnings</span>
    <span v-if="!version.error_count && !version.warning_count" class="badge text-bg-success"><i class="bi bi-check-circle me-1"></i>OK</span>
  </template>
</template>

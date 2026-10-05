<script setup>
defineProps({
  title: { type: String, required: true },
  size: { type: String, default: '' }, // '', 'lg', 'xl'
})
const emit = defineEmits(['close'])
</script>

<template>
  <Teleport to="body">
    <div class="modal d-block" tabindex="-1" @keydown.esc="emit('close')" @click.self="emit('close')">
      <div class="modal-dialog modal-dialog-scrollable" :class="size ? `modal-${size}` : ''">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ title }}</h5>
            <button type="button" class="btn-close" aria-label="Close" @click="emit('close')"></button>
          </div>
          <div class="modal-body">
            <slot />
          </div>
          <div v-if="$slots.footer" class="modal-footer">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </div>
    <div class="modal-backdrop show"></div>
  </Teleport>
</template>

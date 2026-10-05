<script setup>
import { computed, ref } from 'vue'

const props = defineProps({ log: { type: String, default: '' } })
const onlyProblems = ref(false)

const lines = computed(() =>
  (props.log || '')
    .split('\n')
    .map((text, index) => {
      const trimmed = text.trimStart()
      let kind = ''
      if (trimmed.startsWith('ERR')) kind = 'log-err'
      else if (trimmed.startsWith('WARN')) kind = 'log-warn'
      else if (trimmed.startsWith('###')) kind = 'log-head'
      return { index, text, kind }
    })
    .filter((line) => !onlyProblems.value || line.kind === 'log-err' || line.kind === 'log-warn'),
)
</script>

<template>
  <div>
    <div class="form-check form-switch mb-2">
      <input id="only-problems" v-model="onlyProblems" class="form-check-input" type="checkbox" />
      <label class="form-check-label" for="only-problems">Show only errors and warnings</label>
    </div>
    <div class="log-view"><div v-for="line in lines" :key="line.index" :class="line.kind">{{ line.text || ' ' }}</div><div v-if="!lines.length" class="text-secondary">(empty)</div></div>
  </div>
</template>

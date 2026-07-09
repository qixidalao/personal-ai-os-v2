<template>
  <div class="ai-progress">
    <div class="ai-progress__bar" :style="barStyle" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  percent: number
}>()

const barStyle = computed(() => ({
  width: `${props.percent}%`,
  background: props.percent > 90 ? 'var(--error)' : props.percent > 70 ? 'var(--warn)' : 'var(--primary)',
}))
</script>

<style scoped>
.ai-progress{height:4px;background:var(--surface-alt);border-radius:2px;overflow:hidden}
.ai-progress__bar{height:100%;border-radius:2px;transition:width .3s}
</style>

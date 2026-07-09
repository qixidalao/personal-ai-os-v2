<template>
  <div class="ai-skeleton" :style="skeletonStyle" />
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  width?: string
  height?: string
  radius?: string
}>(), {
  width: '100%',
  height: '16px',
  radius: '6px',
})

const skeletonStyle = computed(() => ({
  width: props.width,
  height: props.height,
  borderRadius: props.radius,
}))
</script>

<style scoped>
.ai-skeleton{background:linear-gradient(90deg,var(--surface) 25%,var(--surface-alt) 50%,var(--surface) 75%);background-size:200% 100%;animation:skeleton 1.5s infinite}
@keyframes skeleton{0%{background-position:200% 0}100%{background-position:-200% 0}}
</style>

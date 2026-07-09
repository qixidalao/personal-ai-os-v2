<template>
  <div class="ai-avatar" :style="avatarStyle">
    <span v-if="emoji">{{ emoji }}</span>
    <span v-else>{{ text?.charAt(0)?.toUpperCase() }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  emoji?: string
  text?: string
  size?: number
}>(), {
  size: 32,
})

const avatarStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${props.size * 0.5}px`,
}))
</script>

<style scoped>
.ai-avatar{border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;background:var(--surface-alt)}
</style>

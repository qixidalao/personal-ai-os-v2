<template>
  <div class="ai-empty">
    <div class="ai-empty__icon">{{ icon }}</div>
    <div class="ai-empty__text">{{ text }}</div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  icon?: string
  text?: string
}>(), {
  icon: '📭',
  text: '暂无数据',
})
</script>

<style scoped>
.ai-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px;gap:8px;color:var(--text2)}
.ai-empty__icon{font-size:40px}
.ai-empty__text{font-size:14px}
</style>

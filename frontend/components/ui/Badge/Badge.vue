<template>
  <span :class="['ai-badge', `ai-badge--${color}`]"><slot /></span>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  color?: string
}>(), {
  color: 'purple',
})
</script>

<style scoped>
.ai-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500}
.ai-badge--green{background:rgba(34,197,94,.15);color:#22c55e}
.ai-badge--red{background:rgba(239,68,68,.15);color:#ef4444}
.ai-badge--yellow{background:rgba(245,158,11,.15);color:#f59e0b}
.ai-badge--blue{background:rgba(59,130,246,.15);color:#3b82f6}
.ai-badge--purple{background:rgba(124,58,237,.15);color:#a855f7}
</style>

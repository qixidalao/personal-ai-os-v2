<template>
  <div :class="['ai-card', variant === 'glow' ? 'ai-card--glow' : '']">
    <div v-if="$slots.header" class="ai-card__header"><slot name="header" /></div>
    <div class="ai-card__body"><slot /></div>
    <div v-if="$slots.footer" class="ai-card__footer"><slot name="footer" /></div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  variant?: string
}>(), {
  variant: '',
})
</script>

<style scoped>
.ai-card{background:var(--surface);border-radius:12px;border:1px solid var(--border-light);overflow:hidden}
.ai-card--glow{border-color:var(--primary);box-shadow:0 0 20px rgba(124,58,237,.15)}
.ai-card__header{padding:14px 16px;border-bottom:1px solid var(--border-light);font-size:14px;font-weight:600;display:flex;align-items:center;gap:8px}
.ai-card__body{padding:14px 16px}
.ai-card__footer{padding:10px 16px;border-top:1px solid var(--border-light)}
</style>

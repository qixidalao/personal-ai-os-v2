<template>
  <div :class="['ai-divider', vertical ? 'ai-divider--v' : '']">
    <span v-if="$slots.default" class="ai-divider__text"><slot /></span>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  vertical?: boolean
}>(), {
  vertical: false,
})
</script>

<style scoped>
.ai-divider{display:flex;align-items:center;height:1px;background:var(--border-light);margin:8px 0}
.ai-divider--v{width:1px;height:auto;margin:0 8px}
.ai-divider__text{padding:0 12px;font-size:12px;color:var(--text3);background:var(--bg);white-space:nowrap}
</style>

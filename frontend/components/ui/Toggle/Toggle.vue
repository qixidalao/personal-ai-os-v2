<template>
  <button :class="['ai-toggle', modelValue ? 'ai-toggle--on' : '']" :disabled="disabled" @click="emit('update:modelValue', !modelValue)">
    <span class="ai-toggle__knob" />
  </button>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  modelValue: boolean
  disabled?: boolean
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()
</script>

<style scoped>
.ai-toggle{width:40px;height:22px;border-radius:11px;background:var(--surface-alt);border:none;cursor:pointer;position:relative;transition:background .2s;padding:0}
.ai-toggle:disabled{opacity:.6;cursor:not-allowed}
.ai-toggle--on{background:var(--primary)}
.ai-toggle__knob{position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:#fff;transition:transform .2s}
.ai-toggle--on .ai-toggle__knob{transform:translateX(18px)}
</style>

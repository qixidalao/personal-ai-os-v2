<template>
  <button
    :class="['ai-btn', `ai-btn--${variant}`, `ai-btn--${size}`, { 'ai-btn--loading': loading, 'ai-btn--disabled': disabled }]"
    :disabled="disabled || loading"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="ai-btn__spinner" />
    <slot v-else name="icon" />
    <span class="ai-btn__text" v-if="$slots.default">
      <slot />
    </span>
  </button>
</template>

<script setup lang="ts">
defineProps({
  variant: { type: String, default: 'primary' }, // primary | secondary | ghost | danger
  size: { type: String, default: 'md' }, // sm | md | lg
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

defineEmits(['click'])
</script>

<style scoped>
.ai-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  font-family: inherit;
  font-weight: 500;
  transition: all 0.2s ease;
  outline: none;
  white-space: nowrap;
  user-select: none;
}

.ai-btn:focus-visible {
  box-shadow: 0 0 0 2px var(--primary), 0 0 0 4px var(--bg-primary);
}

/* Sizes */
.ai-btn--sm { padding: 4px 12px; font-size: 12px; }
.ai-btn--md { padding: 8px 16px; font-size: 14px; }
.ai-btn--lg { padding: 12px 24px; font-size: 16px; }

/* Variants */
.ai-btn--primary {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}
.ai-btn--primary:hover:not(:disabled) { opacity: 0.9; transform: translateY(-1px); }

.ai-btn--secondary {
  background: var(--surface);
  color: var(--text-primary);
  border-color: var(--border);
}
.ai-btn--secondary:hover:not(:disabled) { background: var(--surface-alt); }

.ai-btn--ghost {
  background: transparent;
  color: var(--text-primary);
  border-color: transparent;
}
.ai-btn--ghost:hover:not(:disabled) { background: var(--surface); }

.ai-btn--danger {
  background: var(--error);
  color: #fff;
  border-color: var(--error);
}
.ai-btn--danger:hover:not(:disabled) { opacity: 0.9; }

/* States */
.ai-btn--disabled { opacity: 0.5; cursor: not-allowed; }
.ai-btn--loading { cursor: wait; }

.ai-btn__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>

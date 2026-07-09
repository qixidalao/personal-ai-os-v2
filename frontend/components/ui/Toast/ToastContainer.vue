<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast-slide">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="['toast-item', `toast-item--${toast.type}`]"
          @click="remove(toast.id)"
        >
          <span class="toast-icon">{{ icons[toast.type] }}</span>
          <span class="toast-message">{{ toast.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useToast } from './useToast'

const { toasts, remove } = useToast()

const icons: Record<string, string> = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-primary);
  font-size: 14px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  cursor: pointer;
  pointer-events: auto;
  min-width: 280px;
  max-width: 420px;
}

.toast-item--success { border-left: 3px solid var(--success); }
.toast-item--error { border-left: 3px solid var(--error); }
.toast-item--warning { border-left: 3px solid var(--warning); }
.toast-item--info { border-left: 3px solid var(--info); }

.toast-icon { font-size: 18px; flex-shrink: 0; }

.toast-slide-enter-active,
.toast-slide-leave-active { transition: all 0.3s ease; }
.toast-slide-enter-from { transform: translateX(100%); opacity: 0; }
.toast-slide-leave-to { transform: translateX(100%); opacity: 0; }
</style>

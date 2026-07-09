import { ref } from 'vue'

export interface ToastMessage {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  duration: number
}

const toasts = ref<ToastMessage[]>([])
let counter = 0

function add(type: ToastMessage['type'], message: string, duration = 3000) {
  const id = `toast-${++counter}`
  toasts.value.push({ id, type, message, duration })
  setTimeout(() => remove(id), duration)
}

function remove(id: string) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

export function useToast() {
  return {
    toasts,
    success: (msg: string) => add('success', msg),
    error: (msg: string) => add('error', msg, 5000),
    warning: (msg: string) => add('warning', msg, 4000),
    info: (msg: string) => add('info', msg),
    remove,
  }
}

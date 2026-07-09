import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const current = ref<'dark' | 'light'>('dark')

  function toggle() {
    current.value = current.value === 'dark' ? 'light' : 'dark'
    applyTheme()
  }

  function setTheme(theme: 'dark' | 'light') {
    current.value = theme
    applyTheme()
  }

  function applyTheme() {
    document.documentElement.setAttribute('data-theme', current.value)
  }

  // 初始化
  applyTheme()

  return { current, toggle, setTheme }
})

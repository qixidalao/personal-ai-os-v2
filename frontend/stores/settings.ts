import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const hideSidebar = ref(false)
  const sidebarCollapsed = ref(false)

  const chat = reactive({
    maxWidth: 960,
    showTimestamp: true,
    showAvatar: true,
    smoothScroll: true,
  })

  const editor = reactive({
    fontSize: 14,
    tabSize: 2,
    wordWrap: true,
    minimap: true,
  })

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function updateChat(config: Partial<typeof chat>) {
    Object.assign(chat, config)
  }

  function updateEditor(config: Partial<typeof editor>) {
    Object.assign(editor, config)
  }

  return {
    hideSidebar,
    sidebarCollapsed,
    chat,
    editor,
    toggleSidebar,
    updateChat,
    updateEditor,
  }
})

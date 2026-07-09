import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  timestamp: number
  status?: 'sending' | 'streaming' | 'done' | 'error'
  metadata?: Record<string, any>
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const currentSessionId = ref('')
  const isStreaming = ref(false)

  function addMessage(msg: Message) {
    messages.value.push(msg)
  }

  function updateLastMessage(content: string, done: boolean = false) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant') {
      last.content += content
      if (done) {
        last.status = 'done'
        isStreaming.value = false
      }
    }
  }

  function clearMessages() {
    messages.value = []
  }

  function setStreaming(val: boolean) {
    isStreaming.value = val
  }

  return {
    messages,
    currentSessionId,
    isStreaming,
    addMessage,
    updateLastMessage,
    clearMessages,
    setStreaming,
  }
})

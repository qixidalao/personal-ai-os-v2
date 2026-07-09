import { ref, onUnmounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useToast } from '@/components/ui/Toast/useToast'

export function useEventBus() {
  const connected = ref(false)
  const eventSource = ref<EventSource | null>(null)
  const chatStore = useChatStore()
  const toast = useToast()

  function connect(url: string) {
    if (eventSource.value) {
      eventSource.value.close()
    }

    const es = new EventSource(url)
    eventSource.value = es

    es.onopen = () => {
      connected.value = true
    }

    es.onerror = () => {
      connected.value = false
    }

    // 处理各种事件类型
    const eventTypes = [
      'message.user', 'message.assistant',
      'thinking.start', 'thinking.delta', 'thinking.stop',
      'tool.start', 'tool.stdout', 'tool.stderr', 'tool.finish',
      'observation',
      'memory.retrieve', 'memory.update',
      'rag.retrieve',
      'workspace.open', 'workspace.update',
      'error', 'warning', 'info',
    ]

    eventTypes.forEach(type => {
      es.addEventListener(type, (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          handleEvent(type, data)
        } catch (err) {
          console.warn(`[SSE] 解析失败: ${type}`, e.data)
        }
      })
    })
  }

  function handleEvent(type: string, data: any) {
    switch (type) {
      case 'message.user':
        chatStore.addMessage({
          id: data.id || Date.now().toString(),
          role: 'user',
          content: data.content || '',
          timestamp: data.timestamp || Date.now(),
          status: 'done',
        })
        break

      case 'message.assistant':
        if (data.content) {
          if (data.done) {
            chatStore.updateLastMessage('', true)
          } else {
            if (!chatStore.isStreaming) {
              chatStore.addMessage({
                id: data.id || Date.now().toString(),
                role: 'assistant',
                content: '',
                timestamp: data.timestamp || Date.now(),
                status: 'streaming',
              })
              chatStore.setStreaming(true)
            }
            chatStore.updateLastMessage(data.content, data.done || false)
          }
        }
        break

      case 'thinking.start':
        chatStore.setStreaming(true)
        break

      case 'thinking.delta':
        // 可以显示思考过程
        break

      case 'thinking.stop':
        break

      case 'tool.start':
      case 'tool.stdout':
      case 'tool.stderr':
      case 'tool.finish':
        break

      case 'error':
        toast.error(data.error || data.message || '发生错误')
        chatStore.setStreaming(false)
        break

      case 'warning':
        toast.warning(data.message || data)
        break

      case 'info':
        toast.info(data.message || data)
        break
    }
  }

  function disconnect() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
      connected.value = false
    }
  }

  onUnmounted(() => {
    disconnect()
  })

  return { connected, connect, disconnect }
}

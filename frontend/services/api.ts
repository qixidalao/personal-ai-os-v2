/**
 * API 服务层
 * 所有与后端的 HTTP 通信统一管理
 */
const BASE_URL = '/api/v1'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${path}`
  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  }

  const response = await fetch(url, config)
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`)
  }

  return response.json()
}

export const api = {
  // 健康检查
  health: () => request<{ status: string; version: string }>('/health'),

  // 对话
  chat: {
    send: (messages: any[], config?: any) =>
      request('/chat/completions', {
        method: 'POST',
        body: JSON.stringify({ messages, ...config }),
      }),

    stream: (sessionId?: string) =>
      `/api/v1/stream/chat?session_id=${sessionId || ''}`,
  },

  // 配置
  config: {
    get: (name: string) => request(`/config/${name}`),
    update: (name: string, data: any) =>
      request(`/config/${name}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    reload: (name: string) =>
      request(`/config/${name}/reload`, { method: 'POST' }),
    list: () => request<Record<string, any>>('/config'),
  },

  // 工具
  tools: {
    list: () => request('/tools'),
    call: (name: string, args: any) =>
      request('/tools/call', {
        method: 'POST',
        body: JSON.stringify({ name, args }),
      }),
  },

  // 文件
  files: {
    upload: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return request('/upload', { method: 'POST', body: formData })
    },
    list: (path?: string) => request(`/files?path=${path || ''}`),
  },

  // 会话
  sessions: {
    list: () => request('/sessions'),
    get: (id: string) => request(`/sessions/${id}`),
    delete: (id: string) =>
      request(`/sessions/${id}`, { method: 'DELETE' }),
  },
}

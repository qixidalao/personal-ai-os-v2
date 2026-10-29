<template>
  <div class="app-shell" :class="{ mobile: isMobile }">
    <NavRail
      v-if="!isMobile"
      :theme="theme"
      @toggle-theme="toggleTheme"
      @open-palette="openPalette"
    />

    <!-- 会话侧栏：仅在对话页展示 -->
    <aside v-if="showSidebar" class="app-sidebar">
      <div class="sb-header">
        <div class="sb-brand">
          <span class="sb-brand-name">对话</span>
          <span class="sb-brand-count">{{ sessions.length }}</span>
        </div>
        <button class="sb-new" @click="newChat" title="新建对话">＋</button>
      </div>

      <div class="sb-search">
        <Search :size="14" class="sb-search-icon" />
        <input v-model="searchQuery" placeholder="搜索会话…" class="sb-search-inp" />
        <button :class="['sb-select-btn', selectMode ? 'on' : '']" @click="toggleSelectMode" title="多选">
          <CheckSquare :size="13" />
        </button>
      </div>

      <div class="sb-tags">
        <span
          v-for="t in tags"
          :key="t"
          :class="['sb-tag', { active: activeTag === t }]"
          @click="activeTag = activeTag === t ? '' : t"
        >{{ t }}</span>
      </div>

      <nav class="sb-nav">
        <div class="sb-list" v-if="!loading">
          <div
            v-for="s in filteredSessions"
            :key="s.id"
            :class="['sb-item', { active: s.id === currentSession && !selectMode }]"
            @click="selectMode ? toggleSelect(s.id) : switchSession(s.id)"
          >
            <span
              v-if="selectMode"
              :class="['sb-cb', selectedIds.includes(s.id) ? 'sb-cb--on' : '']"
              @click.stop="toggleSelect(s.id)"
            >{{ selectedIds.includes(s.id) ? '✓' : '' }}</span>
            <span class="sb-item-icon">{{ s.icon || '💬' }}</span>
            <div class="sb-item-content">
              <div class="sb-item-title">{{ s.title || '新对话' }}</div>
              <div class="sb-item-meta">{{ s.time || '' }}<template v-if="s.preview"> · {{ s.preview }}</template></div>
            </div>
            <span v-if="s.tag" :class="['sb-item-tag', s.tag]">{{ s.tag }}</span>
            <button v-if="!selectMode" class="sb-item-del" @click.stop="confirmDelete(s.id)" title="删除">
              <X :size="12" />
            </button>
          </div>
          <div v-if="filteredSessions.length === 0" class="sb-empty">
            <div class="sb-empty-title">没有匹配的会话</div>
            <div class="sb-empty-desc">换个关键词，或新建一个对话</div>
          </div>
        </div>
        <div v-else class="sb-loading">
          <div class="ui-skeleton" style="height: 44px; margin-bottom: 8px"></div>
          <div class="ui-skeleton" style="height: 44px; margin-bottom: 8px"></div>
          <div class="ui-skeleton" style="height: 44px"></div>
        </div>
      </nav>

      <div class="sb-footer">
        <div v-if="selectMode" class="sb-actions">
          <button class="sb-del-btn" :disabled="selectedIds.length === 0" @click="deleteSelected">
            删除选中（{{ selectedIds.length }}）
          </button>
          <button class="sb-del-all" @click="confirmDeleteAll">全部删除</button>
        </div>
        <button v-else class="sb-new-btn" @click="newChat">
          <Plus :size="15" /> 新对话
        </button>
      </div>
    </aside>

    <div class="app-main">
      <header class="app-topbar">
        <div class="tb-left">
          <button v-if="isMobile" class="tb-btn" @click="showDrawer = true">
            <Menu :size="17" />
          </button>
          <div class="tb-crumb">
            <span class="tb-page">{{ pageTitle }}</span>
            <span v-if="isChat" class="tb-session">{{ currentSessionTitle }}</span>
          </div>
        </div>

        <div class="tb-center">
          <div class="model-picker-wrap" v-if="isChat">
            <button class="tb-model-btn" @click="showModelPicker = !showModelPicker">
              <span class="tb-model-dot"></span>
              <span class="tb-model-name">{{ currentModel || '选择模型' }}</span>
              <ChevronDown :size="13" class="tb-model-arrow" />
            </button>
            <div v-if="showModelPicker" class="model-picker-drop" @click.stop>
              <div class="mp-head">选择模型</div>
              <div
                v-for="m in models"
                :key="m"
                :class="['model-picker-item', { active: m === currentModel }]"
                @click="currentModel = m; showModelPicker = false"
              >
                <span class="mp-name">{{ m }}</span>
                <span class="mp-tag">{{ m.includes('本地') ? '本地' : '云端' }}</span>
              </div>
              <div v-if="!models.length" class="mp-empty">暂无可用模型，请到设置中添加</div>
            </div>
          </div>
          <span :class="['tb-status', online ? 'online' : 'offline']">
            <span class="tb-status-dot"></span>{{ online ? '在线' : '离线' }}
          </span>
        </div>

        <div class="tb-actions">
          <button class="tb-btn" @click="openPalette" title="命令面板 Ctrl+K">
            <Command :size="16" />
          </button>
          <button class="tb-btn" @click="toggleTheme" :title="theme === 'dark' ? '亮色模式' : '暗色模式'">
            <Sun v-if="theme === 'dark'" :size="16" />
            <Moon v-else :size="16" />
          </button>
          <button class="tb-btn" :title="route.path === '/settings' ? '关闭设置' : '设置'" @click="toggleSettings">
            <X v-if="route.path === '/settings'" :size="16" />
            <Settings v-else :size="16" />
          </button>
        </div>
      </header>

      <div class="app-view">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>

    <CommandPalette ref="paletteRef" />

    <!-- 移动端抽屉 -->
    <Teleport to="body">
      <div v-if="isMobile && showDrawer" class="dr-overlay" @click="showDrawer = false"></div>
      <aside v-if="isMobile" :class="['dr-panel', showDrawer ? 'dr-open' : '']">
        <div class="sb-header">
          <div class="sb-brand"><span class="sb-brand-name">对话</span></div>
          <button class="tb-btn" style="margin-left: auto" @click="showDrawer = false">
            <X :size="16" />
          </button>
        </div>
        <div class="sb-search">
          <Search :size="14" class="sb-search-icon" />
          <input v-model="searchQuery" placeholder="搜索会话…" class="dr-search" />
        </div>
        <div class="sb-tags" style="padding: 4px 12px">
          <span
            v-for="t in tags"
            :key="t"
            :class="['sb-tag', { active: activeTag === t }]"
            @click="activeTag = activeTag === t ? '' : t"
          >{{ t }}</span>
        </div>
        <div class="dr-list" v-if="!loading">
          <div
            v-for="s in filteredSessions"
            :key="s.id"
            :class="['sb-item', { active: s.id === currentSession && !selectMode }]"
            @click="selectMode ? toggleSelect(s.id) : (showDrawer = false, switchSession(s.id))"
          >
            <span class="sb-item-icon">{{ s.icon || '💬' }}</span>
            <div class="sb-item-content">
              <div class="sb-item-title">{{ s.title || '新对话' }}</div>
              <div class="sb-item-meta">{{ s.time }}</div>
            </div>
          </div>
          <div v-if="filteredSessions.length === 0" class="sb-empty">暂无会话</div>
        </div>
        <div class="dr-footer">
          <button class="sb-new-btn" @click="showDrawer = false; newChat()">
            <Plus :size="15" /> 新对话
          </button>
        </div>
      </aside>
    </Teleport>

    <nav v-if="isMobile" class="mtabs">
      <button
        v-for="t in mobileTabs"
        :key="t.path"
        :class="['mtab', { active: route.path === t.path }]"
        @click="router.push(t.path)"
      >
        <component :is="t.icon" :size="19" :stroke-width="1.9" />
        <span>{{ t.label }}</span>
      </button>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Search, CheckSquare, X, Plus, Menu, Settings, Sun, Moon, Command, ChevronDown,
  MessageSquare, Wrench, Clock, Layers,
} from 'lucide-vue-next'
import NavRail from '@/layouts/NavRail.vue'
import CommandPalette from '@/components/CommandPalette.vue'

const router = useRouter()
const route = useRoute()

const isMobile = ref(window.innerWidth < 768)
const showDrawer = ref(false)
const searchQuery = ref('')
const activeTag = ref('')
const showModelPicker = ref(false)
const online = ref(true)
const paletteRef = ref<any>(null)

const models = ref<string[]>([])
const currentModel = ref('')

const API = window.location.origin
const tags = ['工作', '代码', '闲聊', '研究']
const sessions = ref<any[]>([])
const messagesMap = ref<Record<string, any[]>>({})
const currentSession = ref('')
const loading = ref(true)

const selectMode = ref(false)
const selectedIds = ref<string[]>([])

/* ---------------- 主题 ---------------- */
const theme = ref<'dark' | 'light'>('dark')

function applyTheme(next: 'dark' | 'light') {
  theme.value = next
  document.documentElement.dataset.theme = next
  localStorage.setItem('hhs-theme', next)
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', next === 'dark' ? '#0b0d12' : '#f5f6f9')
}

function toggleTheme() {
  document.documentElement.classList.add('theme-switching')
  applyTheme(theme.value === 'dark' ? 'light' : 'dark')
  window.setTimeout(() => document.documentElement.classList.remove('theme-switching'), 300)
}

/* ---------------- 路由状态 ---------------- */
const pageTitles: Record<string, string> = {
  '/chat': '对话',
  '/workspace': '工作台',
  '/agent': '智能体',
  '/prompt': '提示词',
  '/tools': '工具中心',
  '/plugins': '技能中心',
  '/memory': '兴趣与记忆',
  '/history': '历史记录',
  '/search': '全局搜索',
  '/profile': '角色档案',
  '/plugins': '技能中心',
  '/settings': '设置',
}
const pageTitle = computed(() => pageTitles[route.path] || 'Personal AI OS')
const isChat = computed(() => route.path === '/chat')
const showSidebar = computed(() => !isMobile.value && isChat.value)
const currentSessionTitle = computed(
  () => sessions.value.find((s: any) => s.id === currentSession.value)?.title || '',
)

const mobileTabs = [
  { path: '/chat', label: '对话', icon: MessageSquare },
  { path: '/workspace', label: '工作台', icon: Layers },
  { path: '/tools', label: '工具', icon: Wrench },
  { path: '/history', label: '历史', icon: Clock },
  { path: '/settings', label: '设置', icon: Settings },
]

function openPalette() { paletteRef.value?.open?.() }

function toggleSettings() {
  router.push(route.path === '/settings' ? '/chat' : '/settings')
}

/* ---------------- 会话 ---------------- */
function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedIds.value = []
}

function toggleSelect(id: string) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

async function apiGet(path: string) {
  const r = await fetch(`${API}${path}`)
  return r.json()
}
async function apiPost(path: string, body: any) {
  const r = await fetch(`${API}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  return r.json()
}
async function apiPut(path: string, body: any) {
  const r = await fetch(`${API}${path}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  return r.json()
}
async function apiDel(path: string) {
  const r = await fetch(`${API}${path}`, { method: 'DELETE' })
  if (!r.ok) { const t = await r.text().catch(() => ''); throw new Error(t || `DELETE ${path} ${r.status}`) }
  return r.json().catch(() => ({}))
}
async function apiPatch(path: string, body: any) {
  const r = await fetch(`${API}${path}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) { const t = await r.text().catch(() => ''); throw new Error(t || `PATCH ${path} ${r.status}`) }
  return r.json().catch(() => ({}))
}

async function loadFromServer() {
  try {
    const data = await apiGet('/api/v1/sessions')
    sessions.value = data.sessions || []
    if (sessions.value.length > 0) {
      const firstId = sessions.value[0].id
      const d2 = await apiGet(`/api/v1/sessions/${firstId}`)
      messagesMap.value[firstId] = d2.session?.messages || []
      currentSession.value = firstId
    }
    if (sessions.value.length === 0) await newChat()
  } catch (e) {
    console.error('加载失败', e)
    sessions.value = [{ id: 's_default', icon: '💬', title: '离线模式', preview: '无法连接后端', time: '--' }]
    currentSession.value = 's_default'
  }
  loading.value = false
}

async function loadMessages(sessionId: string) {
  try {
    const d = await apiGet(`/api/v1/sessions/${sessionId}`)
    messagesMap.value[sessionId] = d.session?.messages || []
  } catch (e) {
    messagesMap.value[sessionId] = []
  }
}

async function saveMessages(sessionId: string) {
  const msgs = messagesMap.value[sessionId] || []
  try { await apiPut(`/api/v1/sessions/${sessionId}/messages`, msgs) } catch (e) { /* ignore */ }
}

function getCurrentMessages() { return messagesMap.value[currentSession.value] || [] }
function setCurrentMessages(msgs: any[]) {
  messagesMap.value[currentSession.value] = JSON.parse(JSON.stringify(msgs))
  saveMessages(currentSession.value)
}

async function switchSession(id: string) {
  if (id === currentSession.value) return
  await saveMessages(currentSession.value)
  if (!messagesMap.value[id]) await loadMessages(id)
  currentSession.value = id
  showDrawer.value = false
  if (route.path !== '/chat') router.push('/chat')
}

async function newChat() {
  const now = new Date().toLocaleTimeString()
  const id = 's' + Date.now().toString(36)
  try {
    const d = await apiPost('/api/v1/sessions', { id, title: '新对话', icon: '💬', time: now })
    const meta = d.session?.meta || { id, title: '新对话', icon: '💬', time: now }
    sessions.value.unshift(meta)
    messagesMap.value[id] = []
    currentSession.value = id
  } catch (e) {
    sessions.value.unshift({ id, icon: '💬', title: '新对话', preview: '', time: now })
    messagesMap.value[id] = []
    currentSession.value = id
  }
  if (route.path !== '/chat') router.push('/chat')
}

function confirmDelete(id: string) {
  if (!confirm(`删除会话「${sessions.value.find((s) => s.id === id)?.title || ''}」？`)) return
  deleteOne(id)
}

async function deleteOne(id: string) {
  try {
    await apiDel(`/api/v1/sessions/${id}`)
    sessions.value = sessions.value.filter((s) => s.id !== id)
    delete messagesMap.value[id]
    if (id === currentSession.value) {
      if (sessions.value.length > 0) await switchSession(sessions.value[0].id)
      else await newChat()
    }
  } catch (e) {
    console.error('删除失败', e)
  }
}

async function deleteSelected() {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  if (!confirm(`确定删除选中的 ${ids.length} 个会话吗？`)) return
  for (const id of ids) {
    try { await apiDel(`/api/v1/sessions/${id}`) } catch (e) { console.error('删除失败', id, e) }
  }
  sessions.value = sessions.value.filter((s) => !ids.includes(s.id))
  ids.forEach((id) => delete messagesMap.value[id])
  selectedIds.value = []
  selectMode.value = false
  if (ids.includes(currentSession.value)) {
    if (sessions.value.length > 0) await switchSession(sessions.value[0].id)
    else await newChat()
  }
}

async function confirmDeleteAll() {
  if (!confirm(`确定删除全部 ${sessions.value.length} 个会话吗？此操作不可恢复！`)) return
  const allIds = sessions.value.map((s) => s.id)
  for (const id of allIds) {
    try { await apiDel(`/api/v1/sessions/${id}`) } catch (e) { console.error('删除失败', id, e) }
  }
  sessions.value = []
  messagesMap.value = {}
  selectedIds.value = []
  selectMode.value = false
  await newChat()
}

provide('sessionId', currentSession)
provide('getMessages', getCurrentMessages)
provide('setMessages', setCurrentMessages)
provide('sessions', sessions)
provide('currentSession', currentSession)
provide('currentModel', currentModel)
provide('models', models)
provide('loadModels', loadModels)
provide('updateSessionTitle', updateSessionTitle)
provide('openSession', switchSession)
provide('createChat', newChat)
provide('reloadSessions', loadFromServer)

async function updateSessionTitle(sessionId: string, title: string) {
  const session = sessions.value.find((s: any) => s.id === sessionId)
  if (session) {
    session.title = title
    try { await apiPatch(`/api/v1/sessions/${sessionId}/meta`, { title }) } catch (e) { /* ignore */ }
  }
}

const filteredSessions = computed(() =>
  sessions.value.filter((s: any) => {
    if (activeTag.value && s.tag !== activeTag.value) return false
    if (searchQuery.value && s.title && !s.title.includes(searchQuery.value)) return false
    return true
  }),
)

async function loadModels() {
  try {
    const data = await apiGet('/api/v1/settings')
    const allModels: string[] = []
    if (data.providers && Array.isArray(data.providers)) {
      for (const p of data.providers) {
        if (p.models && Array.isArray(p.models)) {
          for (const m of p.models) if (!allModels.includes(m)) allModels.push(m)
        }
      }
    }
    if (allModels.length > 0) {
      models.value = allModels
      if (!currentModel.value || !allModels.includes(currentModel.value)) currentModel.value = allModels[0]
    } else {
      models.value = ['GPT-4o']
      currentModel.value = 'GPT-4o'
    }
  } catch (e) {
    models.value = ['GPT-4o']
    currentModel.value = 'GPT-4o'
  }
}

function onResize() { isMobile.value = window.innerWidth < 768 }

watch(() => route.path, (path) => {
  if (path === '/' || path === '/chat') loadModels()
  showModelPicker.value = false
})

function onProvidersUpdated() { loadModels() }

/* ---------------- 键盘快捷键 ---------------- */
function onKeydown(e: KeyboardEvent) {
  const meta = e.ctrlKey || e.metaKey
  if (!meta) return
  const tag = (e.target as HTMLElement)?.tagName
  const typing = tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable

  if (e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); return }
  if (e.key.toLowerCase() === 'f' && !typing) { e.preventDefault(); router.push('/search'); return }
  if (e.key === '1') { e.preventDefault(); router.push('/chat'); return }
  if (e.key === '2') { e.preventDefault(); router.push('/workspace'); return }
  if (e.key === '3') { e.preventDefault(); router.push('/tools'); return }
  if (e.key === '4') { e.preventDefault(); router.push('/history'); return }
}

onMounted(() => {
  const urlTheme = new URLSearchParams(window.location.search).get('theme')
  const saved = urlTheme || localStorage.getItem('hhs-theme')
  applyTheme(saved === 'light' ? 'light' : 'dark')
  window.addEventListener('resize', onResize)
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('settings:providers-updated', onProvidersUpdated as EventListener)
  loadFromServer()
  loadModels()
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('settings:providers-updated', onProvidersUpdated as EventListener)
})
</script>

<style>
/* 全局重置与基础排版已迁移到 assets/styles/main.css */
</style>

<style scoped>
.app-shell {
  height: 100%;
  display: flex;
  background: var(--bg);
  overflow: hidden;
  max-width: 100vw;
}
.app-shell.mobile { flex-direction: column; }

/* ---------------- 侧栏 ---------------- */
.app-sidebar {
  width: var(--sidebar-w);
  flex-shrink: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-right: 1px solid var(--border-light);
}

.sb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 14px 12px;
  gap: 10px;
}
.sb-brand { display: flex; align-items: baseline; gap: 7px; }
.sb-brand-name { font-size: 14px; font-weight: 700; letter-spacing: -0.01em; }
.sb-brand-count {
  font-size: 10.5px;
  font-weight: 650;
  color: var(--text3);
  background: var(--surface-alt);
  border-radius: var(--r-full);
  padding: 1px 7px;
}
.sb-new {
  width: 28px; height: 28px;
  display: grid; place-items: center;
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  background: var(--surface-alt);
  color: var(--text2);
  font-size: 15px;
  transition: all var(--t-fast);
}
.sb-new:hover { color: var(--primary); border-color: var(--primary); background: var(--primary-soft); }

.sb-search {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 12px 8px;
  padding: 0 9px;
  height: 32px;
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  transition: border-color var(--t-fast);
}
.sb-search:focus-within { border-color: var(--primary); }
.sb-search-icon { color: var(--text3); flex-shrink: 0; }
.sb-search-inp {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  color: var(--text);
  font-size: 12.5px;
  outline: none;
}
.sb-select-btn {
  width: 22px; height: 22px;
  display: grid; place-items: center;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: var(--text3);
  transition: all var(--t-fast);
}
.sb-select-btn:hover { color: var(--text); background: var(--surface-alt); }
.sb-select-btn.on { color: var(--primary); background: var(--primary-soft); }

.sb-tags { display: flex; gap: 5px; padding: 2px 12px 8px; flex-wrap: wrap; }
.sb-tag {
  padding: 3px 9px;
  border-radius: var(--r-full);
  font-size: 11px;
  font-weight: 540;
  color: var(--text3);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--t-fast);
}
.sb-tag:hover { color: var(--text2); border-color: var(--border-strong); }
.sb-tag.active { background: var(--primary-soft); color: var(--primary); border-color: transparent; }

.sb-nav { flex: 1; overflow-y: auto; padding: 0 8px 8px; }
.sb-list { display: flex; flex-direction: column; gap: 1px; }
.sb-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 9px;
  border-radius: var(--r-sm);
  cursor: pointer;
  position: relative;
  transition: background var(--t-fast);
}
.sb-item:hover { background: var(--surface-alt); }
.sb-item.active { background: var(--primary-soft); }
.sb-item.active .sb-item-title { color: var(--primary); }
.sb-item-icon { font-size: 14px; flex-shrink: 0; width: 18px; text-align: center; }
.sb-item-content { flex: 1; min-width: 0; }
.sb-item-title {
  font-size: 12.5px;
  font-weight: 540;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text);
}
.sb-item-meta {
  font-size: 10.5px;
  color: var(--text3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}
.sb-item-tag {
  font-size: 9.5px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--surface-3);
  color: var(--text3);
  flex-shrink: 0;
}
.sb-item-del {
  width: 20px; height: 20px;
  display: grid; place-items: center;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: var(--text3);
  opacity: 0;
  transition: all var(--t-fast);
  flex-shrink: 0;
}
.sb-item:hover .sb-item-del { opacity: 1; }
.sb-item-del:hover { color: var(--error); background: color-mix(in srgb, var(--error) 12%, transparent); }

.sb-cb {
  width: 16px; height: 16px;
  border-radius: 4px;
  border: 1px solid var(--border-strong);
  display: grid;
  place-items: center;
  font-size: 10px;
  color: transparent;
  flex-shrink: 0;
}
.sb-cb--on { background: var(--primary); border-color: var(--primary); color: #fff; }

.sb-loading { padding: 8px; }
.sb-empty { padding: 32px 12px; text-align: center; }
.sb-empty-title { font-size: 12.5px; font-weight: 600; color: var(--text2); }
.sb-empty-desc { font-size: 11px; color: var(--text3); margin-top: 4px; }

.sb-footer { padding: 10px; border-top: 1px solid var(--border-light); }
.sb-new-btn {
  width: 100%;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
  border-radius: var(--r-sm);
  background: var(--grad-primary);
  color: #fff;
  font-size: 12.5px;
  font-weight: 620;
  box-shadow: 0 2px 10px var(--primary-glow);
  transition: filter var(--t-fast), box-shadow var(--t-fast);
}
.sb-new-btn:hover { filter: brightness(1.08); box-shadow: 0 4px 16px var(--primary-glow); }
.sb-actions { display: flex; flex-direction: column; gap: 6px; }
.sb-del-btn {
  width: 100%; height: 32px;
  border: none; border-radius: var(--r-sm);
  background: var(--error); color: #fff;
  font-size: 12px; font-weight: 600;
}
.sb-del-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.sb-del-all {
  width: 100%; height: 30px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text3);
  font-size: 11.5px;
}
.sb-del-all:hover { color: var(--error); border-color: var(--error); }

/* ---------------- 主区 ---------------- */
.app-main { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }

.app-topbar {
  height: var(--topbar-h);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px 0 16px;
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border-light);
  z-index: 30;
}
.tb-left { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
.tb-crumb { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.tb-page { font-size: 13.5px; font-weight: 680; letter-spacing: -0.01em; white-space: nowrap; }
.tb-session {
  font-size: 11.5px;
  color: var(--text3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 220px;
}
.tb-session::before { content: '/'; margin-right: 8px; color: var(--border-strong); }

.tb-btn {
  width: 30px; height: 30px;
  display: grid; place-items: center;
  border: none;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text2);
  transition: all var(--t-fast);
  flex-shrink: 0;
}
.tb-btn:hover { background: var(--surface-alt); color: var(--text); }

.tb-center { display: flex; align-items: center; gap: 10px; justify-content: center; }
.tb-actions { display: flex; align-items: center; gap: 2px; flex: 1; justify-content: flex-end; }

.tb-model-btn {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 30px;
  padding: 0 11px;
  border-radius: var(--r-full);
  background: var(--surface-alt);
  border: 1px solid var(--border-light);
  color: var(--text);
  font-size: 12px;
  font-weight: 560;
  max-width: 200px;
  transition: all var(--t-fast);
}
.tb-model-btn:hover { border-color: var(--border-strong); background: var(--surface-3); }
.tb-model-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--success) 18%, transparent);
  flex-shrink: 0;
}
.tb-model-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tb-model-arrow { color: var(--text3); flex-shrink: 0; }

.tb-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10.5px;
  font-weight: 560;
  color: var(--text3);
}
.tb-status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text3); }
.tb-status.online .tb-status-dot { background: var(--success); }
.tb-status.offline .tb-status-dot { background: var(--error); }

.model-picker-wrap { position: relative; }
.model-picker-drop {
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  min-width: 210px;
  max-height: 320px;
  overflow-y: auto;
  padding: 6px;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-lg);
  z-index: 100;
  animation: drop-in 160ms var(--ease);
}
@keyframes drop-in {
  from { opacity: 0; transform: translateX(-50%) translateY(-6px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
.mp-head {
  font-size: 10px;
  font-weight: 750;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text3);
  padding: 6px 8px 8px;
}
.model-picker-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 9px;
  border-radius: var(--r-sm);
  cursor: pointer;
  font-size: 12.5px;
  transition: background var(--t-fast);
}
.model-picker-item:hover { background: var(--surface-alt); }
.model-picker-item.active { background: var(--primary-soft); color: var(--primary); font-weight: 600; }
.mp-tag { font-size: 9.5px; padding: 1px 6px; border-radius: 4px; background: var(--surface-alt); color: var(--text3); }
.mp-empty { padding: 14px; text-align: center; font-size: 11.5px; color: var(--text3); }

.app-view { flex: 1; min-height: 0; overflow: hidden; }

/* ---------------- 移动端抽屉 ---------------- */
.dr-overlay { position: fixed; inset: 0; background: var(--overlay); backdrop-filter: blur(2px); z-index: 900; }
.dr-panel {
  position: fixed;
  top: 0; bottom: 0; left: 0;
  width: 284px;
  max-width: 86vw;
  background: var(--surface);
  border-right: 1px solid var(--border-light);
  z-index: 901;
  transform: translateX(-100%);
  transition: transform var(--t-slow);
  display: flex;
  flex-direction: column;
}
.dr-panel.dr-open { transform: translateX(0); }
.dr-search { flex: 1; background: transparent; border: none; color: var(--text); font-size: 12.5px; outline: none; }
.dr-list { flex: 1; overflow-y: auto; padding: 0 8px; }
.dr-footer { padding: 10px; border-top: 1px solid var(--border-light); }

/* ---------------- 移动端底部标签栏 ---------------- */
.mtabs {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 60;
  height: 58px;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  align-items: stretch;
  background: color-mix(in srgb, var(--surface) 94%, transparent);
  backdrop-filter: blur(16px);
  border-top: 1px solid var(--border-light);
  padding-bottom: env(safe-area-inset-bottom, 0);
}
.mtab {
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border: none;
  background: transparent;
  color: var(--text3);
  font-size: 9.5px;
  font-weight: 560;
  transition: color var(--t-fast);
}
.mtab.active { color: var(--primary); }
.mtab.active::after {
  content: '';
  position: absolute;
  top: 0;
  width: 22px;
  height: 2px;
  border-radius: 0 0 2px 2px;
  background: var(--primary);
}
.mtab { position: relative; }

@media (max-width: 767px) {
  .app-main { padding-bottom: 58px; }
  .app-topbar { padding: 0 8px; }
  .tb-session { display: none; }
  .tb-center { display: none; }
}
</style>

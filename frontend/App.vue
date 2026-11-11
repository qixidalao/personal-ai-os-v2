<template>
  <div class="app-shell" :class="{ 'is-mobile': isMobile }">
    <AppSidebar
      v-if="!isMobile"
      :collapsed="navCollapsed"
      :theme="theme"
      :online="online"
      :is-chat="isChat"
      :sessions="sessions"
      :filtered-sessions="filteredSessions"
      :current-session="currentSession"
      :current-model="currentModel"
      :search-query="searchQuery"
      :active-tag="activeTag"
      :tags="tags"
      :loading="loading"
      :select-mode="selectMode"
      :selected-ids="selectedIds"
      @toggle-collapse="toggleNav"
      @open-palette="openPalette"
      @toggle-theme="toggleTheme"
      @new-chat="newChat"
      @switch-session="switchSession"
      @delete-session="confirmDelete"
      @toggle-select-mode="toggleSelectMode"
      @toggle-select="toggleSelect"
      @delete-selected="deleteSelected"
      @delete-all="confirmDeleteAll"
      @update:search-query="searchQuery = $event"
      @update:active-tag="activeTag = $event"
    />

    <div class="app-main">
      <header class="console-bar">
        <div class="cb-left">
          <button v-if="isMobile" class="cb-icon" @click="showSessionDrawer = true" title="会话列表">
            <Menu :size="18" />
          </button>
          <div class="cb-crumb">
            <span class="cb-group">{{ currentGroupTitle }}</span>
            <span class="cb-sep">/</span>
            <span class="cb-page">{{ pageTitle }}</span>
            <span v-if="isChat && currentSessionTitle" class="cb-session">{{ currentSessionTitle }}</span>
          </div>
        </div>

        <div class="cb-center">
          <button class="cb-search" @click="openPalette">
            <Search :size="14" />
            <span class="cb-search-text">搜索或跳转…</span>
            <span class="ui-kbd">⌘K</span>
          </button>
        </div>

        <div class="cb-right">
          <div v-if="isChat" class="cb-model-wrap">
            <button class="cb-model-btn" @click="showModelPicker = !showModelPicker">
              <span class="cb-model-dot"></span>
              <span class="cb-model-name">{{ currentModel || '选择模型' }}</span>
              <ChevronDown :size="12" />
            </button>
            <div v-if="showModelPicker" class="cb-model-drop" @click.stop>
              <div class="cb-drop-head">选择模型</div>
              <button
                v-for="m in models"
                :key="m"
                :class="['cb-model-item', { active: m === currentModel }]"
                @click="currentModel = m; showModelPicker = false"
              >
                <span class="cb-model-item-dot"></span>
                <span class="cb-model-item-name">{{ m }}</span>
                <span v-if="m === currentModel" class="cb-model-check">✓</span>
              </button>
              <div v-if="!models.length" class="cb-drop-empty">暂无可用模型，请到设置添加</div>
            </div>
          </div>

          <span :class="['cb-status', online ? 'on' : 'off']"><i></i>{{ online ? '在线' : '离线' }}</span>

          <button v-if="!isMobile" class="cb-icon" :class="{ active: dockOpen }" @click="dockOpen = !dockOpen" title="上下文坞">
            <PanelRight :size="17" />
          </button>
          <button v-if="isMobile" class="cb-icon" @click="openPalette" title="全局搜索 / 命令面板">
            <Search :size="17" />
          </button>
          <button v-if="!isMobile" class="cb-icon" @click="toggleTheme" :title="theme === 'dark' ? '亮色模式' : '暗色模式'">
            <Sun v-if="theme === 'dark'" :size="17" />
            <Moon v-else :size="17" />
          </button>
          <button v-if="isMobile" class="cb-icon" @click="showDrawer = true" title="全部页面">
            <LayoutGrid :size="17" />
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

    <ContextDock
      v-if="!isMobile && dockOpen"
      :sessions="sessions"
      :current-session="currentSession"
      :current-model="currentModel"
      :online="online"
      :loading="loading"
      @close="dockOpen = false"
      @new-chat="newChat"
      @switch-session="switchSession"
      @open-palette="openPalette"
    />

    <CommandPalette ref="paletteRef" />

    <!-- 移动端：左侧会话抽屉 -->
    <Teleport to="body">
      <div v-if="isMobile && showSessionDrawer" class="msess-overlay" @click="showSessionDrawer = false"></div>
      <aside v-if="isMobile" :class="['msess-drawer', { open: showSessionDrawer }]">
        <div class="msess-head">
          <div class="msess-brand">
            <span class="msess-logo">AI</span>
            <div class="msess-brand-text">
              <span class="msess-name">对话</span>
              <span class="msess-sub">{{ sessions.length }} 个会话</span>
            </div>
          </div>
          <button class="cb-icon" @click="showSessionDrawer = false"><X :size="17" /></button>
        </div>
        <div class="msess-search">
          <Search :size="14" />
          <input v-model="searchQuery" placeholder="搜索会话…" />
        </div>
        <div class="msess-tags">
          <button
            :class="['msess-tag', { active: !activeTag }]"
            @click="activeTag = ''"
          >全部</button>
          <button
            v-for="t in tags"
            :key="t"
            :class="['msess-tag', { active: activeTag === t }]"
            @click="activeTag = activeTag === t ? '' : t"
          >{{ t }}</button>
        </div>
        <div class="msess-list">
          <button
            v-for="s in filteredSessions"
            :key="s.id"
            :class="['msess-item', { active: s.id === currentSession }]"
            @click="openSession(s.id)"
          >
            <span class="msess-icon">{{ s.icon || '💬' }}</span>
            <span class="msess-body">
              <span class="msess-title">{{ s.title || '新对话' }}</span>
              <span class="msess-meta">{{ s.time || '' }}<template v-if="s.preview"> · {{ s.preview }}</template></span>
            </span>
          </button>
          <div v-if="!loading && filteredSessions.length === 0" class="msess-empty">
            <div>没有匹配的对话</div>
            <button v-if="activeTag || searchQuery" class="msess-empty-clear" @click="clearSessionFilters">清除筛选，查看全部</button>
          </div>
          <div v-if="loading" class="msess-skel">
            <div class="ui-skeleton" style="height: 42px; margin-bottom: 6px"></div>
            <div class="ui-skeleton" style="height: 42px"></div>
          </div>
        </div>
        <div class="msess-foot">
          <button class="ui-btn ui-btn--primary ui-btn--block" @click="showSessionDrawer = false; newChat()">
            <Plus :size="14" /> 新对话
          </button>
        </div>
      </aside>
    </Teleport>

    <!-- 移动端：全部功能全屏面板 -->
    <Teleport to="body">
      <div v-if="isMobile && showDrawer" class="msheet-overlay" @click="showDrawer = false"></div>
      <section v-if="isMobile" :class="['msheet', { open: showDrawer }]">
        <div class="msheet-head">
          <div class="msheet-brand">
            <span class="msheet-logo">AI</span>
            <div class="msheet-brand-text">
              <span class="msheet-name">Personal AI OS</span>
              <span class="msheet-sub">全部功能 · {{ pageTitle }}</span>
            </div>
          </div>
          <button class="cb-icon" @click="showDrawer = false"><X :size="17" /></button>
        </div>
        <div class="msheet-body">
          <div v-for="g in navGroups" :key="g.key" class="msheet-group">
            <div class="msheet-group-title">{{ g.title }}<em>{{ g.en }}</em></div>
            <div class="msheet-grid">
              <button
                v-for="item in g.items"
                :key="item.path"
                :class="['msheet-item', { active: isRouteActive(item.path) }]"
                @click="goMobile(item.path)"
              >
                <component :is="item.icon" :size="17" :stroke-width="1.9" />
                <span>{{ item.label }}</span>
              </button>
            </div>
          </div>
          <div class="msheet-group">
            <div class="msheet-group-title">系统<em>SYSTEM</em></div>
            <div class="msheet-grid">
              <button
                v-for="item in navFooter"
                :key="item.path"
                :class="['msheet-item', { active: isRouteActive(item.path) }]"
                @click="goMobile(item.path)"
              >
                <component :is="item.icon" :size="17" :stroke-width="1.9" />
                <span>{{ item.label }}</span>
              </button>
              <button class="msheet-item" :class="{ active: isRouteActive('/search') }" @click="goMobile('/search')">
                <Search :size="17" :stroke-width="1.9" />
                <span>全局搜索</span>
              </button>
              <button class="msheet-item" @click="toggleTheme">
                <Sun v-if="theme === 'dark'" :size="17" />
                <Moon v-else :size="17" />
                <span>{{ theme === 'dark' ? '亮色模式' : '暗色模式' }}</span>
              </button>
            </div>
          </div>
        </div>

      </section>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Search, CheckSquare, X, Plus, Menu, Settings, Sun, Moon, Command, ChevronDown,
  MessageSquare, Wrench, Clock, Layers,
  PencilLine, Bot, FileText, Puzzle, Brain, History, User, PanelRight, LayoutGrid,
} from 'lucide-vue-next'
import AppSidebar from '@/layouts/AppSidebar.vue'
import ContextDock from '@/layouts/ContextDock.vue'
import { NAV_GROUPS, NAV_FOOTER, MOBILE_TABS } from '@/layouts/nav'
import CommandPalette from '@/components/CommandPalette.vue'

const router = useRouter()
const route = useRoute()

const isMobile = ref(window.innerWidth < 768)
const showDrawer = ref(false)
const showSessionDrawer = ref(false)
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
  fetch('/api/v1/settings', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme: theme.value }),
  }).catch(() => { /* 普通用户没有全局设置权限，忽略 */ })
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
  '/runs': '执行记录',
  '/search': '全局搜索',
  '/settings': '设置',
}
const pageTitle = computed(() => pageTitles[route.path] || 'Personal AI OS')
const isChat = computed(() => route.path === '/chat')
const currentSessionTitle = computed(
  () => sessions.value.find((s: any) => s.id === currentSession.value)?.title || '',
)

const mobileTabs = MOBILE_TABS

const navGroups = NAV_GROUPS
const navFooter = NAV_FOOTER

/* 侧栏折叠 / 上下文坞：持久化到 localStorage */
const navCollapsed = ref(localStorage.getItem('hhs-nav-collapsed') === '1')
const dockOpen = ref(localStorage.getItem('hhs-dock-open') === '1')
function toggleNav() {
  navCollapsed.value = !navCollapsed.value
  try { localStorage.setItem('hhs-nav-collapsed', navCollapsed.value ? '1' : '0') } catch { /* ignore */
  /* 中文：忽略 */ }
}
watch(dockOpen, (v) => {
  try { localStorage.setItem('hhs-dock-open', v ? '1' : '0') } catch { /* ignore */
  /* 中文：忽略 */ }
})

/* 面包屑分组标题：从单一导航配置推导 */
const currentGroupTitle = computed(() => {
  for (const g of navGroups) {
    if (g.items.some((i) => route.path === i.path || route.path.startsWith(i.path + '/'))) return g.title
  }
  return route.path === '/settings' ? '系统' : '工作区'
})


/** 移动端抽屉里的完整页面导航（桌面 NavRail 在 <768px 被隐藏，这里是唯一入口） */

function isRouteActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

/** 抽屉导航：先关闭抽屉再跳转，避免移动端手势/滚动残留 */
function goMobile(path: string) {
  showDrawer.value = false
  if (route.path !== path) router.push(path)
}

function openSession(id: string) {
  showDrawer.value = false
  showSessionDrawer.value = false
  switchSession(id)
  if (route.path !== '/chat') router.push('/chat')
}

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
  try { await apiPut(`/api/v1/sessions/${sessionId}/messages`, msgs) } catch (e) { /* ignore */
  /* 中文：忽略 */ }
}

function getCurrentMessages() { return messagesMap.value[currentSession.value] || [] }
function setCurrentMessages(msgs: any[]) {
  messagesMap.value[currentSession.value] = JSON.parse(JSON.stringify(msgs))
  saveMessages(currentSession.value)
}

async function switchSession(id: string) {
  if (id === currentSession.value) return
  const prev = currentSession.value
  // 立即切换：上一个会话的保存放后台执行，避免等待 PUT 造成卡顿
  if (prev) {
    void saveMessages(prev).catch(() => { /* 保存失败不阻塞切换 */ })
  }
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
    try { await apiPatch(`/api/v1/sessions/${sessionId}/meta`, { title }) } catch (e) { /* ignore */
    /* 中文：忽略 */ }
  }
}

/* 会话标签：优先用 meta.tag；历史会话没有 tag 时按标题/预览关键词派生，
   避免点「工作/代码/闲聊/研究」一律显示"没有匹配的对话"。 */
const TAG_RULES: Array<{ tag: string; kw: string[] }> = [
  { tag: '代码', kw: ['代码', '脚本', 'python', 'javascript', 'typescript', 'vue', 'react', 'sql', 'git', '报错', 'bug', 'debug', '函数', '接口', 'api', '编程', 'html', 'css', '编译', '部署脚本'] },
  { tag: '研究', kw: ['研究', '论文', '原理', '分析', '对比', '评测', '资料', '检索', '调查', '实验', '概念', '学习', '为什么', '机制', '趋势'] },
  { tag: '工作', kw: ['项目', '任务', '需求', '方案', '会议', '文档', '汇报', '配置', '服务器', '部署', '上线', '运维', '客户', '排期', '工作', '计划', '流程'] },
]

function sessionTag(s: any) {
  if (s?.tag) return s.tag
  const text = `${s?.title || ''} ${s?.preview || ''}`.toLowerCase()
  for (const rule of TAG_RULES) {
    if (rule.kw.some((kw) => text.includes(kw))) return rule.tag
  }
  return '闲聊'
}

function clearSessionFilters() {
  activeTag.value = ''
  searchQuery.value = ''
}

const filteredSessions = computed(() =>
  sessions.value.filter((s: any) => {
    if (activeTag.value && sessionTag(s) !== activeTag.value) return false
    const q = searchQuery.value.trim().toLowerCase()
    if (q && !`${s.title || ''} ${s.preview || ''}`.toLowerCase().includes(q)) return false
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
    if (data.theme === 'light' || data.theme === 'dark') applyTheme(data.theme)
    if (allModels.length > 0) {
      models.value = allModels
      let savedModel = ''
      try { savedModel = localStorage.getItem('hhs-model') || '' } catch { /* ignore */
      /* 中文：忽略 */ }
      if (!currentModel.value || !allModels.includes(currentModel.value)) {
        currentModel.value = savedModel && allModels.includes(savedModel) ? savedModel : allModels[0]
      }
    } else {
      models.value = ['GPT-4o']
      currentModel.value = 'GPT-4o'
    }
  } catch (e) {
    models.value = ['GPT-4o']
    currentModel.value = 'GPT-4o'
  }
}

/* 模型选择持久化：刷新后仍用上次选的模型（多模态时不会掉回纯文本模型） */
watch(currentModel, (m) => {
  if (!m) return
  try { localStorage.setItem('hhs-model', m) } catch { /* ignore */
  /* 中文：忽略 */ }
})

function onThemeUpdated(e: Event) {
  const next = (e as CustomEvent).detail
  if (next === 'light' || next === 'dark') applyTheme(next)
}

function onResize() {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) showDrawer.value = false
}

watch(() => route.path, (path) => {
  if (path === '/' || path === '/chat') loadModels()
  showModelPicker.value = false
  showDrawer.value = false
  showSessionDrawer.value = false
})

/* 抽屉打开时锁定背景滚动，关闭/切换桌面布局/卸载时恢复 */
watch([showDrawer, showSessionDrawer], ([drawerOpen, sessionOpen]) => {
  const locked = (drawerOpen || sessionOpen) && isMobile.value
  document.body.classList.toggle('dr-lock', locked)
})

function onProvidersUpdated() { loadModels() }

/* ---------------- 键盘快捷键 ---------------- */
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && (showDrawer.value || showSessionDrawer.value)) { showDrawer.value = false; showSessionDrawer.value = false; return }
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
  window.addEventListener('settings:theme-updated', onThemeUpdated as EventListener)
  loadFromServer()
  loadModels()
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('settings:providers-updated', onProvidersUpdated as EventListener)
  window.removeEventListener('settings:theme-updated', onThemeUpdated as EventListener)
  document.body.classList.remove('dr-lock')
})
</script>

<style>
/* ============================================================
   Aurora Console 外壳：侧栏 + 控制栏 + 视图 + 上下文坞 + 移动端
   ============================================================ */
.app-shell {
  display: flex;
  width: 100%;
  height: 100%;
  min-width: 0;
  overflow: hidden;
  position: relative;
}
.app-shell.is-mobile { flex-direction: column; }

.app-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

/* ---------------- 控制栏 ---------------- */
.console-bar {
  height: var(--topbar-h, 60px);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 18px;
  border-bottom: 1px solid var(--border-light);
  background: color-mix(in srgb, var(--bg) 72%, transparent);
  backdrop-filter: blur(18px);
  position: relative;
  z-index: 25;
}

.cb-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.cb-crumb {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  font-size: 12.5px;
}
.cb-group {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text3);
}
.cb-sep { color: var(--text3); opacity: 0.6; }
.cb-page { font-weight: 650; color: var(--text); white-space: nowrap; }
.cb-session {
  color: var(--text3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 280px;
  padding-left: 8px;
  border-left: 1px solid var(--border-light);
  font-size: 12px;
}

.cb-center { flex: 1; display: flex; justify-content: center; min-width: 0; }
.cb-search {
  display: flex;
  align-items: center;
  gap: 9px;
  width: min(420px, 100%);
  height: 34px;
  padding: 0 11px;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: color-mix(in srgb, var(--surface) 62%, transparent);
  color: var(--text3);
  font-size: 12px;
  transition: all var(--t-fast);
}
.cb-search:hover {
  border-color: var(--border-strong);
  color: var(--text2);
  background: var(--surface);
}
.cb-search-text { flex: 1; text-align: left; }

.cb-right { display: flex; align-items: center; gap: 6px; }

.cb-icon {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--text3);
  transition: all var(--t-fast);
}
.cb-icon:hover { color: var(--text); background: var(--surface-alt); border-color: var(--border-light); }
.cb-icon.active { color: var(--primary); background: var(--primary-soft); border-color: color-mix(in srgb, var(--primary) 26%, transparent); }

.cb-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding: 0 9px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-full);
  font-size: 10.5px;
  color: var(--text2);
  margin: 0 4px;
}
.cb-status i { width: 6px; height: 6px; border-radius: 50%; background: var(--text3); }
.cb-status.on i { background: var(--success); box-shadow: 0 0 8px color-mix(in srgb, var(--success) 70%, transparent); }
.cb-status.off i { background: var(--error); }

/* 模型选择 */
.cb-model-wrap { position: relative; }
.cb-model-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 30px;
  padding: 0 11px;
  border: 1px solid var(--border-light);
  border-radius: 9px;
  background: color-mix(in srgb, var(--surface) 70%, transparent);
  color: var(--text);
  font-size: 11.5px;
  font-weight: 560;
  transition: all var(--t-fast);
}
.cb-model-btn:hover { border-color: var(--border-strong); background: var(--surface-alt); }
.cb-model-dot {
  width: 6px; height: 6px;
  border-radius: 2px;
  background: var(--grad-primary);
  box-shadow: 0 0 8px var(--primary-glow);
}
.cb-model-name { max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.cb-model-drop {
  position: absolute;
  top: calc(100% + 7px);
  right: 0;
  width: 216px;
  padding: 6px;
  border: 1px solid var(--border-strong);
  border-radius: 13px;
  background: color-mix(in srgb, var(--surface) 96%, transparent);
  box-shadow: var(--shadow-lg);
  backdrop-filter: blur(20px);
  z-index: 80;
  animation: drop-in 140ms var(--ease);
}
@keyframes drop-in {
  from { opacity: 0; transform: translateY(-5px); }
  to { opacity: 1; transform: none; }
}
.cb-drop-head {
  padding: 5px 8px 7px;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text3);
}
.cb-model-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text2);
  font-size: 12px;
  text-align: left;
  transition: all var(--t-fast);
}
.cb-model-item:hover { background: var(--surface-alt); color: var(--text); }
.cb-model-item.active { background: var(--primary-soft); color: var(--primary); border-color: color-mix(in srgb, var(--primary) 24%, transparent); }
.cb-model-item-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; opacity: 0.5; }
.cb-model-item-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cb-model-check { font-size: 11px; }
.cb-drop-empty { padding: 10px 8px; font-size: 11.5px; color: var(--text3); }

/* ---------------- 视图区 ---------------- */
.app-view { flex: 1; min-height: 0; overflow: hidden; position: relative; }

.page-fade-enter-active, .page-fade-leave-active { transition: opacity 160ms var(--ease), transform 160ms var(--ease); }
.page-fade-enter-from { opacity: 0; transform: translateY(5px); }
.page-fade-leave-to { opacity: 0; transform: translateY(-3px); }

/* ---------------- 移动端面板：最近对话 ---------------- */
.msheet-sessions {
  margin-bottom: 16px;
  padding: 12px;
  border: 1px solid var(--border-light);
  border-radius: 15px;
  background: color-mix(in srgb, var(--surface) 76%, transparent);
}
.msheet-sess-head { display: flex; align-items: center; gap: 7px; padding-bottom: 8px; }
.msheet-sess-title { flex: 1; font-size: 10.5px; font-weight: 720; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text2); }
.msheet-sess-count { font-family: var(--font-mono); font-size: 10px; color: var(--text3); }
.msheet-sess-add {
  width: 22px; height: 22px; display: grid; place-items: center;
  border: 1px solid var(--border-light); border-radius: 7px; background: transparent; color: var(--text2);
}
.msheet-sess-add:active { background: var(--surface-alt); }
.msheet-sess-search {
  display: flex; align-items: center; gap: 6px; height: 30px; padding: 0 9px;
  margin-bottom: 7px; border: 1px solid var(--border-light); border-radius: 9px;
  background: color-mix(in srgb, var(--bg) 55%, transparent); color: var(--text3);
}
.msheet-sess-search input { flex: 1; border: none; outline: none; background: transparent; color: var(--text); font-size: 12px; }
.msheet-sess-list { max-height: 34vh; overflow-y: auto; margin-bottom: 8px; }
.msheet-sess {
  width: 100%; display: flex; align-items: center; gap: 8px; padding: 7px 8px;
  border: 1px solid transparent; border-radius: 9px; background: transparent; text-align: left;
}
.msheet-sess.active { background: var(--primary-soft); border-color: color-mix(in srgb, var(--primary) 22%, transparent); }
.msheet-sess-icon { font-size: 13px; flex-shrink: 0; }
.msheet-sess-text { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.msheet-sess-name { font-size: 12px; font-weight: 560; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.msheet-sess-meta { font-size: 9.5px; color: var(--text3); font-family: var(--font-mono); }
.msheet-sess-empty { padding: 10px 4px; font-size: 11.5px; color: var(--text3); }
.msheet-sess-newchat { margin-top: 2px; }

/* 侧栏顶部「新对话」快捷按钮 */
.side-newchat {
  margin: 0 12px 10px; height: 32px; display: flex; align-items: center; justify-content: center; gap: 6px;
  border: 1px solid color-mix(in srgb, var(--primary) 30%, transparent);
  border-radius: 10px; background: var(--primary-soft); color: var(--primary); font-size: 12px; font-weight: 600;
}
.side-newchat:hover { background: color-mix(in srgb, var(--primary) 20%, transparent); }
.side--collapsed .side-newchat { margin: 0 auto 10px; width: 40px; padding: 0; }


/* ---------------- 移动端：左侧会话抽屉 ---------------- */
.msess-overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay);
  backdrop-filter: blur(3px);
  z-index: 400;
  animation: overlay-in 160ms var(--ease);
}
.msess-drawer {
  position: fixed;
  top: 0; bottom: 0; left: 0;
  width: min(320px, 86vw);
  z-index: 410;
  display: flex;
  flex-direction: column;
  background: var(--bg);
  border-right: 1px solid var(--border-light);
  transform: translateX(-102%);
  transition: transform 220ms var(--ease);
  padding-top: env(safe-area-inset-top, 0px);
  box-shadow: var(--shadow-lg);
}
.msess-drawer.open { transform: none; }
.msess-head {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 14px 12px 10px;
  border-bottom: 1px solid var(--border-light);
}
.msess-brand { display: flex; align-items: center; gap: 9px; }
.msess-logo {
  width: 32px; height: 32px; display: grid; place-items: center;
  border-radius: 10px; background: var(--grad-primary); color: #fff;
  font-size: 11px; font-weight: 720; box-shadow: 0 4px 14px var(--primary-glow);
}
.msess-brand-text { display: flex; flex-direction: column; }
.msess-name { font-size: 13px; font-weight: 700; }
.msess-sub { font-size: 10px; color: var(--text3); font-family: var(--font-mono); }
.msess-search {
  display: flex; align-items: center; gap: 7px;
  margin: 10px 12px 6px; padding: 0 10px; height: 34px;
  border: 1px solid var(--border-light); border-radius: 10px;
  background: color-mix(in srgb, var(--surface) 70%, transparent);
  color: var(--text3);
}
.msess-search input { flex: 1; border: none; outline: none; background: transparent; color: var(--text); font-size: 12.5px; }
.msess-tags { display: flex; gap: 5px; flex-wrap: wrap; padding: 4px 12px 8px; }
.msess-tag {
  height: 24px; padding: 0 10px; border-radius: var(--r-full);
  border: 1px solid transparent; background: transparent; color: var(--text3); font-size: 11px;
}
.msess-tag.active { color: var(--primary); background: var(--primary-soft); border-color: color-mix(in srgb, var(--primary) 30%, transparent); }
.msess-list { flex: 1; overflow-y: auto; padding: 0 8px 8px; }
.msess-item {
  width: 100%; display: flex; align-items: center; gap: 9px;
  padding: 9px 9px; margin-bottom: 2px;
  border: 1px solid transparent; border-radius: 10px; background: transparent; text-align: left;
}
.msess-item.active { background: var(--primary-soft); border-color: color-mix(in srgb, var(--primary) 22%, transparent); }
.msess-icon { font-size: 14px; flex-shrink: 0; }
.msess-body { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.msess-title { font-size: 12.5px; font-weight: 560; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.msess-meta { font-size: 10px; color: var(--text3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.msess-empty { padding: 16px 6px; font-size: 12px; color: var(--text3); display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.msess-empty-clear {
  padding: 6px 12px; border-radius: 8px; font-size: 11.5px;
  border: 1px solid color-mix(in srgb, var(--primary) 35%, transparent);
  background: var(--primary-soft); color: var(--primary);
}
.msess-skel { padding: 8px 2px; }
.msess-foot { padding: 10px 12px calc(12px + env(safe-area-inset-bottom, 0px)); border-top: 1px solid var(--border-light); }

/* ---------------- 移动端：顶栏 / 面板 ---------------- */
.is-mobile .console-bar {
  height: 52px;
  padding: 0 8px;
  gap: 6px;
}
.is-mobile .cb-left { flex: 0 1 auto; }
.is-mobile .cb-crumb { gap: 5px; }
.is-mobile .cb-group, .is-mobile .cb-sep { display: none; }
.is-mobile .cb-page { font-size: 13.5px; max-width: 108px; overflow: hidden; text-overflow: ellipsis; }
.is-mobile .cb-session { display: none; }
.is-mobile .cb-center { flex: 1; justify-content: flex-end; }
.is-mobile .cb-search { display: none; }
.is-mobile .cb-right { gap: 2px; }
.is-mobile .cb-icon { width: 30px; height: 30px; }
.is-mobile .cb-status { padding: 0 7px; margin: 0 2px; }
.is-mobile .cb-status span { display: none; }
.is-mobile .cb-model-btn { height: 28px; padding: 0 8px; max-width: min(150px, 42vw); }
.is-mobile .cb-model-name { max-width: 96px; font-size: 11px; }
.is-mobile .cb-model-drop { right: -84px; }

.app-shell.is-mobile .app-main { padding-bottom: env(safe-area-inset-bottom, 0px); }

/* 移动端全屏面板 */
.msheet-overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay);
  backdrop-filter: blur(4px);
  z-index: 190;
  animation: overlay-in 180ms var(--ease);
}
@keyframes overlay-in { from { opacity: 0; } to { opacity: 1; } }

.msheet {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  background: var(--bg);
  transform: translateY(12px);
  opacity: 0;
  pointer-events: none;
  transition: opacity 180ms var(--ease), transform 220ms var(--ease);
}
.msheet.open { opacity: 1; transform: none; pointer-events: auto; }

.msheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 14px 12px;
  border-bottom: 1px solid var(--border-light);
}
.msheet-brand { display: flex; align-items: center; gap: 10px; }
.msheet-logo {
  width: 34px; height: 34px;
  display: grid; place-items: center;
  border-radius: 11px;
  background: var(--grad-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 720;
  box-shadow: 0 4px 16px var(--primary-glow);
}
.msheet-brand-text { display: flex; flex-direction: column; }
.msheet-name { font-size: 13px; font-weight: 700; }
.msheet-sub { font-size: 10.5px; color: var(--text3); font-family: var(--font-mono); }
.msheet-body { flex: 1; overflow-y: auto; padding: 14px; }
.msheet-group { margin-bottom: 18px; }
.msheet-group-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: 10px;
  font-weight: 760;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text3);
  padding: 0 2px 8px;
}
.msheet-group-title em { font-style: normal; font-family: var(--font-mono); font-size: 8px; opacity: 0.55; }
.msheet-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }
.msheet-item {
  display: flex;
  align-items: center;
  gap: 9px;
  height: 46px;
  padding: 0 12px;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface) 80%, transparent);
  color: var(--text2);
  font-size: 12.5px;
  font-weight: 540;
  text-align: left;
  transition: all var(--t-fast);
}
.msheet-item:active { transform: scale(0.98); }
.msheet-item.active {
  color: var(--primary);
  background: var(--primary-soft);
  border-color: color-mix(in srgb, var(--primary) 28%, transparent);
}
.msheet-foot {
  padding: 12px 14px calc(12px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid var(--border-light);
}

</style>

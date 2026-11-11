import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/chat',
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/pages/ChatPage.vue'),
    meta: { title: '对话', icon: 'MessageSquare' },
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('@/pages/WorkspacePage.vue'),
    meta: { title: 'Workspace', icon: 'Pencil' },
  },
  {
    path: '/agent',
    name: 'Agent',
    component: () => import('@/pages/AgentPage.vue'),
    meta: { title: 'Agent', icon: 'Bot' },
  },
  {
    path: '/prompt',
    name: 'Prompt',
    component: () => import('@/pages/PromptPage.vue'),
    meta: { title: 'Prompt', icon: 'FileText' },
  },
  {
    path: '/memory',
    name: 'Memory',
    component: () => import('@/pages/MemoryPage.vue'),
    meta: { title: 'Memory', icon: 'Brain' },
  },
  {
    path: '/tools',
    name: 'Tools',
    component: () => import('@/pages/ToolsPage.vue'),
    meta: { title: '工具', icon: 'Wrench' },
  },
  {
    path: '/plugins',
    name: 'Plugins',
    component: () => import('@/pages/PluginsPage.vue'),
    meta: { title: '插件', icon: 'Puzzle' },
  },
  {
    path: '/profile',
    redirect: '/agent',
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/pages/HistoryPage.vue'),
    meta: { title: '历史记录', icon: 'Clock' },
  },
  {
    path: '/search',
    name: 'GlobalSearch',
    component: () => import('@/pages/GlobalSearchPage.vue'),
    meta: { title: '搜索', icon: 'Search' },
  },
  {
    path: '/runs',
    name: 'Runs',
    component: () => import('@/pages/RunHistoryPage.vue'),
    meta: { title: '执行记录', icon: 'Activity' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/pages/SettingsPage.vue'),
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/pages/SettingsPage.vue'),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach(async (to) => {
  if (to.path === '/admin') {
    try {
      const resp = await fetch('/api/v1/auth/me')
      const data = await resp.json()
      if (!(data.local === true || data.role === 'owner')) return '/settings'
    } catch {
      return '/settings'
    }
  }
  return true
})

export default router

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
    name: 'Profile',
    component: () => import('@/pages/ProfilePage.vue'),
    meta: { title: 'Profile', icon: 'User' },
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
    path: '/settings',
    name: 'Settings',
    component: () => import('@/pages/SettingsPage.vue'),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router

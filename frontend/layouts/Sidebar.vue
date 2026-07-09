<template>
  <aside :class="['sidebar', { 'sidebar--collapsed': collapsed }]">
    <!-- Logo -->
    <div class="sidebar__logo" @click="router.push('/')">
      <span class="logo-icon">🧠</span>
      <span v-show="!collapsed" class="logo-text">AI OS</span>
    </div>

    <!-- 导航菜单 -->
    <nav class="sidebar__nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        :class="['nav-item', { 'nav-item--active': isActive(item.path) }]"
      >
        <span class="nav-icon" v-html="item.icon" />
        <span v-show="!collapsed" class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- 底部 -->
    <div class="sidebar__footer">
      <div class="nav-item" @click="toggleCollapse">
        <span class="nav-icon">{{ collapsed ? '→' : '←' }}</span>
        <span v-show="!collapsed" class="nav-label">折叠</span>
      </div>

      <router-link to="/settings" class="nav-item">
        <span class="nav-icon">⚙</span>
        <span v-show="!collapsed" class="nav-label">设置</span>
      </router-link>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)

const navItems = [
  { path: '/chat', label: '对话', icon: '💬' },
  { path: '/workspace', label: 'Workspace', icon: '📝' },
  { path: '/agent', label: 'Agent', icon: '🤖' },
  { path: '/prompt', label: 'Prompt', icon: '📄' },
  { path: '/memory', label: 'Memory', icon: '🧠' },
  { path: '/tools', label: '工具', icon: '🔧' },
  { path: '/plugins', label: '插件', icon: '🧩' },
  { path: '/profile', label: 'Profile', icon: '👤' },
  { path: '/history', label: '历史', icon: '🕐' },
  { path: '/search', label: '搜索', icon: '🔍' },
]

function isActive(path: string) {
  return route.path.startsWith(path)
}

function toggleCollapse() {
  collapsed.value = !collapsed.value
}
</script>

<style scoped>
.sidebar {
  width: 240px;
  height: 100vh;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;
  flex-shrink: 0;
}

.sidebar--collapsed {
  width: 64px;
}

.sidebar__logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
}

.logo-icon { font-size: 28px; }
.logo-text { font-size: 18px; font-weight: 700; }

.sidebar__nav {
  flex: 1;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.nav-item:hover {
  background: var(--surface-alt);
  color: var(--text-primary);
}

.nav-item--active {
  background: var(--primary);
  color: #fff;
}

.nav-icon { font-size: 18px; width: 24px; text-align: center; flex-shrink: 0; }
.nav-label { font-size: 14px; }

.sidebar__footer {
  padding: 8px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
</style>

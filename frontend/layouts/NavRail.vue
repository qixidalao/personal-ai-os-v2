<template>
  <nav class="rail">
    <div class="rail-logo" @click="go('/chat')" title="Personal AI OS">
      <div class="rail-logo-mark">
        <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 3v3M12 18v3M4.2 7.5l2.6 1.5M17.2 15l2.6 1.5M4.2 16.5l2.6-1.5M17.2 9l2.6-1.5" />
          <circle cx="12" cy="12" r="4.2" />
        </svg>
      </div>
    </div>

    <div class="rail-items">
      <button
        v-for="item in primary"
        :key="item.path"
        :class="['rail-btn', { active: isActive(item.path) }]"
        @click="go(item.path)"
      >
        <component :is="item.icon" :size="19" :stroke-width="1.85" />
        <span class="rail-tip">{{ item.label }}<em v-if="item.hint">{{ item.hint }}</em></span>
      </button>
    </div>

    <div class="rail-bottom">
      <button class="rail-btn" @click="$emit('toggle-theme')">
        <Sun v-if="theme === 'dark'" :size="19" :stroke-width="1.85" />
        <Moon v-else :size="19" :stroke-width="1.85" />
        <span class="rail-tip">{{ theme === 'dark' ? '亮色模式' : '暗色模式' }}</span>
      </button>
      <button class="rail-btn" @click="$emit('open-palette')">
        <Command :size="19" :stroke-width="1.85" />
        <span class="rail-tip">命令面板<em>Ctrl K</em></span>
      </button>
      <button :class="['rail-btn', { active: route.path === '/settings' }]" @click="go('/settings')">
        <Settings :size="19" :stroke-width="1.85" />
        <span class="rail-tip">设置</span>
      </button>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import {
  MessageSquare, PencilLine, Bot, FileText, Wrench, Puzzle, Brain,
  History, Search, Settings, Sun, Moon, Command,
} from 'lucide-vue-next'

defineProps<{ theme: 'dark' | 'light'; mobile?: boolean }>()
defineEmits<{ (e: 'toggle-theme'): void; (e: 'open-palette'): void }>()

const route = useRoute()
const router = useRouter()

const primary = [
  { path: '/chat', label: '对话', icon: MessageSquare, hint: 'Ctrl 1' },
  { path: '/workspace', label: '工作台', icon: PencilLine, hint: 'Ctrl 2' },
  { path: '/agent', label: '智能体', icon: Bot },
  { path: '/prompt', label: '提示词', icon: FileText },
  { path: '/tools', label: '工具', icon: Wrench },
  { path: '/plugins', label: '技能', icon: Puzzle },
  { path: '/memory', label: '记忆', icon: Brain },
  { path: '/history', label: '历史', icon: History },
  { path: '/search', label: '搜索', icon: Search, hint: 'Ctrl F' },
]

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}
function go(path: string) {
  if (route.path !== path) router.push(path)
}
</script>

<style scoped>
.rail {
  width: var(--rail-w);
  flex-shrink: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 0 12px;
  background: var(--surface-2);
  border-right: 1px solid var(--border-light);
  z-index: 40;
}

.rail-logo { padding: 4px 0 12px; }
.rail-logo-mark {
  width: 36px; height: 36px;
  display: grid; place-items: center;
  border-radius: 11px;
  background: var(--grad-primary);
  color: #fff;
  box-shadow: 0 4px 14px var(--primary-glow);
  cursor: pointer;
  transition: transform var(--t-mid), box-shadow var(--t-mid);
}
.rail-logo-mark:hover { transform: translateY(-1px) scale(1.04); box-shadow: 0 6px 20px var(--primary-glow); }

.rail-items {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  flex: 1;
  width: 100%;
  overflow-y: auto;
  overflow-x: visible;
  padding-top: 4px;
}
.rail-items::-webkit-scrollbar { width: 0; }

.rail-bottom {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding-top: 8px;
  border-top: 1px solid var(--border-light);
  width: 40px;
}

.rail-btn {
  position: relative;
  width: 42px; height: 42px;
  display: grid; place-items: center;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: var(--text3);
  transition: background var(--t-fast), color var(--t-fast), transform var(--t-fast);
}

.rail-btn::before {
  content: '';
  position: absolute;
  left: -11px;
  top: 50%;
  width: 3px;
  height: 0;
  border-radius: 0 3px 3px 0;
  background: var(--primary);
  transform: translateY(-50%);
  transition: height var(--t-mid);
}

.rail-btn:hover { background: var(--surface-alt); color: var(--text); }
.rail-btn:active { transform: scale(0.94); }

.rail-btn.active {
  background: var(--primary-soft);
  color: var(--primary);
}
.rail-btn.active::before { height: 20px; }

/* 悬浮提示 */
.rail-tip {
  position: absolute;
  left: calc(100% + 10px);
  top: 50%;
  transform: translateY(-50%) translateX(-4px);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--r-sm);
  background: var(--surface-3);
  border: 1px solid var(--border-strong);
  color: var(--text);
  font-size: 12px;
  font-weight: 560;
  white-space: nowrap;
  box-shadow: var(--shadow-md);
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--t-fast), transform var(--t-fast);
  z-index: 60;
}
.rail-tip em {
  font-style: normal;
  font-size: 10px;
  color: var(--text3);
  font-family: var(--font-mono);
}
.rail-btn:hover .rail-tip { opacity: 1; transform: translateY(-50%) translateX(0); }

/* 移动端：底部标签栏 */
.rail--mobile {
  flex-direction: row;
  width: 100%;
  height: 58px;
  padding: 0 6px;
  border-right: none;
  border-top: 1px solid var(--border-light);
  gap: 0;
  justify-content: space-around;
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  backdrop-filter: blur(14px);
}
.rail--mobile .rail-logo,
.rail--mobile .rail-bottom { display: none; }
.rail--mobile .rail-items { flex-direction: row; justify-content: space-around; overflow: visible; }
.rail--mobile .rail-btn { width: 44px; height: 44px; }
.rail--mobile .rail-btn::before { display: none; }
.rail--mobile .rail-tip { display: none; }
.rail--mobile .rail-btn.active { background: var(--primary-soft); }
</style>

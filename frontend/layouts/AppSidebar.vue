<template>
  <aside :class="['side', { 'side--collapsed': collapsed }]">
    <div class="side-brand">
      <button class="side-logo" @click="go('/chat')" title="Personal AI OS">
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 3v3M12 18v3M4.2 7.5l2.6 1.5M17.2 15l2.6 1.5M4.2 16.5l2.6-1.5M17.2 9l2.6-1.5" />
          <circle cx="12" cy="12" r="4.2" />
        </svg>
      </button>
      <div v-if="!collapsed" class="side-brand-text">
        <span class="side-name">Personal AI OS</span>
        <span class="side-ver">CONSOLE</span>
      </div>
      <button v-if="!collapsed" class="side-collapse" @click="$emit('toggle-collapse')" title="收起侧栏">
        <PanelLeftClose :size="15" />
      </button>
    </div>

    <button class="side-cmd" @click="$emit('open-palette')" :title="collapsed ? '搜索或跳转 ⌘K' : ''">
      <Search :size="15" />
      <template v-if="!collapsed">
        <span class="side-cmd-text">搜索或跳转</span>
        <span class="ui-kbd">⌘K</span>
      </template>
    </button>

    <button v-if="!collapsed" class="side-newchat" @click="$emit('new-chat')">
      <Plus :size="14" /> 新对话
    </button>
    <button v-else class="side-newchat" @click="$emit('new-chat')" title="新对话">
      <Plus :size="16" />
    </button>

    <nav class="side-nav">
      <div v-for="g in navGroups" :key="g.key" class="side-group">
        <div v-if="!collapsed" class="side-group-title">
          <span>{{ g.title }}</span><em>{{ g.en }}</em>
        </div>
        <div v-else class="side-group-rule"></div>
        <button
          v-for="item in g.items"
          :key="item.path"
          :class="['side-item', { active: isActive(item.path) }]"
          :title="collapsed ? item.label : ''"
          @click="go(item.path)"
        >
          <span class="side-item-icon"><component :is="item.icon" :size="16" :stroke-width="1.85" /></span>
          <template v-if="!collapsed">
            <span class="side-item-label">{{ item.label }}</span>
            <span v-if="item.hint" class="side-item-hint">{{ item.hint }}</span>
          </template>
        </button>
      </div>
    </nav>

    <section v-if="!collapsed" :class="['side-sess', { 'side-sess--compact': !isChat }]">
      <div class="side-sess-head">
        <span class="side-sess-title">最近对话</span>
        <span class="side-sess-count">{{ sessions.length }}</span>
        <button class="side-sess-new" @click="$emit('new-chat')" title="新对话"><Plus :size="13" /></button>
      </div>
      <div v-if="isChat" class="side-sess-search">
        <Search :size="13" class="side-sess-search-icon" />
        <input
          :value="searchQuery"
          class="side-sess-input"
          placeholder="搜索会话…"
          @input="$emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
        />
        <button :class="['side-sess-multi', { on: selectMode }]" @click="$emit('toggle-select-mode')" title="多选">
          <CheckSquare :size="12" />
        </button>
      </div>
      <div v-if="isChat" class="side-sess-tags">
        <button
          :class="['side-sess-tag', { active: !activeTag }]"
          @click="$emit('update:activeTag', '')"
        >全部</button>
        <button
          v-for="t in tags"
          :key="t"
          :class="['side-sess-tag', { active: activeTag === t }]"
          @click="$emit('update:activeTag', activeTag === t ? '' : t)"
        >{{ t }}</button>
      </div>
      <div class="side-sess-list">
        <template v-if="!loading">
          <button
            v-for="s in filteredSessions"
            :key="s.id"
            :class="['side-sess-item', { active: s.id === currentSession && !selectMode }]"
            @click="selectMode ? $emit('toggle-select', s.id) : selectSession(s.id)"
          >
            <span v-if="selectMode" :class="['side-sess-cb', { on: selectedIds.includes(s.id) }]">{{ selectedIds.includes(s.id) ? '✓' : '' }}</span>
            <span class="side-sess-icon">{{ s.icon || '💬' }}</span>
            <span class="side-sess-body">
              <span class="side-sess-name">{{ s.title || '新对话' }}</span>
              <span class="side-sess-meta">{{ s.time || '' }}<template v-if="s.preview"> · {{ s.preview }}</template></span>
            </span>
            <span v-if="!selectMode" class="side-sess-del" @click.stop="$emit('delete-session', s.id)" title="删除">
              <X :size="11" />
            </span>
          </button>
          <div v-if="filteredSessions.length === 0" class="side-sess-empty">
            <div class="side-sess-empty-title">没有匹配的对话</div>
            <div class="side-sess-empty-desc">换个关键词，或新建一个对话</div>
            <button
              v-if="activeTag || searchQuery"
              class="side-sess-empty-clear"
              @click="$emit('update:activeTag', ''); $emit('update:searchQuery', '')"
            >清除筛选，查看全部</button>
          </div>
        </template>
        <div v-else class="side-sess-skel">
          <div class="ui-skeleton" style="height: 38px; margin-bottom: 6px"></div>
          <div class="ui-skeleton" style="height: 38px; margin-bottom: 6px"></div>
          <div class="ui-skeleton" style="height: 38px"></div>
        </div>
      </div>
      <div v-if="selectMode" class="side-sess-actions">
        <button class="ui-btn ui-btn--danger ui-btn--sm" :disabled="selectedIds.length === 0" @click="$emit('delete-selected')">
          删除选中（{{ selectedIds.length }}）
        </button>
        <button class="ui-btn ui-btn--ghost ui-btn--sm" @click="$emit('delete-all')">全部删除</button>
      </div>
    </section>

    <div class="side-foot">
      <button class="side-item" @click="$emit('toggle-theme')" :title="collapsed ? (theme === 'dark' ? '亮色模式' : '暗色模式') : ''">
        <span class="side-item-icon"><Sun v-if="theme === 'dark'" :size="16" :stroke-width="1.85" /><Moon v-else :size="16" :stroke-width="1.85" /></span>
        <template v-if="!collapsed"><span class="side-item-label">{{ theme === 'dark' ? '亮色模式' : '暗色模式' }}</span></template>
      </button>
      <button :class="['side-item', { active: isActive('/settings') }]" @click="go('/settings')" :title="collapsed ? '设置' : ''">
        <span class="side-item-icon"><Settings :size="16" :stroke-width="1.85" /></span>
        <template v-if="!collapsed"><span class="side-item-label">设置</span></template>
      </button>
      <button v-if="collapsed" class="side-expand" @click="$emit('toggle-collapse')" title="展开侧栏查看会话">
        <PanelLeftOpen :size="15" />
      </button>
      <div v-if="!collapsed" class="side-status">
        <span :class="['side-status-dot', online ? 'on' : 'off']"></span>
        <span class="side-status-text">{{ online ? '服务在线' : '服务离线' }}</span>
        <span v-if="currentModel" class="side-status-model">{{ currentModel }}</span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Search, CheckSquare, Plus, X, Sun, Moon, Settings,
  PanelLeftClose, PanelLeftOpen,
} from 'lucide-vue-next'
import { NAV_GROUPS } from './nav'

const props = defineProps<{
  collapsed: boolean
  theme: 'dark' | 'light'
  online: boolean
  isChat: boolean
  sessions: any[]
  filteredSessions: any[]
  currentSession: string
  currentModel: string
  searchQuery: string
  activeTag: string
  tags: string[]
  loading: boolean
  selectMode: boolean
  selectedIds: string[]
}>()

const emit = defineEmits<{
  (e: 'toggle-collapse'): void
  (e: 'open-palette'): void
  (e: 'toggle-theme'): void
  (e: 'new-chat'): void
  (e: 'switch-session', id: string): void
  (e: 'delete-session', id: string): void
  (e: 'toggle-select-mode'): void
  (e: 'toggle-select', id: string): void
  (e: 'delete-selected'): void
  (e: 'delete-all'): void
  (e: 'update:searchQuery', value: string): void
  (e: 'update:activeTag', value: string): void
}>()

const navGroups = NAV_GROUPS
const route = useRoute()
const router = useRouter()

// 路由变化时把当前导航项滚进可视区（避免导航被会话列表挤压后找不到）
watch(
  () => route.path,
  () => {
    nextTick(() => {
      document.querySelector('.side-item.active')?.scrollIntoView({ block: 'nearest' })
    })
  },
  { immediate: true },
)

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}
function go(path: string) {
  if (route.path !== path) router.push(path)
}

/** 非对话页点会话：切过去并回到对话页，避免“点了没反应” */
function selectSession(id: string) {
  emit('switch-session', id)
  if (route.path !== '/chat') router.push('/chat')
}
</script>

<style scoped>
.side {
  width: var(--nav-w, 268px);
  flex-shrink: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-light);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--surface) 88%, transparent), color-mix(in srgb, var(--bg) 92%, transparent));
  backdrop-filter: blur(20px);
  transition: width var(--t-mid);
  position: relative;
  z-index: 30;
}
.side--collapsed { width: var(--nav-w-collapsed, 78px); }

/* 品牌 */
.side-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 14px 12px;
  min-height: 62px;
}
.side-logo {
  width: 34px; height: 34px;
  flex-shrink: 0;
  display: grid; place-items: center;
  border: none;
  border-radius: 11px;
  background: var(--grad-primary);
  color: #fff;
  box-shadow: 0 4px 16px var(--primary-glow);
  transition: transform var(--t-mid), box-shadow var(--t-mid);
}
.side-logo:hover { transform: translateY(-1px) scale(1.04); box-shadow: 0 7px 22px var(--primary-glow); }
.side-brand-text { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.side-name { font-size: 13px; font-weight: 720; letter-spacing: -0.015em; white-space: nowrap; }
.side-ver {
  font-family: var(--font-mono);
  font-size: 8.5px;
  letter-spacing: 0.22em;
  color: var(--text3);
  margin-top: 1px;
}
.side-collapse {
  width: 26px; height: 26px;
  display: grid; place-items: center;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text3);
  transition: all var(--t-fast);
}
.side-collapse:hover { color: var(--text); background: var(--surface-alt); border-color: var(--border-light); }

/* 命令入口 */
.side-cmd {
  margin: 2px 12px 12px;
  height: 34px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  border-radius: 10px;
  border: 1px solid var(--border-light);
  background: color-mix(in srgb, var(--surface) 70%, transparent);
  color: var(--text2);
  font-size: 12px;
  transition: all var(--t-fast);
}
.side-cmd:hover { color: var(--text); border-color: var(--border-strong); background: var(--surface-alt); }
.side-cmd-text { flex: 1; text-align: left; }
.side--collapsed .side-cmd { margin: 2px 14px 12px; width: 46px; padding: 0; justify-content: center; }

/* 分组导航 */
.side-nav { flex: 1 1 0; overflow-y: auto; padding: 0 10px 8px; min-height: 200px; scrollbar-width: thin; scrollbar-color: color-mix(in srgb, var(--text3) 30%, transparent) transparent; }
.side-nav::-webkit-scrollbar { width: 6px; }
.side-group { margin-bottom: 12px; }
.side-group-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px 5px;
  font-size: 10px;
  font-weight: 760;
  letter-spacing: 0.14em;
  color: var(--text3);
  text-transform: uppercase;
}
.side-group-title em {
  font-style: normal;
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.12em;
  opacity: 0.55;
}
.side-group-rule { height: 1px; margin: 6px 8px; background: var(--border-light); }

.side-item {
  position: relative;
  width: 100%;
  height: 36px;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 9px;
  margin-bottom: 1px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text2);
  font-size: 12.5px;
  font-weight: 540;
  text-align: left;
  transition: background var(--t-fast), color var(--t-fast), border-color var(--t-fast);
}
.side-item:hover { background: var(--surface-alt); color: var(--text); }
.side-item.active {
  background: linear-gradient(90deg, var(--primary-soft), color-mix(in srgb, var(--primary-soft) 35%, transparent));
  border-color: color-mix(in srgb, var(--primary) 24%, transparent);
  color: var(--text);
  font-weight: 620;
}
.side-item.active::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 50%;
  transform: translateY(-50%);
  width: 2px;
  height: 18px;
  border-radius: 0 2px 2px 0;
  background: var(--primary);
  box-shadow: 0 0 10px var(--primary-glow);
}
.side-item-icon { display: grid; place-items: center; flex-shrink: 0; color: var(--text3); }
.side-item.active .side-item-icon { color: var(--primary); }
.side-item-label { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.side-item-hint {
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--text3);
  opacity: 0.75;
}
.side-newchat {
  margin: 0 12px 10px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid color-mix(in srgb, var(--primary) 30%, transparent);
  border-radius: 10px;
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  transition: all var(--t-fast);
}
.side-newchat:hover { background: color-mix(in srgb, var(--primary) 20%, transparent); border-color: var(--primary); }
.side--collapsed .side-newchat { margin: 0 auto 10px; width: 40px; padding: 0; }

.side--collapsed .side-item { justify-content: center; padding: 0; height: 38px; }
.side--collapsed .side-item.active::before { left: -9px; }

/* 会话区（仅对话页，展开态） */
.side-sess--compact { flex: 0 1 auto; max-height: 34%; }
.side-sess {
  display: flex;
  flex-direction: column;
  min-height: 132px;
  max-height: 27%;
  flex: 0 1 auto;
  border-top: 1px solid var(--border-light);
  padding: 8px 10px 0;
}
.side-sess-head { display: flex; align-items: center; gap: 7px; padding: 4px 4px 7px; }
.side-sess-title { font-size: 10.5px; font-weight: 720; letter-spacing: 0.1em; color: var(--text2); text-transform: uppercase; flex: 1; }
.side-sess-count { font-family: var(--font-mono); font-size: 10px; color: var(--text3); }
.side-sess-new {
  width: 22px; height: 22px;
  display: grid; place-items: center;
  border-radius: 7px;
  border: 1px solid var(--border-light);
  background: transparent;
  color: var(--text2);
  transition: all var(--t-fast);
}
.side-sess-new:hover { color: var(--primary); border-color: color-mix(in srgb, var(--primary) 40%, transparent); background: var(--primary-soft); }

.side-sess-search {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 8px;
  margin-bottom: 6px;
  border: 1px solid var(--border-light);
  border-radius: 9px;
  background: color-mix(in srgb, var(--bg) 55%, transparent);
}
.side-sess-search-icon { color: var(--text3); flex-shrink: 0; }
.side-sess-input {
  flex: 1; min-width: 0;
  border: none; outline: none; background: transparent;
  color: var(--text); font-size: 12px;
}
.side-sess-input::placeholder { color: var(--text3); }
.side-sess-multi {
  width: 20px; height: 20px;
  display: grid; place-items: center;
  border: none; border-radius: 6px;
  background: transparent; color: var(--text3);
}
.side-sess-multi.on { color: var(--primary); background: var(--primary-soft); }

.side-sess-tags { display: flex; gap: 4px; flex-wrap: wrap; padding: 0 2px 7px; }
.side-sess-tag {
  height: 20px;
  padding: 0 8px;
  border-radius: var(--r-full);
  border: 1px solid transparent;
  background: transparent;
  color: var(--text3);
  font-size: 10.5px;
  transition: all var(--t-fast);
}
.side-sess-tag:hover { color: var(--text2); background: var(--surface-alt); }
.side-sess-tag.active { color: var(--primary); background: var(--primary-soft); border-color: color-mix(in srgb, var(--primary) 30%, transparent); }

.side-sess-list { flex: 1; min-height: 0; overflow-y: auto; padding: 0 0 6px; }
.side-sess-list::-webkit-scrollbar { width: 6px; }
.side-sess-list { scrollbar-width: thin; scrollbar-color: color-mix(in srgb, var(--text3) 30%, transparent) transparent; }
.side-sess-item {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  margin-bottom: 1px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  text-align: left;
  transition: background var(--t-fast), border-color var(--t-fast);
}
.side-sess-item:hover { background: var(--surface-alt); }
.side-sess-item.active { background: var(--primary-soft); border-color: color-mix(in srgb, var(--primary) 22%, transparent); }
.side-sess-icon { font-size: 13px; flex-shrink: 0; }
.side-sess-body { display: flex; flex-direction: column; min-width: 0; flex: 1; gap: 0; }
.side-sess-name {
  font-size: 12px; font-weight: 560; color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.side-sess-meta {
  font-size: 10px; color: var(--text3); font-family: var(--font-mono);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.side-sess-del {
  width: 18px; height: 18px;
  display: grid; place-items: center;
  border-radius: 5px;
  color: var(--text3);
  opacity: 0;
  transition: all var(--t-fast);
}
.side-sess-item:hover .side-sess-del { opacity: 1; }
.side-sess-del:hover { color: var(--error); background: color-mix(in srgb, var(--error) 12%, transparent); }
.side-sess-cb {
  width: 15px; height: 15px;
  display: grid; place-items: center;
  border: 1px solid var(--border-strong);
  border-radius: 4px;
  font-size: 9px;
  color: transparent;
  flex-shrink: 0;
}
.side-sess-cb.on { background: var(--primary); border-color: var(--primary); color: #fff; }
.side-sess-empty { padding: 14px 8px; }
.side-sess-empty-clear {
  margin-top: 8px; padding: 5px 10px; border-radius: 7px; font-size: 11px;
  border: 1px solid color-mix(in srgb, var(--primary) 35%, transparent);
  background: var(--primary-soft); color: var(--primary);
}
.side-sess-empty-title { font-size: 12px; font-weight: 600; color: var(--text2); }
.side-sess-empty-desc { font-size: 11px; color: var(--text3); margin-top: 2px; }
.side-sess-skel { padding: 4px 2px; }
.side-sess-actions { display: flex; gap: 6px; padding: 6px 2px 8px; }

/* 底部 */
.side-foot {
  border-top: 1px solid var(--border-light);
  padding: 8px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.side-expand {
  height: 32px;
  margin-top: 4px;
  display: grid;
  place-items: center;
  border: 1px dashed var(--border);
  border-radius: 9px;
  background: transparent;
  color: var(--text3);
}
.side-expand:hover { color: var(--text); border-color: var(--border-strong); }
.side-status {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px 8px 2px;
  font-size: 10.5px;
  color: var(--text3);
}
.side-status-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--text3);
  flex-shrink: 0;
}
.side-status-dot.on { background: var(--success); box-shadow: 0 0 8px color-mix(in srgb, var(--success) 70%, transparent); }
.side-status-dot.off { background: var(--error); }
.side-status-text { flex-shrink: 0; }
.side-status-model {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--text3);
  max-width: 96px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.side--collapsed .side-foot { padding: 8px 14px 10px; }
@media (max-height: 980px) {
  .side-group { margin-bottom: 6px; }
  .side-sess { max-height: 20%; min-height: 120px; }
  .side-sess--compact { max-height: 26%; }
}
@media (max-height: 850px) {
  .side-group { margin-bottom: 4px; }
  .side-sess { max-height: 18%; min-height: 110px; }
  .side-sess--compact { max-height: 24%; }
}
</style>

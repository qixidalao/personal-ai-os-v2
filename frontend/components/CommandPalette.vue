<template>
  <Teleport to="body">
    <Transition name="cp-fade">
      <div v-if="visible" class="cp-overlay" @click.self="close">
        <div class="cp-modal" role="dialog" aria-modal="true">
          <div class="cp-search">
            <Search :size="16" class="cp-search-icon" />
            <input
              ref="inputRef"
              v-model="query"
              class="cp-input"
              placeholder="搜索页面、命令或动作…"
              @keydown.down.prevent="move(1)"
              @keydown.up.prevent="move(-1)"
              @keydown.enter.prevent="runActive"
              @keydown.esc="close"
            />
            <span class="cp-esc">ESC</span>
          </div>

          <div class="cp-results">
            <template v-for="group in grouped" :key="group.name">
              <div class="cp-group">{{ group.name }}</div>
              <button
                v-for="item in group.items"
                :key="item.id"
                :class="['cp-item', { active: item.id === activeId }]"
                @click="run(item)"
                @mouseenter="activeId = item.id"
              >
                <span class="cp-item-icon"><component :is="item.icon" :size="15" /></span>
                <span class="cp-item-label">{{ item.label }}</span>
                <span v-if="item.hint" class="cp-item-hint">{{ item.hint }}</span>
                <ArrowRight v-if="item.id === activeId" :size="13" class="cp-item-arrow" />
              </button>
            </template>

            <div v-if="!flat.length" class="cp-empty">
              <span>没有找到「{{ query }}」相关的命令</span>
            </div>
          </div>

          <div class="cp-foot">
            <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
            <span><kbd>↵</kbd> 执行</span>
            <span><kbd>ESC</kbd> 关闭</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search, ArrowRight, MessageSquare, PencilLine, Bot, FileText, Wrench, Puzzle,
  Brain, History, Settings, Sun, Moon, Plus, Sparkles,
} from 'lucide-vue-next'

const router = useRouter()
const visible = ref(false)
const query = ref('')
const inputRef = ref<HTMLInputElement>()
const activeId = ref('')

interface Cmd {
  id: string
  label: string
  hint?: string
  icon: any
  group: string
  run: () => void
}

function go(path: string) { return () => router.push(path) }

function toggleTheme() {
  const cur = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'
  const next = cur === 'dark' ? 'light' : 'dark'
  document.documentElement.classList.add('theme-switching')
  document.documentElement.dataset.theme = next
  localStorage.setItem('aios-theme', next)
  window.setTimeout(() => document.documentElement.classList.remove('theme-switching'), 300)
}

const commands = computed<Cmd[]>(() => [
  { id: 'chat', label: '对话', hint: 'Ctrl 1', icon: MessageSquare, group: '前往', run: go('/chat') },
  { id: 'workspace', label: '工作台', hint: 'Ctrl 2', icon: PencilLine, group: '前往', run: go('/workspace') },
  { id: 'agent', label: '智能体', icon: Bot, group: '前往', run: go('/agent') },
  { id: 'prompt', label: '提示词库', icon: FileText, group: '前往', run: go('/prompt') },
  { id: 'tools', label: '工具中心', hint: 'Ctrl 3', icon: Wrench, group: '前往', run: go('/tools') },
  { id: 'plugins', label: '技能中心', icon: Puzzle, group: '前往', run: go('/plugins') },
  { id: 'memory', label: '兴趣与记忆', icon: Brain, group: '前往', run: go('/memory') },
  { id: 'history', label: '历史记录', hint: 'Ctrl 4', icon: History, group: '前往', run: go('/history') },
  { id: 'search', label: '全局搜索', hint: 'Ctrl F', icon: Search, group: '前往', run: go('/search') },
  { id: 'settings', label: '设置', icon: Settings, group: '前往', run: go('/settings') },
  { id: 'new-chat', label: '新建对话', icon: Plus, group: '动作', run: () => { router.push('/chat'); window.dispatchEvent(new CustomEvent('aios:new-chat')) } },
  { id: 'theme', label: '切换亮色 / 暗色主题', icon: Sun, group: '动作', run: toggleTheme },
  { id: 'pick-model', label: '切换模型', icon: Sparkles, group: '动作', run: () => { router.push('/settings') } },
])

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return commands.value
  return commands.value.filter(
    (c) => c.label.toLowerCase().includes(q) || c.id.includes(q) || (c.group && c.group.includes(q)),
  )
})

const grouped = computed(() => {
  const map = new Map<string, Cmd[]>()
  for (const c of filtered.value) {
    if (!map.has(c.group)) map.set(c.group, [])
    map.get(c.group)!.push(c)
  }
  return [...map.entries()].map(([name, items]) => ({ name, items }))
})

const flat = computed(() => grouped.value.flatMap((g) => g.items))

watch([query, visible], () => {
  if (flat.value.length && !flat.value.some((c) => c.id === activeId.value)) {
    activeId.value = flat.value[0].id
  }
})

watch(visible, (v) => {
  if (v) {
    query.value = ''
    nextTick(() => { inputRef.value?.focus(); activeId.value = flat.value[0]?.id || '' })
  }
})

function move(dir: number) {
  const list = flat.value
  if (!list.length) return
  const idx = list.findIndex((c) => c.id === activeId.value)
  const next = (idx + dir + list.length) % list.length
  activeId.value = list[next].id
}

function run(cmd: Cmd) { close(); cmd.run() }
function runActive() {
  const item = flat.value.find((c) => c.id === activeId.value) || flat.value[0]
  if (item) run(item)
}

function close() { visible.value = false }

defineExpose({ open: () => { visible.value = true }, close })
</script>

<style scoped>
.cp-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 13vh;
  background: var(--overlay);
  backdrop-filter: blur(6px);
}

.cp-modal {
  width: min(92vw, 560px);
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 66vh;
}

.cp-search {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-light);
}
.cp-search-icon { color: var(--text3); flex-shrink: 0; }
.cp-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text);
  font-size: 14.5px;
  letter-spacing: -0.01em;
}
.cp-input::placeholder { color: var(--text3); }
.cp-esc {
  font-family: var(--font-mono);
  font-size: 9.5px;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border-strong);
  color: var(--text3);
}

.cp-results { overflow-y: auto; padding: 8px; flex: 1; }
.cp-group {
  font-size: 9.5px;
  font-weight: 780;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text3);
  padding: 10px 10px 6px;
}

.cp-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border: none;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text2);
  font-size: 13px;
  text-align: left;
  transition: background var(--t-fast), color var(--t-fast);
}
.cp-item.active { background: var(--primary-soft); color: var(--text); }
.cp-item-icon { display: grid; place-items: center; color: var(--text3); }
.cp-item.active .cp-item-icon { color: var(--primary); }
.cp-item-label { flex: 1; }
.cp-item-hint {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text3);
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--surface-alt);
}
.cp-item-arrow { color: var(--primary); }

.cp-empty { padding: 36px 20px; text-align: center; color: var(--text3); font-size: 12.5px; }

.cp-foot {
  display: flex;
  gap: 16px;
  padding: 9px 16px;
  border-top: 1px solid var(--border-light);
  background: var(--surface-2);
  font-size: 10.5px;
  color: var(--text3);
}
.cp-foot span { display: flex; align-items: center; gap: 4px; }
.cp-foot kbd {
  font-family: var(--font-mono);
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 4px;
  border: 1px solid var(--border-strong);
  background: var(--surface-alt);
}

.cp-fade-enter-active, .cp-fade-leave-active { transition: opacity 160ms var(--ease); }
.cp-fade-enter-from, .cp-fade-leave-to { opacity: 0; }
</style>

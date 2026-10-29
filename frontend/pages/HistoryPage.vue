<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <header class="ui-head">
        <div>
          <div class="ui-eyebrow">Archive</div>
          <h1 class="ui-title">历史记录</h1>
          <p class="ui-sub">所有对话按时间归档。可以搜索内容、复制会话、导出为 Markdown，或批量清理。</p>
        </div>
        <div class="ui-head-actions">
          <button class="ui-btn" :disabled="loading" @click="load">
            <RefreshCw :size="14" :class="{ spin: loading }" /> 刷新
          </button>
        </div>
      </header>

      <div class="stat-row">
        <div class="stat" v-for="s in stats" :key="s.label">
          <div class="stat-icon" :style="{ color: s.color, background: s.bg }">
            <component :is="s.icon" :size="15" />
          </div>
          <div>
            <div class="stat-value">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
        </div>
      </div>

      <div class="toolbar">
        <div class="tb-search">
          <Search :size="14" />
          <input v-model="query" placeholder="搜索标题或摘要…" />
          <button v-if="query" class="tb-clear" @click="query = ''"><X :size="12" /></button>
        </div>

        <div class="sort-group">
          <button
            v-for="opt in sortOptions"
            :key="opt.key"
            :class="['ui-chip', { active: sortBy === opt.key }]"
            @click="sortBy = opt.key"
          >{{ opt.label }}</button>
        </div>

        <div class="view-toggle">
          <button :class="['vt-btn', { on: view === 'card' }]" @click="view = 'card'" title="卡片视图">
            <LayoutGrid :size="14" />
          </button>
          <button :class="['vt-btn', { on: view === 'list' }]" @click="view = 'list'" title="列表视图">
            <List :size="14" />
          </button>
        </div>
      </div>

      <div v-if="loading" class="group">
        <div v-for="i in 6" :key="i" class="ui-skeleton" style="height: 78px; margin-bottom: 10px"></div>
      </div>

      <div v-else-if="!groups.length" class="ui-empty">
        <div class="ui-empty-icon">🗂️</div>
        <div class="ui-empty-title">{{ query ? '没有匹配的会话' : '还没有任何会话' }}</div>
        <div class="ui-empty-desc">{{ query ? '换个关键词试试，或清空搜索条件。' : '开始一次对话后，记录会自动出现在这里。' }}</div>
        <button v-if="!query" class="ui-btn ui-btn--primary" style="margin-top: 8px" @click="createChat">
          <Plus :size="14" /> 新建对话
        </button>
      </div>

      <div v-else class="groups" :class="view">
        <section v-for="g in groups" :key="g.name" class="group">
          <div class="group-title">
            <span>{{ g.name }}</span>
            <em>{{ g.items.length }}</em>
            <div class="group-line"></div>
          </div>

          <div class="items">
            <article
              v-for="s in g.items"
              :key="s.id"
              class="hcard"
              @click="goSession(s.id)"
            >
              <div class="hcard-icon">{{ s.icon || '💬' }}</div>
              <div class="hcard-body">
                <div class="hcard-top">
                  <h3 class="hcard-title">{{ s.title || '新对话' }}</h3>
                  <span v-if="s.tag" class="ui-badge ui-badge--primary">{{ s.tag }}</span>
                </div>
                <p class="hcard-preview">{{ cleanPreview(s.preview) || '（暂无内容）' }}</p>
                <div class="hcard-meta">
                  <span><Clock :size="11" /> {{ fmtDate(s.updated_at || s.created_at) }}</span>
                  <span><Hash :size="11" /> {{ s.id }}</span>
                </div>
              </div>
              <div class="hcard-actions" @click.stop>
                <button class="act" title="打开" @click="goSession(s.id)"><CornerUpRight :size="14" /></button>
                <button class="act" title="复制会话" @click="duplicate(s)"><Copy :size="14" /></button>
                <button class="act" title="导出 Markdown" @click="exportMd(s)"><Download :size="14" /></button>
                <button class="act act--danger" title="删除" @click="remove(s)"><Trash2 :size="14" /></button>
              </div>
            </article>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, inject } from 'vue'
import {
  RefreshCw, Search, X, LayoutGrid, List, Clock, Hash, CornerUpRight,
  Copy, Download, Trash2, Plus, MessagesSquare, CalendarDays, Tag, Flame,
} from 'lucide-vue-next'

const openSession = inject<any>('openSession', null)
const createChat = inject<any>('createChat', null)
const reloadSessions = inject<any>('reloadSessions', null)

interface Session {
  id: string
  title?: string
  icon?: string
  preview?: string
  tag?: string
  time?: string
  created_at?: string
  updated_at?: string
}

const sessions = ref<Session[]>([])
const loading = ref(true)
const query = ref('')
const sortBy = ref<'updated' | 'created' | 'title'>('updated')
const view = ref<'card' | 'list'>('card')

const sortOptions = [
  { key: 'updated', label: '最近更新' },
  { key: 'created', label: '创建时间' },
  { key: 'title', label: '标题' },
] as const

function cleanPreview(text?: string) {
  if (!text) return ''
  return text
    .replace(/```[\s\S]*?```/g, ' [代码] ')
    .replace(/[#>*`_|]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 120)
}

function toDate(value?: string) {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

function fmtDate(value?: string) {
  const d = toDate(value)
  if (!d) return '未知时间'
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  if (min < 60 * 24) return `${Math.floor(min / 60)} 小时前`
  if (min < 60 * 24 * 7) return `${Math.floor(min / 1440)} 天前`
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function bucketOf(value?: string) {
  const d = toDate(value)
  if (!d) return '更早'
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const t = d.getTime()
  if (t >= startOfToday) return '今天'
  if (t >= startOfToday - 86400000) return '昨天'
  if (t >= startOfToday - 86400000 * 7) return '本周'
  if (t >= startOfToday - 86400000 * 30) return '本月'
  return '更早'
}

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  let list = sessions.value.filter((s) => {
    if (!q) return true
    return (
      (s.title || '').toLowerCase().includes(q) ||
      (s.preview || '').toLowerCase().includes(q) ||
      (s.tag || '').toLowerCase().includes(q)
    )
  })

  list = [...list].sort((a, b) => {
    if (sortBy.value === 'title') return (a.title || '').localeCompare(b.title || '', 'zh')
    const key = sortBy.value === 'created' ? 'created_at' : 'updated_at'
    const ta = toDate(a[key])?.getTime() || 0
    const tb = toDate(b[key])?.getTime() || 0
    return tb - ta
  })
  return list
})

const order = ['今天', '昨天', '本周', '本月', '更早']

const groups = computed(() => {
  const map = new Map<string, Session[]>()
  for (const s of filtered.value) {
    const key = bucketOf(s.updated_at || s.created_at)
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(s)
  }
  return order
    .filter((k) => map.has(k))
    .map((k) => ({ name: k, items: map.get(k)! }))
})

const stats = computed(() => {
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const weekAgo = startOfToday - 86400000 * 7
  let today = 0
  let week = 0
  const tags = new Set<string>()
  for (const s of sessions.value) {
    const t = toDate(s.updated_at || s.created_at)?.getTime() || 0
    if (t >= startOfToday) today++
    if (t >= weekAgo) week++
    if (s.tag) tags.add(s.tag)
  }
  return [
    { label: '会话总数', value: sessions.value.length, icon: MessagesSquare, color: 'var(--primary)', bg: 'var(--primary-soft)' },
    { label: '今日活跃', value: today, icon: Flame, color: 'var(--warn)', bg: 'color-mix(in srgb, var(--warn) 14%, transparent)' },
    { label: '本周更新', value: week, icon: CalendarDays, color: 'var(--info)', bg: 'color-mix(in srgb, var(--info) 14%, transparent)' },
    { label: '使用标签', value: tags.size, icon: Tag, color: 'var(--success)', bg: 'color-mix(in srgb, var(--success) 14%, transparent)' },
  ]
})

async function load() {
  loading.value = true
  try {
    const r = await fetch('/api/v1/sessions')
    const data = await r.json()
    sessions.value = data.sessions || []
  } catch (e) {
    console.error(e)
    sessions.value = []
  } finally {
    loading.value = false
  }
}

function goSession(id: string) {
  if (openSession) openSession(id)
}

async function duplicate(s: Session) {
  try {
    const r = await fetch(`/api/v1/sessions/${s.id}/duplicate`, { method: 'POST' })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    await load()
    if (reloadSessions) reloadSessions()
  } catch (e: any) {
    alert(`复制失败：${e?.message || e}`)
  }
}

function exportMd(s: Session) {
  const a = document.createElement('a')
  a.href = `/api/v1/sessions/${s.id}/export?format=markdown`
  a.download = `${(s.title || s.id).replace(/[\\/:*?"<>|]/g, '_')}.md`
  document.body.appendChild(a)
  a.click()
  a.remove()
}

async function remove(s: Session) {
  if (!confirm(`删除会话「${s.title || s.id}」？此操作不可恢复。`)) return
  try {
    const r = await fetch(`/api/v1/sessions/${s.id}`, { method: 'DELETE' })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    sessions.value = sessions.value.filter((x) => x.id !== s.id)
    if (reloadSessions) reloadSessions()
  } catch (e: any) {
    alert(`删除失败：${e?.message || e}`)
  }
}

onMounted(load)
</script>

<style scoped>
.stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface);
  transition: border-color var(--t-mid), transform var(--t-mid);
}
.stat:hover { border-color: var(--border-strong); transform: translateY(-1px); }

.stat-icon {
  width: 34px;
  height: 34px;
  border-radius: var(--r-sm);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}
.stat-value { font-size: 19px; font-weight: 720; letter-spacing: -0.02em; line-height: 1.2; }
.stat-label { font-size: 11px; color: var(--text3); margin-top: 1px; }

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.tb-search {
  flex: 1;
  min-width: 200px;
  max-width: 380px;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 11px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  background: var(--surface);
  color: var(--text3);
  transition: border-color var(--t-fast), box-shadow var(--t-fast);
}
.tb-search:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }
.tb-search input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text);
  font-size: 12.5px;
}
.tb-clear {
  border: none;
  background: transparent;
  color: var(--text3);
  display: grid;
  place-items: center;
  padding: 2px;
  border-radius: 4px;
}
.tb-clear:hover { color: var(--text); background: var(--surface-alt); }

.sort-group { display: flex; gap: 6px; flex-wrap: wrap; }

.view-toggle {
  display: flex;
  gap: 2px;
  padding: 2px;
  border-radius: var(--r-sm);
  background: var(--surface-alt);
  margin-left: auto;
}
.vt-btn {
  width: 28px;
  height: 26px;
  display: grid;
  place-items: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text3);
  transition: all var(--t-fast);
}
.vt-btn.on { background: var(--surface); color: var(--primary); box-shadow: var(--shadow-sm); }

.group { margin-bottom: 26px; }
.group-title {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text2);
  margin-bottom: 12px;
}
.group-title em {
  font-style: normal;
  font-size: 10px;
  color: var(--text3);
  background: var(--surface-alt);
  border-radius: var(--r-full);
  padding: 1px 7px;
}
.group-line { flex: 1; height: 1px; background: var(--border-light); }

.items { display: grid; gap: 10px; }
.groups.card .items { grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); }
.groups.list .items { grid-template-columns: 1fr; }

.hcard {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface);
  cursor: pointer;
  position: relative;
  transition: border-color var(--t-mid), transform var(--t-mid), box-shadow var(--t-mid);
}
.hcard:hover {
  border-color: color-mix(in srgb, var(--primary) 42%, transparent);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.hcard-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--r-sm);
  background: var(--surface-alt);
  display: grid;
  place-items: center;
  font-size: 14px;
  flex-shrink: 0;
}

.hcard-body { flex: 1; min-width: 0; }
.hcard-top { display: flex; align-items: center; gap: 8px; }
.hcard-title {
  font-size: 13px;
  font-weight: 620;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hcard-preview {
  font-size: 11.5px;
  color: var(--text2);
  line-height: 1.55;
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hcard-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  font-size: 10.5px;
  color: var(--text3);
}
.hcard-meta span { display: flex; align-items: center; gap: 4px; }

.hcard-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity var(--t-fast);
  flex-shrink: 0;
}
.hcard:hover .hcard-actions { opacity: 1; }

.act {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text3);
  transition: all var(--t-fast);
}
.act:hover { background: var(--surface-alt); color: var(--text); }
.act--danger:hover { background: color-mix(in srgb, var(--error) 14%, transparent); color: var(--error); }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 640px) {
  .groups.card .items { grid-template-columns: 1fr; }
  .hcard-actions { opacity: 1; }
  .view-toggle { display: none; }
}
</style>

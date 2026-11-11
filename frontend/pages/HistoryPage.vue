<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <header class="ui-hero hist-hero">
        <div class="ui-hero-main">
          <div class="ui-eyebrow">ARCHIVE</div>
          <h1 class="ui-title">历史记录</h1>
          <p class="ui-sub">所有对话按时间归档，可检索、导出与批量清理。</p>
        </div>
        <div class="ui-head-actions">
          <button class="ui-btn" :disabled="loading" @click="load">
            <RefreshCw :size="14" :class="{ spin: loading }" /> 刷新
          </button>
        </div>
      </header>

      <div class="ui-grid ui-grid--4 hist-stats">
        <div v-for="s in stats" :key="s.label" class="ui-stat hist-stat">
          <div class="hist-stat-head">
            <span class="ui-stat-label">{{ s.label }}</span>
            <span class="hist-stat-icon" :style="{ color: s.color, background: s.bg }">
              <component :is="s.icon" :size="14" />
            </span>
          </div>
          <div class="ui-stat-value">{{ s.value }}</div>
          <div class="ui-stat-hint">
            {{ s.label === '会话总数' ? '全部归档' : s.label === '今日活跃' ? '24 小时内' : s.label === '本周更新' ? '近 7 天' : '已打标' }}
          </div>
        </div>
      </div>

      <div class="ui-toolbar hist-toolbar">
        <div class="hist-searchbox">
          <Search :size="14" class="hist-search-icon" />
          <input v-model="query" class="ui-input hist-search" placeholder="搜索标题或摘要…" />
          <button v-if="query" class="hist-search-clear" title="清空" @click="query = ''">
            <X :size="12" />
          </button>
        </div>

        <div class="ui-seg hist-sort">
          <button
            v-for="opt in sortOptions"
            :key="opt.key"
            :class="['ui-seg-item', { active: sortBy === opt.key }]"
            @click="sortBy = opt.key"
          >{{ opt.label }}</button>
        </div>

        <div class="ui-seg hist-view">
          <button :class="['ui-seg-item', { active: view === 'card' }]" @click="view = 'card'" title="卡片视图">
            <LayoutGrid :size="14" />
          </button>
          <button :class="['ui-seg-item', { active: view === 'list' }]" @click="view = 'list'" title="列表视图">
            <List :size="14" />
          </button>
        </div>
      </div>

      <div v-if="loading" class="hist-skel">
        <div v-for="i in 6" :key="i" class="ui-skeleton hist-skel-item"></div>
      </div>

      <div v-else-if="!groups.length" class="ui-empty">
        <div class="ui-empty-icon">🗂️</div>
        <div class="ui-empty-title">{{ query ? '没有匹配的会话' : '还没有任何会话' }}</div>
        <div class="ui-empty-desc">{{ query ? '换个关键词试试，或清空搜索条件。' : '开始一次对话后，记录会自动出现在这里。' }}</div>
        <button v-if="!query" class="ui-btn ui-btn--primary" @click="createChat">
          <Plus :size="14" /> 新建对话
        </button>
      </div>

      <div v-else class="groups" :class="view">
        <section v-for="g in groups" :key="g.name" class="ui-section hist-group">
          <div class="ui-section-head">
            <div class="hist-group-main">
              <h2 class="ui-section-title">{{ g.name }}</h2>
              <p class="ui-section-sub">{{ g.items.length }} 个会话</p>
            </div>
            <div class="ui-section-actions">
              <span class="ui-badge">{{ g.items.length }} 项</span>
            </div>
          </div>

          <div class="hist-items">
            <article
              v-for="s in g.items"
              :key="s.id"
              class="ui-card ui-card--hover hcard"
              @click="goSession(s.id)"
            >
              <div class="hcard-top">
                <div class="hcard-icon">{{ s.icon || '💬' }}</div>
                <div class="hcard-head">
                  <div class="hcard-title-row">
                    <h3 class="hcard-title">{{ s.title || '新对话' }}</h3>
                    <span v-if="s.tag" class="ui-badge ui-badge--primary">{{ s.tag }}</span>
                  </div>
                  <div class="hcard-meta">
                    <span><Clock :size="11" /> {{ fmtDate(s.updated_at || s.created_at) }}</span>
                    <span><Hash :size="11" /> {{ s.id }}</span>
                  </div>
                </div>
              </div>

              <p class="hcard-preview">{{ cleanPreview(s.preview) || '（暂无内容）' }}</p>

              <div class="hcard-actions" @click.stop>
                <button class="ui-btn ui-btn--sm ui-btn--ghost ui-btn--icon" title="打开" @click="goSession(s.id)">
                  <CornerUpRight :size="14" />
                </button>
                <button class="ui-btn ui-btn--sm ui-btn--ghost ui-btn--icon" title="复制会话" @click="duplicate(s)">
                  <Copy :size="14" />
                </button>
                <button class="ui-btn ui-btn--sm ui-btn--ghost ui-btn--icon" title="导出 Markdown" @click="exportMd(s)">
                  <Download :size="14" />
                </button>
                <button class="ui-btn ui-btn--sm ui-btn--danger ui-btn--icon" title="删除" @click="remove(s)">
                  <Trash2 :size="14" />
                </button>
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
/* ---------- hero / 统计 ---------- */
.hist-hero { margin-bottom: 22px; }

.hist-stats { margin-bottom: 20px; }
.hist-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.hist-stat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.hist-stat-icon {
  width: 28px;
  height: 28px;
  border-radius: var(--r-sm);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}
.hist-stat .ui-stat-head { margin-bottom: 4px; }

/* ---------- 工具条 ---------- */
.hist-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 22px;
}
.hist-searchbox {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1 1 240px;
  min-width: 0;
  max-width: 380px;
}
.hist-search-icon {
  position: absolute;
  left: 12px;
  color: var(--text3);
  pointer-events: none;
}
.hist-search {
  height: 34px;
  padding-left: 34px;
  padding-right: 36px;
}
.hist-search-clear {
  position: absolute;
  right: 6px;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: none;
  border-radius: var(--r-xs);
  background: transparent;
  color: var(--text3);
  transition: color var(--t-fast), background var(--t-fast);
}
.hist-search-clear:hover { color: var(--text); background: var(--surface-alt); }

.hist-sort { flex-wrap: nowrap; }
.hist-view { margin-left: auto; }

/* ---------- 加载 ---------- */
.hist-skel { display: flex; flex-direction: column; gap: 10px; }
.hist-skel-item { height: 92px; }

/* ---------- 分组 / 网格 ---------- */
.hist-group { margin-bottom: 26px; }
.hist-group-main { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.hist-group .ui-section-title { font-size: 14px; }
.hist-group .ui-section-sub { margin: 0; }

.hist-items { display: grid; gap: 12px; }
.groups.card .hist-items { grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); }
.groups.list .hist-items { grid-template-columns: minmax(0, 1fr); }

/* ---------- 档案卡片 ---------- */
.hcard {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 15px 16px;
  cursor: pointer;
}
.hcard-top { display: flex; align-items: flex-start; gap: 10px; }
.hcard-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--r-sm);
  background: var(--surface-alt);
  display: grid;
  place-items: center;
  font-size: 15px;
  flex-shrink: 0;
}
.hcard-head { flex: 1; min-width: 0; }
.hcard-title-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
.hcard-title {
  font-size: 13.5px;
  font-weight: 640;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hcard-title-row .ui-badge { flex-shrink: 0; }
.hcard-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 5px;
  font-size: 10.5px;
  color: var(--text3);
  font-family: var(--font-mono);
}
.hcard-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.hcard-meta span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hcard-preview {
  font-size: 12px;
  color: var(--text2);
  line-height: 1.6;
  min-height: 38px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hcard-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.hcard-actions .ui-btn { opacity: 0.55; }
.hcard:hover .hcard-actions .ui-btn { opacity: 1; }
.hcard-actions .ui-btn--danger { margin-left: auto; }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ---------- 移动端 ---------- */
@media (max-width: 767px) {
  .hist-hero { margin-bottom: 16px; }
  .hist-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hist-stat { padding: 12px 12px 10px; }
  .hist-stat .ui-stat-value { font-size: 20px; }

  .hist-toolbar { gap: 8px; margin-bottom: 16px; }
  .hist-searchbox { flex: 1 1 100%; max-width: none; }
  .hist-sort {
    flex: 1 1 100%;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .hist-sort::-webkit-scrollbar { display: none; }
  .hist-sort .ui-seg-item { flex-shrink: 0; }
  .hist-view { margin-left: 0; width: auto; flex: 0 0 auto; }

  .hist-group { margin-bottom: 20px; }
  .hist-items,
  .groups.card .hist-items,
  .groups.list .hist-items { grid-template-columns: minmax(0, 1fr); }
  .hcard { padding: 13px 14px; }
  .hcard-actions .ui-btn { opacity: 1; }
  .hcard-preview { -webkit-line-clamp: 3; line-clamp: 3; }
}
</style>

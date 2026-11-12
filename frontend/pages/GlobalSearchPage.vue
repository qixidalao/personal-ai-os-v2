<template>
  <div class="ui-page">
    <div class="ui-page-inner search-wrap">
      <header class="ui-hero search-hero">
        <div class="ui-hero-main">
          <div class="ui-eyebrow">COMMAND SEARCH</div>
          <h1 class="ui-title">全局搜索</h1>
          <p class="ui-sub">在所有对话的标题与消息正文中检索，命中内容会高亮显示，点击可直接跳回对应会话。</p>
        </div>
        <div class="ui-head-actions">
          <span v-if="indexed" class="ui-badge">已索引 {{ indexed }} 个会话 · {{ messagesIndexed }} 条消息</span>
        </div>
      </header>

      <div class="cmd-search">
        <Search :size="20" class="cmd-search-icon" />
        <input
          ref="inputRef"
          v-model="query"
          class="ui-input cmd-search-input"
          placeholder="输入关键词，回车搜索…"
          @keydown.enter="run"
        />
        <button v-if="query" class="cmd-clear" title="清空" @click="clear">
          <X :size="14" />
        </button>
        <button class="ui-btn ui-btn--primary cmd-go" :disabled="searching || !query.trim()" @click="run">
          {{ searching ? '搜索中…' : '搜索' }}
        </button>
      </div>

      <div class="cmd-meta">
        <div class="ui-seg cmd-scope">
          <button
            v-for="f in filters"
            :key="f.key"
            :class="['ui-seg-item', { active: scope === f.key }]"
            @click="scope = f.key; run()"
          >{{ f.label }}</button>
        </div>
        <span class="cmd-tip"><span class="ui-kbd">↵</span> 回车直接搜索 · 结果按会话归档</span>
      </div>

      <section v-if="history.length && !hasSearched" class="ui-section cmd-recent">
        <div class="ui-section-head">
          <div>
            <h2 class="ui-section-title">最近搜索</h2>
            <p class="ui-section-sub">点击即可再次检索</p>
          </div>
          <div class="ui-section-actions">
            <button class="ui-btn ui-btn--ghost ui-btn--sm" @click="clearHistory">清空</button>
          </div>
        </div>
        <div class="cmd-chips">
          <button v-for="h in history" :key="h" class="ui-chip" @click="query = h; run()">
            <History :size="12" /> {{ h }}
          </button>
        </div>
      </section>

      <div v-if="searching" class="results">
        <div v-for="i in 3" :key="i" class="ui-skeleton cmd-skel"></div>
      </div>

      <div v-else-if="hasSearched && !groups.length" class="ui-empty cmd-empty">
        <div class="ui-empty-icon">🔍</div>
        <div class="ui-empty-title">没有找到「{{ lastQuery }}」</div>
        <div class="ui-empty-desc">试试更短的关键词，或切换到「全部」范围再搜一次。</div>
      </div>

      <div v-else-if="groups.length" class="results">
        <div class="result-count">
          <span class="ui-badge ui-badge--primary">共 {{ totalHits }} 条命中</span>
          <span>分布在 {{ groups.length }} 个会话</span>
        </div>

        <section v-for="g in groups" :key="g.session.id" class="ui-card rgroup">
          <button class="rgroup-hd" @click="openSession(g.session.id)">
            <span class="rgroup-icon">{{ g.session.icon || '💬' }}</span>
            <span class="rgroup-title">{{ g.session.title || '新对话' }}</span>
            <span class="ui-badge">{{ g.hits.length }} 条命中</span>
            <CornerUpRight :size="13" class="rgroup-go" />
          </button>

          <div class="rhits">
            <button v-for="(hit, i) in g.hits" :key="i" class="rhit" @click="openSession(g.session.id)">
              <span :class="['rhit-role', hit.role]">{{ hit.role === 'user' ? '你' : 'AI' }}</span>
              <span class="rhit-text" v-html="highlight(hit.snippet)"></span>
            </button>
          </div>
        </section>
      </div>

      <div v-else class="ui-empty cmd-empty">
        <div class="ui-empty-icon">🧭</div>
        <div class="ui-empty-title">搜点什么吧</div>
        <div class="ui-empty-desc">例如工具名、项目名、某段代码片段，都会在历史对话里被找出来。</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, inject, nextTick } from 'vue'
import { Search, X, History, CornerUpRight } from 'lucide-vue-next'

const openSession = inject<any>('openSession', null)

interface Hit { role: string; snippet: string }
interface Group { session: any; hits: Hit[] }

const query = ref('')
const lastQuery = ref('')
const scope = ref<'all' | 'title' | 'content'>('all')
const searching = ref(false)
const hasSearched = ref(false)
const groups = ref<Group[]>([])
const indexed = ref(0)
const messagesIndexed = ref(0)
const history = ref<string[]>([])
const inputRef = ref<HTMLInputElement>()

const filters = [
  { key: 'all', label: '全部' },
  { key: 'title', label: '仅标题' },
  { key: 'content', label: '仅内容' },
] as const

const totalHits = computed(() => groups.value.reduce((n, g) => n + g.hits.length, 0))

function loadHistory() {
  try {
    history.value = JSON.parse(localStorage.getItem('aios:search:history') || '[]')
  } catch { history.value = [] }
}

function pushHistory(q: string) {
  const list = [q, ...history.value.filter((x) => x !== q)].slice(0, 8)
  history.value = list
  localStorage.setItem('aios:search:history', JSON.stringify(list))
}

function clearHistory() {
  history.value = []
  localStorage.removeItem('aios:search:history')
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string))
}

function highlight(text: string) {
  const q = lastQuery.value.trim()
  const safe = escapeHtml(text)
  if (!q) return safe
  const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return safe.replace(re, '<mark>$1</mark>')
}

function snippetOf(content: string, q: string) {
  const idx = content.toLowerCase().indexOf(q.toLowerCase())
  if (idx < 0) return content.slice(0, 140)
  const start = Math.max(0, idx - 50)
  const end = Math.min(content.length, idx + q.length + 90)
  return (start > 0 ? '…' : '') + content.slice(start, end) + (end < content.length ? '…' : '')
}

async function run() {
  const q = query.value.trim()
  if (!q) return
  lastQuery.value = q
  searching.value = true
  hasSearched.value = true
  groups.value = []
  pushHistory(q)

  try {
    const listRes = await fetch('/api/v1/sessions')
    const listData = await listRes.json()
    const sessions: any[] = listData.sessions || []
    indexed.value = sessions.length

    const targets = sessions.slice(0, 40)
    const details = await Promise.all(
      targets.map(async (s) => {
        try {
          const r = await fetch(`/api/v1/sessions/${s.id}`)
          const d = await r.json()
          return { session: s, messages: d.session?.messages || [] }
        } catch {
          return { session: s, messages: [] }
        }
      }),
    )

    let msgCount = 0
    const found: Group[] = []
    const lower = q.toLowerCase()

    for (const { session, messages } of details) {
      msgCount += messages.length
      const hits: Hit[] = []

      if (scope.value !== 'content' && (session.title || '').toLowerCase().includes(lower)) {
        hits.push({ role: 'title', snippet: session.title })
      }

      if (scope.value !== 'title') {
        for (const m of messages) {
          const content = String(m.content || '')
          if (!content) continue
          if (content.toLowerCase().includes(lower)) {
            hits.push({ role: m.role, snippet: snippetOf(content, q) })
            if (hits.length >= 6) break
          }
        }
      }

      if (hits.length) found.push({ session, hits })
    }

    messagesIndexed.value = msgCount
    groups.value = found
  } catch (e) {
    console.error(e)
    groups.value = []
  } finally {
    searching.value = false
  }
}

function clear() {
  query.value = ''
  groups.value = []
  hasSearched.value = false
  nextTick(() => inputRef.value?.focus())
}

onMounted(() => {
  loadHistory()
  nextTick(() => inputRef.value?.focus())
})
</script>

<style scoped>
/* ---------- 布局 ---------- */
.search-wrap { max-width: 900px; }
.search-hero { margin-bottom: 24px; }

/* ---------- 命令式搜索台 ---------- */
.cmd-search {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 8px 8px 18px;
  border: 1px solid var(--border-strong);
  border-radius: var(--r-lg);
  background:
    var(--grad-surface),
    var(--surface);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--t-mid), box-shadow var(--t-mid);
}
.cmd-search:focus-within {
  border-color: var(--primary);
  box-shadow: var(--shadow-glow);
}
.cmd-search-icon { color: var(--text3); flex-shrink: 0; }
.cmd-search-input,
.cmd-search-input:focus {
  flex: 1;
  width: auto;
  min-width: 0;
  height: 42px;
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
  font-size: 15px;
  letter-spacing: -0.01em;
}
.cmd-clear {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  border: none;
  border-radius: var(--r-full);
  background: var(--surface-alt);
  color: var(--text3);
  transition: color var(--t-fast), background var(--t-fast);
}
.cmd-clear:hover { color: var(--text); background: var(--surface-3); }
.cmd-go {
  height: 40px;
  padding: 0 20px;
  border-radius: var(--r-sm);
  flex-shrink: 0;
}
.cmd-go:disabled { box-shadow: none; }

.cmd-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin: 16px 0 24px;
}
.cmd-scope { flex-wrap: nowrap; }
.cmd-tip {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text3);
}

/* ---------- 最近搜索 ---------- */
.cmd-recent { margin-bottom: 26px; }
.cmd-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.cmd-chips .ui-chip { height: 28px; }

/* ---------- 加载 / 空态 ---------- */
.cmd-skel { height: 96px; margin-bottom: 10px; }
.cmd-empty { padding-top: 64px; }

/* ---------- 结果 ---------- */
.results { animation: results-in 220ms var(--ease); }
@keyframes results-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
}
.result-count {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11.5px;
  color: var(--text3);
  margin-bottom: 14px;
}

.rgroup {
  padding: 0;
  overflow: hidden;
  margin-bottom: 12px;
}
.rgroup-hd {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 13px 15px;
  border: none;
  border-bottom: 1px solid var(--border-light);
  background: transparent;
  text-align: left;
  transition: background var(--t-fast);
}
.rgroup-hd:hover { background: var(--surface-alt); }
.rgroup-icon { font-size: 14px; flex-shrink: 0; }
.rgroup-title {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 640;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rgroup-go { color: var(--text3); flex-shrink: 0; }

.rhits { display: flex; flex-direction: column; }
.rhit {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 15px;
  border: none;
  border-bottom: 1px solid var(--border-light);
  background: transparent;
  text-align: left;
  transition: background var(--t-fast);
}
.rhit:last-child { border-bottom: none; }
.rhit:hover { background: var(--primary-soft); }
.rhit-role {
  flex-shrink: 0;
  margin-top: 2px;
  font-size: 9.5px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: var(--r-full);
  background: var(--surface-alt);
  color: var(--text3);
}
.rhit-role.user { background: var(--primary-soft); color: var(--primary); }
.rhit-role.title { background: var(--accent-soft); color: var(--accent); }
.rhit-text {
  font-size: 12px;
  line-height: 1.7;
  color: var(--text2);
  word-break: break-word;
}
.rhit-text :deep(mark) {
  background: color-mix(in srgb, var(--warn) 34%, transparent);
  color: var(--text);
  border-radius: 3px;
  padding: 0 2px;
}

/* ---------- 移动端 ---------- */
@media (max-width: 767px) {
  .search-hero { margin-bottom: 16px; }
  .cmd-search {
    padding: 6px 6px 6px 14px;
    gap: 8px;
    border-radius: var(--r-md);
  }
  .cmd-search-input,
  .cmd-search-input:focus { height: 40px; font-size: 14px; }
  .cmd-go { height: 38px; padding: 0 14px; }
  .cmd-meta { margin: 12px 0 18px; gap: 8px; }
  .cmd-tip { display: none; }
  .cmd-scope { flex: 1 1 100%; overflow-x: auto; scrollbar-width: none; }
  .cmd-scope::-webkit-scrollbar { display: none; }
  .cmd-scope .ui-seg-item { flex-shrink: 0; }
  .cmd-chips .ui-chip { height: 32px; }
  .rgroup-hd { padding: 11px 12px; }
  .rhit { padding: 10px 12px; gap: 8px; }
}
</style>

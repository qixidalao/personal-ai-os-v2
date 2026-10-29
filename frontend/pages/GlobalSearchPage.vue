<template>
  <div class="ui-page">
    <div class="ui-page-inner search-wrap">
      <header class="ui-head">
        <div>
          <div class="ui-eyebrow">Universal Search</div>
          <h1 class="ui-title">全局搜索</h1>
          <p class="ui-sub">在所有对话的标题与消息正文中检索，命中内容会高亮显示，点击可直接跳回对应会话。</p>
        </div>
      </header>

      <div class="search-box">
        <Search :size="18" class="sb-icon" />
        <input
          ref="inputRef"
          v-model="query"
          class="sb-input"
          placeholder="输入关键词，回车搜索…"
          @keydown.enter="run"
        />
        <button v-if="query" class="sb-clear" @click="clear"><X :size="14" /></button>
        <button class="sb-go" :disabled="searching || !query.trim()" @click="run">
          {{ searching ? '搜索中…' : '搜索' }}
        </button>
      </div>

      <div class="filters">
        <button
          v-for="f in filters"
          :key="f.key"
          :class="['ui-chip', { active: scope === f.key }]"
          @click="scope = f.key; run()"
        >{{ f.label }}</button>
        <span class="filters-hint" v-if="indexed">
          已索引 {{ indexed }} 个会话 · {{ messagesIndexed }} 条消息
        </span>
      </div>

      <div v-if="history.length && !hasSearched" class="recent">
        <div class="recent-hd">
          <span>最近搜索</span>
          <button class="link" @click="clearHistory">清空</button>
        </div>
        <div class="recent-list">
          <button v-for="h in history" :key="h" class="recent-item" @click="query = h; run()">
            <History :size="12" /> {{ h }}
          </button>
        </div>
      </div>

      <div v-if="searching" class="results">
        <div v-for="i in 3" :key="i" class="ui-skeleton" style="height: 92px; margin-bottom: 10px"></div>
      </div>

      <div v-else-if="hasSearched && !groups.length" class="ui-empty">
        <div class="ui-empty-icon">🔍</div>
        <div class="ui-empty-title">没有找到「{{ lastQuery }}」</div>
        <div class="ui-empty-desc">试试更短的关键词，或切换到「全部」范围再搜一次。</div>
      </div>

      <div v-else-if="groups.length" class="results">
        <div class="result-count">共 {{ totalHits }} 条命中，分布在 {{ groups.length }} 个会话</div>

        <section v-for="g in groups" :key="g.session.id" class="rgroup">
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

      <div v-else class="ui-empty">
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
    history.value = JSON.parse(localStorage.getItem('hhs:search:history') || '[]')
  } catch { history.value = [] }
}

function pushHistory(q: string) {
  const list = [q, ...history.value.filter((x) => x !== q)].slice(0, 8)
  history.value = list
  localStorage.setItem('hhs:search:history', JSON.stringify(list))
}

function clearHistory() {
  history.value = []
  localStorage.removeItem('hhs:search:history')
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
.search-wrap { max-width: 900px; }

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 52px;
  padding: 0 8px 0 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-lg);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--t-fast), box-shadow var(--t-fast);
}
.search-box:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 4px var(--primary-soft), var(--shadow-md);
}
.sb-icon { color: var(--text3); flex-shrink: 0; }
.sb-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text);
  font-size: 15px;
  letter-spacing: -0.01em;
}
.sb-input::placeholder { color: var(--text3); }
.sb-clear {
  width: 26px; height: 26px;
  display: grid; place-items: center;
  border: none; border-radius: 50%;
  background: var(--surface-alt);
  color: var(--text3);
}
.sb-clear:hover { color: var(--text); }
.sb-go {
  height: 36px;
  padding: 0 16px;
  border: none;
  border-radius: var(--r-sm);
  background: var(--grad-primary);
  color: #fff;
  font-size: 12.5px;
  font-weight: 620;
  box-shadow: 0 2px 10px var(--primary-glow);
}
.sb-go:disabled { opacity: 0.45; cursor: not-allowed; box-shadow: none; }

.filters {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  margin: 16px 0 18px;
}
.filters-hint { font-size: 10.5px; color: var(--text3); margin-left: auto; }

.recent { margin-bottom: 20px; }
.recent-hd {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 11px;
  font-weight: 650;
  color: var(--text3);
  margin-bottom: 9px;
}
.link { border: none; background: transparent; color: var(--text3); font-size: 11px; }
.link:hover { color: var(--error); }
.recent-list { display: flex; gap: 7px; flex-wrap: wrap; }
.recent-item {
  display: inline-flex; align-items: center; gap: 5px;
  height: 27px; padding: 0 11px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-full);
  background: var(--surface);
  color: var(--text2);
  font-size: 11.5px;
  transition: all var(--t-fast);
}
.recent-item:hover { color: var(--primary); border-color: var(--primary); }

.result-count { font-size: 11.5px; color: var(--text3); margin-bottom: 14px; }

.rgroup {
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface);
  overflow: hidden;
  margin-bottom: 12px;
}
.rgroup-hd {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 14px;
  border: none;
  border-bottom: 1px solid var(--border-light);
  background: var(--surface-2);
  text-align: left;
  transition: background var(--t-fast);
}
.rgroup-hd:hover { background: var(--surface-alt); }
.rgroup-icon { font-size: 13px; }
.rgroup-title {
  flex: 1;
  font-size: 12.5px;
  font-weight: 640;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rgroup-go { color: var(--text3); }

.rhits { display: flex; flex-direction: column; }
.rhit {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border: none;
  background: transparent;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  transition: background var(--t-fast);
}
.rhit:last-child { border-bottom: none; }
.rhit:hover { background: var(--primary-soft); }
.rhit-role {
  flex-shrink: 0;
  font-size: 9.5px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: var(--r-full);
  background: var(--surface-alt);
  color: var(--text3);
  margin-top: 2px;
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
</style>

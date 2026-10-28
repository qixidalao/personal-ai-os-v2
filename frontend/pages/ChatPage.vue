<template>
  <div class="chat-page">
    <div class="chat-msgs" ref="msgBox" @scroll.passive="onChatScroll">
      <div v-if="allMsgs.length === 0" class="chat-empty">
        <div class="chat-empty__icon">🧠</div>
        <div class="chat-empty__title">Personal AI OS</div>
        <div class="chat-empty__hint">V2.0 · 思考流 / 工具流收纳盒 · 移动端优先</div>
        <div class="chat-chips">
          <button class="chat-chip" v-for="c in suggestions" :key="c" @click="handleSend(c)">{{ c }}</button>
        </div>
      </div>

      <div v-if="displayLimit > 0 && allMsgs.length > displayLimit" class="chat-load-more" @click="loadMore">
        ↑ 加载更早的消息（共 {{ allMsgs.length }} 条，已加载 {{ Math.min(displayLimit, allMsgs.length) }} 条）
      </div>

      <template v-for="m in msgs" :key="m.id">
        <div v-if="m.toolCall" :class="['tool-card', { expanded: m.toolExpanded }]" @click="m.toolExpanded = !m.toolExpanded">
          <div class="tool-card__header">
            <span class="tool-card__icon">🔧</span>
            <span class="tool-card__name">{{ m.toolCall.name }}</span>
            <span v-if="m.toolCall.running" class="tool-card__status">执行中...</span>
            <span v-else class="tool-card__status done">✓ 完成</span>
            <span class="tool-card__arrow">{{ m.toolExpanded ? '▾' : '▸' }}</span>
          </div>
          <div v-if="m.toolExpanded" class="tool-card__body">
            <div class="tool-card__section">
              <div class="tool-card__label">入参 (Input)</div>
              <pre class="tool-card__code">{{ JSON.stringify(m.toolCall.args, null, 2) }}</pre>
            </div>
            <div class="tool-card__section">
              <div class="tool-card__label">返回 (Output)</div>
              <pre class="tool-card__code">{{ m.toolCall.result || '(执行中...)' }}</pre>
              <button v-if="hasSpill(m.toolCall.result || '') && !m.toolCall.spillFull" class="spill-btn" @click.stop="loadSpillFull(m.toolCall)">
                {{ m.toolCall.spillLoading ? '加载中...' : '📄 查看完整结果' }}
              </button>
              <pre v-if="m.toolCall.spillFull" class="tool-card__code spill-full">{{ m.toolCall.spillFull }}</pre>
            </div>
          </div>
        </div>

        <div :class="['msg', m.role === 'user' ? 'msg--user' : 'msg--ai']">
          <div class="msg__avatar">{{ m.role === 'user' ? '👤' : '🤖' }}</div>
          <div class="msg__body">
            <template v-if="m.role === 'ai' && m.segments?.length">
              <template v-for="(seg, si) in m.segments" :key="seg.id || si">
                <div v-if="seg.type === 'reasoning'" :data-seg-id="seg.id" class="trace-box trace-seg think-seg">
                  <button class="trace-head" @click="toggleSegment(m, seg)">
                    <span class="trace-title">{{ seg.expanded ? '▾' : '▸' }} 🧠 思考流</span>
                    <span class="trace-pill think">{{ seg.active ? '思考中' : '已完成' }}</span>
                    <span v-if="seg.durationMs" class="trace-pill think-time">⏱ {{ fmtDur(seg.durationMs) }}</span>
                  </button>
                  <Transition name="trace-slide">
                    <div v-if="seg.expanded" class="trace-body"><div v-if="seg.active && m.streaming" class="trace-reason trace-reason--parts"><div v-for="(part, i) in seg.renderedParts" :key="i" class="msg__text-part" v-html="part"></div><span v-if="seg.pending" class="msg__text-pending" :class="{ 'no-fade': seg.noFade }" v-html="_renderInline(seg.pending)"></span></div><div v-else class="trace-reason" v-html="renderMarkdownCached(seg)"></div></div>
                  </Transition>
                </div>
                <div v-else-if="seg.type === 'tool'" :data-seg-id="seg.id" class="trace-box trace-seg tool-seg">
                  <button class="trace-head" @click="toggleSegment(m, seg)">
                    <span class="trace-title">{{ seg.expanded ? '▾' : '▸' }} 🔧 工具流</span>
                    <span class="trace-pill tool">{{ seg.tools?.length || 0 }} 次调用</span>
                    <span v-if="seg.active" class="trace-live">执行中</span>
                  </button>
                  <Transition name="trace-slide">
                    <div v-if="seg.expanded" class="trace-body">
                    <div class="trace-tools-list">
                      <div v-for="(t, ti) in seg.tools" :key="t.id || ti" :data-tool-id="t.id" :class="['trace-tool', { open: t.expanded }]">
                        <button class="trace-tool__head" @click.stop="toggleToolEntry(t)">
                          <span class="trace-tool__arrow">{{ t.expanded ? '▾' : '▸' }}</span>
                          <span class="trace-tool__name">{{ toolTitle(t) }}</span>
                          <span class="trace-tool__summary">{{ toolSummary(t) }}</span>
                          <span :class="['trace-tool__state', t.running ? 'running' : (t.ok === false ? 'bad' : 'ok')]">{{ t.running ? '执行中' : (t.ok === false ? '失败' : '完成') }}</span>
                          <span v-if="typeof t.durationMs === 'number'" class="trace-tool__time">{{ t.durationMs }}ms</span>
                        </button>
                        <div v-if="t.expanded" class="trace-tool__body">
                          <div class="trace-mini-title">入参</div><pre class="trace-code">{{ formatJson(t.args) }}</pre>
                          <div class="trace-mini-title">输出</div>
                          <div v-if="t.name === 'web_search' && webSearchResults(t.result).length" class="trace-search-results">
                            <a v-for="(result, ri) in webSearchResults(t.result)" :key="ri" :href="result.url" target="_blank" rel="noopener noreferrer" class="trace-search-card">
                              <strong>{{ result.title || result.url }}</strong><span>{{ result.snippet }}</span><small>{{ result.host }} ↗</small>
                            </a>
                          </div>
                          <pre v-else class="trace-code">{{ t.running ? '(执行中...)' : (t.result || t.error || '(空)') }}</pre>
                          <button v-if="hasSpill(t.result || '') && !t.spillFull" class="spill-btn" @click.stop="loadSpillFull(t)">
                            {{ t.spillLoading ? '加载中...' : '📄 查看完整结果' }}
                          </button>
                          <pre v-if="t.spillFull" class="trace-code spill-full">{{ t.spillFull }}</pre>
                        </div>
                      </div>
                    </div>
                    </div>
                  </Transition>
                </div>
                <figure v-else-if="seg.type === 'media' && seg.media" class="msg-media">
                  <a :href="mediaUrl(seg.media.url)" target="_blank" rel="noopener"><img :src="mediaUrl(seg.media.url)" :alt="seg.media.caption || seg.media.name || 'AI 图片'" loading="lazy" /></a>
                  <figcaption v-if="seg.media.caption">{{ seg.media.caption }}</figcaption>
                </figure>
                <div v-else class="msg__bubble">
                  <div v-if="seg.active && m.streaming" class="msg__text msg__text--parts"><div v-for="(part, i) in seg.renderedParts" :key="i" class="msg__text-part" v-html="part"></div><span v-if="seg.pending" class="msg__text-pending" :class="{ 'no-fade': seg.noFade }" v-html="_renderInline(seg.pending)"></span></div>
                  <div v-else class="msg__text" v-html="renderMarkdownCached(seg)"></div>
                  <span v-if="m.streaming && si === m.segments.length - 1" class="msg__cursor"></span>
                </div>
              </template>
            </template>
            <div v-else class="msg__bubble">
              <div class="msg__text" v-html="renderMarkdownCached({ id: m.id, content: m.content } as any)"></div>
              <span v-if="m.streaming" class="msg__cursor"></span>
            </div>
            <div v-if="!m.streaming" class="msg__actions">
              <button class="msg__act" @click="copyMsg(m, $event)" title="复制">📋</button>
              <button class="msg__act" @click="deleteMsg(m)" title="删除此后所有消息">🗑️</button>
              <button v-if="m.role === 'ai'" class="msg__act" @click="retryMsg(m)" title="重试">🔄</button>
              <button v-if="m.role === 'user'" class="msg__act" @click="editMsg(m)" title="编辑">✏️</button>
            </div>
            <div v-if="!m.streaming && (m.usage || m.createdAt || m.finishedAt)" class="msg__meta">
              <span v-if="m.cumTokens != null" class="msg__meta-tokens">⚡ 上下文 {{ m.cumTokens }} tok</span>
              <span v-if="m.tokPerSec" class="msg__meta-speed">⚡ {{ m.tokPerSec }} tok/s</span>
              <span v-if="m.cachedTokens" class="msg__meta-cached">⚡ 缓存 {{ m.cachedTokens }}</span>
              <span v-if="m.finishedAt" class="msg__meta-elapsed">⏱ {{ fmtElapsed(m.createdAt, m.finishedAt) }}</span>
              <span v-if="m.finishedAt" class="msg__meta-time">🕒 {{ formatTime(m.finishedAt) }}</span>
            </div>
            <div v-if="m.branches && m.branches.length > 1" class="msg__branch">
              <span class="msg__branch-hint">分支 &lt;{{ (m.branchIdx || 0) + 1 }}/{{ m.branches.length }}&gt;</span>
              <span class="msg__branch-nav">
                <button :disabled="(m.branchIdx || 0) === 0" @click="prevBranch(m)">‹</button>
                <button :disabled="(m.branchIdx || 0) >= m.branches.length - 1" @click="nextBranch(m)">›</button>
              </span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <div class="chat-input-wrap">
      <div v-if="attachments.length" class="chat-files">
        <div v-for="(f, i) in attachments" :key="i" class="chat-file">
          <span>{{ f.name }}</span>
          <button class="chat-file__rm" @click="attachments.splice(i, 1)">✕</button>
        </div>
      </div>
      <div class="chat-input-area">
        <div v-if="editingMsg" class="chat-edit-bar">
          <span class="chat-edit-hint">✏️ 编辑中</span>
          <button class="chat-edit-cancel" @click="cancelEdit">取消</button>
        </div>
        <div class="chat-input-row">
          <textarea ref="inputRef" v-model="input" class="chat-input" placeholder="输入消息... / 斜杠命令" rows="1" @keydown="handleKey" @input="autoSize" @paste="handlePaste" />
          <button v-if="!loading" :class="['chat-send', { disabled: !input.trim() }]" @click="handleSend()"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22 11 13 2 9Z"/></svg></button>
          <button v-else class="chat-send stop" @click="stopGen" title="停止生成"><svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg></button>
        </div>
      </div>
      <div class="chat-hints">
        <span class="chat-hint">{{ isMobile ? '移动端 Enter 换行 · 🚀 发送' : 'Enter 发送 · Shift+Enter 换行' }}</span>
        <span class="chat-hint" v-if="currentModel">模型：{{ currentModel }}</span>
        <span v-if="apiError" class="chat-hint err">{{ apiError }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, inject, watch, onMounted, onUnmounted, computed } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/common'
import katex from 'katex'
import 'katex/dist/katex.min.css'

marked.use({ gfm: true, breaks: true })
interface ChatMedia { kind: 'aios.image'; media_id: string; url: string; name?: string; mime?: string; size?: number; caption?: string }
interface ChatSegment { id: string; type: 'reasoning' | 'tool' | 'text' | 'media'; content?: string; tools?: TraceTool[]; media?: ChatMedia; expanded?: boolean; active?: boolean; userToggled?: boolean; renderedParts?: string[]; pending?: string; startedAt?: number; durationMs?: number; noFade?: boolean }
type Role = 'user' | 'ai'
interface ToolCall { name: string; args: any; result?: string; running?: boolean; spillFull?: string; spillLoading?: boolean }
interface TraceTool { id?: string; round?: number; name: string; args?: any; result?: string; ok?: boolean; error?: string; durationMs?: number; expanded?: boolean; running?: boolean; userToggled?: boolean; spillFull?: string; spillLoading?: boolean }
interface Message {
  id: string; role: Role; content: string; streaming?: boolean
  branches?: string[]; branchIdx?: number; toolCall?: ToolCall; toolExpanded?: boolean
  reasoning?: string; tools?: TraceTool[]; traceExpanded?: boolean; reasoningExpanded?: boolean; toolsExpanded?: boolean; segments?: ChatSegment[]
  usage?: any; createdAt?: number; finishedAt?: number; tokPerSec?: number; cachedTokens?: number; cumTokens?: number
}
interface MathBlock { placeholder: string; html: string }

const sessionId = inject('sessionId') as any
const getMessages = inject('getMessages') as () => any[]
const setMessages = inject('setMessages') as (msgs: any[]) => void
const currentModel = inject('currentModel') as any
const updateSessionTitle = inject('updateSessionTitle') as (id: string, title: string) => void
const sessions = inject('sessions') as any

const titleUpdated = ref(false)
const allMsgs = ref<Message[]>([])
const displayLimit = ref(30)
const shouldScrollAfterLimitChange = ref(false)
const msgs = computed(() => displayLimit.value === 0 ? allMsgs.value : allMsgs.value.slice(Math.max(0, allMsgs.value.length - displayLimit.value)))
const input = ref('')
const loading = ref(false)
const abortRef = ref<AbortController | null>(null)
const streamIntervalRef = ref<number | null>(null)
const apiError = ref('')
const editingMsg = ref<Message | null>(null)
const attachments = ref<{ name: string; data: any }[]>([])
const inputRef = ref<HTMLTextAreaElement>()
const msgBox = ref<HTMLElement>()
const isMobile = computed(() => window.innerWidth < 768)
const suggestions = ['💬 你是谁？', '🔧 系统状态', '📊 有什么 API', '🚀 /help 帮助']
const API = window.location.origin

function mediaUrl(url: string): string { return url.startsWith('/') ? `${API}${url}` : url }
function escapeHtml(value: string): string { return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;') }
function sanitizeHtml(html: string): string {
  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, 'text/html')
  doc.querySelectorAll('script, iframe, object, embed, link, meta').forEach(n => n.remove())
  doc.querySelectorAll('*').forEach(el => {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase(); const value = attr.value.trim().toLowerCase()
      if (name.startsWith('on') || value.startsWith('javascript:')) el.removeAttribute(attr.name)
    }
  })
  // 参考工具流卡片方案：正文 markdown 表格包一层圆角容器，超宽时卡片内滚动，避免视觉截断
  doc.querySelectorAll('.markdown-table').forEach(w => w.replaceWith(...Array.from(w.childNodes)))
  doc.querySelectorAll('table:not(.npc-card)').forEach((tbl) => {
    const wrap = doc.createElement('div')
    wrap.className = 'markdown-table'
    const parent = tbl.parentNode
    if (parent) { parent.insertBefore(wrap, tbl); wrap.appendChild(tbl) }
  })
  return doc.body.firstElementChild?.innerHTML || ''
}
function codeRender(text: string, lang = ''): string {
  const language = lang && hljs.getLanguage(lang) ? lang : ''
  let highlighted: string
  try { highlighted = language ? hljs.highlight(text, { language }).value : hljs.highlightAuto(text).value } catch { highlighted = escapeHtml(text) }
  const data = encodeURIComponent(text); const langText = escapeHtml(language || 'text')
  return `<pre class="code-block" data-lang="${langText}"><code class="hljs${language ? ` language-${escapeHtml(language)}` : ''}">${highlighted}</code><button type="button" class="code-copy" data-code="${data}" title="复制代码">📋</button></pre>`
}
function renderKatex(src: string, displayMode: boolean): string { try { return katex.renderToString(src, { displayMode, throwOnError: false, strict: false, output: 'html' }) } catch (e: any) { return `<span class="katex-err">${escapeHtml(e?.message || src)}</span>` } }
function extractMath(src: string): { text: string; blocks: MathBlock[] } {
  const blocks: MathBlock[] = []
  let text = src.replace(/\$\$([\s\S]+?)\$\$/g, (_, body) => { const placeholder = `@@MATH_${blocks.length}@@`; blocks.push({ placeholder, html: renderKatex(String(body).trim(), true) }); return placeholder })
  text = text.replace(/(^|[^\\$])\$([^\n$]+?)\$/g, (_, prefix, body) => { const placeholder = `@@MATH_${blocks.length}@@`; blocks.push({ placeholder, html: renderKatex(String(body).trim(), false) }); return `${prefix}${placeholder}` })
  return { text, blocks }
}
const NPC_CARD_LABELS = ['姓名/修为','时间/地点','心境/气质','羁绊/情欲','胸部/乳汁','小穴/淫汁','后庭/状态','身体/服装','性欲/高潮']
function renderNpcCards(src: string): string {
  return src.replace(/\[人物卡:([^\]]+)\]\s*([^\n]*)/g, (full, nameRaw, dataRaw) => {
    const name = escapeHtml(String(nameRaw).trim())
    const data = String(dataRaw).trim()
    if (!data) return `<table class="npc-card"><caption>${name}</caption><tbody><tr><td>—</td></tr></tbody></table>`
    const parts = data.split('|').map(s => s.trim())
    const rows = parts.map((p, i) => {
      const label = NPC_CARD_LABELS[i] || `字段${i + 1}`
      return `<tr><td><strong>${escapeHtml(label)}</strong></td><td>${escapeHtml(p)}</td></tr>`
    }).join('')
    return `\n<table class="npc-card"><caption>🧊 ${name}</caption><thead><tr><th>维度</th><th>实时数据</th></tr></thead><tbody>${rows}</tbody></table>\n`
  })
}
const _mdCache = new Map<string, string>()
let _mdCacheSeq = 0
function renderMarkdown(text: string): string {
  if (!text) return ''
  const cached = _mdCache.get(text)
  if (cached !== undefined) return cached
  if (_mdCache.size > 64) { _mdCache.clear() }
  const fences: string[] = []
  const withoutFences = text.replace(/```([\w-]*)\s*\n([\s\S]*?)```/g, (full) => { const key = `@@FENCE_${fences.length}@@`; fences.push(full); return key })
  const { text: mathText, blocks: mathBlocks } = extractMath(withoutFences)
  let source = mathText.replace(/@@FENCE_(\d+)@@/g, (_, idx) => fences[Number(idx)] || '')
  source = source.replace(/```mermaid\s*\n([\s\S]*?)```/gi, (_, code) => `<div class="mermaid-wrap" data-mermaid="${encodeURIComponent(String(code).trim())}"><div class="mermaid-loading">🔄 渲染中...</div></div>`)
  source = source.replace(/```([\w-]*)\s*\n([\s\S]*?)```/g, (_, lang, code) => codeRender(String(code).replace(/\n$/, ''), String(lang || '')))
  source = renderNpcCards(source)
  let html = marked.parse(source, { async: false }) as string
  html = sanitizeHtml(html)
  for (const block of mathBlocks) html = html.split(block.placeholder).join(block.html)
  if (_mdCache.size < 64) _mdCache.set(text, html)
  return html
}
function renderMarkdownCached(seg: ChatSegment | { id: string; content?: string }): string {
  return renderMarkdown(seg.content || '')
}

// === 轻量行内渲染：只处理行内语法(加粗/代码/链接/删除线/行内公式)，开销极小，供流式 pending 实时显示 ===
function _renderInline(text: string): string {
  if (!text) return ''
  let s = escapeHtml(text)
  // 行内代码（先保护，避免被后续加粗规则误伤）
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>')
  // 加粗
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  // 斜体（单个 * 包裹，避开 **）
  s = s.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>')
  // 删除线
  s = s.replace(/~~([^~]+)~~/g, '<del>$1</del>')
  // 行内链接（https 安全白名单）
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (full, t, u) => /^(https?:|mailto:|#)/i.test(u) ? `<a href="${u}" target="_blank" rel="noopener">${t}</a>` : full)
  // 裸链接
  s = s.replace(/(^|[^>"'=])(https?:\/\/[^\s<]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>')
  return s
}

let mermaidReady: Promise<any> | null = null
function loadMermaid(): Promise<any> {
  const w = window as any
  if (w.mermaid) return Promise.resolve(w.mermaid)
  if (mermaidReady) return mermaidReady
  mermaidReady = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js'; script.async = true
    script.onload = () => { const mermaid = (window as any).mermaid; if (!mermaid) { reject(new Error('Mermaid 加载失败')); return }; mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' }); resolve(mermaid) }
    script.onerror = () => reject(new Error('Mermaid CDN 加载失败'))
    document.head.appendChild(script)
  })
  return mermaidReady
}
async function renderMermaidDiagrams(root?: HTMLElement) {
  if (!root) return
  const wraps = Array.from(root.querySelectorAll<HTMLElement>('.mermaid-wrap[data-mermaid]:not([data-rendered="1"])'))
  if (!wraps.length) return
  let mermaid: any
  try { mermaid = await loadMermaid() } catch (e: any) { for (const wrap of wraps) { wrap.setAttribute('data-rendered', '1'); wrap.innerHTML = `<pre class="code-block"><code>${escapeHtml(e?.message || 'Mermaid 加载失败')}</code></pre>` }; return }
  for (const wrap of wraps) {
    const code = decodeURIComponent(wrap.getAttribute('data-mermaid') || '')
    if (!code) continue
    wrap.setAttribute('data-rendered', '1')
    try { const id = `mmd-${Date.now()}-${Math.random().toString(16).slice(2)}`; const { svg } = await mermaid.render(id, code); wrap.innerHTML = svg } catch (e: any) { wrap.innerHTML = `<pre class="code-block"><code>${escapeHtml(e?.message || code)}</code></pre>` }
  }
}

function normalizeTrace(m: Message) {
  if (m.reasoning == null) m.reasoning = ''
  if (Array.isArray(m.tools)) m.tools = m.tools.map(t => ({ ...t, expanded: !!t.expanded }))
  else m.tools = []
  if (!Array.isArray(m.segments)) m.segments = []
  for (const seg of m.segments) if (seg.type === 'tool' && Array.isArray(seg.tools)) seg.tools = seg.tools.map(t => ({ ...t, expanded: !!t.expanded }))
  if (typeof m.traceExpanded !== 'boolean') m.traceExpanded = false
  if (typeof m.reasoningExpanded !== 'boolean') m.reasoningExpanded = true
  if (typeof m.toolsExpanded !== 'boolean') m.toolsExpanded = true
}
function reloadMessages() {
  const raw = getMessages?.() || []
  allMsgs.value = JSON.parse(JSON.stringify(raw)) as Message[]
  for (const m of allMsgs.value) {
    normalizeTrace(m)
    if (m.streaming && (!m.content || m.content === '')) { m.streaming = false; m.content = '⚠️ 此消息未完成（已标记）' }
  }
  titleUpdated.value = allMsgs.value.some(m => m.role === 'user' && !!m.content)
  afterRender()
}
watch(sessionId, () => { reloadMessages(); loadDisplayLimit() }, { immediate: true })
watch(displayLimit, () => { if (shouldScrollAfterLimitChange.value) { shouldScrollAfterLimitChange.value = false; afterRender() } })

let autoScrollFrozenUntil = 0
function freezeAutoScroll(ms = 3000) { autoScrollFrozenUntil = Date.now() + ms }
function canAutoScroll() { return Date.now() > autoScrollFrozenUntil }
function isNearBottom(el?: HTMLElement) {
  if (!el) el = msgBox.value
  if (!el) return true
  return el.scrollTop + el.clientHeight >= el.scrollHeight - 100
}
function onChatScroll() {
  if (!msgBox.value) return
  if (isNearBottom(msgBox.value)) autoScrollFrozenUntil = 0
  else autoScrollFrozenUntil = Infinity  // 滚离底部就永久冻结，不自动抢滚动
}
function sync() {
  const copy = [...allMsgs.value] as any[]
  allMsgs.value = copy
  setMessages?.(copy)
}

// --- frontend stream debug ---
let _dbgSeq = 0; let _dbgBuf: any[] = []
function _dbg(tag: string, extra?: any) {
  const ts = performance.now().toFixed(1); _dbgSeq++
  const entry = { seq: _dbgSeq, ts: parseFloat(ts), tag, ...(extra || {}) }
  _dbgBuf.push(entry)
  if (_dbgBuf.length > 300) _dbgBuf.shift()
}
;(window as any).__stream_dbg = () => _dbgBuf

let rafId: number | null = null
let rafDirty = false
function scheduleSync() {
  rafDirty = true
  if (rafId !== null) return
  _dbg('scheduleSync:rAF-reg')
  rafId = requestAnimationFrame(() => {
    rafId = null
    if (rafDirty) {
      rafDirty = false
      sync()
      nextTick(() => {
        // 只对还在接收内容的思考流自动滚底，已完成的让用户自由翻阅
        for (const m of allMsgs.value) {
          if (!m.segments) continue
          for (const seg of m.segments) {
            if (seg.type === 'reasoning' && seg.active && seg.expanded) {
              const el = msgBox.value?.querySelector(`[data-seg-id="${seg.id}"] .trace-reason`)
              if (el) (el as HTMLElement).scrollTop = (el as HTMLElement).scrollHeight
            }
          }
        }
      })
    }
  })
}
function flushSync() {
  if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null }
  rafDirty = false
  sync()
}


function scrollDown(force = false) {
  if (!force && !canAutoScroll()) return
  const box = msgBox.value
  if (!box) return
  nextTick(() => { box.scrollTop = box.scrollHeight })
}
function scrollIntoViewIfNeeded(el: HTMLElement, margin = 8) {
  const box = msgBox.value
  if (!box) return
  const br = box.getBoundingClientRect()
  const er = el.getBoundingClientRect()
  if (er.bottom > br.bottom) box.scrollTop += er.bottom - br.bottom + margin
}
function afterRender() { nextTick(() => { scrollDown(); renderMermaidDiagrams(msgBox.value) }) }
function traceHasContent(m: Message) { return !!((m.reasoning && m.reasoning.trim()) || (m.tools && m.tools.length)) }
function toggleTrace(m: Message) { freezeAutoScroll(); m.traceExpanded = !m.traceExpanded; sync() }
function toggleReasoning(m: Message) { freezeAutoScroll(); m.reasoningExpanded = !m.reasoningExpanded; sync() }
function toggleTools(m: Message) { freezeAutoScroll(); m.toolsExpanded = !m.toolsExpanded; sync() }
function scrollToSegment(seg: ChatSegment) {
  nextTick(() => {
    const el = msgBox.value?.querySelector(`[data-seg-id="${seg.id}"]`)
    if (el instanceof HTMLElement) scrollIntoViewIfNeeded(el)
  })
}
function toggleSegment(m: Message, seg: ChatSegment) {
  seg.userToggled = true
  seg.expanded = !seg.expanded
  sync()
  if (seg.expanded) scrollToSegment(seg)
}
function toggleToolEntry(t: TraceTool) {
  t.userToggled = true
  t.expanded = !t.expanded
  sync()
  if (t.expanded && t.id) {
    nextTick(() => {
      const el = msgBox.value?.querySelector(`[data-tool-id="${t.id}"]`)
      if (el instanceof HTMLElement) scrollIntoViewIfNeeded(el)
    })
  }
}
function compactValue(value: any, limit = 48) { const s = String(value ?? '').replace(/\s+/g, ' ').trim(); return s.length > limit ? s.slice(0, limit - 1) + '…' : s }
function baseName(pathLike: any) { const s = String(pathLike ?? '').replace(/\\/g, '/').replace(/\/+$/, ''); return s.split('/').filter(Boolean).pop() || s || '.' }
function dirLabel(pathLike: any) { const s = String(pathLike ?? '').replace(/\\/g, '/').replace(/\/+$/, ''); return s ? (s === '.' ? '当前目录' : baseName(s)) : '当前目录' }
function extractSpillLocator(text: string): string | null {
  const m = String(text || '').match(/spill:\/\/([A-Za-z0-9._-]+)\/([A-Za-z0-9._-]+\.txt)/)
  return m ? `spill://${m[1]}/${m[2]}` : null
}
function hasSpill(text: string): boolean { return extractSpillLocator(text) !== null }
async function loadSpillFull(t: TraceTool | ToolCall) {
  const locator = extractSpillLocator(t.result || '')
  if (!locator || t.spillFull || t.spillLoading) return
  t.spillLoading = true
  try {
    const rest = locator.slice('spill://'.length)
    const resp = await fetch(`${API}/api/v1/tools/spills/${rest}`)
    if (resp.ok) {
      const data = await resp.json()
      t.spillFull = data.content || '(空)'
    } else {
      t.spillFull = `(读取失败: HTTP ${resp.status})`
    }
  } catch {
    t.spillFull = '(读取失败: 网络错误)'
  } finally {
    t.spillLoading = false
  }
}
function toolTitle(t: TraceTool) { return t.name || 'unknown_tool' }
function webSearchResults(value?: string) {
  try {
    const rows = JSON.parse(value || '[]')
    if (!Array.isArray(rows)) return []
    return rows.flatMap((row: any) => {
      if (!row || typeof row.url !== 'string') return []
      try {
        const parsed = new URL(row.url)
        if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return []
        return [{ title: String(row.title || ''), url: parsed.href, snippet: String(row.snippet || ''), host: parsed.host }]
      } catch { return [] }
    }).slice(0, 10)
  } catch { return [] }
}
function toolSummary(t: TraceTool) {
  const a: any = t.args || {}
  const name = String(t.name || '').toLowerCase()
  const path = a.path ?? a.file ?? a.filename
  const dir = a.dir ?? a.directory ?? a.folder ?? a.path
  if (name.includes('list_directory') || name === 'list_dir' || name.includes('list_dir')) return `查看目录 ${dirLabel(dir)}`
  if (name.includes('read_file_lines')) return `读取文件片段 ${baseName(path)}`
  if (name.includes('file_read') || name.includes('read_file')) return `读取文件 ${baseName(path)}`
  if (name.includes('write_file') || name.includes('file_write')) return `写入文件 ${baseName(path)}`
  if (name.includes('patch') || name.includes('replace') || name.includes('edit_file')) return `修改文件 ${baseName(path)}`
  if (name.includes('run_command') || name.includes('shell') || name.includes('exec')) return `执行命令 ${compactValue(a.command ?? a.cmd ?? a.code, 42)}`
  if (name.includes('web_search') || name.includes('search')) return `搜索 ${compactValue(a.query ?? a.keyword ?? a.q, 42)}`
  if (name.includes('fetch') || name.includes('browser') || name.includes('webpage')) return `读取网页 ${compactValue(a.url ?? a.link, 42)}`
  if (a.query) return `查询 ${compactValue(a.query, 42)}`
  if (a.url) return `访问 ${compactValue(a.url, 42)}`
  if (path) return `处理 ${baseName(path)}`
  return Object.keys(a).length ? compactValue(JSON.stringify(a), 56) : '无参数'
}
function formatJson(value: any) { try { return typeof value === 'string' ? value : JSON.stringify(value ?? {}, null, 2) } catch { return String(value) } }
async function loadDisplayLimit() { try { const resp = await fetch(`${API}/api/v1/settings`); if (resp.ok) { const settings = await resp.json(); if (typeof settings.displayLimit === 'number' && settings.displayLimit >= 0) { shouldScrollAfterLimitChange.value = true; displayLimit.value = settings.displayLimit } } } catch { /* 静默 */ } }
function loadMore() { shouldScrollAfterLimitChange.value = false; displayLimit.value += 20 }
function handleKey(e: KeyboardEvent) { if (e.key === 'Escape' && editingMsg.value) { cancelEdit(); return }; if (e.key !== 'Enter') return; if (window.innerWidth < 768 || e.shiftKey) return; e.preventDefault(); handleSend() }
function handlePaste(e: ClipboardEvent) { const items = e.clipboardData?.items; if (!items) return; for (let i = 0; i < items.length; i++) { if (items[i].type.startsWith('image/')) { const f = items[i].getAsFile(); if (f) attachments.value.push({ name: f.name || '图片', data: f }) } } }
function autoSize() { nextTick(() => { const el = inputRef.value; if (!el) return; el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, 120)}px` }) }
function stopGen() { if (abortRef.value) { abortRef.value.abort(); abortRef.value = null }; if (streamIntervalRef.value !== null) { clearInterval(streamIntervalRef.value); streamIntervalRef.value = null }; const streamingMsg = allMsgs.value.find(m => m.streaming); if (streamingMsg) streamingMsg.streaming = false; loading.value = false; flushSync(); afterRender() }

async function buildRequestContext(untilIdx?: number) {
  const settingsResp = await fetch(`${API}/api/v1/settings`)
  if (!settingsResp.ok) throw new Error(`设置读取失败 HTTP ${settingsResp.status}`)
  const settings = await settingsResp.json()
  const modelName = currentModel?.value || ''
  let provider: any = null
  if (settings.providers && modelName) provider = settings.providers.find((p: any) => p.models && p.models.includes(modelName))
  if (!provider && settings.providers?.length) provider = settings.providers.find((p: any) => p.models?.length) || settings.providers[0]
  const history: { role: string; content: string }[] = []
  if (Array.isArray(settings.prompts)) { const def = settings.prompts.find((p: any) => p.isDefault); if (def?.content) history.push({ role: 'system', content: def.content }) }
  const source = typeof untilIdx === 'number' ? allMsgs.value.slice(0, untilIdx + 1) : allMsgs.value
  history.push(...source.filter((m: any) => m.role && m.content && !m.streaming && !m.toolCall).map((m: any) => ({ role: m.role === 'ai' ? 'assistant' : 'user', content: m.content })))
  return {
    settings,
    requestBody: {
      messages: history,
      model: modelName || provider?.models?.[0] || 'gpt-4o',
      baseUrl: provider?.baseUrl || 'https://api.openai.com',
      apiKey: provider?.key || '',
      temperature: settings.params?.temperature ?? 0.7,
      maxTokens: settings.params?.maxTokens || 4096,
    },
  }
}
async function requestAi(aiMsg: Message, untilIdx?: number) {
  const ac = new AbortController(); abortRef.value = ac
  const { requestBody } = await buildRequestContext(untilIdx)
  function findMsg() { return allMsgs.value.find(m => m.id === aiMsg.id) }
  const proxyMsg = findMsg()
  if (!proxyMsg) { loading.value = false; return }

  proxyMsg.reasoning = ''
  proxyMsg.tools = []
  proxyMsg.segments = []
  proxyMsg.traceExpanded = false
  proxyMsg.reasoningExpanded = false
  proxyMsg.toolsExpanded = false
  proxyMsg.content = ''
  proxyMsg.streaming = true

  let currentReasoningSeg: ChatSegment | null = null
  let currentToolSeg: ChatSegment | null = null
  let done = false

  function closeActiveSegs(m: Message) {
    const now = Date.now()
    for (const seg of m.segments || []) {
      seg.active = false
      if (seg.type === 'reasoning' && seg.startedAt && !seg.durationMs) seg.durationMs = now - seg.startedAt
      // 思考段完成后不自动折叠，内容保留在屏幕上让用户看完
      // 工具段也不自动折叠，避免闪烁
    }
    currentReasoningSeg = null
    currentToolSeg = null
  }
  function ensureToolSeg(m: Message) {
    if (currentToolSeg) return currentToolSeg
    const lastSeg = m.segments?.[m.segments.length - 1]
    if (lastSeg?.type === 'tool') currentToolSeg = lastSeg
    else {
      currentToolSeg = { id: `toolseg-${Date.now()}-${Math.random().toString(16).slice(2)}`, type: 'tool', tools: [], expanded: true, active: true }
      m.segments = [...(m.segments || []), currentToolSeg]
    }
    currentToolSeg.active = true
    if (!currentToolSeg.userToggled) currentToolSeg.expanded = true
    return currentToolSeg
  }
  // === token 批量缓冲：非响应式累积，定时/定量 flush，降低渲染频率 ===
  const STREAM_FLUSH_CHARS = 120          // 每累积 ~120 字符 flush 一次（更细腻）
  const STREAM_FLUSH_MS = 48              // 或每 48ms 兜底 flush（更细腻）
  let _streamTextBuf = ''                 // 非响应式 token 缓冲（text）
  let _streamReasonBuf = ''               // 非响应式 token 缓冲（reasoning）
  let _streamFlushTimer: number | null = null
  let _streamActiveSeg: ChatSegment | null = null

  // === 分段渲染：按段落边界切分，已完成段落渲染为 HTML（增量追加，不重渲染全文）===
  function _inFence(p: string): boolean {
    const m = p.match(/```/g)
    return !!(m && m.length % 2 === 1)
  }
  function _splitPendingParts(seg: any) {
    if (!seg.pending) return
    seg.renderedParts = seg.renderedParts || []
    let p = seg.pending
    // 代码块内不按空行切分（防止拆断代码块）；但超长代码块强制切分防 pending 无限膨胀
    const inFence = _inFence(p)
    if (inFence && p.length < 1500) return
    let idx
    while ((idx = p.indexOf('\n\n')) !== -1) {
      const part = p.slice(0, idx)
      p = p.slice(idx + 2)
      if (part.trim()) seg.renderedParts.push(renderMarkdown(part))
    }
    if (p.length > 600) { seg.renderedParts.push(renderMarkdown(p)); p = '' }
    seg.pending = p
  }
  function _flushStreamBuf(m: Message) {
    if (_streamFlushTimer !== null) { clearTimeout(_streamFlushTimer); _streamFlushTimer = null }
    // 刷新 text 缓冲
    if (_streamTextBuf && _streamActiveSeg) {
      const seg = _streamActiveSeg
      seg.content = (seg.content || '') + _streamTextBuf
      m.content += _streamTextBuf
      seg.pending = (seg.pending || '') + _streamTextBuf
      _streamTextBuf = ''
      // 借鉴 LibreChat：流式开始时已有 >120 字符（续聊/重连）视为基线，不重放动画
      if (seg.noFade === undefined && (seg.pending.length > 120 || (seg.renderedParts || []).length > 0)) seg.noFade = true
      _splitPendingParts(seg)
    }
    // 刷新 reasoning 缓冲
    if (_streamReasonBuf && currentReasoningSeg) {
      const seg = currentReasoningSeg
      seg.content = (seg.content || '') + _streamReasonBuf
      m.reasoning = (m.reasoning || '') + _streamReasonBuf
      seg.pending = (seg.pending || '') + _streamReasonBuf
      _streamReasonBuf = ''
      _splitPendingParts(seg)
    }
    _dbg('stream:flush', { textBuf: _streamTextBuf.length, reasonBuf: _streamReasonBuf.length })
    scrollDown()
    scheduleSync()
  }
  function _scheduleStreamFlush(m: Message) {
    // 借鉴 OpenWebUI：优先用 requestAnimationFrame 节流，帧对齐更跟手；
    // setTimeout 兜底（后台标签页 rAF 会暂停）
    if (_streamFlushTimer !== null) return
    if (typeof requestAnimationFrame === 'function') {
      _streamFlushTimer = window.setTimeout(() => {}, STREAM_FLUSH_MS) // 占位防重入
      requestAnimationFrame(() => {
        _streamFlushTimer = null
        _flushStreamBuf(m)
      })
      // 兜底：rAF 被挂起（后台/降频）时最多 STREAM_FLUSH_MS*3 后强制 flush
      window.setTimeout(() => {
        if (_streamFlushTimer !== null) { _streamFlushTimer = null; _flushStreamBuf(m) }
      }, STREAM_FLUSH_MS * 3)
    } else {
      _streamFlushTimer = window.setTimeout(() => { _streamFlushTimer = null; _flushStreamBuf(m) }, STREAM_FLUSH_MS)
    }
  }

  function appendTextSeg(m: Message, chunk: string) {
    closeActiveSegs(m)
    let last = m.segments?.[m.segments.length - 1]
    if (!last || last.type !== 'text') {
      last = { id: `text-${Date.now()}-${Math.random().toString(16).slice(2)}`, type: 'text', content: '', active: true }
      m.segments = [...(m.segments || []), last]
    }
    last.active = true
    _streamActiveSeg = last
    _streamTextBuf += chunk
    if (_streamTextBuf.length >= STREAM_FLUSH_CHARS) _flushStreamBuf(m)
    else _scheduleStreamFlush(m)
  }

  try {
    const resp = await fetch(`${API}/api/v1/chat/stream`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody), signal: ac.signal,
    })
    if (!resp.ok) { const errText = await resp.text().catch(() => ''); throw new Error(`API ${resp.status}: ${errText.slice(0, 300)}`) }
    if (!resp.body) throw new Error('浏览器不支持流式读取')

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done: streamDone, value } = await reader.read()
      _dbg('reader:chunk', { bytes: value?.length || 0, done: streamDone })
      if (streamDone && !buffer.trim()) break
      buffer += decoder.decode(value || new Uint8Array(), { stream: !streamDone })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      _dbg('reader:lines', { n: lines.length })

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        if (trimmed === 'data: [DONE]') { _dbg('ss:done-marker'); done = true; break }
        if (!trimmed.startsWith('data: ')) continue
        const event = JSON.parse(trimmed.slice(6))
        const m = findMsg()
        if (!m) { loading.value = false; return }

        switch (event.type) {
          case 'reasoning': {
            if (currentToolSeg) { currentToolSeg.active = false; currentToolSeg = null }
            if (!currentReasoningSeg) {
              currentReasoningSeg = { id: `reasoning-${Date.now()}-${Math.random().toString(16).slice(2)}`, type: 'reasoning', content: '', expanded: true, active: true, startedAt: Date.now() }
              m.segments = [...(m.segments || []), currentReasoningSeg]
            }
            currentReasoningSeg.active = true
            _streamReasonBuf += event.content
            _dbg('evt:reasoning', { delta: event.content.length, buf: _streamReasonBuf.length, preview: event.content.slice(0, 20) })
            if (_streamReasonBuf.length >= STREAM_FLUSH_CHARS) _flushStreamBuf(m)
            else _scheduleStreamFlush(m)
            break
          }
          case 'tool_round_start': {
            if (currentReasoningSeg) {
              currentReasoningSeg.active = false
              currentReasoningSeg = null
            }
            ensureToolSeg(m)
            scrollDown()
            break
          }
          case 'tool_call_start': {
            const seg = ensureToolSeg(m)
            const toolId = event.id || `tool-${seg.tools?.length || 0}`
            const runningTool: TraceTool = { id: toolId, round: event.round, name: event.name, args: event.args, running: true, expanded: false }
            seg.tools = [...(seg.tools || []), runningTool]
            m.tools = [...(m.tools || []), runningTool]
            scrollDown()
            break
          }
          case 'tool_call': {
            const seg = ensureToolSeg(m)
            const toolId = event.id || `tool-${seg.tools?.length || 0}`
            const prevTool = (seg.tools || []).find(t => t.id === toolId)
            const toolEntry: TraceTool = {
              id: toolId, round: event.round, name: event.name, args: event.args,
              result: event.result, ok: event.ok, error: event.error, durationMs: event.durationMs,
              expanded: prevTool?.userToggled ? !!prevTool.expanded : event.ok === false,
              running: false, userToggled: prevTool?.userToggled,
            }
            const idx = (seg.tools || []).findIndex(t => t.id === toolId)
            if (idx >= 0) seg.tools!.splice(idx, 1, toolEntry)
            else seg.tools = [...(seg.tools || []), toolEntry]
            const flatIdx = (m.tools || []).findIndex(t => t.id === toolId)
            if (flatIdx >= 0) m.tools!.splice(flatIdx, 1, toolEntry)
            else m.tools = [...(m.tools || []), toolEntry]
            break
          }
          case 'media': {
            closeActiveSegs(m)
            const media = event.media as ChatMedia
            if (media?.kind === 'aios.image' && media.url && !(m.segments || []).some(seg => seg.type === 'media' && seg.media?.media_id === media.media_id)) {
              m.segments = [...(m.segments || []), { id: `media-${media.media_id}`, type: 'media', media }]
            }
            scrollDown(); scheduleSync()
            break
          }
          case 'usage':
            if (event.data) {
              m.usage = event.data
              m.finishedAt = Date.now()
              const u = event.data
              const comp = u?.completion_tokens ?? u?.completionTokens ?? u?.output_tokens ?? 0
              const secs = Math.max(0.001, (m.finishedAt - (m.createdAt || m.finishedAt)) / 1000)
              m.tokPerSec = comp > 0 ? Math.round(comp / secs) : 0
              m.cachedTokens = u?.prompt_tokens_details?.cached_tokens ?? u?.cached_tokens ?? u?.cachedTokens ?? 0
              // 全部上下文累加（遍历所有 AI 消息 usage）
              let cum = 0
              for (const mm of allMsgs.value) {
                if (mm.usage) {
                  const uu = mm.usage
                  cum += uu?.total_tokens ?? uu?.totalTokens ?? ((uu?.prompt_tokens ?? 0) + (uu?.completion_tokens ?? 0))
                }
              }
              m.cumTokens = cum
            }
            _dbg('evt:usage', event.data)
            scheduleSync()
            break
          case 'content':
            appendTextSeg(m, event.content)
            _dbg('evt:content', { delta: event.content.length, preview: event.content.slice(0, 20) })
            scrollDown()
            scheduleSync()
            break
        }
      }
    }
  } catch (e: any) {
    if (e?.name === 'AbortError') { const mm = findMsg(); if (mm) _flushStreamBuf(mm); loading.value = false; flushSync(); afterRender(); return }
    const m = findMsg()
    if (m) { _flushStreamBuf(m); m.content = `❌ **请求失败**\n\n\`\`\`\n${e?.message || e}\n\`\`\`\n\n> 请检查设置。` }
    apiError.value = e?.message || '请求失败'
    loading.value = false; flushSync(); afterRender(); return
  }

  const finalMsg = findMsg()
  if (!finalMsg) { loading.value = false; return }
  _flushStreamBuf(finalMsg)  // 强制 flush 剩余缓冲
  // 分段收尾：把剩余未完成段落渲染进 renderedParts（防止流式与完成态之间闪烁）
  for (const seg of finalMsg.segments || []) {
    if ((seg.type === 'text' || seg.type === 'reasoning') && seg.pending) {
      seg.renderedParts = seg.renderedParts || []
      seg.renderedParts.push(renderMarkdown(seg.pending))
      seg.pending = ''
    }
  }
  finalMsg.streaming = false; loading.value = false
  closeActiveSegs(finalMsg)
  if (!finalMsg.finishedAt) finalMsg.finishedAt = Date.now()
  if (finalMsg.usage && finalMsg.tokPerSec == null) {
    const u = finalMsg.usage
    const comp = u?.completion_tokens ?? u?.completionTokens ?? u?.output_tokens ?? 0
    const secs = Math.max(0.001, (finalMsg.finishedAt - (finalMsg.createdAt || finalMsg.finishedAt)) / 1000)
    finalMsg.tokPerSec = comp > 0 ? Math.round(comp / secs) : 0
    finalMsg.cachedTokens = u?.prompt_tokens_details?.cached_tokens ?? u?.cached_tokens ?? u?.cachedTokens ?? 0
    let cum = 0
    for (const mm of allMsgs.value) {
      if (mm.usage) {
        const uu = mm.usage
        cum += uu?.total_tokens ?? uu?.totalTokens ?? ((uu?.prompt_tokens ?? 0) + (uu?.completion_tokens ?? 0))
      }
    }
    finalMsg.cumTokens = cum
  }
  finalMsg.reasoningExpanded = false
  finalMsg.toolsExpanded = false
  finalMsg.traceExpanded = false
  flushSync(); afterRender()
}

function getSessionTitle(): string {
  const sid = sessionId?.value
  const list = sessions?.value || []
  const cur = list.find((x: any) => x.id === sid)
  const t = cur?.title || ''
  return t && t !== '新对话' ? t : ''
}
function autoGenTitle(text: string): string {
  let t = String(text || '').replace(/\s+/g, ' ').trim()
  if (t.startsWith('/')) return ''
  t = t.replace(/^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\s]+/u, '')
  if (!t) return ''
  const MAX = 20
  return t.length > MAX ? t.slice(0, MAX) + '…' : t
}
async function handleSend(text?: string) {
  loadDisplayLimit()
  const msg = (text ?? input.value).trim()
  if (!msg || loading.value) return
  input.value = ''; autoSize(); apiError.value = ''
  if (msg.startsWith('/')) { handleSlashCommand(msg); return }
  if (editingMsg.value) { const editIdx = allMsgs.value.findIndex(m => m.id === editingMsg.value?.id); if (editIdx >= 0) allMsgs.value.splice(editIdx); editingMsg.value = null }
  const lastMsg = allMsgs.value[allMsgs.value.length - 1]
  const isFirstUserMsg = !allMsgs.value.some(m => m.role === 'user' && m.content)
  if (!lastMsg || !(lastMsg.role === 'user' && lastMsg.content === msg)) { allMsgs.value.push({ id: Date.now().toString(), role: 'user', content: msg }); sync() }
  // 自动生成会话标题：标题仍为默认"新对话"时自动生成（首条消息用当前，旧会话用第一条用户消息）
  if (isFirstUserMsg || !getSessionTitle()) {
    const firstUser = allMsgs.value.find(m => m.role === 'user' && !!m.content)
    const t = autoGenTitle(firstUser?.content || msg)
    if (t && sessionId?.value) updateSessionTitle(sessionId.value, t)
  }
  loading.value = true
  const aiId = (Date.now() + 1).toString()
  const aiMsg: Message = { id: aiId, role: 'ai', content: '', streaming: true, branches: [], branchIdx: 0, reasoning: '', tools: [], segments: [], traceExpanded: false, createdAt: Date.now() }
  allMsgs.value.push(aiMsg); sync(); scrollDown()
  try { await requestAi(aiMsg) } catch (e: any) {
    if (e?.name === 'AbortError') { loading.value = false; sync(); afterRender(); return }
    const proxyMsg = allMsgs.value.find(m => m.id === aiId)
    if (proxyMsg) { proxyMsg.streaming = false; proxyMsg.content = `❌ **请求失败**\n\n\`\`\`\n${e?.message || e}\n\`\`\`\n\n> 请检查设置中的 Provider 配置（API Key / Base URL / 模型名称）是否正确。` }
    apiError.value = e?.message || '请求失败'; loading.value = false; sync(); afterRender()
  }
}
function handleSlashCommand(cmd: string) { allMsgs.value.push({ id: Date.now().toString(), role: 'user', content: cmd }); let reply = ''; if (cmd === '/help') reply = '🎯 **斜杠命令**\n\n`/clear` 清空当前对话\n`/help` 显示帮助\n`/model <name>` 切换模型\n`/export` 导出对话\n`/status` 系统状态'; else if (cmd === '/clear') { allMsgs.value = []; sync(); scrollDown(); return } else if (cmd === '/status') reply = `🖥️ **Personal AI OS V2**\n\n后端：✅ 运行中 (8080)\n模型：${currentModel?.value || '未选择'}\n工具：5 个已注册`; else reply = `未识别命令 \`${cmd}\`，输入 \`/help\` 查看可用命令`; allMsgs.value.push({ id: (Date.now() + 1).toString(), role: 'ai', content: reply, reasoning: '', tools: [], segments: [], traceExpanded: false }); sync(); afterRender() }
async function retryMsg(m: Message) {
  if (loading.value) return
  const idx = allMsgs.value.indexOf(m); if (idx === -1) return
  let userIdx = -1; for (let i = idx - 1; i >= 0; i--) { if (allMsgs.value[i].role === 'user') { userIdx = i; break } }
  if (userIdx === -1) return
  loading.value = true; apiError.value = ''
  const aiId = (Date.now() + 1).toString()
  const aiMsg: Message = { id: aiId, role: 'ai', content: '', streaming: true, branches: [], branchIdx: 0, reasoning: '', tools: [], segments: [], traceExpanded: false, createdAt: Date.now() }
  allMsgs.value.splice(idx, allMsgs.value.length - idx, aiMsg); sync(); scrollDown()
  try { await requestAi(aiMsg, userIdx) } catch (e: any) {
    if (e?.name === 'AbortError') { loading.value = false; sync(); afterRender(); return }
    const proxyMsg = allMsgs.value.find(m => m.id === aiId)
    if (proxyMsg) { proxyMsg.streaming = false; proxyMsg.content = `❌ **请求失败**\n\n\`\`\`\n${e?.message || e}\n\`\`\`\n\n> 请检查设置中的 Provider 配置（API Key / Base URL / 模型名称）是否正确。` }
    apiError.value = e?.message || '请求失败'; loading.value = false; sync(); afterRender()
  }
}

async function copyMsg(m: Message, e: Event) { const btn = (e.target as HTMLElement).closest('button'); if (!btn) return; copyToClipboard(m.content, btn) }
function cancelEdit() { editingMsg.value = null; input.value = ''; autoSize(); inputRef.value?.blur() }
function editMsg(m: Message) { editingMsg.value = m; input.value = m.content; autoSize(); nextTick(() => inputRef.value?.focus()) }
function deleteMsg(m: Message) { const idx = allMsgs.value.findIndex(msg => msg.id === m.id); if (idx === -1) return; allMsgs.value.splice(idx); sync(); setMessages(allMsgs.value as any[]) }
function prevBranch(m: Message) { if ((m.branchIdx || 0) > 0 && m.branches) { m.branchIdx = (m.branchIdx || 0) - 1; m.content = m.branches[m.branchIdx]; sync() } }
function nextBranch(m: Message) { if (m.branches && (m.branchIdx || 0) < m.branches.length - 1) { m.branchIdx = (m.branchIdx || 0) + 1; m.content = m.branches[m.branchIdx]; sync() } }
function onMsgClick(e: MouseEvent) { const btn = (e.target as HTMLElement).closest<HTMLButtonElement>('.code-copy'); if (!btn) return; const code = decodeURIComponent(btn.dataset.code || ''); copyToClipboard(code, btn) }
function fmtUsage(u: any): string {
  const p = u?.prompt_tokens ?? u?.promptTokens
  const c = u?.completion_tokens ?? u?.completionTokens ?? u?.output_tokens
  const t = u?.total_tokens ?? u?.totalTokens
  if (t != null) return `${t} tokens`
  if (p != null || c != null) return `${p ?? 0}↑ / ${c ?? 0}↓`
  return ''
}
function formatTime(ts: number): string {
  const d = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
function fmtElapsed(start?: number, end?: number): string {
  if (!start || !end) return ''
  const total = Math.max(0, Math.floor((end - start) / 1000))
  const pad = (n: number) => String(n).padStart(2, '0')
  const h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), sec = total % 60
  return `${pad(h)}:${pad(m)}:${pad(sec)}`
}
function fmtDur(ms: number): string {
  const msNum = Math.max(0, ms)
  // ≤1s 显示毫秒级（如 860ms / 120ms）
  if (msNum < 1000) return `${Math.round(msNum)}ms`
  const total = Math.floor(msNum / 1000)
  const h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), sec = total % 60
  if (h > 0) return `${h}h${String(m).padStart(2, '0')}m${String(sec).padStart(2, '0')}s`
  if (m > 0) return `${m}m${String(sec).padStart(2, '0')}s`
  return `${sec}s`
}
async function copyToClipboard(text: string, btn: HTMLElement) { try { await navigator.clipboard.writeText(text); btn.textContent = '✅'; window.setTimeout(() => { btn.textContent = '📋' }, 900); return } catch { const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.left = '-9999px'; ta.style.top = '-9999px'; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); btn.textContent = '✅'; window.setTimeout(() => { btn.textContent = '📋' }, 900) } }
onMounted(() => msgBox.value?.addEventListener('click', onMsgClick))
onUnmounted(() => msgBox.value?.removeEventListener('click', onMsgClick))
</script>

<style scoped>
.chat-page{height:100%;display:flex;flex-direction:column;background:var(--bg);overflow:hidden}.chat-msgs{flex:1;display:flex;flex-direction:column;gap:14px;padding:16px;overflow-y:auto}.chat-empty{margin:auto;display:flex;flex-direction:column;align-items:center;gap:10px;color:var(--text2);text-align:center}.chat-empty__icon{font-size:48px}.chat-empty__title{font-size:18px;font-weight:600;color:var(--text)}.chat-empty__hint{font-size:13px;color:var(--text2)}.chat-chips{display:flex;flex-direction:column;gap:6px;width:100%;max-width:280px;margin-top:8px}.chat-chip{padding:10px 14px;border-radius:8px;background:var(--surface);border:1px solid var(--border-light);color:var(--text);cursor:pointer;font-size:13px;text-align:left;transition:all .15s}.chat-chip:active,.chat-chip:hover{border-color:var(--primary);background:var(--surface-alt)}.chat-load-more{padding:10px 16px;text-align:center;color:var(--primary);font-size:13px;cursor:pointer;border-radius:8px;background:var(--surface);border:1px dashed var(--border-light);transition:all .15s;user-select:none}.chat-load-more:hover{background:var(--surface-alt);border-color:var(--primary)}
.chat-input-wrap{padding:8px 8px max(8px,env(safe-area-inset-bottom));background:var(--bg);border-top:1px solid var(--border-light);flex-shrink:0}.chat-files{display:flex;gap:6px;flex-wrap:wrap;padding-bottom:6px}.chat-file{display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:6px;background:var(--surface);font-size:12px}.chat-file__rm{background:transparent;border:none;color:var(--text3);cursor:pointer;font-size:14px}.chat-input-area{display:flex;flex-direction:column}.chat-edit-bar{display:flex;align-items:center;gap:8px;padding:0 4px 6px;font-size:12px}.chat-edit-hint{color:var(--warn);font-weight:500}.chat-edit-cancel{background:transparent;border:none;color:var(--text3);cursor:pointer;text-decoration:underline;font-size:12px;padding:0;font-family:inherit}.chat-edit-cancel:hover{color:var(--text)}.chat-input-row{display:flex;gap:8px;align-items:flex-end}.chat-input{flex:1;padding:12px 16px;border-radius:20px;background:var(--surface);border:1px solid var(--border-light);color:var(--text);font-size:14px;font-family:inherit;resize:none;outline:none;overflow:hidden;min-height:44px;max-height:120px;line-height:1.4;transition:border .2s}.chat-input:focus{border-color:var(--primary)}
.msg{display:flex;gap:8px;max-width:90%;animation:msgIn .2s ease}@keyframes msgIn{from{opacity:0;transform:translateY(6px)}}.msg--user{align-self:flex-end;flex-direction:row-reverse}.msg--ai{align-self:flex-start}.msg__avatar{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;background:var(--surface-alt)}.msg__body{display:flex;flex-direction:column;gap:4px;max-width:100%;min-width:0}.msg__bubble{padding:10px 14px;border-radius:12px;font-size:14px;line-height:1.6;word-break:break-word;max-width:100%;overflow:hidden}.msg--user .msg__bubble{background:var(--primary);color:#fff;border-bottom-right-radius:4px}.msg--ai .msg__bubble{background:var(--surface);border:1px solid var(--border-light);border-bottom-left-radius:4px}.msg__text{max-width:100%;overflow-wrap:anywhere;transition:opacity .08s ease}
/* 流式渲染：纯文本阶段（token 批量缓冲期间不跑 markdown，省内存/CPU） */
.msg__text--stream,.msg__text--parts{display:block}
.msg__text-part{display:block;animation:partFade .18s ease-out}
.msg__text-part:not(:last-child){margin-bottom:3px}
.msg__text-part:last-child{margin-bottom:2px}
.msg__text-pending,.trace-reason .msg__text-pending{white-space:pre-wrap;word-break:break-word;color:var(--text2);animation:partFade .15s ease-out}
.msg__text-pending::after,.trace-reason .msg__text-pending::after{content:'▍';display:inline-block;margin-left:1px;color:var(--primary);animation:cursorPulse 1.1s ease-in-out infinite}
.msg__text-pending code,.trace-reason .msg__text-pending code{background:var(--surface-alt);border:1px solid var(--border-light);border-radius:4px;padding:0 4px;font-size:.92em;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--primary-light)}
.msg__text-pending strong,.trace-reason .msg__text-pending strong{color:var(--text1);font-weight:600}
.msg__text-pending a,.trace-reason .msg__text-pending a{color:var(--primary-light);text-decoration:underline;text-underline-offset:2px}
@keyframes partFade{from{opacity:.6;transform:translateY(.5px)}to{opacity:1;transform:none}}
.msg__text-pending.no-fade,.trace-reason .msg__text-pending.no-fade{animation:none}
@media (prefers-reduced-motion:reduce){.msg__text-part,.msg__text-pending,.trace-reason .msg__text-pending,.msg__cursor{animation:none!important}}
.trace-reason--parts .msg__text-pending{color:var(--text2)}.msg-media{margin:0;max-width:min(680px,100%);overflow:hidden;border:1px solid var(--border-light);border-radius:14px;background:var(--surface);box-shadow:0 6px 24px rgba(0,0,0,.1)}.msg-media a{display:block;line-height:0}.msg-media img{display:block;max-width:100%;max-height:70vh;width:auto;height:auto;object-fit:contain;background:var(--surface-alt)}.msg-media figcaption{padding:8px 11px;color:var(--text2);font-size:12px;line-height:1.4}.msg__text img,.trace-reason img{display:block;max-width:100%;height:auto;margin:8px auto;border-radius:8px} textFade{from{opacity:.7}to{opacity:1}}.trace-slide-enter-active,.trace-slide-leave-active{transition:all .25s ease;overflow:hidden}.trace-slide-enter-from,.trace-slide-leave-to{max-height:0;opacity:0;padding-top:0;padding-bottom:0}.trace-slide-enter-to,.trace-slide-leave-from{max-height:600px;opacity:1}.msg__cursor{display:inline-block;width:2px;height:14px;background:var(--primary);animation:cursorPulse 1.2s ease-in-out infinite;vertical-align:middle;margin-left:2px}@keyframes cursorPulse{0%,100%{opacity:0.4}50%{opacity:1}75%{opacity:0.8}}
.trace-box{max-width:100%;border:1px solid color-mix(in srgb,var(--primary) 28%,var(--border-light));background:linear-gradient(135deg,color-mix(in srgb,var(--primary) 8%,var(--surface)),var(--surface));border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.05)}.trace-head{width:100%;display:flex;align-items:center;gap:6px;padding:8px 10px;background:transparent;border:none;color:var(--text2);font-size:12px;cursor:pointer;text-align:left}.trace-title{font-weight:700;color:var(--text)}.trace-pill{padding:2px 7px;border-radius:999px;font-size:11px;border:1px solid var(--border-light)}.trace-pill.think{color:#a855f7;background:rgba(168,85,247,.1);animation:thinkBreathe 2s ease-in-out infinite}@keyframes thinkBreathe{0%,100%{box-shadow:0 0 0 0 rgba(168,85,247,0)}50%{box-shadow:0 0 6px 2px rgba(168,85,247,.2)}}.trace-pill.tool{color:var(--primary);background:rgba(59,130,246,.1)}.trace-live{margin-left:auto;color:var(--warn);font-size:11px}.trace-body{border-top:1px solid var(--border-light);padding:9px;display:flex;flex-direction:column;gap:10px}.trace-section__head{width:100%;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 8px;margin:0 0 6px;border:1px solid var(--border-light);border-radius:8px;background:rgba(127,127,127,.04);color:var(--text2);cursor:pointer;text-align:left}.trace-section__head:hover{background:rgba(127,127,127,.08);border-color:color-mix(in srgb,var(--primary) 38%,var(--border-light))}.trace-section__title{font-size:12px;font-weight:700;color:var(--text2)}.trace-section__meta{font-size:11px;color:var(--text3);white-space:nowrap}.trace-tools-list{display:flex;flex-direction:column;gap:6px}.trace-reason{max-height:260px;transition:opacity .08s ease;overflow:auto;padding:9px;border-radius:8px;background:rgba(127,127,127,.07);font-size:12px;line-height:1.55;color:var(--text2)}.trace-tool{border:1px solid var(--border-light);border-radius:9px;overflow:hidden;background:rgba(127,127,127,.04)}.trace-tool+.trace-tool{margin-top:6px}.trace-tool__head{width:100%;display:flex;align-items:center;gap:7px;padding:8px;background:transparent;border:none;color:var(--text);cursor:pointer;font-size:12px;text-align:left}.trace-tool__name{font-weight:700;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.trace-tool__round,.trace-tool__time{color:var(--text3);font-size:11px}.trace-tool__state{margin-left:auto;font-size:11px;padding:1px 6px;border-radius:999px}.trace-tool__state.ok{color:var(--success);background:rgba(34,197,94,.1)}.trace-tool__state.bad{color:var(--error);background:rgba(239,68,68,.1)}.trace-tool__body{padding:8px;border-top:1px solid var(--border-light)}.trace-mini-title{font-size:11px;color:var(--text3);margin:4px 0}.trace-code{background:#0d1117;color:#e6edf3;padding:8px;border-radius:7px;font-size:11px;font-family:'JetBrains Mono','Fira Code',monospace;white-space:pre-wrap;word-break:break-word;max-height:210px;overflow:auto}
.spill-btn{display:inline-flex;align-items:center;gap:4px;margin-top:6px;padding:3px 10px;border:1px solid color-mix(in srgb,var(--primary) 35%,var(--border-light));border-radius:999px;background:rgba(59,130,246,.08);color:var(--primary-light);font-size:11px;cursor:pointer;transition:all .15s ease}
.spill-btn:hover{background:rgba(59,130,246,.16);border-color:var(--primary)}
.spill-full{margin-top:6px;max-height:320px}
.trace-tool__summary{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text2);font-size:12px}.trace-tool__state.running{color:var(--warn);background:rgba(245,158,11,.12)}
.msg__meta{display:flex;align-items:center;gap:10px;padding:4px 2px 0;font-size:11px;color:var(--text3);opacity:0;transition:opacity .2s}.msg:hover .msg__meta{opacity:1}.msg--user .msg__meta{justify-content:flex-end}.msg__meta-tokens{font-family:'JetBrains Mono','Fira Code',monospace;background:rgba(127,127,127,.06);border:1px solid var(--border-light);border-radius:999px;padding:1px 8px;color:var(--text2)}.msg__meta-speed{font-family:'JetBrains Mono','Fira Code',monospace;color:var(--primary)}.msg__meta-cached{color:var(--success)}.msg__meta-elapsed{font-family:'JetBrains Mono','Fira Code',monospace;color:var(--warn)}.msg__meta-time{color:var(--text3)}.trace-pill.think-time{margin-left:auto;color:var(--text3);font-size:11px;border-color:var(--border-light)}.msg__actions{display:flex;gap:4px;padding:4px 0 0;opacity:0;transition:opacity .2s}.msg:hover .msg__actions{opacity:1}.msg--user .msg__actions{justify-content:flex-end}.msg__act{width:28px;height:28px;border-radius:6px;background:var(--surface-alt);border:1px solid var(--border-light);color:var(--text2);font-size:13px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;transition:all .15s}.msg__act:hover{background:var(--surface);border-color:var(--primary);color:var(--primary)}.msg__branch{display:flex;align-items:center;gap:8px;color:var(--text3);font-size:11px}.msg__branch-nav button{width:22px;height:22px;border-radius:5px;border:1px solid var(--border-light);background:var(--surface);color:var(--text2)}.tool-card{align-self:flex-start;max-width:90%;border:1px solid var(--border-light);background:var(--surface);border-radius:10px;overflow:hidden;cursor:pointer}.tool-card__header{display:flex;align-items:center;gap:8px;padding:9px 12px;font-size:13px}.tool-card__name{font-weight:600}.tool-card__status{color:var(--warn);font-size:12px}.tool-card__status.done{color:var(--success)}.tool-card__arrow{margin-left:auto;color:var(--text3)}.tool-card__body{border-top:1px solid var(--border-light);padding:10px}.tool-card__label{font-size:11px;color:var(--text3);margin-bottom:4px}.tool-card__code{background:#0d1117;padding:8px;border-radius:6px;font-size:11px;font-family:monospace;color:var(--text2);overflow-x:auto;white-space:pre-wrap;max-height:200px;overflow-y:auto}.tool-card__section+.tool-card__section{margin-top:8px}.chat-send{width:44px;height:44px;border-radius:50%;background:var(--primary);color:#fff;border:none;font-size:20px;cursor:pointer;flex-shrink:0;transition:all .2s;display:flex;align-items:center;justify-content:center}.chat-send:active{transform:scale(.9)}.chat-send.disabled{opacity:.4;pointer-events:none}.chat-send.stop{background:var(--error);animation:pulse-stop 1.2s ease-in-out infinite}@keyframes pulse-stop{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.4)}50%{box-shadow:0 0 0 8px rgba(239,68,68,0)}}
:deep(.msg__text p),:deep(.trace-reason p){margin:0 0 8px}:deep(.msg__text p:last-child),:deep(.trace-reason p:last-child){margin-bottom:0}:deep(.code-block){background:#0d1117;border-radius:8px;padding:32px 12px 12px;margin:8px 0;overflow-x:auto;font-family:'JetBrains Mono','Fira Code',monospace;font-size:12px;line-height:1.6;border:1px solid var(--border-light);position:relative;color:#e6edf3}:deep(.code-block)::before{content:attr(data-lang);position:absolute;top:7px;left:12px;font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.5px}:deep(.code-copy){position:absolute;top:4px;right:4px;width:28px;height:28px;border-radius:4px;background:transparent;border:1px solid transparent;color:var(--text3);font-size:12px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s;opacity:.55}:deep(.code-copy):hover{opacity:1;background:rgba(255,255,255,.08);border-color:var(--border-light);color:var(--text)}:deep(.inline-code),:deep(:not(pre)>code){background:var(--surface-alt);padding:1px 6px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--primary-light)}:deep(a){color:var(--primary-light);text-decoration:underline}:deep(strong){font-weight:700}:deep(em){font-style:italic}:deep(ol),:deep(ul){padding-left:0.1em;list-style-position:inside;margin:6px 0}:deep(li){margin:2px 0}:deep(li)::marker{color:var(--text3)}

:deep(table){border-collapse:collapse;border-spacing:0;width:100%;margin:10px 0;font-size:13px;border-radius:8px;border:1px solid var(--border-light);box-shadow:0 1px 4px rgba(0,0,0,.08)}:deep(thead){background:var(--surface-alt);position:sticky;top:0}:deep(th){font-weight:700;padding:10px 12px;border-bottom:2px solid var(--border-light);text-align:left;color:var(--text);font-size:12.5px;letter-spacing:.3px;word-break:break-word;overflow-wrap:anywhere}:deep(th):not(:last-child){border-right:1px solid var(--border-light)}:deep(td){padding:9px 12px;border-bottom:1px solid var(--border-light);color:var(--text);vertical-align:top;line-height:1.5;word-break:break-word;overflow-wrap:anywhere}:deep(td):not(:last-child){border-right:1px solid var(--border-light)}:deep(tr:last-child td){border-bottom:none}:deep(tr:nth-child(even)){background:rgba(128,128,128,.04)}:deep(tr:hover){background:rgba(128,128,128,.07)}:deep(.hljs){color:#e6edf3;background:transparent}:deep(.hljs-keyword){color:#ff7b72}:deep(.hljs-string){color:#a5d6ff}:deep(.hljs-number){color:#79c0ff}:deep(.hljs-comment){color:#8b949e;font-style:italic}:deep(.hljs-title){color:#d2a8ff}:deep(.hljs-built_in),:deep(.hljs-type){color:#ffa657}:deep(.hljs-attr),:deep(.hljs-attribute){color:#79c0ff}:deep(.hljs-literal){color:#ff7b72}:deep(.hljs-meta){color:#8b949e}:deep(.hljs-tag),:deep(.hljs-name){color:#7ee787}:deep(.hljs-selector-class),:deep(.hljs-selector-id){color:#d2a8ff}:deep(.hljs-selector-tag){color:#7ee787}:deep(.hljs-regexp){color:#a5d6ff}:deep(.hljs-symbol){color:#79c0ff}:deep(.hljs-deletion){color:#ff7b72;background:rgba(255,123,114,.1)}:deep(.hljs-addition){color:#7ee787;background:rgba(126,231,135,.1)}:deep(.hljs-section){color:#d2a8ff;font-weight:700}
::deep(.npc-card){display:block;overflow-x:auto}:deep(.npc-card caption){padding:8px 12px;text-align:left;font-weight:700;color:var(--text);border-bottom:2px solid var(--border-light);background:color-mix(in srgb,var(--primary) 7%,var(--surface));font-size:13px;letter-spacing:.4px}:deep(.npc-card td:first-child){white-space:nowrap;width:128px;color:var(--text2);font-size:12.5px}:deep(.npc-card tbody tr:last-child td){border-bottom:none}
@media (max-width:767px){.chat-msgs{padding:12px 10px}.msg,.tool-card{max-width:96%}.msg__actions{opacity:1}.chat-hints{display:none}.trace-body{animation:textFade .12s ease;padding:8px}.trace-reason{max-height:200px}.trace-tool__head{gap:5px}.trace-tool__time{display:none}}

/* ========== 思考流 / 聊天区 专属滚动条美化 (PC) ========== */

/* 思考流内容区 — 紫色渐变滚动条 */
.trace-reason::-webkit-scrollbar { width: 6px; height: 6px; }
.trace-reason::-webkit-scrollbar-track { background: transparent; }
.trace-reason::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, var(--primary-light), var(--primary));
  border-radius: 6px;
  border: none;
  background-clip: border-box;
}
.trace-reason::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, var(--primary), var(--primary-light));
}
.trace-reason {
  scrollbar-width: thin;
  scrollbar-color: var(--primary-light) transparent;
  scrollbar-gutter: stable;
}

/* 工具流代码区 — 深色环境亮色滚动条 */
.trace-code::-webkit-scrollbar { width: 6px; height: 6px; }
.trace-code::-webkit-scrollbar-track { background: transparent; }
.trace-code::-webkit-scrollbar-thumb {
  background: rgba(148,163,184,.35);
  border-radius: 6px;
  border: none;
}
.trace-code::-webkit-scrollbar-thumb:hover { background: rgba(148,163,184,.65); }
.trace-code {
  scrollbar-width: thin;
  scrollbar-color: rgba(148,163,184,.35) transparent;
}

/* Markdown 代码块（v-html 生成）— 深色亮色滚动条 */
:deep(.code-block::-webkit-scrollbar) { height: 6px; width: 6px; }
:deep(.code-block::-webkit-scrollbar-track) { background: transparent; }
:deep(.code-block::-webkit-scrollbar-thumb) {
  background: rgba(148,163,184,.35);
  border-radius: 6px;
  border: none;
}
:deep(.code-block::-webkit-scrollbar-thumb:hover) { background: rgba(148,163,184,.65); }
:deep(.code-block) {
  scrollbar-width: thin;
  scrollbar-color: rgba(148,163,184,.35) transparent;
}

/* 聊天主滚动区 — 布局稳定 + 平滑滚动 */
.chat-msgs {
  scrollbar-gutter: stable;
  scroll-behavior: smooth;
}

/* 工具卡 / 表格等横向溢出容器 */
:deep(.npc-card) {
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--text3) 45%, transparent) transparent;
}

/* 移动端：滚动条更细 */
@media (max-width:767px){
  .trace-reason::-webkit-scrollbar { width: 3px; }
  .trace-code::-webkit-scrollbar { width: 3px; }
  .chat-msgs::-webkit-scrollbar { width: 4px; }
}


/* 正文表格卡片 — 参考工具流 .trace-tool 卡片方案：圆角边框+内部滚动，超宽不截断 */
:deep(.markdown-table) {
  margin: 10px 0;
  border: 1px solid var(--border-light);
  border-radius: 9px;
  background: rgba(127,127,127,.04);
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--text3) 45%, transparent) transparent;
}
:deep(.markdown-table > table) {
  margin: 0;
  border: none;
  border-radius: 0;
  box-shadow: none;
}
:deep(.markdown-table::-webkit-scrollbar) { height: 6px; }
:deep(.markdown-table::-webkit-scrollbar-track) { background: transparent; }
:deep(.markdown-table::-webkit-scrollbar-thumb) { background: color-mix(in srgb, var(--text3) 45%, transparent); border-radius: 999px; }
:deep(.markdown-table::-webkit-scrollbar-thumb:hover) { background: color-mix(in srgb, var(--primary) 70%, transparent); }

.trace-search-results{display:grid;gap:7px}.trace-search-card{display:grid;gap:4px;padding:9px 10px;border:1px solid var(--border-light);border-radius:8px;background:color-mix(in srgb,var(--surface) 96%,var(--primary) 4%);color:var(--text);text-decoration:none}.trace-search-card:hover{border-color:var(--primary);background:color-mix(in srgb,var(--surface) 90%,var(--primary) 10%)}.trace-search-card strong{font-size:12px;line-height:1.4}.trace-search-card span{font-size:11px;line-height:1.45;color:var(--text-secondary)}.trace-search-card small{font-size:10px;color:var(--primary)}

</style>

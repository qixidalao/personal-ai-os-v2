<template>
  <div class="ws">
    <!-- 笔记列表 -->
    <aside class="ws-list" :class="{ hidden: isMobile && !showList }">
      <div class="ws-list-hd">
        <span class="ws-list-title">笔记 <em>{{ notes.length }}</em></span>
        <button class="ui-btn ui-btn--sm ui-btn--primary" @click="createNote">
          <Plus :size="12" /> 新建
        </button>
      </div>

      <div class="ws-search">
        <Search :size="13" />
        <input v-model="query" placeholder="搜索笔记…" />
      </div>

      <div class="ws-notes">
        <button
          v-for="n in filteredNotes"
          :key="n.id"
          :class="['ws-note', { active: n.id === activeId }]"
          @click="selectNote(n.id)"
        >
          <div class="ws-note-top">
            <span v-if="n.pinned" class="pin">📌</span>
            <span class="ws-note-title">{{ n.title || '未命名笔记' }}</span>
          </div>
          <div class="ws-note-meta">
            <span>{{ fmtTime(n.updatedAt) }}</span>
            <span>{{ n.content.length }} 字</span>
          </div>
        </button>

        <div v-if="!filteredNotes.length" class="ws-empty">
          <span>没有笔记</span>
        </div>
      </div>

      <div class="ws-list-ft">
        <button class="ui-btn ui-btn--sm ui-btn--block" @click="importFile">
          <Upload :size="12" /> 导入 .md
        </button>
        <input ref="fileRef" type="file" accept=".md,.txt,.markdown" hidden @change="onFile" />
      </div>
    </aside>

    <!-- 编辑器 -->
    <section class="ws-editor" v-if="active">
      <header class="ws-hd">
        <button v-if="isMobile" class="ui-btn ui-btn--ghost ui-btn--icon" @click="showList = true">
          <List :size="15" />
        </button>
        <input v-model="active.title" class="ws-title-inp" placeholder="笔记标题…" />
        <div class="ws-hd-actions">
          <div class="mode-group">
            <button :class="['mode', { on: mode === 'edit' }]" @click="mode = 'edit'" title="仅编辑"><PenLine :size="13" /></button>
            <button :class="['mode', { on: mode === 'split' }]" @click="mode = 'split'" title="分屏"><Columns2 :size="13" /></button>
            <button :class="['mode', { on: mode === 'preview' }]" @click="mode = 'preview'" title="仅预览"><Eye :size="13" /></button>
          </div>
          <button class="ui-btn ui-btn--sm" @click="togglePin" :title="active.pinned ? '取消置顶' : '置顶'">
            <Pin :size="12" :class="{ 'pin-on': active.pinned }" />
          </button>
          <button class="ui-btn ui-btn--sm" @click="exportNote" title="导出 Markdown">
            <Download :size="12" />
          </button>
          <button class="ui-btn ui-btn--sm ui-btn--danger" @click="removeNote" title="删除">
            <Trash2 :size="12" />
          </button>
        </div>
      </header>

      <div class="ws-body" :class="mode">
        <div v-if="mode !== 'preview'" class="ws-pane">
          <textarea
            ref="editorRef"
            v-model="active.content"
            class="ws-textarea"
            placeholder="用 Markdown 写下想法…  支持 # 标题、- 列表、> 引用、``` 代码块"
            spellcheck="false"
            @keydown.tab.prevent="insertTab"
          ></textarea>
        </div>
        <div v-if="mode !== 'edit'" class="ws-pane ws-preview">
          <article class="md" v-html="rendered"></article>
        </div>
      </div>

      <footer class="ws-ft">
        <span>{{ stats.chars }} 字符 · {{ stats.words }} 词 · {{ stats.lines }} 行</span>
        <span class="ws-saved">
          <Check :size="11" /> {{ savedLabel }}
        </span>
      </footer>
    </section>

    <section v-else class="ws-editor ws-blank">
      <div class="ui-empty">
        <div class="ui-empty-icon">📝</div>
        <div class="ui-empty-title">还没有打开任何笔记</div>
        <div class="ui-empty-desc">新建一篇，或从左侧选择已有笔记。内容保存在本地浏览器，不会上传。</div>
        <button class="ui-btn ui-btn--primary" style="margin-top: 8px" @click="createNote">
          <Plus :size="14" /> 新建笔记
        </button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { marked } from 'marked'
import {
  Plus, Search, Upload, List, PenLine, Columns2, Eye, Pin, Download, Trash2, Check,
} from 'lucide-vue-next'

interface Note {
  id: string
  title: string
  content: string
  pinned?: boolean
  updatedAt: number
}

const KEY = 'hhs:workspace:notes'
const notes = ref<Note[]>([])
const activeId = ref('')
const query = ref('')
const mode = ref<'edit' | 'split' | 'preview'>('split')
const savedLabel = ref('已保存')
const isMobile = ref(window.innerWidth < 900)
const showList = ref(false)
const fileRef = ref<HTMLInputElement>()
const editorRef = ref<HTMLTextAreaElement>()
let saveTimer: number | undefined

const active = computed(() => notes.value.find((n) => n.id === activeId.value) || null)

const filteredNotes = computed(() => {
  const q = query.value.trim().toLowerCase()
  return [...notes.value]
    .filter((n) => !q || n.title.toLowerCase().includes(q) || n.content.toLowerCase().includes(q))
    .sort((a, b) => Number(b.pinned || false) - Number(a.pinned || false) || b.updatedAt - a.updatedAt)
})

const rendered = computed(() => {
  if (!active.value) return ''
  try {
    return marked.parse(active.value.content || '', { async: false }) as string
  } catch {
    return '<p>渲染失败</p>'
  }
})

const stats = computed(() => {
  const text = active.value?.content || ''
  const words = text.trim() ? text.trim().split(/\s+/).length : 0
  return { chars: text.length, words, lines: text ? text.split('\n').length : 0 }
})

function persist() {
  localStorage.setItem(KEY, JSON.stringify(notes.value))
  savedLabel.value = '已保存 ' + new Date().toLocaleTimeString().slice(0, 5)
}

function scheduleSave() {
  savedLabel.value = '保存中…'
  window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(persist, 500)
}

function load() {
  try {
    const raw = localStorage.getItem(KEY)
    const parsed = raw ? JSON.parse(raw) : []
    notes.value = Array.isArray(parsed) ? parsed : []
  } catch {
    notes.value = []
  }
  if (notes.value.length) activeId.value = notes.value[0].id
  else createNote()
}

function createNote() {
  const now = Date.now()
  const note: Note = {
    id: 'n' + now.toString(36),
    title: '未命名笔记',
    content: '',
    updatedAt: now,
  }
  notes.value.unshift(note)
  activeId.value = note.id
  persist()
  nextTick(() => editorRef.value?.focus())
}

function selectNote(id: string) {
  activeId.value = id
  if (isMobile.value) showList.value = false
}

function togglePin() {
  if (!active.value) return
  active.value.pinned = !active.value.pinned
  persist()
}

function removeNote() {
  if (!active.value) return
  if (!confirm(`删除笔记「${active.value.title || '未命名'}」？`)) return
  notes.value = notes.value.filter((n) => n.id !== activeId.value)
  activeId.value = notes.value[0]?.id || ''
  if (!notes.value.length) createNote()
  persist()
}

function exportNote() {
  if (!active.value) return
  const blob = new Blob([`# ${active.value.title}\n\n${active.value.content}`], { type: 'text/markdown;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${active.value.title || 'note'}.md`
  a.click()
  URL.revokeObjectURL(a.href)
}

function importFile() { fileRef.value?.click() }

function onFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    const text = String(reader.result || '')
    const title = file.name.replace(/\.(md|markdown|txt)$/i, '')
    const note: Note = { id: 'n' + Date.now().toString(36), title, content: text, updatedAt: Date.now() }
    notes.value.unshift(note)
    activeId.value = note.id
    persist()
  }
  reader.readAsText(file)
  ;(e.target as HTMLInputElement).value = ''
}

function insertTab(e: KeyboardEvent) {
  const el = e.target as HTMLTextAreaElement
  const start = el.selectionStart
  el.setRangeText('  ', start, el.selectionEnd, 'end')
  if (active.value) active.value.content = el.value
}

function fmtTime(ts: number) {
  const diff = Date.now() - ts
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return new Date(ts).toLocaleDateString()
}

watch(
  () => active.value?.content,
  () => { if (active.value) { active.value.updatedAt = Date.now(); scheduleSave() } },
)
watch(() => active.value?.title, () => { if (active.value) scheduleSave() })

function onResize() { isMobile.value = window.innerWidth < 900 }

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.clearTimeout(saveTimer)
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
.ws { height: 100%; display: flex; overflow: hidden; background: var(--bg); }

/* 列表 */
.ws-list {
  width: 268px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-light);
  background: var(--surface);
}
.ws-list.hidden { display: none; }

.ws-list-hd {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 14px 10px;
}
.ws-list-title { font-size: 13px; font-weight: 700; }
.ws-list-title em {
  font-style: normal;
  font-size: 10px;
  color: var(--text3);
  background: var(--surface-alt);
  border-radius: var(--r-full);
  padding: 1px 7px;
  margin-left: 5px;
}

.ws-search {
  display: flex; align-items: center; gap: 7px;
  margin: 0 12px 8px;
  height: 32px; padding: 0 10px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  background: var(--bg);
  color: var(--text3);
}
.ws-search:focus-within { border-color: var(--primary); }
.ws-search input { flex: 1; min-width: 0; border: none; outline: none; background: transparent; color: var(--text); font-size: 12.5px; }

.ws-notes { flex: 1; overflow-y: auto; padding: 0 8px 8px; display: flex; flex-direction: column; gap: 2px; }

.ws-note {
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  border-radius: var(--r-sm);
  padding: 9px 10px;
  transition: background var(--t-fast);
}
.ws-note:hover { background: var(--surface-alt); }
.ws-note.active { background: var(--primary-soft); }
.ws-note.active .ws-note-title { color: var(--primary); }
.ws-note-top { display: flex; align-items: center; gap: 5px; }
.pin { font-size: 9px; }
.ws-note-title {
  font-size: 12.5px;
  font-weight: 560;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ws-note-meta { display: flex; gap: 9px; font-size: 10px; color: var(--text3); margin-top: 3px; }

.ws-empty { padding: 24px 10px; text-align: center; font-size: 11.5px; color: var(--text3); }
.ws-list-ft { padding: 10px; border-top: 1px solid var(--border-light); }

/* 编辑器 */
.ws-editor { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.ws-blank { align-items: center; justify-content: center; }

.ws-hd {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-light);
  background: var(--surface);
  flex-shrink: 0;
}
.ws-title-inp {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text);
  font-size: 15px;
  font-weight: 680;
  letter-spacing: -0.01em;
}
.ws-title-inp::placeholder { color: var(--text3); font-weight: 500; }

.ws-hd-actions { display: flex; align-items: center; gap: 5px; flex-shrink: 0; }

.mode-group {
  display: flex;
  gap: 1px;
  padding: 2px;
  border-radius: var(--r-sm);
  background: var(--surface-alt);
  margin-right: 4px;
}
.mode {
  width: 26px; height: 24px;
  display: grid; place-items: center;
  border: none; border-radius: 6px;
  background: transparent;
  color: var(--text3);
  transition: all var(--t-fast);
}
.mode.on { background: var(--surface); color: var(--primary); box-shadow: var(--shadow-sm); }

.ws-body { flex: 1; display: flex; min-height: 0; }
.ws-body.edit .ws-pane, .ws-body.preview .ws-pane { flex: 1; }
.ws-pane { flex: 1; min-width: 0; display: flex; }
.ws-body.split .ws-pane:first-child { border-right: 1px solid var(--border-light); }

.ws-textarea {
  flex: 1;
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.85;
  padding: 22px 26px;
}

.ws-preview { overflow-y: auto; background: var(--surface-2); }
.ws-preview .md { padding: 22px 30px; max-width: 760px; margin: 0 auto; width: 100%; }

.ws-ft {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  border-top: 1px solid var(--border-light);
  background: var(--surface);
  font-size: 10.5px;
  color: var(--text3);
  flex-shrink: 0;
}
.ws-saved { display: flex; align-items: center; gap: 4px; }
.pin-on { color: var(--primary); }

/* Markdown 排版 */
.md :deep(h1), .md :deep(h2), .md :deep(h3) {
  font-weight: 700;
  letter-spacing: -0.015em;
  line-height: 1.35;
  margin: 1.4em 0 0.6em;
  color: var(--text);
}
.md :deep(h1) { font-size: 1.7em; }
.md :deep(h2) { font-size: 1.32em; padding-bottom: 0.3em; border-bottom: 1px solid var(--border-light); }
.md :deep(h3) { font-size: 1.12em; }
.md :deep(p) { margin: 0.75em 0; line-height: 1.85; color: var(--text); }
.md :deep(ul), .md :deep(ol) { margin: 0.7em 0; padding-left: 1.5em; }
.md :deep(li) { margin: 0.3em 0; line-height: 1.75; }
.md :deep(blockquote) {
  margin: 1em 0;
  padding: 0.6em 1em;
  border-left: 3px solid var(--primary);
  background: var(--primary-soft);
  border-radius: 0 var(--r-sm) var(--r-sm) 0;
  color: var(--text2);
}
.md :deep(code) { background: var(--surface-alt); color: var(--primary); font-size: 0.88em; }
.md :deep(pre) { background: var(--bg); border: 1px solid var(--border-light); margin: 1em 0; }
.md :deep(pre code) { background: transparent; color: var(--text); }
.md :deep(table) { width: 100%; border-collapse: collapse; margin: 1em 0; font-size: 12.5px; }
.md :deep(th), .md :deep(td) { border: 1px solid var(--border-light); padding: 7px 11px; text-align: left; }
.md :deep(th) { background: var(--surface-alt); font-weight: 650; }
.md :deep(img) { max-width: 100%; border-radius: var(--r-sm); }
.md :deep(a) { color: var(--primary); }
.md :deep(hr) { border: none; border-top: 1px solid var(--border-light); margin: 1.6em 0; }

@media (max-width: 900px) {
  .ws-list { position: absolute; left: 0; top: 0; bottom: 0; z-index: 60; box-shadow: var(--shadow-lg); }
  .ws-body.split .ws-pane:first-child { display: none; }
}
</style>

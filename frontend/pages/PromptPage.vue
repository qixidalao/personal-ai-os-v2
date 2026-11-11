<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <!-- 页头 -->
      <header class="ui-hero pl-hero">
        <div class="ui-hero-main">
          <div class="ui-eyebrow">PROMPT LIBRARY</div>
          <h1 class="ui-title">提示词库</h1>
          <p class="ui-sub">把常用的 System Prompt 沉淀下来。支持 <code v-pre>{{变量}}</code> 占位符，填写后一键复制成最终提示词。</p>
        </div>
        <div class="ui-head-actions">
          <button class="ui-btn" @click="load" :disabled="loading">
            <RefreshCw :size="14" :class="{ spin: loading }" /> 重新加载
          </button>
          <button class="ui-btn ui-btn--primary" @click="createPrompt">
            <Plus :size="14" /> 新建提示词
          </button>
        </div>
      </header>

      <!-- 指标 -->
      <div class="ui-grid ui-grid--3 pl-stats">
        <div class="ui-stat">
          <div class="ui-stat-label">提示词</div>
          <div class="ui-stat-value">{{ prompts.length }}</div>
          <div class="ui-stat-hint">已沉淀的 System Prompt</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label">默认项</div>
          <div class="ui-stat-value">{{ prompts.filter((p) => p.isDefault).length }}</div>
          <div class="ui-stat-hint">对话默认使用</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label">变量</div>
          <div class="ui-stat-value">{{ prompts.reduce((n, p) => n + varsOf(p).length, 0) }}</div>
          <div class="ui-stat-hint">占位符总数</div>
        </div>
      </div>

      <!-- 列表 -->
      <section class="ui-section pl-section">
        <div class="ui-section-head">
          <div>
            <div class="ui-section-title">全部提示词</div>
            <div class="ui-section-sub">点击「去对话」可直接把内容带入对话输入框。</div>
          </div>
          <div class="ui-section-actions">
            <span class="ui-chip">共 {{ prompts.length }} 条</span>
          </div>
        </div>

        <div v-if="loading" class="pl-grid">
          <div v-for="i in 4" :key="i" class="ui-skeleton" style="height: 168px"></div>
        </div>

        <div v-else-if="!prompts.length" class="ui-empty">
          <div class="ui-empty-icon">📄</div>
          <div class="ui-empty-title">提示词库是空的</div>
          <div class="ui-empty-desc">新建一条，把好用的角色设定固定下来，下次直接复用。</div>
          <button class="ui-btn ui-btn--primary" style="margin-top: 8px" @click="createPrompt">
            <Plus :size="14" /> 新建提示词
          </button>
        </div>

        <div v-else class="pl-grid">
          <article
            v-for="(p, idx) in prompts"
            :key="idx"
            class="pcard ui-card ui-card--hover"
            :class="{ default: p.isDefault }"
          >
            <div class="pcard-hd ui-card-hd">
              <div class="pcard-name ui-card-title">
                <FileText :size="14" class="pcard-icon" />
                <span>{{ p.name || '未命名' }}</span>
              </div>
              <span v-if="p.isDefault" class="ui-badge ui-badge--primary"><Star :size="9" /> 默认</span>
            </div>

            <p class="pcard-body">{{ p.content || '（空）' }}</p>

            <div v-if="varsOf(p).length" class="pcard-vars">
              <span v-for="v in varsOf(p)" :key="v" class="var-pill ui-chip">{{ v }}</span>
            </div>

            <div class="pcard-ft">
              <button class="ui-btn ui-btn--sm ui-btn--ghost" @click="copy(p)"><Copy :size="12" /> 复制</button>
              <button class="ui-btn ui-btn--sm ui-btn--ghost" @click="useInChat(p)"><MessageSquare :size="12" /> 去对话</button>
              <button v-if="!p.isDefault" class="ui-btn ui-btn--sm ui-btn--ghost" @click="setDefault(idx)"><Star :size="12" /> 设为默认</button>
              <button class="ui-btn ui-btn--sm ui-btn--ghost" @click="edit(idx)"><Pencil :size="12" /> 编辑</button>
              <button class="ui-btn ui-btn--sm ui-btn--danger pcard-del" @click="remove(idx)"><Trash2 :size="12" /> 删除</button>
            </div>
          </article>
        </div>
      </section>
    </div>

    <!-- 编辑弹窗 -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="editing !== null" class="modal-mask" @click.self="editing = null">
          <div class="modal">
            <div class="modal-hd">
              <div class="modal-title">{{ editing === -1 ? '新建提示词' : '编辑提示词' }}</div>
              <button class="ui-btn ui-btn--ghost ui-btn--icon" @click="editing = null"><X :size="15" /></button>
            </div>

            <div class="modal-bd">
              <div class="ui-field">
                <label class="ui-label">名称</label>
                <input v-model="draft.name" class="ui-input" placeholder="例如：代码审查专家" />
              </div>
              <div class="ui-field">
                <label class="ui-label">内容（System Prompt）</label>
                <textarea
                  v-model="draft.content"
                  class="ui-textarea mono"
                  rows="10"
                  placeholder="你是……&#10;&#10;可以用 {{主题}} 这样的占位符，复制时会提示填写。"
                ></textarea>
              </div>

              <div v-if="draftVars.length" class="draft-vars">
                <div class="ui-label">填写变量</div>
                <div class="var-inputs">
                  <div v-for="v in draftVars" :key="v" class="var-input">
                    <span>{{ v }}</span>
                    <input v-model="varValues[v]" class="ui-input" :placeholder="`输入 ${v}`" />
                  </div>
                </div>
              </div>

              <label class="default-row">
                <span :class="['ui-switch', { on: draft.isDefault }]" @click="draft.isDefault = !draft.isDefault"></span>
                <span>设为默认提示词</span>
              </label>

              <div class="modal-actions">
                <button class="ui-btn ui-btn--primary" @click="save"><Save :size="13" /> 保存</button>
                <button class="ui-btn" @click="editing = null">取消</button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  RefreshCw, Plus, FileText, Star, Copy, MessageSquare, Pencil, Trash2, X, Save,
} from 'lucide-vue-next'

interface Prompt {
  name: string
  content: string
  isDefault: boolean
}

const router = useRouter()
const prompts = ref<Prompt[]>([])
const loading = ref(true)
const editing = ref<number | null>(null)
const draft = ref<Prompt>({ name: '', content: '', isDefault: false })
const varValues = ref<Record<string, string>>({})
let allSettings: Record<string, any> = {}

const VAR_RE = /\{\{\s*([\w\u4e00-\u9fa5-]+)\s*\}\}/g

function varsOf(p: Prompt) {
  const set = new Set<string>()
  let m: RegExpExecArray | null
  VAR_RE.lastIndex = 0
  while ((m = VAR_RE.exec(p.content || ''))) set.add(m[1])
  return [...set]
}

const draftVars = computed(() => varsOf(draft.value))

async function load() {
  loading.value = true
  try {
    const r = await fetch('/api/v1/settings')
    allSettings = await r.json()
    const list = Array.isArray(allSettings.prompts) ? allSettings.prompts : []
    prompts.value = list.map((p: any) => ({
      name: p.name || '未命名',
      content: p.content || '',
      isDefault: !!p.isDefault,
    }))
  } catch (e) {
    console.error(e)
    prompts.value = []
  } finally {
    loading.value = false
  }
}

async function persist() {
  const r = await fetch('/api/v1/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompts: prompts.value }),
  })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  window.dispatchEvent(new CustomEvent('settings:providers-updated'))
}

function createPrompt() {
  draft.value = { name: '', content: '', isDefault: false }
  varValues.value = {}
  editing.value = -1
}

function edit(idx: number) {
  draft.value = { ...prompts.value[idx] }
  varValues.value = {}
  editing.value = idx
}

async function save() {
  if (!draft.value.name.trim()) { alert('请填写名称'); return }
  const item: Prompt = {
    name: draft.value.name.trim(),
    content: draft.value.content,
    isDefault: !!draft.value.isDefault,
  }
  if (item.isDefault) prompts.value.forEach((p) => (p.isDefault = false))

  if (editing.value === -1) prompts.value.push(item)
  else if (editing.value !== null) prompts.value[editing.value] = item

  try {
    await persist()
    editing.value = null
  } catch (e: any) {
    alert(`保存失败：${e?.message || e}`)
  }
}

async function setDefault(idx: number) {
  prompts.value.forEach((p, i) => (p.isDefault = i === idx))
  try { await persist() } catch (e: any) { alert(`保存失败：${e?.message || e}`) }
}

async function remove(idx: number) {
  if (!confirm(`删除提示词「${prompts.value[idx].name}」？`)) return
  prompts.value.splice(idx, 1)
  try { await persist() } catch (e: any) { alert(`删除失败：${e?.message || e}`) }
}

async function copy(p: Prompt) {
  const vars = varsOf(p)
  let text = p.content
  if (vars.length) {
    const values: Record<string, string> = {}
    for (const v of vars) {
      const input = prompt(`请填写变量 ${v}（留空则保留占位符）`)
      if (input) values[v] = input
    }
    text = text.replace(VAR_RE, (_, name: string) => values[name] ?? `{{${name}}}`)
  }
  try {
    await navigator.clipboard.writeText(text)
    toast('已复制到剪贴板')
  } catch {
    alert('复制失败，请手动选择文本复制')
  }
}

function useInChat(p: Prompt) {
  localStorage.setItem('hhs:prefill', p.content)
  router.push('/chat')
}

function toast(msg: string) {
  const el = document.createElement('div')
  el.textContent = msg
  el.style.cssText = `position:fixed;left:50%;bottom:34px;transform:translateX(-50%);background:var(--surface-3);color:var(--text);border:1px solid var(--border-strong);padding:9px 16px;border-radius:999px;font-size:12.5px;z-index:3000;box-shadow:var(--shadow-lg)`
  document.body.appendChild(el)
  setTimeout(() => el.remove(), 1800)
}

onMounted(load)
</script>

<style scoped>
/* ============================================================
   Prompt Library — Aurora Console
   ============================================================ */
/* 中文：============================================================ Prompt Library — Aurora Console ============================================================ */
.pl-stats { margin-bottom: 18px; }

/* ---------------- 卡片网格 ---------------- */
.pl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.pcard {
  display: flex;
  flex-direction: column;
  padding: 16px;
  border-radius: var(--r-md);
}
.pcard:hover { transform: translateY(-1px); }
.pcard.default {
  border-color: color-mix(in srgb, var(--primary) 42%, transparent);
  background:
    radial-gradient(120% 130% at 100% 0%, var(--primary-soft) 0%, transparent 60%),
    var(--surface);
}

.pcard-hd { gap: 10px; margin-bottom: 10px; }
.pcard-name { min-width: 0; font-size: 13.5px; }
.pcard-name span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pcard-icon { color: var(--primary); flex-shrink: 0; }

.pcard-body {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.72;
  color: var(--text2);
  font-family: var(--font-mono);
  white-space: pre-wrap;
  display: -webkit-box;
  -webkit-line-clamp: 5;
  line-clamp: 5;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
  min-height: 96px;
}

.pcard-vars { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 10px; }
.var-pill {
  height: 22px;
  padding: 0 9px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--accent);
  background: var(--accent-soft);
  border-color: color-mix(in srgb, var(--accent) 26%, transparent);
}

.pcard-ft {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.pcard-ft .ui-btn { color: var(--text2); }
.pcard-ft .ui-btn:hover { color: var(--text); }
.pcard-del { margin-left: auto; }

/* ---------------- 弹窗 ---------------- */
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 1500;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: var(--overlay);
  backdrop-filter: blur(5px);
}
.modal {
  width: min(94vw, 620px);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.modal-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-light);
  background: var(--grad-surface);
}
.modal-title { font-size: 14px; font-weight: 680; letter-spacing: -0.01em; }
.modal-bd { padding: 18px; overflow-y: auto; }
.mono { font-family: var(--font-mono); font-size: 12px; }
.modal-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--border-light);
}

.draft-vars { margin-bottom: 14px; }
.var-inputs { display: flex; flex-direction: column; gap: 8px; }
.var-input { display: flex; align-items: center; gap: 10px; }
.var-input span {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--accent);
  min-width: 72px;
}

.default-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  background: var(--surface-2);
  font-size: 12.5px;
  color: var(--text2);
  cursor: pointer;
  user-select: none;
}

.fade-enter-active, .fade-leave-active { transition: opacity 180ms var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* AIOS-MOBILE */
/* 中文：AIOS-MOBILE */
@media (max-width: 767px) {
  .pl-grid { grid-template-columns: minmax(0, 1fr); gap: 10px; }
  .pcard { padding: 14px; }
  .pcard-body { min-height: 0; -webkit-line-clamp: 4; line-clamp: 4; }
  .pcard-ft { gap: 4px; }
  .pcard-ft .ui-btn { min-height: 36px; }
  .pcard-del { margin-left: 0; }
  .var-input { flex-direction: column; align-items: stretch; gap: 4px; }
  .var-input span { min-width: 0; }
  .modal-mask { padding: 12px; }
  .modal { width: 100%; max-height: 88vh; }
  .modal-hd { padding: 12px 14px; }
  .modal-bd { padding: 14px; }
}
/* /AIOS-MOBILE */
/* 中文：/AIOS-MOBILE */
</style>

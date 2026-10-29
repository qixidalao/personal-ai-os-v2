<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <header class="ui-head">
        <div>
          <div class="ui-eyebrow">Prompt Library</div>
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
          class="pcard"
          :class="{ default: p.isDefault }"
        >
          <div class="pcard-hd">
            <div class="pcard-name">
              <FileText :size="14" class="pcard-icon" />
              <span>{{ p.name || '未命名' }}</span>
            </div>
            <span v-if="p.isDefault" class="ui-badge ui-badge--primary"><Star :size="9" /> 默认</span>
          </div>

          <p class="pcard-body">{{ p.content || '（空）' }}</p>

          <div v-if="varsOf(p).length" class="pcard-vars">
            <span v-for="v in varsOf(p)" :key="v" class="var-pill">{{ v }}</span>
          </div>

          <div class="pcard-ft">
            <button class="link-btn" @click="copy(p)"><Copy :size="12" /> 复制</button>
            <button class="link-btn" @click="useInChat(p)"><MessageSquare :size="12" /> 去对话</button>
            <button v-if="!p.isDefault" class="link-btn" @click="setDefault(idx)"><Star :size="12" /> 设为默认</button>
            <button class="link-btn" @click="edit(idx)"><Pencil :size="12" /> 编辑</button>
            <button class="link-btn danger" @click="remove(idx)"><Trash2 :size="12" /> 删除</button>
          </div>
        </article>
      </div>
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
.pl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: 14px;
}

.pcard {
  display: flex;
  flex-direction: column;
  padding: 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface);
  transition: border-color var(--t-mid), box-shadow var(--t-mid), transform var(--t-mid);
}
.pcard:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); transform: translateY(-1px); }
.pcard.default {
  border-color: color-mix(in srgb, var(--primary) 42%, transparent);
  background:
    radial-gradient(120% 130% at 100% 0%, var(--primary-soft) 0%, transparent 60%),
    var(--surface);
}

.pcard-hd { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.pcard-name { display: flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 650; min-width: 0; }
.pcard-name span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pcard-icon { color: var(--primary); flex-shrink: 0; }

.pcard-body {
  margin-top: 10px;
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
  min-height: 100px;
}

.pcard-vars { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 10px; }
.var-pill {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 1px 7px;
  border-radius: var(--r-full);
  background: var(--accent-soft);
  color: var(--accent);
}

.pcard-ft {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.link-btn {
  display: inline-flex; align-items: center; gap: 4px;
  border: none; background: transparent;
  color: var(--text3);
  font-size: 11px;
  font-weight: 560;
  transition: color var(--t-fast);
}
.link-btn:hover { color: var(--primary); }
.link-btn.danger:hover { color: var(--error); }

/* 弹窗 */
.modal-mask {
  position: fixed; inset: 0; z-index: 1500;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
  background: var(--overlay);
  backdrop-filter: blur(5px);
}
.modal {
  width: min(94vw, 620px);
  max-height: 86vh;
  display: flex; flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.modal-hd {
  display: flex; align-items: center; justify-content: space-between;
  padding: 15px 18px;
  border-bottom: 1px solid var(--border-light);
}
.modal-title { font-size: 14px; font-weight: 680; }
.modal-bd { padding: 18px; overflow-y: auto; }
.mono { font-family: var(--font-mono); font-size: 12px; }
.modal-actions { display: flex; gap: 8px; margin-top: 16px; }

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
  display: flex; align-items: center; gap: 10px;
  font-size: 12.5px;
  color: var(--text2);
  cursor: pointer;
  user-select: none;
}

.fade-enter-active, .fade-leave-active { transition: opacity 180ms var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>

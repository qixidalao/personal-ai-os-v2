<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <header class="ui-head">
        <div>
          <div class="ui-eyebrow">Personas</div>
          <h1 class="ui-title">角色档案</h1>
          <p class="ui-sub">为不同场景准备不同的人设。一键写入提示词库后，对话就会按这个人设工作。</p>
        </div>
        <div class="ui-head-actions">
          <button class="ui-btn ui-btn--primary" @click="create">
            <Plus :size="14" /> 新建角色
          </button>
        </div>
      </header>

      <div class="persona-grid">
        <article
          v-for="p in personas"
          :key="p.id"
          :class="['persona', { active: p.active }]"
        >
          <div class="persona-top">
            <div class="persona-avatar">{{ p.emoji }}</div>
            <div class="persona-id">
              <div class="persona-name">
                {{ p.name }}
                <span v-if="p.active" class="ui-badge ui-badge--primary">当前使用</span>
              </div>
              <div class="persona-role">{{ p.role || '通用助手' }}</div>
            </div>
            <div class="persona-menu">
              <button class="act" title="编辑" @click="edit(p)"><Pencil :size="13" /></button>
              <button class="act act--danger" title="删除" @click="remove(p)"><Trash2 :size="13" /></button>
            </div>
          </div>

          <p class="persona-desc">{{ p.description || '（没有描述）' }}</p>

          <pre class="persona-prompt">{{ p.systemPrompt || '（未设置系统提示词）' }}</pre>

          <div class="persona-ft">
            <button class="link-btn" :disabled="p.active" @click="activate(p)">
              <CheckCircle2 :size="12" /> {{ p.active ? '使用中' : '设为当前' }}
            </button>
            <button class="link-btn" @click="applyToPrompts(p)">
              <Upload :size="12" /> 写入提示词库
            </button>
            <button class="link-btn" @click="chatWith(p)">
              <MessageSquare :size="12" /> 用它对话
            </button>
          </div>
        </article>

        <button class="persona persona--new" @click="create">
          <div class="new-icon"><Plus :size="20" /></div>
          <div class="new-title">新建角色</div>
          <div class="new-desc">比如「代码审查」「文案润色」「学习教练」</div>
        </button>
      </div>

      <section class="ui-card" style="margin-top: 20px">
        <div class="ui-card-hd">
          <div>
            <div class="ui-card-title"><Activity :size="15" /> 使用概况</div>
            <div class="ui-card-desc">来自后端运行时的真实统计。</div>
          </div>
        </div>
        <div class="stats">
          <div class="st" v-for="s in stats" :key="s.label">
            <div class="st-value">{{ s.value }}</div>
            <div class="st-label">{{ s.label }}</div>
          </div>
        </div>
      </section>
    </div>

    <!-- 编辑弹窗 -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="editing" class="modal-mask" @click.self="editing = false">
          <div class="modal">
            <div class="modal-hd">
              <div class="modal-title">{{ draft.id ? '编辑角色' : '新建角色' }}</div>
              <button class="ui-btn ui-btn--ghost ui-btn--icon" @click="editing = false"><X :size="15" /></button>
            </div>
            <div class="modal-bd">
              <div class="row">
                <div class="ui-field" style="flex: 0 0 88px">
                  <label class="ui-label">图标</label>
                  <input v-model="draft.emoji" class="ui-input emoji-inp" maxlength="2" />
                </div>
                <div class="ui-field" style="flex: 1">
                  <label class="ui-label">名称</label>
                  <input v-model="draft.name" class="ui-input" placeholder="例如：代码审查官" />
                </div>
              </div>
              <div class="ui-field">
                <label class="ui-label">角色定位</label>
                <input v-model="draft.role" class="ui-input" placeholder="例如：资深后端工程师" />
              </div>
              <div class="ui-field">
                <label class="ui-label">一句话描述</label>
                <input v-model="draft.description" class="ui-input" placeholder="这个角色擅长什么？" />
              </div>
              <div class="ui-field">
                <label class="ui-label">系统提示词</label>
                <textarea v-model="draft.systemPrompt" class="ui-textarea mono" rows="8" placeholder="你是……请始终……"></textarea>
              </div>
              <div class="modal-actions">
                <button class="ui-btn ui-btn--primary" @click="save"><Save :size="13" /> 保存</button>
                <button class="ui-btn" @click="editing = false">取消</button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import {
  Plus, Pencil, Trash2, CheckCircle2, Upload, MessageSquare, Activity, X, Save,
} from 'lucide-vue-next'

interface Persona {
  id: string
  emoji: string
  name: string
  role: string
  description: string
  systemPrompt: string
  active?: boolean
}

const KEY = 'hhs:personas'
const router = useRouter()
const createChat = inject<any>('createChat', null)

const personas = ref<Persona[]>([])
const editing = ref(false)
const draft = ref<Persona>(emptyDraft())
const stats = ref<any[]>([])

function emptyDraft(): Persona {
  return { id: '', emoji: '🧑‍💻', name: '', role: '', description: '', systemPrompt: '' }
}

function seed(): Persona[] {
  return [
    {
      id: 'p-default',
      emoji: '🧠',
      name: '通用助手',
      role: 'Personal AI OS 默认人格',
      description: '平衡型助手，回答简洁、先给结论再给细节。',
      systemPrompt: '你是 Personal AI OS 的 AI 助手。回答简洁准确，优先给出结论，再补充必要细节。不确定时明确说明。',
      active: true,
    },
    {
      id: 'p-code',
      emoji: '🛠️',
      name: '代码审查官',
      role: '资深全栈工程师',
      description: '关注正确性、边界条件与可维护性，直接给可运行的改法。',
      systemPrompt: '你是资深全栈工程师，负责代码审查。优先指出真正的缺陷（正确性、边界条件、并发、安全），再谈风格。给出的修改必须可以直接运行。',
    },
    {
      id: 'p-writer',
      emoji: '✍️',
      name: '文案润色',
      role: '中文写作编辑',
      description: '把口语化表达改成干净利落的中文，保留原意。',
      systemPrompt: '你是中文写作编辑。在保留原意与信息量的前提下，把文字改得更准确、更简洁、更有节奏。不要堆砌形容词。',
    },
  ]
}

function load() {
  try {
    const raw = localStorage.getItem(KEY)
    const parsed = raw ? JSON.parse(raw) : null
    personas.value = Array.isArray(parsed) && parsed.length ? parsed : seed()
  } catch {
    personas.value = seed()
  }
  if (!personas.value.some((p) => p.active) && personas.value.length) personas.value[0].active = true
}

function persist() {
  localStorage.setItem(KEY, JSON.stringify(personas.value))
}

function create() {
  draft.value = emptyDraft()
  editing.value = true
}

function edit(p: Persona) {
  draft.value = { ...p }
  editing.value = true
}

function save() {
  if (!draft.value.name.trim()) { alert('请填写名称'); return }
  if (draft.value.id) {
    const i = personas.value.findIndex((p) => p.id === draft.value.id)
    if (i >= 0) personas.value[i] = { ...draft.value }
  } else {
    personas.value.push({ ...draft.value, id: 'p' + Date.now().toString(36), active: false })
  }
  persist()
  editing.value = false
}

function remove(p: Persona) {
  if (!confirm(`删除角色「${p.name}」？`)) return
  personas.value = personas.value.filter((x) => x.id !== p.id)
  if (p.active && personas.value.length) personas.value[0].active = true
  persist()
}

function activate(p: Persona) {
  personas.value.forEach((x) => (x.active = x.id === p.id))
  persist()
}

async function applyToPrompts(p: Persona) {
  try {
    const r = await fetch('/api/v1/settings')
    const s = await r.json()
    const prompts: any[] = Array.isArray(s.prompts) ? s.prompts : []
    const next = prompts.map((x) => ({ ...x, isDefault: false }))
    const existing = next.findIndex((x) => x.name === p.name)
    const item = { name: p.name, content: p.systemPrompt, isDefault: true }
    if (existing >= 0) next[existing] = item
    else next.push(item)

    const put = await fetch('/api/v1/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompts: next }),
    })
    if (!put.ok) throw new Error(`HTTP ${put.status}`)
    toast(`「${p.name}」已写入提示词库并设为默认`)
  } catch (e: any) {
    alert(`写入失败：${e?.message || e}`)
  }
}

function chatWith(p: Persona) {
  localStorage.setItem('hhs:prefill', p.systemPrompt)
  if (createChat) createChat()
  else router.push('/chat')
}

function toast(msg: string) {
  const el = document.createElement('div')
  el.textContent = msg
  el.style.cssText = `position:fixed;left:50%;bottom:34px;transform:translateX(-50%);background:var(--surface-3);color:var(--text);border:1px solid var(--border-strong);padding:9px 16px;border-radius:999px;font-size:12.5px;z-index:3000;box-shadow:var(--shadow-lg)`
  document.body.appendChild(el)
  setTimeout(() => el.remove(), 2000)
}

async function loadStats() {
  try {
    const [st, se, sk, tl] = await Promise.all([
      fetch('/api/v1/status').then((r) => r.json()).catch(() => ({})),
      fetch('/api/v1/sessions').then((r) => r.json()).catch(() => ({})),
      fetch('/api/v1/skills').then((r) => r.json()).catch(() => ({})),
      fetch('/api/v1/tools').then((r) => r.json()).catch(() => ({})),
    ])
    stats.value = [
      { label: '会话总数', value: (se.sessions || []).length },
      { label: '工具数量', value: (tl.tools || []).length },
      { label: '技能数量', value: (sk.skills || []).length },
      { label: '运行版本', value: st.version || '—' },
    ]
  } catch { /* ignore */ }
}

onMounted(() => {
  load()
  loadStats()
})
</script>

<style scoped>
.persona-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
  gap: 14px;
}

.persona {
  display: flex;
  flex-direction: column;
  padding: 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-lg);
  background: var(--surface);
  text-align: left;
  transition: border-color var(--t-mid), box-shadow var(--t-mid), transform var(--t-mid);
}
.persona:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); transform: translateY(-1px); }
.persona.active {
  border-color: color-mix(in srgb, var(--primary) 46%, transparent);
  background:
    radial-gradient(120% 130% at 0% 0%, var(--primary-soft) 0%, transparent 58%),
    var(--surface);
}

.persona-top { display: flex; align-items: center; gap: 11px; }
.persona-avatar {
  width: 40px; height: 40px;
  border-radius: var(--r-md);
  display: grid; place-items: center;
  font-size: 20px;
  background: var(--surface-alt);
  flex-shrink: 0;
}
.persona.active .persona-avatar { background: var(--primary-soft); }
.persona-id { flex: 1; min-width: 0; }
.persona-name {
  display: flex; align-items: center; gap: 7px;
  font-size: 13.5px;
  font-weight: 660;
  letter-spacing: -0.01em;
}
.persona-role { font-size: 11px; color: var(--text3); margin-top: 1px; }
.persona-menu { display: flex; gap: 2px; }

.act {
  width: 26px; height: 26px;
  display: grid; place-items: center;
  border: none; border-radius: 6px;
  background: transparent;
  color: var(--text3);
  transition: all var(--t-fast);
}
.act:hover { background: var(--surface-alt); color: var(--text); }
.act--danger:hover { background: color-mix(in srgb, var(--error) 14%, transparent); color: var(--error); }

.persona-desc {
  font-size: 11.5px;
  color: var(--text2);
  line-height: 1.6;
  margin-top: 10px;
}

.persona-prompt {
  margin-top: 10px;
  font-size: 10.5px;
  line-height: 1.65;
  color: var(--text3);
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  padding: 10px;
  max-height: 84px;
  overflow: hidden;
  white-space: pre-wrap;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  line-clamp: 4;
  -webkit-box-orient: vertical;
}

.persona-ft {
  display: flex;
  align-items: center;
  gap: 13px;
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
.link-btn:hover:not(:disabled) { color: var(--primary); }
.link-btn:disabled { opacity: 0.5; cursor: default; }

.persona--new {
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-style: dashed;
  min-height: 180px;
  color: var(--text3);
  cursor: pointer;
}
.persona--new:hover { border-color: var(--primary); color: var(--primary); }
.new-icon {
  width: 40px; height: 40px;
  border-radius: var(--r-md);
  display: grid; place-items: center;
  background: var(--surface-alt);
  margin-bottom: 4px;
}
.new-title { font-size: 12.5px; font-weight: 640; }
.new-desc { font-size: 11px; }

.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
.st {
  padding: 14px;
  border-radius: var(--r-md);
  background: var(--surface-2);
  border: 1px solid var(--border-light);
}
.st-value { font-size: 20px; font-weight: 720; letter-spacing: -0.02em; }
.st-label { font-size: 10.5px; color: var(--text3); margin-top: 2px; }

/* 弹窗 */
.modal-mask {
  position: fixed; inset: 0; z-index: 1500;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
  background: var(--overlay);
  backdrop-filter: blur(5px);
}
.modal {
  width: min(94vw, 600px);
  max-height: 88vh;
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
.row { display: flex; gap: 12px; }
.emoji-inp { text-align: center; font-size: 18px; }
.mono { font-family: var(--font-mono); font-size: 12px; }
.modal-actions { display: flex; gap: 8px; margin-top: 16px; }

.fade-enter-active, .fade-leave-active { transition: opacity 180ms var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

<template>
  <div class="persona-panel">
    <!-- 角色列表（面板顶部指标 + 列表 + 新建入口） -->
    <section class="ui-section persona-section">
      <div class="ui-section-head">
        <div>
          <div class="ui-section-title">角色列表</div>
          <div class="ui-section-sub">
            为不同场景准备不同的人设。一键写入提示词库后，对话就会按这个人设工作。当前使用的角色会带「当前使用」标记。
          </div>
        </div>
        <div class="ui-section-actions">
          <span class="ui-chip">共 {{ personas.length }} 个</span>
          <button class="ui-btn ui-btn--primary ui-btn--sm" @click="create">
            <Plus :size="14" /> 新建角色
          </button>
        </div>
      </div>

      <!-- 指标 -->
      <div class="ui-grid ui-grid--3 persona-stats">
        <div class="ui-stat">
          <div class="ui-stat-label">角色</div>
          <div class="ui-stat-value">{{ personas.length }}</div>
          <div class="ui-stat-hint">已保存的人设</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label">当前使用</div>
          <div class="ui-stat-value persona-stat-sm">{{ personas.find((p) => p.active)?.name || '—' }}</div>
          <div class="ui-stat-hint">{{ personas.find((p) => p.active)?.role || '尚未选择' }}</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label">系统提示词</div>
          <div class="ui-stat-value">{{ personas.filter((p) => p.systemPrompt).length }}</div>
          <div class="ui-stat-hint">已配置人设内容</div>
        </div>
      </div>

      <div class="persona-grid">
        <article
          v-for="p in personas"
          :key="p.id"
          :class="['persona', { active: p.active }]"
          class="ui-card ui-card--hover"
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
              <button class="ui-btn ui-btn--sm ui-btn--icon ui-btn--ghost" title="编辑" @click="edit(p)"><Pencil :size="13" /></button>
              <button class="ui-btn ui-btn--sm ui-btn--icon ui-btn--ghost persona-del" title="删除" @click="remove(p)"><Trash2 :size="13" /></button>
            </div>
          </div>

          <p class="persona-desc">{{ p.description || '（没有描述）' }}</p>

          <pre class="persona-prompt">{{ p.systemPrompt || '（未设置系统提示词）' }}</pre>

          <div class="persona-ft">
            <button class="ui-btn ui-btn--sm ui-btn--ghost" :disabled="p.active" @click="activate(p)">
              <CheckCircle2 :size="12" /> {{ p.active ? '使用中' : '设为当前' }}
            </button>
            <button class="ui-btn ui-btn--sm ui-btn--ghost" @click="applyToPrompts(p)">
              <Upload :size="12" /> 写入提示词库
            </button>
            <button class="ui-btn ui-btn--sm ui-btn--ghost" @click="chatWith(p)">
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
    </section>

    <!-- 使用概况 -->
    <section class="ui-section persona-section">
      <div class="ui-section-head">
        <div>
          <div class="ui-section-title"><Activity :size="15" /> 使用概况</div>
          <div class="ui-section-sub">来自后端运行时的真实统计。</div>
        </div>
      </div>
      <div class="ui-grid ui-grid--4">
        <div class="ui-stat" v-for="s in stats" :key="s.label">
          <div class="ui-stat-label">{{ s.label }}</div>
          <div class="ui-stat-value">{{ s.value }}</div>
        </div>
      </div>
    </section>

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
  } catch { /* ignore */
  /* 中文：忽略 */ }
}

onMounted(() => {
  load()
  loadStats()
})
</script>

<style scoped>
/* ============================================================
   Persona Panel — 从 ProfilePage 提取，嵌入 Agent 页 Tab
   不再包含页面壳 .ui-page / .ui-page-inner / .ui-hero / 固定视口滚动容器
   ============================================================ */
.persona-panel { min-width: 0; }
.persona-stats { margin-bottom: 16px; }
.persona-stat-sm { font-size: 17px; letter-spacing: 0; }
.persona-section:last-of-type { margin-bottom: 0; }

/* ---------------- 角色网格 ---------------- */
.persona-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
  gap: 14px;
}

.persona {
  display: flex;
  flex-direction: column;
  padding: 16px;
  text-align: left;
  border-radius: var(--r-lg);
}
.persona:hover { transform: translateY(-1px); }
.persona.active {
  border-color: color-mix(in srgb, var(--primary) 46%, transparent);
  background:
    radial-gradient(120% 130% at 0% 0%, var(--primary-soft) 0%, transparent 58%),
    var(--surface);
}

.persona-top { display: flex; align-items: center; gap: 11px; }
.persona-avatar {
  width: 42px;
  height: 42px;
  border-radius: var(--r-md);
  display: grid;
  place-items: center;
  font-size: 21px;
  line-height: 1;
  background: var(--surface-alt);
  flex-shrink: 0;
}
.persona.active .persona-avatar { background: var(--primary-soft); }
.persona-id { flex: 1; min-width: 0; }
.persona-name {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13.5px;
  font-weight: 660;
  letter-spacing: -0.01em;
  flex-wrap: wrap;
}
.persona-role {
  font-size: 11px;
  color: var(--text3);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.persona-menu { display: flex; gap: 2px; flex-shrink: 0; }
.persona-menu .ui-btn { width: 28px; height: 28px; }
.persona-del:hover { color: var(--error); background: color-mix(in srgb, var(--error) 12%, transparent); }

.persona-desc {
  margin: 10px 0 0;
  font-size: 11.5px;
  color: var(--text2);
  line-height: 1.62;
}

.persona-prompt {
  margin: 10px 0 0;
  font-family: var(--font-mono);
  font-size: 10.5px;
  line-height: 1.7;
  color: var(--text3);
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  padding: 10px;
  max-height: 86px;
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
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.persona-ft .ui-btn { color: var(--text2); }
.persona-ft .ui-btn:hover:not(:disabled) { color: var(--text); }

.persona--new {
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--r-lg);
  background: transparent;
  min-height: 190px;
  color: var(--text3);
  cursor: pointer;
  transition: border-color var(--t-fast), color var(--t-fast), background var(--t-fast), transform var(--t-fast);
}
.persona--new:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-soft);
  transform: translateY(-1px);
}
.new-icon {
  width: 42px;
  height: 42px;
  border-radius: var(--r-md);
  display: grid;
  place-items: center;
  background: var(--surface-alt);
  margin-bottom: 4px;
}
.new-title { font-size: 12.5px; font-weight: 640; }
.new-desc { font-size: 11px; max-width: 26ch; text-align: center; line-height: 1.5; }

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
  width: min(94vw, 600px);
  max-height: 88vh;
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
.row { display: flex; gap: 12px; }
.emoji-inp { text-align: center; font-size: 18px; }
.mono { font-family: var(--font-mono); font-size: 12px; }
.modal-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--border-light);
}

.fade-enter-active, .fade-leave-active { transition: opacity 180ms var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* AIOS-MOBILE */
/* 中文：AIOS-MOBILE */
@media (max-width: 767px) {
  .persona-stats { margin-bottom: 12px; }
  .persona-grid { grid-template-columns: minmax(0, 1fr); gap: 10px; }
  .persona { padding: 14px; }
  .persona-menu .ui-btn { width: 34px; height: 34px; }
  .persona-ft .ui-btn { height: 34px; }
  .persona--new { min-height: 140px; }
  .row { flex-direction: column; gap: 0; }
  .row .ui-field { flex: 1 1 auto !important; }
  .emoji-inp { width: 100%; }
  .modal-mask { padding: 12px; }
  .modal { width: 100%; max-height: 88vh; }
  .modal-hd { padding: 12px 14px; }
  .modal-bd { padding: 14px; }
}
/* /AIOS-MOBILE */
/* 中文：/AIOS-MOBILE */
</style>

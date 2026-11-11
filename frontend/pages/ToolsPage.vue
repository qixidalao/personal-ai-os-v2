<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <!-- 页头 -->
      <header class="ui-hero tl-hero">
        <div class="ui-hero-main">
          <div class="ui-eyebrow">TOOL REGISTRY</div>
          <h1 class="ui-title">工具中心</h1>
          <p class="ui-sub">模型真正可以调用的能力清单。可按需启停、查看参数结构，并在不进入对话的情况下直接试跑。</p>
        </div>
        <div class="ui-head-actions">
          <button class="ui-btn" :disabled="loading" @click="load">
            <RefreshCw :size="14" :class="{ spin: loading }" /> 刷新
          </button>
          <button class="ui-btn" @click="expandAll = !expandAll">
            <Code2 :size="14" /> {{ expandAll ? '收起全部' : '展开全部' }}
          </button>
        </div>
      </header>

      <!-- 指标 -->
      <div class="ui-grid ui-grid--3 tl-stats">
        <div class="ui-stat">
          <div class="ui-stat-label stat-label"><Wrench :size="12" /> 注册工具</div>
          <div class="ui-stat-value">{{ tools.length }}</div>
          <div class="ui-stat-hint">Tool Registry 已注册条目</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label stat-label"><Power :size="12" /> 已启用</div>
          <div class="ui-stat-value">{{ enabledCount }}</div>
          <div class="ui-stat-hint">模型当前可调用的工具</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label stat-label"><Layers :size="12" /> 分类</div>
          <div class="ui-stat-value">{{ categories.length }}</div>
          <div class="ui-stat-hint">按能力域归类的工具族</div>
        </div>
      </div>

      <!-- 工具条 -->
      <div class="ui-toolbar tl-toolbar">
        <div class="tb-search">
          <Search :size="14" />
          <input v-model="query" class="tb-input" placeholder="搜索工具名或描述…" />
          <button v-if="query" class="tb-clear" title="清空" @click="query = ''"><X :size="12" /></button>
        </div>

        <div class="ui-seg tl-seg">
          <button :class="['ui-seg-item', { active: cat === '' }]" @click="cat = ''">全部</button>
          <button
            v-for="c in categories"
            :key="c"
            :class="['ui-seg-item', { active: cat === c }]"
            @click="cat = c"
          >{{ c }}</button>
        </div>

        <button :class="['ui-chip', { active: onlyEnabled }]" @click="onlyEnabled = !onlyEnabled">
          <Filter :size="12" /> 只看启用
        </button>

        <span class="tl-sum">显示 {{ filtered.length }} / 共 {{ tools.length }}</span>
      </div>

      <!-- 工具目录 -->
      <div v-if="loading" class="tool-grid">
        <div v-for="i in 6" :key="i" class="ui-skeleton" style="height: 138px"></div>
      </div>

      <div v-else-if="!filtered.length" class="ui-empty">
        <div class="ui-empty-icon">🧰</div>
        <div class="ui-empty-title">没有匹配的工具</div>
        <div class="ui-empty-desc">调整筛选条件，或检查后端 ToolRegistry 是否正常注册。</div>
      </div>

      <div v-else class="tool-grid">
        <article v-for="t in filtered" :key="t.name" :class="['ui-card', 'ui-card--hover', 'tcard', { off: !t.enabled }]">
          <div class="tcard-hd">
            <div class="tcard-name">
              <span class="tcard-dot" :class="t.enabled ? 'on' : 'off'"></span>
              <code>{{ t.name }}</code>
            </div>
            <div class="tcard-hd-right">
              <span class="ui-badge">{{ t.category || 'general' }}</span>
              <button
                :class="['ui-switch', { on: t.enabled }]"
                :disabled="toggling === t.name"
                @click="toggle(t)"
                :title="t.enabled ? '点击停用' : '点击启用'"
              ></button>
            </div>
          </div>

          <p class="tcard-desc">{{ t.description || '（无描述）' }}</p>

          <div v-if="t.registered === false" class="tcard-warn">
            <AlertTriangle :size="12" /> 设置中存在但未在运行时注册
          </div>

          <div class="tcard-foot">
            <button class="ui-btn ui-btn--sm ui-btn--ghost" @click="toggleSchema(t.name)">
              <Code2 :size="12" /> {{ openSchema.includes(t.name) ? '收起参数' : '查看参数' }}
            </button>
            <button class="ui-btn ui-btn--sm ui-btn--ghost" :disabled="!t.enabled" @click="openTest(t)">
              <Play :size="12" /> 试运行
            </button>
          </div>

          <Transition name="schema">
            <pre v-if="openSchema.includes(t.name)" class="tcard-schema">{{ prettySchema(t.schema) }}</pre>
          </Transition>
        </article>
      </div>
    </div>

    <!-- 试运行弹窗 -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="testTool" class="modal-mask" @click.self="testTool = null">
          <div class="modal">
            <div class="modal-hd">
              <div class="modal-hd-main">
                <div class="modal-title">试运行 <code>{{ testTool.name }}</code></div>
                <div class="modal-sub">{{ testTool.description }}</div>
              </div>
              <button class="ui-btn ui-btn--ghost ui-btn--icon" @click="testTool = null"><X :size="15" /></button>
            </div>

            <div class="modal-bd">
              <div class="ui-field">
                <label class="ui-label">参数（JSON）</label>
                <textarea
                  v-model="testArgs"
                  class="ui-textarea mono"
                  rows="6"
                  spellcheck="false"
                  :disabled="pendingApproval !== null"
                ></textarea>
                <div v-if="argError" class="err-line">{{ argError }}</div>
              </div>

              <!-- 审批卡：202 approval_required -->
              <div v-if="pendingApproval" class="approval-card" :class="'is-' + approvalState">
                <div class="approval-hd">
                  <span class="risk-badge" :class="riskClass(pendingApproval.risk)">{{ riskLabel(pendingApproval.risk) }}</span>
                  <span class="approval-title">需要审批 · <code>{{ pendingApproval.tool }}</code></span>
                </div>
                <div class="approval-meta">
                  <span class="approval-expire" :class="{ expired: approvalExpired }">
                    {{ approvalExpired ? '审批已过期，请重新执行' : approvalExpireHint }}
                  </span>
                  <span v-if="pendingApproval.args_hash" class="approval-hash" :title="pendingApproval.args_hash">#{{ shortHash(pendingApproval.args_hash) }}</span>
                  <span v-if="pendingApproval.session_id" class="approval-session">会话 {{ shortSession(pendingApproval.session_id) }}</span>
                </div>
                <pre class="approval-args">{{ prettyApprovalArgs }}</pre>
                <div v-if="approvalError" class="approval-err">{{ approvalError }}</div>
                <div class="approval-actions">
                  <label v-if="approvalState === 'pending'" class="approval-remember">
                    <input v-model="rememberSession" type="checkbox" /> 本会话记住该工具
                  </label>
                  <span v-if="approvalState === 'denied'" class="approval-done bad">已拒绝</span>
                  <span v-if="approvalState === 'approved'" class="approval-done ok">已批准 · 已重新调用工具</span>
                  <button
                    v-if="approvalState === 'pending'"
                    class="ui-btn ui-btn--primary ui-btn--sm"
                    :disabled="approvalBusy || approvalExpired"
                    @click="approveAndRun"
                  >
                    <Play :size="12" /> {{ approvalBusy ? '处理中…' : '批准并执行' }}
                  </button>
                  <button
                    v-if="approvalState === 'pending'"
                    class="ui-btn ui-btn--sm"
                    :disabled="approvalBusy"
                    @click="denyApproval"
                  >拒绝</button>
                  <button
                    v-if="approvalState === 'approved'"
                    class="ui-btn ui-btn--sm"
                    :disabled="approvalBusy"
                    @click="retryApproved"
                  ><Play :size="12" /> 重试执行</button>
                  <button
                    v-if="approvalState === 'denied' || (approvalState === 'pending' && approvalExpired)"
                    class="ui-btn ui-btn--sm ui-btn--ghost"
                    @click="dismissApproval"
                  >重新编辑</button>
                </div>
              </div>

              <div class="modal-actions">
                <button class="ui-btn ui-btn--primary" :disabled="running || pendingApproval !== null" @click="runTest">
                  <Play :size="13" /> {{ running ? '执行中…' : '执行' }}
                </button>
                <button class="ui-btn" :disabled="pendingApproval !== null" @click="fillExample">填充示例</button>
                <span v-if="pendingApproval" class="modal-note">审批处理中，参数已锁定</span>
              </div>

              <template v-if="testResult !== null">
                <div class="ui-label" style="margin-top: 14px">返回结果</div>
                <pre class="result" :class="{ bad: testFailed }">{{ testResult }}</pre>
              </template>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  RefreshCw, Code2, Wrench, Power, Layers, Search, X, Filter, Play, AlertTriangle,
} from 'lucide-vue-next'

interface Tool {
  name: string
  description?: string
  category?: string
  enabled: boolean
  schema?: any
  registered?: boolean
}

interface ApprovalInfo {
  id: string
  tool: string
  args_json?: any
  args_hash?: string
  risk?: string
  status?: string
  created_at?: string | null
  expires_at?: string | null
  session_id?: string | null
}

type ApprovalState = 'pending' | 'approved' | 'denied'

const tools = ref<Tool[]>([])
const loading = ref(true)
const query = ref('')
const cat = ref('')
const onlyEnabled = ref(false)
const toggling = ref('')
const openSchema = ref<string[]>([])
const expandAll = ref(false)

const testTool = ref<Tool | null>(null)
const testArgs = ref('{}')
const testResult = ref<string | null>(null)
const testFailed = ref(false)
const running = ref(false)
const argError = ref('')

const pendingApproval = ref<ApprovalInfo | null>(null)
const approvalState = ref<ApprovalState>('pending')
const approvalError = ref('')
const approvalBusy = ref(false)
const rememberSession = ref(true)
const nowTs = ref(Date.now())
let approvalTimer: ReturnType<typeof setInterval> | null = null

const categories = computed(() => {
  const set = new Set<string>()
  for (const t of tools.value) if (t.category) set.add(t.category)
  return [...set].sort()
})

const enabledCount = computed(() => tools.value.filter((t) => t.enabled).length)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  return tools.value.filter((t) => {
    if (cat.value && t.category !== cat.value) return false
    if (onlyEnabled.value && !t.enabled) return false
    if (!q) return true
    return t.name.toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q)
  })
})

function prettySchema(schema: any) {
  if (!schema) return '（无参数）'
  try {
    return JSON.stringify(schema, null, 2)
  } catch {
    return String(schema)
  }
}

function toggleSchema(name: string) {
  const i = openSchema.value.indexOf(name)
  if (i >= 0) openSchema.value.splice(i, 1)
  else openSchema.value.push(name)
}

async function load() {
  loading.value = true
  try {
    const r = await fetch('/api/v1/tools')
    const data = await r.json()
    tools.value = data.tools || []
    if (expandAll.value) openSchema.value = tools.value.map((t) => t.name)
  } catch (e) {
    console.error(e)
    tools.value = []
  } finally {
    loading.value = false
  }
}

async function toggle(t: Tool) {
  toggling.value = t.name
  try {
    const sres = await fetch('/api/v1/settings')
    const settings = await sres.json()
    const list: any[] = Array.isArray(settings.agentTools) ? settings.agentTools : []
    const next = list.map((item) =>
      item.name === t.name ? { ...item, enabled: !t.enabled } : item,
    )
    if (!next.some((item) => item.name === t.name)) {
      next.push({ name: t.name, description: t.description || '', schema: JSON.stringify(t.schema || {}), enabled: !t.enabled, showSchema: false })
    }
    const r = await fetch('/api/v1/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agentTools: next }),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    t.enabled = !t.enabled
  } catch (e: any) {
    alert(`切换失败：${e?.message || e}`)
  } finally {
    toggling.value = ''
  }
}

function openTest(t: Tool) {
  testTool.value = t
  testResult.value = null
  testFailed.value = false
  argError.value = ''
  testArgs.value = buildExample(t.schema)
  resetApproval()
  rememberSession.value = true
}

function buildExample(schema: any) {
  const props = schema?.properties
  if (!props || typeof props !== 'object') return '{}'
  const out: Record<string, any> = {}
  for (const [key, val] of Object.entries<any>(props)) {
    const type = val?.type
    out[key] =
      type === 'number' || type === 'integer' ? 0 :
      type === 'boolean' ? false :
      type === 'array' ? [] :
      type === 'object' ? {} : ''
  }
  return JSON.stringify(out, null, 2)
}

function fillExample() {
  if (!testTool.value) return
  testArgs.value = buildExample(testTool.value.schema)
  argError.value = ''
}

/* ---------------- 审批（202 approval_required） ---------------- */
function toMs(value?: string | null) {
  if (!value) return null
  const t = new Date(value).getTime()
  return Number.isNaN(t) ? null : t
}
function pad2(n: number) {
  return String(n).padStart(2, '0')
}
function fmtAbs(value?: string | null) {
  const ms = toMs(value)
  if (ms === null) return '—'
  const d = new Date(ms)
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}
function shortHash(value?: string | null, max = 10) {
  if (!value) return ''
  return value.length > max ? value.slice(0, max) : value
}
function shortSession(value?: string | null, max = 12) {
  if (!value) return ''
  return value.length > max ? `${value.slice(0, max)}…` : value
}
function riskLabel(risk?: string) {
  const key = String(risk || '').toLowerCase()
  if (!key) return '需审批'
  if (key === 'high' || key === 'critical') return '高风险'
  if (key === 'medium' || key === 'mid') return '中风险'
  if (key === 'low') return '低风险'
  return `风险 ${risk}`
}
function riskClass(risk?: string) {
  const key = String(risk || '').toLowerCase()
  if (key === 'high' || key === 'critical') return 'risk-high'
  if (key === 'medium' || key === 'mid') return 'risk-mid'
  if (key === 'low') return 'risk-low'
  return 'risk-unknown'
}
const approvalExpired = computed(() => {
  const ms = toMs(pendingApproval.value?.expires_at)
  return ms !== null && ms <= nowTs.value
})
const approvalExpireHint = computed(() => {
  const ms = toMs(pendingApproval.value?.expires_at)
  if (ms === null) return '该审批未设置过期时间'
  const left = ms - nowTs.value
  if (left <= 0) return '审批已过期，请重新执行'
  const mins = Math.ceil(left / 60000)
  const abs = fmtAbs(pendingApproval.value?.expires_at)
  return mins <= 1 ? `1 分钟内过期 · ${abs}` : `${mins} 分钟后过期 · ${abs}`
})
const prettyApprovalArgs = computed(() => {
  const raw = pendingApproval.value?.args_json
  if (raw === null || raw === undefined || raw === '') return '（无参数）'
  if (typeof raw === 'string') {
    try { return JSON.stringify(JSON.parse(raw), null, 2) } catch { return raw }
  }
  try { return JSON.stringify(raw, null, 2) } catch { return String(raw) }
})

async function readJson(res: Response): Promise<any> {
  try { return await res.json() } catch { return null }
}
function detailOf(data: any, status: number) {
  const detail = data?.detail || data?.message
  return typeof detail === 'string' ? detail : `HTTP ${status}`
}
function resetApproval() {
  pendingApproval.value = null
  approvalState.value = 'pending'
  approvalError.value = ''
  approvalBusy.value = false
}
function dismissApproval() {
  resetApproval()
}
function postToolCall(args: any, approvalId?: string) {
  const body: Record<string, any> = { name: testTool.value?.name || '', arguments: args }
  if (approvalId) body.approval_id = approvalId
  return fetch('/api/v1/tools/call', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}
async function executeWithApproval(approvalId: string) {
  let args: any
  try { args = JSON.parse(testArgs.value || '{}') } catch { args = {} }
  const retry = await postToolCall(args, approvalId)
  const retryData = await readJson(retry)
  if (!retry.ok || retryData?.ok === false) {
    testFailed.value = true
    testResult.value = typeof retryData?.detail === 'string' ? retryData.detail : JSON.stringify(retryData, null, 2)
    approvalState.value = 'approved'
    approvalError.value = `批准后执行失败：${detailOf(retryData, retry.status)}`
    return
  }
  testFailed.value = false
  testResult.value = JSON.stringify(retryData, null, 2)
  resetApproval()
}
async function approveAndRun() {
  const approval = pendingApproval.value
  if (!approval || approvalBusy.value || approvalExpired.value) return
  approvalBusy.value = true
  approvalError.value = ''
  try {
    const body: Record<string, any> = { decision: 'approve' }
    if (rememberSession.value) body.remember = 'session'
    const r = await fetch(`/api/v1/approvals/${encodeURIComponent(approval.id)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await readJson(r)
    if (!r.ok) throw new Error(detailOf(data, r.status))
    approvalState.value = 'approved'
    await executeWithApproval(approval.id)
  } catch (e: any) {
    approvalState.value = 'pending'
    approvalError.value = `审批失败：${e?.message || e}`
  } finally {
    approvalBusy.value = false
  }
}
async function retryApproved() {
  const approval = pendingApproval.value
  if (!approval || approvalBusy.value) return
  approvalBusy.value = true
  approvalError.value = ''
  try {
    await executeWithApproval(approval.id)
  } catch (e: any) {
    approvalError.value = `重试执行失败：${e?.message || e}`
  } finally {
    approvalBusy.value = false
  }
}
async function denyApproval() {
  const approval = pendingApproval.value
  if (!approval || approvalBusy.value) return
  approvalBusy.value = true
  approvalError.value = ''
  try {
    const r = await fetch(`/api/v1/approvals/${encodeURIComponent(approval.id)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: 'deny' }),
    })
    const data = await readJson(r)
    if (!r.ok) throw new Error(detailOf(data, r.status))
    approvalState.value = 'denied'
    testResult.value = null
    testFailed.value = false
  } catch (e: any) {
    approvalError.value = `拒绝失败：${e?.message || e}`
  } finally {
    approvalBusy.value = false
  }
}

async function runTest() {
  if (!testTool.value || pendingApproval.value) return
  argError.value = ''
  let args: any
  try {
    args = JSON.parse(testArgs.value || '{}')
  } catch (e: any) {
    argError.value = `JSON 解析失败：${e?.message || e}`
    return
  }
  running.value = true
  testResult.value = null
  testFailed.value = false
  resetApproval()
  try {
    const r = await postToolCall(args)
    const data = await readJson(r)
    if (r.status === 202 && data?.status === 'approval_required' && data?.approval) {
      pendingApproval.value = data.approval as ApprovalInfo
      approvalState.value = 'pending'
      approvalError.value = ''
      testResult.value = null
      return
    }
    if (!r.ok || data?.ok === false) {
      testFailed.value = true
      testResult.value = typeof data?.detail === 'string' ? data.detail : JSON.stringify(data, null, 2)
      return
    }
    testFailed.value = false
    testResult.value = JSON.stringify(data, null, 2)
  } catch (e: any) {
    testFailed.value = true
    testResult.value = `请求失败：${e?.message || e}`
  } finally {
    running.value = false
  }
}

onMounted(() => {
  load()
  approvalTimer = setInterval(() => {
    nowTs.value = Date.now()
  }, 15000)
})

onUnmounted(() => {
  if (approvalTimer) clearInterval(approvalTimer)
})
</script>

<style scoped>
/* ============================================================
   Tool Registry — Aurora Console
   ============================================================ */
/* 中文：============================================================ Tool Registry — Aurora Console ============================================================ */
.tl-hero { margin-bottom: 18px; }
.tl-stats { margin-bottom: 18px; }

.stat-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.stat-label svg { color: var(--primary); flex-shrink: 0; }

/* ---------------- 工具条 ---------------- */
.tl-toolbar { align-items: center; }

.tb-search {
  flex: 1 1 240px;
  max-width: 380px;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  padding: 0 11px;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: color-mix(in srgb, var(--bg) 62%, transparent);
  color: var(--text3);
  transition: border-color var(--t-fast), box-shadow var(--t-fast);
}
.tb-search:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-soft);
}
.tb-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text);
  font-size: 12.5px;
}
.tb-input::placeholder { color: var(--text3); }
.tb-clear {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  border: none;
  border-radius: var(--r-full);
  background: transparent;
  color: var(--text3);
}
.tb-clear:hover { color: var(--text); background: var(--surface-alt); }

.tl-seg {
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
}
.tl-seg::-webkit-scrollbar { display: none; }
.tl-seg .ui-seg-item { flex-shrink: 0; }

.tl-sum {
  margin-left: auto;
  font-size: 11px;
  color: var(--text3);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* ---------------- 工具卡 ---------------- */
.tool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 14px;
}

.tcard {
  display: flex;
  flex-direction: column;
  padding: 16px;
  border-radius: var(--r-md);
  transition: border-color var(--t-mid), box-shadow var(--t-mid), opacity var(--t-mid), transform var(--t-mid);
}
.tcard:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }
.tcard.off { opacity: 0.6; }
.tcard.off:hover { transform: none; box-shadow: none; }

.tcard-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.tcard-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.tcard-name code {
  background: transparent;
  padding: 0;
  font-family: var(--font-mono);
  font-size: 12.5px;
  font-weight: 640;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tcard-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.tcard-dot.on {
  background: var(--success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--success) 16%, transparent);
}
.tcard-dot.off { background: var(--text3); }
.tcard-hd-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.tcard-desc {
  margin-top: 9px;
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--text2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 38px;
  flex: 1;
}

.tcard-warn {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 8px;
  padding: 5px 8px;
  border-radius: var(--r-xs);
  font-size: 10.5px;
  color: var(--warn);
  background: color-mix(in srgb, var(--warn) 10%, transparent);
}

.tcard-foot {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.tcard-foot .ui-btn { color: var(--text2); }
.tcard-foot .ui-btn:hover:not(:disabled) { color: var(--text); }

.tcard-schema {
  margin: 10px 0 0;
  padding: 12px;
  max-height: 220px;
  overflow: auto;
  font-size: 10.5px;
  line-height: 1.6;
  color: var(--text2);
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: 10px;
}

.schema-enter-active, .schema-leave-active { transition: opacity var(--t-mid), transform var(--t-mid); }
.schema-enter-from, .schema-leave-to { opacity: 0; transform: translateY(-4px); }

/* ---------------- 试运行弹窗 ---------------- */
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
  width: min(94vw, 640px);
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
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-light);
  background: var(--grad-surface);
}
.modal-hd-main { min-width: 0; }
.modal-title {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  font-size: 14px;
  font-weight: 680;
  letter-spacing: -0.01em;
}
.modal-title code {
  font-size: 12px;
  color: var(--primary);
  background: var(--primary-soft);
  padding: 2px 7px;
  border-radius: var(--r-xs);
}
.modal-sub {
  margin-top: 4px;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--text3);
}
.modal-bd { padding: 18px; overflow-y: auto; }
.mono { font-family: var(--font-mono); font-size: 11.5px; }
.modal-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 14px;
  border-top: 1px solid var(--border-light);
}
.err-line { margin-top: 7px; font-size: 11.5px; color: var(--error); }
.result {
  margin: 0;
  padding: 12px;
  max-height: 300px;
  overflow: auto;
  font-size: 11px;
  line-height: 1.65;
  color: var(--text2);
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  white-space: pre-wrap;
  word-break: break-word;
}
.result.bad {
  border-color: color-mix(in srgb, var(--error) 42%, transparent);
  color: var(--error);
}

/* ---------------- 审批卡 ---------------- */
.approval-card {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-bottom: 2px;
  padding: 12px 14px;
  border: 1px solid color-mix(in srgb, var(--warn) 36%, var(--border-light));
  border-radius: var(--r-md);
  background: color-mix(in srgb, var(--warn) 7%, transparent);
}
.approval-card.is-approved {
  border-color: color-mix(in srgb, var(--success) 36%, var(--border-light));
  background: color-mix(in srgb, var(--success) 7%, transparent);
}
.approval-card.is-denied {
  border-color: color-mix(in srgb, var(--error) 32%, var(--border-light));
  background: color-mix(in srgb, var(--error) 6%, transparent);
}
.approval-hd {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.risk-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.03em;
  padding: 2px 8px;
  border-radius: var(--r-full);
  border: 1px solid transparent;
  white-space: nowrap;
}
.risk-high {
  color: var(--error);
  background: color-mix(in srgb, var(--error) 12%, transparent);
  border-color: color-mix(in srgb, var(--error) 30%, transparent);
}
.risk-mid {
  color: var(--warn);
  background: color-mix(in srgb, var(--warn) 12%, transparent);
  border-color: color-mix(in srgb, var(--warn) 30%, transparent);
}
.risk-low {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 12%, transparent);
  border-color: color-mix(in srgb, var(--success) 28%, transparent);
}
.risk-unknown {
  color: var(--text3);
  background: color-mix(in srgb, var(--text3) 10%, transparent);
  border-color: var(--border-light);
}
.approval-title { font-size: 12px; font-weight: 560; color: var(--text); }
.approval-title code {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--primary);
  background: var(--primary-soft);
  padding: 1px 6px;
  border-radius: var(--r-xs);
}
.approval-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 10.5px;
  color: var(--text3);
  font-variant-numeric: tabular-nums;
}
.approval-expire.expired { color: var(--error); }
.approval-hash,
.approval-session { font-family: var(--font-mono); font-size: 10px; }
.approval-args {
  margin: 0;
  padding: 9px 11px;
  max-height: 160px;
  overflow: auto;
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  font-family: var(--font-mono);
  font-size: 10.5px;
  line-height: 1.6;
  color: var(--text2);
  white-space: pre-wrap;
  word-break: break-word;
}
.approval-err {
  font-size: 11px;
  line-height: 1.5;
  color: var(--error);
  word-break: break-word;
}
.approval-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.approval-remember {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-right: auto;
  font-size: 11px;
  color: var(--text2);
  cursor: pointer;
}
.approval-remember input { width: 14px; height: 14px; accent-color: var(--primary); }
.approval-done { font-size: 11.5px; font-weight: 620; }
.approval-done.bad { color: var(--error); }
.approval-done.ok { color: var(--success); }
.modal-note {
  align-self: center;
  margin-left: auto;
  font-size: 10.5px;
  color: var(--text3);
}

.fade-enter-active, .fade-leave-active { transition: opacity 180ms var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* AIOS-MOBILE */
/* 中文：AIOS-MOBILE */
@media (max-width: 767px) {
  .tl-hero { margin-bottom: 16px; }
  .tl-stats { margin-bottom: 13px; }

  .tl-toolbar { gap: 8px; }
  .tb-search { flex: 1 1 100%; max-width: none; height: 40px; }
  .tl-seg { width: 100%; }
  .tl-sum { display: none; }

  .tool-grid { grid-template-columns: minmax(0, 1fr); gap: 10px; }
  .tcard { padding: 14px; }
  .tcard:hover { transform: none; box-shadow: none; }
  .tcard-desc { min-height: 0; }
  .tcard-foot .ui-btn { height: 34px; }

  .modal-mask { padding: 12px; }
  .modal { width: 100%; max-height: 88vh; }
  .modal-hd { padding: 12px 14px; }
  .modal-bd { padding: 14px; }
  .result { max-height: 240px; }

  .approval-card { padding: 11px 12px; }
  .approval-args { max-height: 140px; }
  .approval-actions { gap: 6px; }
  .approval-actions .ui-btn { min-height: 34px; }
  .approval-remember { flex: 1 1 100%; margin-right: 0; }
}
/* /AIOS-MOBILE */
/* 中文：/AIOS-MOBILE */
</style>

<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <header class="ui-hero runs-hero">
        <div class="ui-hero-main">
          <div class="ui-eyebrow">RUN TRACE</div>
          <h1 class="ui-title">执行记录</h1>
          <p class="ui-sub">每一次 run 与工具调用都会落库成审计链路：调了什么、被权限如何裁决、耗时多久、产物多大，全部可追溯。</p>
        </div>
        <div class="ui-head-actions">
          <span class="ui-badge">只读审计</span>
        </div>
      </header>

      <div class="ui-grid ui-grid--4 runs-stats">
        <div class="ui-stat">
          <div class="ui-stat-label stat-label"><Layers :size="12" /> 总运行</div>
          <div class="ui-stat-value">{{ statTotal }}</div>
          <div class="ui-stat-hint">{{ statTotalHint }}</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label stat-label"><Power :size="12" /> 成功率</div>
          <div class="ui-stat-value">{{ statRate }}</div>
          <div class="ui-stat-hint">{{ statRateHint }}</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label stat-label"><Wrench :size="12" /> 工具调用</div>
          <div class="ui-stat-value">{{ statTools }}</div>
          <div class="ui-stat-hint">{{ statToolsHint }}</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label stat-label"><AlertTriangle :size="12" /> 失败与异常</div>
          <div class="ui-stat-value">{{ statFailures }}</div>
          <div class="ui-stat-hint">{{ statFailHint }}</div>
        </div>
      </div>

      <div class="ui-toolbar runs-toolbar">
        <div class="runs-search">
          <Search :size="14" />
          <input v-model="query" class="runs-search-input" placeholder="搜索 run id / 模型 / 会话…" />
          <button v-if="query" class="runs-search-clear" title="清空搜索" @click="query = ''">
            <X :size="12" />
          </button>
        </div>

        <div class="ui-seg runs-seg">
          <button
            v-for="f in statusFilters"
            :key="f.key"
            :class="['ui-seg-item', { active: statusFilter === f.key }]"
            @click="statusFilter = f.key"
          >{{ f.label }}</button>
        </div>

        <span class="runs-count">显示 {{ filteredRuns.length }} · 已加载 {{ runs.length }} / 共 {{ total }}</span>

        <div class="runs-toolbar-btns">
          <button class="ui-btn" :disabled="exportingAll" @click="exportAllRuns">
            <Download :size="14" /> {{ exportingAll ? '导出中…' : '导出全部' }}
          </button>
          <button class="ui-btn" :disabled="loading" @click="load">
            <RefreshCw :size="14" :class="{ spin: loading }" /> 刷新
          </button>
        </div>
      </div>

      <div v-if="exportAllError" class="export-alert">
        <AlertTriangle :size="13" />
        <span class="export-alert-text">{{ exportAllError }}</span>
        <button class="ui-btn ui-btn--sm ui-btn--ghost" @click="exportAllError = ''">关闭</button>
      </div>

      <div class="runs-layout">
        <!-- ==================== 运行列表 ==================== -->
        <section class="runs-list" aria-label="运行列表">
          <div class="runs-list-head">
            <span class="runs-list-title">运行列表</span>
            <span class="runs-list-hint">
              按开始时间倒序<template v-if="isFiltering"> · 筛选仅作用于已加载页</template>
            </span>
          </div>

          <div v-if="loading" class="run-skel">
            <div v-for="i in 6" :key="i" class="ui-skeleton run-skel-row"></div>
          </div>

          <div v-else-if="loadError" class="ui-empty">
            <div class="ui-empty-icon">⚠️</div>
            <div class="ui-empty-title">运行记录加载失败</div>
            <div class="ui-empty-desc">{{ loadError }}</div>
            <button class="ui-btn ui-btn--sm" @click="load">重试</button>
          </div>

          <div v-else-if="!runs.length" class="ui-empty">
            <div class="ui-empty-icon">🛰️</div>
            <div class="ui-empty-title">还没有执行记录</div>
            <div class="ui-empty-desc">触发一次带工具调用的对话后，run、tool call 与审计事件会自动出现在这里。</div>
            <button class="ui-btn ui-btn--sm" @click="load"><RefreshCw :size="12" /> 刷新</button>
          </div>

          <div v-else-if="!filteredRuns.length" class="ui-empty">
            <div class="ui-empty-icon">🔎</div>
            <div class="ui-empty-title">当前页没有匹配的执行记录</div>
            <div class="ui-empty-desc">筛选只作用于已加载的 {{ runs.length }} 条记录，可以清空筛选或继续加载更多。</div>
            <div class="empty-actions">
              <button class="ui-btn ui-btn--sm" @click="resetFilters">清空筛选</button>
              <button v-if="hasMore" class="ui-btn ui-btn--sm" :disabled="loadingMore" @click="loadMore">
                {{ loadingMore ? '加载中…' : '加载更多' }}
              </button>
            </div>
          </div>

          <div v-else class="run-rows">
            <button
              v-for="r in filteredRuns"
              :key="r.id"
              type="button"
              :class="['run-row', { active: r.id === selectedId }]"
              @click="selectRun(r.id)"
            >
              <span class="run-row-main">
                <span class="run-row-top">
                  <span :class="['st-badge', statusClass(r.status)]">{{ statusLabel(r.status) }}</span>
                  <code class="run-id" :title="r.id">{{ shortId(r.id, 12) }}</code>
                  <span class="run-model">{{ r.model || '未知模型' }}</span>
                  <span class="run-time" :title="fmtAbs(r.started_at)">{{ fmtRel(r.started_at) }}</span>
                </span>
                <span class="run-row-bot">
                  <span class="run-meta"><Clock :size="11" /> {{ durationOf(r) }}</span>
                  <span class="run-meta"><Wrench :size="11" /> {{ runToolLabel(r) }}</span>
                  <span v-if="r.session_id" class="run-meta"><Hash :size="11" /> {{ shortId(r.session_id, 10) }}</span>
                  <span v-if="r.error" class="run-err">{{ truncate(r.error || '', 90) }}</span>
                </span>
              </span>
              <CornerUpRight :size="14" class="run-go" />
            </button>
          </div>

          <div v-if="loadingMore" class="ui-skeleton run-skel-row more-skel"></div>

          <div v-if="moreError" class="more-error">
            <AlertTriangle :size="13" />
            <span>{{ moreError }}</span>
            <button class="ui-btn ui-btn--sm ui-btn--ghost" @click="loadMore">重试</button>
          </div>

          <div v-if="!loading && !loadError && runs.length" class="runs-more">
            <span class="runs-more-hint">已加载 {{ runs.length }} / 共 {{ total }} 条</span>
            <button v-if="hasMore" class="ui-btn ui-btn--sm" :disabled="loadingMore" @click="loadMore">
              <RefreshCw v-if="loadingMore" :size="12" class="spin" />
              {{ loadingMore ? '加载中…' : '加载更多' }}
            </button>
            <span v-else class="runs-more-done">已加载全部</span>
          </div>
        </section>

        <!-- ==================== 运行详情 ==================== -->
        <aside ref="detailEl" class="run-detail" aria-label="运行详情">
          <div v-if="detailLoading" class="detail-skel">
            <div class="ui-skeleton" style="height: 22px; width: 48%"></div>
            <div class="ui-skeleton" style="height: 12px; width: 74%"></div>
            <div class="ui-skeleton detail-skel-block" style="height: 64px"></div>
            <div class="ui-skeleton detail-skel-block" style="height: 120px"></div>
          </div>

          <div v-else-if="detailError" class="ui-empty detail-empty">
            <div class="ui-empty-icon">⚠️</div>
            <div class="ui-empty-title">详情加载失败</div>
            <div class="ui-empty-desc">{{ detailError }}</div>
            <button class="ui-btn ui-btn--sm" @click="reloadDetail">重试</button>
          </div>

          <div v-else-if="!detail && !runs.length" class="ui-empty detail-empty">
            <div class="ui-empty-icon">🧾</div>
            <div class="ui-empty-title">暂无可查看的详情</div>
            <div class="ui-empty-desc">有 run 之后，这里会展示元信息、工具调用链与事件时间线。</div>
          </div>

          <div v-else-if="!detail" class="ui-empty detail-empty">
            <div class="ui-empty-icon">🛰️</div>
            <div class="ui-empty-title">选择一条执行记录</div>
            <div class="ui-empty-desc">点选左侧任意 run，查看它的工具调用与审计事件。</div>
          </div>

          <template v-else>
            <header class="detail-hd">
              <div class="detail-hd-main">
                <span :class="['st-badge', statusClass(detail.run.status)]">{{ statusLabel(detail.run.status) }}</span>
                <code class="detail-id" :title="detail.run.id">{{ detail.run.id }}</code>
              </div>
              <div class="detail-actions">
                <button class="ui-btn ui-btn--sm ui-btn--ghost" :disabled="exportingRun" @click="exportRunMarkdown">
                  <Download :size="12" /> {{ exportingRun ? '导出中…' : '导出 MD' }}
                </button>
                <button class="ui-btn ui-btn--sm ui-btn--ghost detail-copy" @click="copyRunId">
                  <Copy :size="12" /> {{ copied ? '已复制' : '复制 ID' }}
                </button>
              </div>
            </header>

            <div v-if="runExportError" class="detail-error detail-export-error">
              <div class="detail-error-title"><AlertTriangle :size="13" /> 导出失败</div>
              <pre class="detail-error-body">{{ runExportError }}</pre>
            </div>

            <div class="detail-sub">
              <span class="detail-model">{{ detail.run.model || '未知模型' }}</span>
              <span class="dot">·</span>
              <span class="detail-session" :title="detail.run.session_id || '未关联会话'">会话 {{ shortId(detail.run.session_id, 16) || '—' }}</span>
              <span class="dot">·</span>
              <span :title="fmtAbs(detail.run.started_at)">{{ fmtRel(detail.run.started_at) }}</span>
            </div>

            <div class="detail-meta">
              <div class="meta-item">
                <span class="meta-k">开始时间</span>
                <span class="meta-v">{{ fmtAbs(detail.run.started_at) }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-k">结束时间</span>
                <span class="meta-v">{{ detail.run.finished_at ? fmtAbs(detail.run.finished_at) : '进行中' }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-k">耗时</span>
                <span class="meta-v">{{ durationOf(detail.run) }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-k">工具调用</span>
                <span class="meta-v">{{ detail.tool_calls.length }}</span>
              </div>
            </div>

            <div v-if="detail.run.error" class="detail-error">
              <div class="detail-error-title"><AlertTriangle :size="13" /> 错误信息</div>
              <pre class="detail-error-body">{{ detail.run.error }}</pre>
            </div>

            <details v-if="hasRunMeta" class="detail-fold">
              <summary>run.meta <span class="fold-hint">JSON</span></summary>
              <pre class="code-block">{{ prettyJson(detail.run.meta) }}</pre>
            </details>

            <section class="detail-sec">
              <div class="detail-sec-head">
                <span class="detail-sec-title">工具调用</span>
                <span class="ui-badge">{{ detail.tool_calls.length }}</span>
              </div>

              <div v-if="!detail.tool_calls.length" class="detail-none">这次运行没有工具调用。</div>

              <div v-else class="tc-list">
                <article v-for="tc in detail.tool_calls" :key="tc.id" class="tc-item">
                  <div class="tc-top">
                    <code class="tc-name">{{ tc.name }}</code>
                    <span :class="['st-badge', statusClass(tc.status)]">{{ toolStatusLabel(tc.status) }}</span>
                    <span :class="['perm-badge', permClass(tc.permission_decision)]">{{ permLabel(tc.permission_decision) }}</span>
                  </div>
                  <div class="tc-meta">
                    <span :title="fmtAbs(tc.started_at)">{{ fmtRel(tc.started_at) }}</span>
                    <span>耗时 {{ durationOf(tc) }}</span>
                    <span>输出 {{ fmtBytes(tc.output_bytes) }}</span>
                    <span v-if="tc.args_hash" class="tc-hash" :title="tc.args_hash">#{{ shortHash(tc.args_hash) }}</span>
                  </div>
                  <div v-if="tc.error" class="tc-error">{{ tc.error }}</div>
                  <details class="tc-args">
                    <summary>参数 <span class="fold-hint">{{ argHint(tc) }}</span></summary>
                    <pre class="code-block">{{ prettyJson(argOf(tc)) }}</pre>
                  </details>
                </article>
              </div>
            </section>

            <section class="detail-sec">
              <div class="detail-sec-head">
                <span class="detail-sec-title">事件时间线</span>
                <span class="ui-badge">{{ detail.events.length }}</span>
              </div>

              <div v-if="!detail.events.length" class="detail-none">暂无审计事件。</div>

              <ol v-else class="ev-list">
                <li v-for="(ev, idx) in detail.events" :key="ev.seq ?? idx" class="ev-item">
                  <span class="ev-seq">#{{ ev.seq }}</span>
                  <span class="ev-body">
                    <span class="ev-top">
                      <span class="ev-type">{{ ev.type }}</span>
                      <span class="ev-ts" :title="fmtAbs(ev.ts)">{{ fmtRel(ev.ts) }}</span>
                    </span>
                    <details class="ev-data">
                      <summary>data <span class="fold-hint">{{ dataHint(ev) }}</span></summary>
                      <pre class="code-block">{{ prettyJson(eventData(ev)) }}</pre>
                    </details>
                  </span>
                </li>
              </ol>
            </section>
          </template>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import {
  RefreshCw, Search, X, Copy, Download, AlertTriangle, Wrench, Layers, Power, Clock, Hash, CornerUpRight,
} from 'lucide-vue-next'

interface RunRecord {
  id: string
  session_id?: string | null
  model?: string | null
  status: string
  started_at?: string | null
  finished_at?: string | null
  error?: string | null
  meta?: Record<string, any> | null
}

interface ToolCallRecord {
  id: string
  name: string
  status: string
  permission_decision?: string
  args?: any
  args_json?: any
  args_hash?: string
  started_at?: string | null
  finished_at?: string | null
  error?: string | null
  output_bytes?: number | null
}

interface RunEventRecord {
  id?: number
  seq?: number
  type: string
  data?: any
  data_json?: any
  ts?: string | null
}

interface RunDetail {
  run: RunRecord
  tool_calls: ToolCallRecord[]
  events: RunEventRecord[]
}

const PAGE_SIZE = 20
const PREFETCH_COUNT = 8
const TERMINAL_RUN_STATUSES = ['succeeded', 'failed', 'cancelled', 'unknown']
const ACTIVE_STATUSES = ['running', 'prepared', 'dispatched']

const runs = ref<RunRecord[]>([])
const loading = ref(true)
const loadError = ref('')
const query = ref('')
const statusFilter = ref('')
const total = ref(0)
const offset = ref(0)
const loadingMore = ref(false)
const moreError = ref('')
const exportingAll = ref(false)
const exportAllError = ref('')
const exportingRun = ref(false)
const runExportError = ref('')

const selectedId = ref('')
const detail = ref<RunDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
const detailCache = ref<Record<string, RunDetail>>({})
const detailEl = ref<HTMLElement | null>(null)
const copied = ref(false)

const nowTs = ref(Date.now())

let detailToken = 0
let prefetching = false
let tickTimer: ReturnType<typeof setInterval> | null = null
let copyTimer: ReturnType<typeof setTimeout> | null = null

const statusFilters = [
  { key: '', label: '全部' },
  { key: 'succeeded', label: '成功' },
  { key: 'failed', label: '失败' },
  { key: 'cancelled', label: '取消' },
  { key: 'unknown', label: '未知' },
] as const

const hasMore = computed(() => runs.value.length < total.value)
const isFiltering = computed(() => !!query.value.trim() || !!statusFilter.value)

/* ---------------- 列表 / 过滤 ---------------- */
const filteredRuns = computed(() => {
  const q = query.value.trim().toLowerCase()
  return runs.value.filter((r) => {
    if (statusFilter.value && r.status !== statusFilter.value) return false
    if (!q) return true
    const hay = [r.id, r.model || '', r.session_id || ''].join(' ').toLowerCase()
    return hay.includes(q)
  })
})

function resetFilters() {
  query.value = ''
  statusFilter.value = ''
}

/* ---------------- 统计 ---------------- */
const terminalRuns = computed(() => runs.value.filter((r) => TERMINAL_RUN_STATUSES.includes(r.status)))
const succeededRuns = computed(() => runs.value.filter((r) => r.status === 'succeeded'))
const failedRuns = computed(() => runs.value.filter((r) => r.status === 'failed'))
const cancelledRuns = computed(() => runs.value.filter((r) => r.status === 'cancelled'))
const unknownRuns = computed(() => runs.value.filter((r) => r.status === 'unknown'))
const failureLikeRuns = computed(() => [...failedRuns.value, ...cancelledRuns.value, ...unknownRuns.value])

const cachedDetailCount = computed(() => Object.keys(detailCache.value).length)
const toolCallTotal = computed<number | null>(() => {
  const list = Object.values(detailCache.value)
  if (!list.length) return null
  return list.reduce((n, d) => n + (d.tool_calls?.length || 0), 0)
})

const successRate = computed(() => {
  const total = terminalRuns.value.length
  if (!total) return '—'
  const rate = (succeededRuns.value.length / total) * 100
  return `${Number.isInteger(rate) ? rate : rate.toFixed(1)}%`
})

const statTotal = computed(() => (loading.value || loadError.value ? '—' : String(total.value)))
const statRate = computed(() => (loading.value ? '—' : successRate.value))
const statTools = computed(() => (loading.value || toolCallTotal.value === null ? '—' : String(toolCallTotal.value)))
const statFailures = computed(() => (loading.value ? '—' : String(failureLikeRuns.value.length)))

const statTotalHint = computed(() => {
  if (loading.value) return '正在读取审计库…'
  if (loadError.value) return '接口读取失败'
  if (!total.value) return '审计库里还没有 run'
  return `已加载 ${runs.value.length} / 共 ${total.value} 条`
})
const statRateHint = computed(() => {
  if (loading.value) return '基于已加载页估算'
  const finished = terminalRuns.value.length
  const loaded = runs.value.length
  return finished
    ? `基于已加载 ${loaded} 条 · 成功 ${succeededRuns.value.length} / 已结束 ${finished}`
    : `基于已加载 ${loaded} 条 · 暂无已结束运行`
})
const statToolsHint = computed(() => {
  if (loading.value) return '基于已加载页汇总'
  if (!cachedDetailCount.value) return `基于已加载 ${runs.value.length} 条 · 打开详情后汇总`
  return `基于已加载 · 已汇总 ${cachedDetailCount.value} / ${runs.value.length} 次`
})
const statFailHint = computed(() => {
  if (loading.value) return '基于已加载页统计'
  return `基于已加载 ${runs.value.length} 条 · 失败 ${failedRuns.value.length} · 取消 ${cancelledRuns.value.length} · 未知 ${unknownRuns.value.length}`
})

const hasRunMeta = computed(() => {
  const meta = detail.value?.run?.meta
  return !!meta && typeof meta === 'object' && Object.keys(meta).length > 0
})

/* ---------------- 状态 / 文案 ---------------- */
const RUN_STATUS_LABELS: Record<string, string> = {
  running: '运行中',
  succeeded: '成功',
  failed: '失败',
  cancelled: '已取消',
  unknown: '未知',
}
const TOOL_STATUS_LABELS: Record<string, string> = {
  prepared: '已准备',
  dispatched: '已派发',
  succeeded: '成功',
  failed: '失败',
  cancelled: '已取消',
  unknown: '未知',
}
const PERMISSION_LABELS: Record<string, string> = {
  allow: '允许',
  allowed: '允许',
  approved: '已批准',
  deny: '拒绝',
  denied: '已拒绝',
  rejected: '已拒绝',
  ask: '待确认',
  pending: '待审批',
}

function statusLabel(status?: string) {
  if (!status) return '未知'
  return RUN_STATUS_LABELS[status] || status
}
function toolStatusLabel(status?: string) {
  if (!status) return '未知'
  return TOOL_STATUS_LABELS[status] || status
}
function statusClass(status?: string) {
  switch (status) {
    case 'succeeded':
      return 'st--ok'
    case 'failed':
      return 'st--bad'
    case 'cancelled':
      return 'st--warn'
    case 'running':
    case 'dispatched':
      return 'st--run'
    case 'prepared':
      return 'st--primary'
    default:
      return 'st--muted'
  }
}
function permLabel(decision?: string) {
  if (!decision) return '未记录'
  return PERMISSION_LABELS[decision] || decision
}
function permClass(decision?: string) {
  if (['allow', 'allowed', 'approved'].includes(decision || '')) return 'perm--ok'
  if (['deny', 'denied', 'rejected'].includes(decision || '')) return 'perm--bad'
  if (['ask', 'pending'].includes(decision || '')) return 'perm--warn'
  return ''
}

/* ---------------- 时间 / 数值格式化 ---------------- */
function toMs(value?: string | null): number | null {
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
function fmtRel(value?: string | null) {
  const ms = toMs(value)
  if (ms === null) return '—'
  const diff = Math.max(0, nowTs.value - ms)
  const sec = Math.floor(diff / 1000)
  if (sec < 5) return '刚刚'
  if (sec < 60) return `${sec} 秒前`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day} 天前`
  return fmtAbs(value)
}
function durationOf(item: { started_at?: string | null; finished_at?: string | null; status?: string }) {
  const start = toMs(item.started_at)
  if (start === null) return '—'
  const finished = toMs(item.finished_at)
  const active = ACTIVE_STATUSES.includes(item.status || '')
  const end = finished ?? (active ? nowTs.value : null)
  if (end === null) return '—'
  const ms = Math.max(0, end - start)
  if (ms < 1000) return `${Math.round(ms)}ms`
  const sec = ms / 1000
  if (sec < 60) return `${sec < 10 ? sec.toFixed(1) : Math.round(sec)}s`
  const min = Math.floor(sec / 60)
  const rest = Math.round(sec % 60)
  if (min < 60) return `${min}m ${rest}s`
  const hr = Math.floor(min / 60)
  return `${hr}h ${min % 60}m`
}
function fmtBytes(bytes?: number | null) {
  if (bytes === null || bytes === undefined) return '—'
  if (!Number.isFinite(bytes)) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
function truncate(text: string, max = 90) {
  const t = text.replace(/\s+/g, ' ').trim()
  return t.length > max ? `${t.slice(0, max)}…` : t
}
function shortId(value?: string | null, max = 12) {
  if (!value) return ''
  return value.length > max ? `${value.slice(0, max)}…` : value
}
function shortHash(value?: string | null, max = 8) {
  if (!value) return ''
  return value.length > max ? value.slice(0, max) : value
}
function runToolLabel(run: RunRecord) {
  const cached = detailCache.value[run.id]
  if (!cached) return '工具 —'
  return `${cached.tool_calls.length} 次工具`
}

/* ---------------- JSON / 参数辅助 ---------------- */
function parseMaybe(raw: any) {
  if (typeof raw !== 'string') return raw
  const text = raw.trim()
  if (!text) return raw
  try {
    return JSON.parse(text)
  } catch {
    return raw
  }
}
function argOf(tc: ToolCallRecord) {
  return tc.args !== undefined ? tc.args : parseMaybe(tc.args_json)
}
function eventData(ev: RunEventRecord) {
  return ev.data !== undefined ? ev.data : parseMaybe(ev.data_json)
}
function prettyJson(value: any): string {
  if (value === null || value === undefined || value === '') return '（空）'
  const parsed = typeof value === 'string' ? parseMaybe(value) : value
  if (typeof parsed === 'string') return parsed
  try {
    return JSON.stringify(parsed, null, 2)
  } catch {
    return String(parsed)
  }
}
function argHint(tc: ToolCallRecord) {
  const value = argOf(tc)
  if (value && typeof value === 'object') return `${Object.keys(value).length} 个字段`
  if (typeof value === 'string' && value) return truncate(value, 24)
  return '空'
}
function dataHint(ev: RunEventRecord) {
  const value = eventData(ev)
  if (value && typeof value === 'object') return `${Object.keys(value).length} 个字段`
  if (typeof value === 'string' && value) return truncate(value, 24)
  return '空'
}

/* ---------------- 数据获取 ---------------- */
async function responseError(res: Response) {
  try {
    const data = await res.json()
    return data?.detail || data?.message || `HTTP ${res.status}`
  } catch {
    return `HTTP ${res.status}`
  }
}

async function fetchDetail(id: string): Promise<RunDetail> {
  const res = await fetch(`/api/v1/runs/${encodeURIComponent(id)}`)
  if (!res.ok) throw new Error(await responseError(res))
  const data = await res.json()
  return {
    run: data?.run || { id, status: 'unknown' },
    tool_calls: Array.isArray(data?.tool_calls) ? data.tool_calls : [],
    events: Array.isArray(data?.events) ? data.events : [],
  }
}

async function prefetchDetails() {
  if (prefetching) return
  const targets = runs.value
    .map((r) => r.id)
    .filter((id) => !detailCache.value[id])
    .slice(0, PREFETCH_COUNT)
  if (!targets.length) return
  prefetching = true
  try {
    const results = await Promise.allSettled(
      targets.map(async (id) => ({ id, detail: await fetchDetail(id) })),
    )
    const next = { ...detailCache.value }
    for (const result of results) {
      if (result.status === 'fulfilled') next[result.value.id] = result.value.detail
    }
    detailCache.value = next
  } finally {
    prefetching = false
  }
}

async function loadDetail(id: string) {
  const token = ++detailToken
  detailLoading.value = !detailCache.value[id]
  detailError.value = ''
  try {
    const data = await fetchDetail(id)
    detailCache.value = { ...detailCache.value, [id]: data }
    if (token !== detailToken) return
    if (selectedId.value === id) detail.value = data
  } catch (e: any) {
    if (token !== detailToken) return
    if (selectedId.value === id && !detailCache.value[id]) {
      detail.value = null
      detailError.value = `加载 run 详情失败：${e?.message || e}`
    }
  } finally {
    if (token === detailToken) detailLoading.value = false
  }
}

function activate(id: string, scroll = false) {
  if (!id) return
  selectedId.value = id
  detailError.value = ''
  runExportError.value = ''
  const cached = detailCache.value[id]
  detail.value = cached || null
  detailLoading.value = !cached
  void loadDetail(id)
  if (scroll && typeof window !== 'undefined' && window.innerWidth < 1080) {
    nextTick(() => detailEl.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }
}

function selectRun(id: string) {
  if (!id || id === selectedId.value) return
  activate(id, true)
}

function reloadDetail() {
  if (selectedId.value) void loadDetail(selectedId.value)
}

function resolveTotal(data: any, fallback: number) {
  const value = Number(data?.total)
  return Number.isFinite(value) && value >= 0 ? value : fallback
}

async function load() {
  loading.value = true
  loadError.value = ''
  moreError.value = ''
  exportAllError.value = ''
  try {
    const res = await fetch(`/api/v1/runs?limit=${PAGE_SIZE}&offset=0`)
    if (!res.ok) throw new Error(await responseError(res))
    const data = await res.json()
    const page: RunRecord[] = Array.isArray(data?.runs) ? data.runs : []
    runs.value = page
    offset.value = page.length
    total.value = resolveTotal(data, page.length)
    if (!page.length) {
      selectedId.value = ''
      detail.value = null
      detailError.value = ''
      detailLoading.value = false
      return
    }
    const keep = page.find((r) => r.id === selectedId.value)
    const targetId = keep ? keep.id : page[0]?.id
    if (!targetId) return
    activate(targetId)
  } catch (e: any) {
    runs.value = []
    offset.value = 0
    total.value = 0
    selectedId.value = ''
    detail.value = null
    detailError.value = ''
    loadError.value = `无法读取 /api/v1/runs：${e?.message || e}`
  } finally {
    loading.value = false
    void prefetchDetails()
  }
}

async function loadMore() {
  if (loading.value || loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  moreError.value = ''
  const requestedOffset = offset.value
  try {
    const res = await fetch(`/api/v1/runs?limit=${PAGE_SIZE}&offset=${requestedOffset}`)
    if (!res.ok) throw new Error(await responseError(res))
    const data = await res.json()
    const page: RunRecord[] = Array.isArray(data?.runs) ? data.runs : []
    const seen = new Set(runs.value.map((r) => r.id))
    const fresh = page.filter((r) => !seen.has(r.id))
    runs.value = fresh.length ? [...runs.value, ...fresh] : runs.value
    offset.value = requestedOffset + page.length
    total.value = resolveTotal(data, offset.value)
    if (!page.length) total.value = offset.value
  } catch (e: any) {
    moreError.value = `加载更多失败：${e?.message || e}`
  } finally {
    loadingMore.value = false
    void prefetchDetails()
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1500)
}

async function exportRunMarkdown() {
  if (!detail.value || exportingRun.value) return
  const runId = detail.value.run.id
  exportingRun.value = true
  runExportError.value = ''
  try {
    const res = await fetch(`/api/v1/runs/${encodeURIComponent(runId)}/export?format=markdown`)
    if (!res.ok) throw new Error(await responseError(res))
    const blob = await res.blob()
    downloadBlob(blob, `${runId}.md`)
  } catch (e: any) {
    runExportError.value = `导出 Markdown 失败：${e?.message || e}`
  } finally {
    exportingRun.value = false
  }
}

async function exportAllRuns() {
  if (exportingAll.value) return
  exportingAll.value = true
  exportAllError.value = ''
  try {
    const res = await fetch('/api/v1/runs/export')
    if (!res.ok) throw new Error(await responseError(res))
    const blob = await res.blob()
    downloadBlob(blob, 'runs-export.json')
  } catch (e: any) {
    exportAllError.value = `导出全部失败：${e?.message || e}`
  } finally {
    exportingAll.value = false
  }
}

async function copyRunId() {
  if (!detail.value) return
  try {
    await navigator.clipboard.writeText(detail.value.run.id)
    copied.value = true
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => {
      copied.value = false
    }, 1600)
  } catch {
    copied.value = false
  }
}

onMounted(() => {
  load()
  tickTimer = setInterval(() => {
    nowTs.value = Date.now()
  }, 15000)
})

onUnmounted(() => {
  if (tickTimer) clearInterval(tickTimer)
  if (copyTimer) clearTimeout(copyTimer)
})
</script>

<style scoped>
/* ============================================================
   执行记录 — Aurora Console
   ============================================================ */
.runs-hero { margin-bottom: 20px; }
.runs-stats { margin-bottom: 18px; }

.stat-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.stat-label svg { color: var(--primary); flex-shrink: 0; }

/* ---------------- 工具条 ---------------- */
.runs-toolbar { align-items: center; }

.runs-search {
  flex: 1 1 260px;
  max-width: 420px;
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
.runs-search:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-soft);
}
.runs-search-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text);
  font-size: 12.5px;
}
.runs-search-input::placeholder { color: var(--text3); }
.runs-search-clear {
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
.runs-search-clear:hover { color: var(--text); background: var(--surface-alt); }

.runs-seg {
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
}
.runs-seg::-webkit-scrollbar { display: none; }
.runs-seg .ui-seg-item { flex-shrink: 0; }

.runs-count {
  margin-left: auto;
  font-size: 11px;
  color: var(--text3);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.runs-toolbar .ui-btn { flex-shrink: 0; }

.runs-toolbar-btns {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

/* ---------------- 导出提示 ---------------- */
.export-alert {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: -8px 0 14px;
  padding: 8px 12px;
  border: 1px solid color-mix(in srgb, var(--error) 32%, transparent);
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--error) 8%, transparent);
  color: var(--error);
  font-size: 11.5px;
}
.export-alert-text { flex: 1; min-width: 0; word-break: break-word; }
.export-alert .ui-btn {
  color: var(--error);
  flex-shrink: 0;
}
.export-alert .ui-btn:hover { background: color-mix(in srgb, var(--error) 12%, transparent); }

/* ---------------- 双栏布局 ---------------- */
.runs-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 432px;
  gap: 16px;
  align-items: start;
}
.runs-list { min-width: 0; }
.runs-list-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin: 2px 2px 10px;
}
.runs-list-title {
  font-size: 11px;
  font-weight: 760;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text3);
}
.runs-list-hint { font-size: 10.5px; color: var(--text3); }

/* ---------------- 列表 ---------------- */
.run-skel { display: flex; flex-direction: column; gap: 10px; }
.run-skel-row { height: 80px; border-radius: var(--r-md); }

.run-rows { display: flex; flex-direction: column; gap: 10px; }

.run-row {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 13px 14px 13px 16px;
  text-align: left;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.02), transparent 60%),
    var(--surface);
  transition: border-color var(--t-mid), background var(--t-mid), box-shadow var(--t-mid), transform var(--t-mid);
}
.run-row::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 2px;
  border-radius: var(--r-full);
  background: transparent;
  transition: background var(--t-mid);
}
.run-row:hover {
  border-color: color-mix(in srgb, var(--primary) 28%, var(--border-strong));
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}
.run-row.active {
  border-color: color-mix(in srgb, var(--primary) 48%, transparent);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--primary) 8%, transparent), transparent 65%),
    var(--surface);
}
.run-row.active::before { background: var(--primary); }

.run-row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.run-row-top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}
.run-id {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 640;
  color: var(--text);
  background: transparent;
  padding: 0;
  white-space: nowrap;
}
.run-model {
  font-size: 11px;
  color: var(--text2);
  max-width: 190px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.run-time {
  margin-left: auto;
  font-size: 10.5px;
  color: var(--text3);
  white-space: nowrap;
}
.run-row-bot {
  display: flex;
  align-items: center;
  gap: 4px 12px;
  flex-wrap: wrap;
  font-size: 10.5px;
  color: var(--text3);
  font-variant-numeric: tabular-nums;
  min-width: 0;
}
.run-meta { display: inline-flex; align-items: center; gap: 4px; }
.run-err {
  color: var(--error);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.run-go { color: var(--text3); flex-shrink: 0; }
.run-row.active .run-go { color: var(--primary); }

/* ---------------- 状态徽章 ---------------- */
.st-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 8px;
  border-radius: var(--r-full);
  border: 1px solid transparent;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  white-space: nowrap;
  flex-shrink: 0;
}
.st-badge::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.9;
}
.st--ok {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 12%, transparent);
  border-color: color-mix(in srgb, var(--success) 24%, transparent);
}
.st--bad {
  color: var(--error);
  background: color-mix(in srgb, var(--error) 12%, transparent);
  border-color: color-mix(in srgb, var(--error) 26%, transparent);
}
.st--warn {
  color: var(--warn);
  background: color-mix(in srgb, var(--warn) 12%, transparent);
  border-color: color-mix(in srgb, var(--warn) 26%, transparent);
}
.st--run {
  color: var(--info);
  background: color-mix(in srgb, var(--info) 12%, transparent);
  border-color: color-mix(in srgb, var(--info) 26%, transparent);
}
.st--run::before { animation: run-pulse 1.4s ease-in-out infinite; }
.st--primary {
  color: var(--primary);
  background: var(--primary-soft);
  border-color: color-mix(in srgb, var(--primary) 26%, transparent);
}
.st--muted {
  color: var(--text3);
  background: color-mix(in srgb, var(--text3) 10%, transparent);
  border-color: var(--border-light);
}
@keyframes run-pulse {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

/* ---------------- 详情面板 ---------------- */
.run-detail {
  position: sticky;
  top: 14px;
  max-height: calc(100vh - 28px);
  overflow-y: auto;
  scrollbar-width: thin;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-lg);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.02), transparent 55%),
    var(--surface);
  box-shadow: var(--shadow-sm);
  scroll-margin-top: 12px;
}

.detail-skel { display: flex; flex-direction: column; gap: 10px; }
.detail-skel-block { border-radius: var(--r-sm); }
.detail-empty { padding: 44px 12px; }

.detail-hd {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.detail-hd-main {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}
.detail-hd-main .st-badge { align-self: flex-start; }
.detail-id {
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--text);
  background: var(--surface-alt);
  padding: 3px 8px;
  border-radius: var(--r-xs);
  word-break: break-all;
  cursor: text;
}
.detail-copy { flex-shrink: 0; }

.detail-sub {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--text2);
  font-variant-numeric: tabular-nums;
}
.detail-model { color: var(--text); font-weight: 560; }
.detail-session {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text2);
}
.dot { color: var(--text3); }

.detail-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--bg) 45%, transparent);
  min-width: 0;
}
.meta-k {
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--text3);
}
.meta-v {
  font-size: 11px;
  color: var(--text);
  font-variant-numeric: tabular-nums;
  word-break: break-word;
}

.detail-error {
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--error) 35%, transparent);
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--error) 8%, transparent);
}
.detail-error-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 11.5px;
  font-weight: 650;
  color: var(--error);
}
.detail-error-body {
  margin: 0;
  max-height: 140px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 10.5px;
  line-height: 1.6;
  color: var(--text2);
  white-space: pre-wrap;
  word-break: break-word;
}

/* ---------------- 折叠区 / 代码块 ---------------- */
.detail-fold,
.tc-args,
.ev-data {
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--bg) 45%, transparent);
  overflow: hidden;
}
.detail-fold > summary,
.tc-args > summary,
.ev-data > summary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  font-size: 11px;
  color: var(--text2);
  cursor: pointer;
  list-style: none;
  user-select: none;
}
.detail-fold > summary::-webkit-details-marker,
.tc-args > summary::-webkit-details-marker,
.ev-data > summary::-webkit-details-marker { display: none; }
.detail-fold > summary::before,
.tc-args > summary::before,
.ev-data > summary::before {
  content: '›';
  display: inline-block;
  width: 10px;
  font-size: 12px;
  line-height: 1;
  color: var(--text3);
  transition: transform var(--t-fast);
}
.detail-fold[open] > summary::before,
.tc-args[open] > summary::before,
.ev-data[open] > summary::before { transform: rotate(90deg); }
.detail-fold > summary:hover,
.tc-args > summary:hover,
.ev-data > summary:hover { color: var(--text); }

.fold-hint {
  margin-left: auto;
  font-size: 9.5px;
  color: var(--text3);
  font-family: var(--font-mono);
}

.code-block {
  margin: 0;
  padding: 10px 12px;
  max-height: 220px;
  overflow: auto;
  border-top: 1px solid var(--border-light);
  background: var(--bg);
  font-family: var(--font-mono);
  font-size: 10.5px;
  line-height: 1.6;
  color: var(--text2);
  white-space: pre-wrap;
  word-break: break-word;
  scrollbar-width: thin;
}

/* ---------------- 详情分区 ---------------- */
.detail-sec { display: flex; flex-direction: column; gap: 9px; }
.detail-sec-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 7px;
  border-bottom: 1px solid var(--border-light);
}
.detail-sec-title {
  font-size: 10.5px;
  font-weight: 760;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text3);
}
.detail-none {
  padding: 10px 12px;
  font-size: 11px;
  color: var(--text3);
  border: 1px dashed var(--border-light);
  border-radius: var(--r-sm);
  text-align: center;
}

/* ---------------- 工具调用 ---------------- */
.tc-list { display: flex; flex-direction: column; gap: 8px; }
.tc-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 9px 10px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  background: color-mix(in srgb, var(--bg) 35%, transparent);
}
.tc-top {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.tc-name {
  font-family: var(--font-mono);
  font-size: 11.5px;
  font-weight: 640;
  color: var(--text);
  background: transparent;
  padding: 0;
  word-break: break-all;
}
.perm-badge {
  font-size: 9.5px;
  line-height: 18px;
  padding: 0 7px;
  border-radius: var(--r-full);
  border: 1px solid var(--border-light);
  color: var(--text3);
  white-space: nowrap;
}
.perm--ok {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 10%, transparent);
  border-color: color-mix(in srgb, var(--success) 22%, transparent);
}
.perm--bad {
  color: var(--error);
  background: color-mix(in srgb, var(--error) 10%, transparent);
  border-color: color-mix(in srgb, var(--error) 22%, transparent);
}
.perm--warn {
  color: var(--warn);
  background: color-mix(in srgb, var(--warn) 10%, transparent);
  border-color: color-mix(in srgb, var(--warn) 22%, transparent);
}
.tc-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 3px 10px;
  font-size: 10px;
  color: var(--text3);
  font-variant-numeric: tabular-nums;
}
.tc-hash { font-family: var(--font-mono); }
.tc-error {
  padding: 4px 7px;
  border-radius: var(--r-xs);
  background: color-mix(in srgb, var(--error) 8%, transparent);
  font-size: 10.5px;
  line-height: 1.5;
  color: var(--error);
  word-break: break-word;
}
.tc-args > summary { padding: 6px 0; font-size: 10px; }
.tc-args { border: none; background: transparent; }
.tc-args > summary {
  border-top: 1px dashed var(--border-light);
  margin-top: 2px;
}
.tc-args .code-block {
  margin-top: 6px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-xs);
  max-height: 180px;
}

/* ---------------- 事件时间线 ---------------- */
.ev-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.ev-item {
  position: relative;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  gap: 10px;
  padding-bottom: 10px;
}
.ev-item:last-child { padding-bottom: 0; }
.ev-item::before {
  content: '';
  position: absolute;
  left: 18px;
  top: 20px;
  bottom: 0;
  width: 1px;
  background: var(--border-light);
}
.ev-item:last-child::before { display: none; }
.ev-seq {
  position: relative;
  z-index: 1;
  justify-self: center;
  align-self: start;
  font-family: var(--font-mono);
  font-size: 9.5px;
  line-height: 18px;
  padding: 0 6px;
  border-radius: var(--r-full);
  background: var(--primary-soft);
  color: var(--primary);
  white-space: nowrap;
}
.ev-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ev-top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.ev-type {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text);
  word-break: break-all;
}
.ev-ts {
  margin-left: auto;
  font-size: 10px;
  color: var(--text3);
  white-space: nowrap;
}
.ev-data { border: none; background: transparent; }
.ev-data > summary { padding: 2px 0 0; font-size: 10px; color: var(--text3); }
.ev-data .code-block {
  margin-top: 5px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-xs);
  max-height: 160px;
}

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ---------------- 平板：单列 ---------------- */
@media (max-width: 1080px) {
  .runs-layout { grid-template-columns: minmax(0, 1fr); gap: 12px; }
  .run-detail {
    position: static;
    max-height: none;
    overflow: visible;
  }
}

/* ---------------- 移动端 ---------------- */
@media (max-width: 767px) {
  .runs-hero { margin-bottom: 16px; }
  .runs-stats { margin-bottom: 13px; }

  .runs-toolbar { gap: 8px; }
  .runs-search { flex: 1 1 100%; max-width: none; height: 40px; }
  .runs-seg { width: 100%; }
  .runs-count { display: none; }
  .runs-toolbar .ui-btn { width: 100%; }

  .runs-list { min-width: 0; }
  .run-row { padding: 12px 12px 12px 14px; }
  .run-row:hover { transform: none; }
  .run-model { max-width: 130px; }
  .run-time { margin-left: 0; }
  .run-err { flex-basis: 100%; }

  .run-detail { padding: 14px; border-radius: var(--r-md); }
  .detail-meta { grid-template-columns: minmax(0, 1fr); }
  .code-block { max-height: 200px; }
}
</style>

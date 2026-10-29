<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <header class="ui-head">
        <div>
          <div class="ui-eyebrow">Tool Registry</div>
          <h1 class="ui-title">工具中心</h1>
          <p class="ui-sub">这里是模型真正可以调用的能力清单。可以按需启停、查看参数结构，并在不进入对话的情况下直接试跑。</p>
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

      <div class="stat-row">
        <div class="stat">
          <div class="stat-icon" style="color: var(--primary); background: var(--primary-soft)">
            <Wrench :size="15" />
          </div>
          <div><div class="stat-value">{{ tools.length }}</div><div class="stat-label">已注册工具</div></div>
        </div>
        <div class="stat">
          <div class="stat-icon" style="color: var(--success); background: color-mix(in srgb, var(--success) 14%, transparent)">
            <Power :size="15" />
          </div>
          <div><div class="stat-value">{{ enabledCount }}</div><div class="stat-label">已启用</div></div>
        </div>
        <div class="stat">
          <div class="stat-icon" style="color: var(--info); background: color-mix(in srgb, var(--info) 14%, transparent)">
            <Layers :size="15" />
          </div>
          <div><div class="stat-value">{{ categories.length }}</div><div class="stat-label">分类</div></div>
        </div>
      </div>

      <div class="toolbar">
        <div class="tb-search">
          <Search :size="14" />
          <input v-model="query" placeholder="搜索工具名或描述…" />
          <button v-if="query" class="tb-clear" @click="query = ''"><X :size="12" /></button>
        </div>
        <div class="cats">
          <button :class="['ui-chip', { active: cat === '' }]" @click="cat = ''">全部</button>
          <button
            v-for="c in categories"
            :key="c"
            :class="['ui-chip', { active: cat === c }]"
            @click="cat = c"
          >{{ c }}</button>
        </div>
        <button :class="['ui-chip', { active: onlyEnabled }]" @click="onlyEnabled = !onlyEnabled">
          <Filter :size="12" /> 只看启用
        </button>
      </div>

      <div v-if="loading" class="tool-grid">
        <div v-for="i in 6" :key="i" class="ui-skeleton" style="height: 132px"></div>
      </div>

      <div v-else-if="!filtered.length" class="ui-empty">
        <div class="ui-empty-icon">🧰</div>
        <div class="ui-empty-title">没有匹配的工具</div>
        <div class="ui-empty-desc">调整筛选条件，或检查后端 ToolRegistry 是否正常注册。</div>
      </div>

      <div v-else class="tool-grid">
        <article v-for="t in filtered" :key="t.name" :class="['tcard', { off: !t.enabled }]">
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
            <button class="link-btn" @click="toggleSchema(t.name)">
              <Code2 :size="12" /> {{ openSchema.includes(t.name) ? '收起参数' : '查看参数' }}
            </button>
            <button class="link-btn" :disabled="!t.enabled" @click="openTest(t)">
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
              <div>
                <div class="modal-title">试运行 <code>{{ testTool.name }}</code></div>
                <div class="modal-sub">{{ testTool.description }}</div>
              </div>
              <button class="ui-btn ui-btn--ghost ui-btn--icon" @click="testTool = null"><X :size="15" /></button>
            </div>

            <div class="modal-bd">
              <label class="ui-label">参数（JSON）</label>
              <textarea v-model="testArgs" class="ui-textarea mono" rows="6" spellcheck="false"></textarea>
              <div v-if="argError" class="err-line">{{ argError }}</div>

              <div class="modal-actions">
                <button class="ui-btn ui-btn--primary" :disabled="running" @click="runTest">
                  <Play :size="13" /> {{ running ? '执行中…' : '执行' }}
                </button>
                <button class="ui-btn" @click="fillExample">填充示例</button>
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
import { ref, computed, onMounted } from 'vue'
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

async function runTest() {
  if (!testTool.value) return
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
  try {
    const r = await fetch('/api/v1/tools/call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: testTool.value.name, arguments: args }),
    })
    const data = await r.json()
    testFailed.value = !r.ok || data.ok === false
    testResult.value = JSON.stringify(data, null, 2)
  } catch (e: any) {
    testFailed.value = true
    testResult.value = `请求失败：${e?.message || e}`
  } finally {
    running.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.stat {
  display: flex; align-items: center; gap: 11px;
  padding: 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface);
}
.stat-icon { width: 34px; height: 34px; border-radius: var(--r-sm); display: grid; place-items: center; flex-shrink: 0; }
.stat-value { font-size: 19px; font-weight: 720; letter-spacing: -0.02em; line-height: 1.2; }
.stat-label { font-size: 11px; color: var(--text3); }

.toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
.tb-search {
  flex: 1; min-width: 190px; max-width: 340px;
  display: flex; align-items: center; gap: 8px;
  height: 34px; padding: 0 11px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-sm);
  background: var(--surface);
  color: var(--text3);
}
.tb-search:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }
.tb-search input { flex: 1; min-width: 0; border: none; outline: none; background: transparent; color: var(--text); font-size: 12.5px; }
.tb-clear { border: none; background: transparent; color: var(--text3); display: grid; place-items: center; padding: 2px; border-radius: 4px; }
.cats { display: flex; gap: 6px; flex-wrap: wrap; }

.tool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.tcard {
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface);
  padding: 15px;
  transition: border-color var(--t-mid), box-shadow var(--t-mid), opacity var(--t-mid);
}
.tcard:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); }
.tcard.off { opacity: 0.62; }

.tcard-hd { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.tcard-name { display: flex; align-items: center; gap: 8px; min-width: 0; }
.tcard-name code {
  background: transparent;
  padding: 0;
  font-size: 12.5px;
  font-weight: 640;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tcard-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.tcard-dot.on { background: var(--success); box-shadow: 0 0 0 3px color-mix(in srgb, var(--success) 16%, transparent); }
.tcard-dot.off { background: var(--text3); }
.tcard-hd-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.tcard-desc {
  font-size: 11.5px;
  color: var(--text2);
  line-height: 1.6;
  margin-top: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 37px;
}

.tcard-warn {
  display: flex; align-items: center; gap: 5px;
  margin-top: 8px;
  font-size: 10.5px;
  color: var(--warn);
}

.tcard-foot {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 11px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.link-btn {
  display: inline-flex; align-items: center; gap: 4px;
  border: none; background: transparent;
  color: var(--text3);
  font-size: 11px;
  font-weight: 560;
  padding: 2px 0;
  transition: color var(--t-fast);
}
.link-btn:hover:not(:disabled) { color: var(--primary); }
.link-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.tcard-schema {
  margin-top: 10px;
  font-size: 10.5px;
  line-height: 1.6;
  max-height: 220px;
  overflow: auto;
  background: var(--bg);
  color: var(--text2);
}

.schema-enter-active, .schema-leave-active { transition: opacity var(--t-mid), transform var(--t-mid); }
.schema-enter-from, .schema-leave-to { opacity: 0; transform: translateY(-4px); }

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
  max-height: 84vh;
  display: flex; flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.modal-hd {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border-light);
}
.modal-title { font-size: 14px; font-weight: 680; display: flex; align-items: center; gap: 7px; }
.modal-title code { background: var(--primary-soft); color: var(--primary); font-size: 12px; }
.modal-sub { font-size: 11.5px; color: var(--text3); margin-top: 4px; line-height: 1.5; }
.modal-bd { padding: 16px 18px; overflow-y: auto; }
.mono { font-family: var(--font-mono); font-size: 11.5px; }
.modal-actions { display: flex; gap: 8px; margin-top: 10px; }
.err-line { color: var(--error); font-size: 11.5px; margin-top: 6px; }
.result {
  font-size: 11px;
  line-height: 1.6;
  max-height: 300px;
  overflow: auto;
  background: var(--bg);
  color: var(--text2);
  white-space: pre-wrap;
  word-break: break-word;
}
.result.bad { border-color: color-mix(in srgb, var(--error) 40%, transparent); color: var(--error); }

.fade-enter-active, .fade-leave-active { transition: opacity 180ms var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>

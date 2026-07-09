<template>
  <div class="settings-page">
    <div class="set-layout" :class="{ mobile: isMobile }">
      <nav class="set-tabs">
        <div v-for="t in tabs" :key="t.id" :class="['set-tab', { active: activeTab === t.id }]" @click="activeTab = t.id">
          <span class="set-tab-icon">{{ t.icon }}</span>
          <span class="set-tab-label">{{ t.label }}</span>
        </div>
      </nav>
      <div class="set-content">
        <div v-if="activeTab === 'global'" class="set-section">
          <h3 class="set-title">🌐 全局设置</h3>
          <div class="set-card">
            <div class="set-card-header"><span>🏪 模型提供商 Providers</span><button class="set-add-btn" @click="addProvider">+ 添加</button></div>
            <div class="set-list">
              <div v-if="providers.length === 0" class="set-empty">还没有 Provider，添加 API Key 后会自动发现模型。</div>
              <div v-for="(p, i) in providers" :key="providerKey(p, i)" class="set-list-item">
                <div class="set-list-item-main">
                  <div class="set-list-item-name">{{ p.name || '新 Provider' }}</div>
                  <div class="set-list-item-meta">{{ p.baseUrl || '未配置 Base URL' }} · {{ p.models?.length || 0 }} 模型</div>
                  <div v-if="p.models?.length" class="set-list-item-tags">
                    <span v-for="m in p.models.slice(0, 4)" :key="m" class="set-model-tag">{{ m }}</span>
                    <span v-if="p.models.length > 4" class="set-model-tag more">+{{ p.models.length - 4 }}</span>
                  </div>
                </div>
                <button class="set-list-item-edit" @click="editProvider(i)">编辑</button>
                <button class="set-list-item-del" @click="removeProvider(i)">✕</button>
              </div>
            </div>
          </div>
          <div v-if="editingProvider !== null" class="set-modal-overlay" @click.self="closeProviderEditor">
            <div class="set-modal">
              <div class="set-modal-title">编辑 Provider</div>
              <div class="set-field"><label>名称</label><input v-model="editingProvider.name" class="set-inp" placeholder="OpenAI / DeepSeek / OpenRouter" /></div>
              <div class="set-field"><label>API Key</label><input v-model="editingProvider.key" type="password" class="set-inp" placeholder="sk-..." /></div>
              <div class="set-field"><label>Base URL</label><input v-model="editingProvider.baseUrl" class="set-inp" placeholder="https://api.openai.com" /></div>
              <div class="set-field">
                <label>模型列表</label>
                <div class="set-inline-row">
                  <input v-model="editingProvider.modelsStr" class="set-inp" placeholder="自动加载或逗号分隔" />
                  <button class="set-list-item-edit set-refresh-btn" :disabled="modelLoading" @click="loadEditingProviderModels">{{ modelLoading ? '加载中' : '刷新' }}</button>
                </div>
                <div v-if="modelLoadHint" :class="['set-hint', modelLoadOk ? 'ok' : '']">{{ modelLoadHint }}</div>
              </div>
              <div class="set-field"><label>余额查询路径</label><input v-model="editingProvider.billingPath" class="set-inp" placeholder="/v1/dashboard/billing" /></div>
              <div class="set-field"><label>JSONPath 解析</label><input v-model="editingProvider.jsonPath" class="set-inp" placeholder="$.data.total_available" /></div>
              <div class="set-modal-actions">
                <button class="ai-btn--ghost set-btn" @click="closeProviderEditor">取消</button>
                <button class="ai-btn--primary set-btn" :disabled="modelLoading" @click="saveProvider">保存</button>
              </div>
            </div>
          </div>
          <div class="set-card" style="margin-top: 12px">
            <div class="set-card-header">🎛️ 全局 LLM 生成参数</div>
            <div class="set-body">
              <div class="set-toggle-row"><span>流式输出 Streaming</span><button :class="['set-toggle', streaming ? 'on' : '']" @click="streaming = !streaming"><span class="set-toggle-knob"></span></button></div>
              <div class="set-slider-row"><label>Temperature: {{ params.temperature }}</label><input type="range" min="0" max="2" step="0.1" v-model.number="params.temperature" /></div>
              <div class="set-slider-row"><label>Top P: {{ params.topP }}</label><input type="range" min="0" max="1" step="0.05" v-model.number="params.topP" /></div>
              <div class="set-slider-row"><label>Max Tokens: {{ params.maxTokens }}</label><input type="range" min="256" max="32768" step="256" v-model.number="params.maxTokens" /></div>
              <div class="set-slider-row"><label>Presence Penalty: {{ params.presencePenalty }}</label><input type="range" min="-2" max="2" step="0.1" v-model.number="params.presencePenalty" /></div>
            </div>
          </div>
          <div class="set-card" style="margin-top: 12px">
            <div class="set-card-header">💬 对话界面</div>
            <div class="set-body">
              <div class="set-field">
                <label>默认显示消息条数（0 为无限制）</label>
                <div class="set-inline-row">
                  <Dropdown :items="displayLimitOptions" :label="displayLimitLabel" @select="onSelectLimitItem" class="set-dropdown-wrp" />
                  <Input v-if="displayLimitSelect === '__custom__'" :model-value="String(displayLimitCustom)" type="number" placeholder="输入条数" @update:model-value="onInputCustom" class="set-input-wrp" />
                </div>
              </div>
            </div>
          </div>
          <div class="set-card" style="margin-top: 12px">
            <div class="set-card-header"><span>📝 全局 Prompt 库</span><button class="set-add-btn" @click="addPrompt">+ 新增</button></div>
            <div class="set-list">
              <div v-for="(p, i) in prompts" :key="i" class="set-list-item" :class="{ default: p.isDefault }">
                <div class="set-list-item-main">
                  <div class="set-list-item-name">{{ p.name }} <span v-if="p.isDefault" class="set-tag-default">默认</span></div>
                  <div class="set-list-item-meta">{{ p.content?.slice(0, 60) }}...</div>
                </div>
                <button class="set-list-item-edit" @click="setDefaultPrompt(i)">设为默认</button>
                <button class="set-list-item-edit" @click="editPrompt(i)">✏️</button>
                <button class="set-list-item-del" @click="removePrompt(i)">✕</button>
              </div>
            </div>
          </div>
          <div v-if="editingPromptIndex !== null" class="set-modal-overlay" @click.self="cancelEditPrompt">
            <div class="set-modal">
              <div class="set-modal-title">📝 编辑 Prompt</div>
              <div class="set-field"><label>名称</label><input v-model="editingPrompt.name" class="set-inp" placeholder="Prompt 名称" /></div>
              <div class="set-field"><label>内容（System Prompt）</label><textarea v-model="editingPrompt.content" class="set-textarea set-prompt-content" rows="8" placeholder="输入系统提示词内容..."></textarea></div>
              <div class="set-modal-actions">
                <button class="ai-btn--ghost set-btn" @click="cancelEditPrompt">取消</button>
                <button class="ai-btn--primary set-btn" @click="savePrompt">保存</button>
              </div>
            </div>
          </div>
        </div>
        <div v-if="activeTab === 'agent'" class="set-section">
          <h3 class="set-title">🤖 Agent Studio</h3>
          <div class="set-card" style="margin-top: 12px">
            <div class="set-card-header">🔧 工具链管理器</div>
            <div class="set-tool-box">
              <div v-for="(t, i) in agentTools" :key="i" class="set-tool-item">
                <div class="set-tool-item-main">
                  <label class="set-checkbox"><input type="checkbox" v-model="t.enabled" />{{ t.name }}</label>
                  <div class="set-tool-item-desc">{{ t.description || '暂无说明' }}</div>
                </div>
                <button class="set-list-item-edit" @click="openToolSchema(i)">Schema</button>
              </div>
              <div v-if="agentTools.length === 0" class="set-empty">暂无工具</div>
            </div>
          </div>
          <div v-if="editingToolIdx !== null" class="set-modal-overlay" @click.self="cancelToolSchema">
            <div class="set-modal set-schema-modal">
              <div class="set-modal-title">🔍 {{ editingTool?.name }} — 工具配置</div>
              <div class="set-field"><label>Function Description</label><textarea v-model="editingToolDesc" class="set-textarea" rows="3" placeholder="修改大模型看到的工具说明..."></textarea></div>
              <div class="set-field"><label>Schema（只读）</label><textarea :value="editingToolSchema" class="set-textarea code" rows="6" readonly></textarea></div>
              <div class="set-modal-actions">
                <button class="ai-btn--ghost set-btn" @click="cancelToolSchema">取消</button>
                <button class="ai-btn--primary set-btn" @click="saveToolSchema">保存</button>
              </div>
            </div>
          </div>
          <div class="set-card" style="margin-top: 12px">
            <div class="set-card-header">🎛️ Agent 专属参数</div>
            <div class="set-body" style="display:flex;flex-direction:column;gap:10px">
              <div class="set-field">
                <label>🤖 Agent 系统提示词</label>
                <textarea v-model="agentParams.agentPrompt" class="set-textarea" rows="4" placeholder="Agent 专属 System Prompt，留空则使用全局默认 Prompt。"></textarea>
              </div>
              <div class="set-slider-row">
                <label>🔧 最大工具调用轮数: {{ agentParams.maxToolRounds }}</label>
                <input type="range" min="1" max="50" step="1" v-model.number="agentParams.maxToolRounds" />
                <span class="set-slider-hint">单次 AI 回复内连续调用工具的上限；不是后端冒充用户续杯</span>
              </div>
            </div>
          </div>
        </div>
        <div v-if="activeTab === 'appearance'" class="set-section">
          <h3 class="set-title">🎨 外观与个性化</h3>
          <div class="set-card">
            <div class="set-card-header">主题</div>
            <div class="set-body">
              <div class="set-radio-row"><label><input type="radio" v-model="theme" value="dark" /> 🌙 暗色</label></div>
              <div class="set-radio-row"><label><input type="radio" v-model="theme" value="light" /> ☀️ 亮色</label></div>
            </div>
          </div>
          <div class="set-card" style="margin-top: 12px">
            <div class="set-card-header">排版</div>
            <div class="set-body">
              <div class="set-field"><label>代码字体</label><input v-model="codeFont" class="set-inp" placeholder="JetBrains Mono" /></div>
              <div class="set-toggle-row"><span>代码连字 Ligatures</span><button :class="['set-toggle', ligatures ? 'on' : '']" @click="ligatures = !ligatures"><span class="set-toggle-knob"></span></button></div>
              <div class="set-toggle-row"><span>毛玻璃效果</span><button :class="['set-toggle', glass ? 'on' : '']" @click="glass = !glass"><span class="set-toggle-knob"></span></button></div>
            </div>
          </div>
        </div>
        <div v-if="activeTab === 'about'" class="set-section">
          <h3 class="set-title">ℹ️ 关于与数据主权</h3>
          <div class="set-card">
            <div class="set-card-header">存储统计</div>
            <div class="set-body">
              <div class="set-stat-row"><span>本地数据</span><span>{{ storageUsed }}MB / 1024MB</span></div>
              <div class="set-stat-row"><span>会话数量</span><span>{{ sessionCount }}</span></div>
              <div class="set-stat-row"><span>缓存大小</span><span>128MB</span></div>
            </div>
          </div>
          <div class="set-card" style="margin-top: 12px; border-color: var(--error)">
            <div class="set-card-header" style="color: var(--error)">⚠️ 数据核弹</div>
            <div class="set-body">
              <p class="set-warning-text">此操作将重置设置数据，不会删除会话文件。</p>
              <button class="set-danger-btn" @click="showNuke = true">💣 重置所有设置</button>
            </div>
          </div>
          <div class="set-card" style="margin-top: 12px">
            <div class="set-card-header">🛠️ 开发者模式</div>
            <div class="set-body">
              <div class="set-toggle-row"><span>开启 Dev Console</span><button :class="['set-toggle', devMode ? 'on' : '']" @click="devMode = !devMode"><span class="set-toggle-knob"></span></button></div>
              <p class="set-hint">开启后可在主界面查看实时 HTTP 请求日志。</p>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showNuke" class="set-modal-overlay" @click.self="showNuke = false">
      <div class="set-modal">
        <div class="set-modal-title">⚠️ 确认重置</div>
        <p style="color: var(--text2); margin-bottom: 12px; font-size: 14px">确定要重置所有设置吗？Provider、Prompt、外观等配置会恢复默认。</p>
        <div class="set-modal-actions">
          <button class="ai-btn--ghost set-btn" @click="showNuke = false">取消</button>
          <button class="set-danger-btn" @click="nukeAll">确认重置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import Input from '../components/ui/Input/Input.vue'
import Dropdown from '../components/ui/Dropdown/Dropdown.vue'

type Provider = {
  name: string
  key: string
  baseUrl: string
  models: string[]
  modelsStr?: string
  billingPath?: string
  jsonPath?: string
}

const API = window.location.origin
const isMobile = ref(window.innerWidth < 768)
const activeTab = ref('global')
const tabs = [
  { id: 'global', label: '全局设置', icon: '🌐' },
  { id: 'agent', label: 'Agent Studio', icon: '🤖' },
  { id: 'appearance', label: '外观', icon: '🎨' },
  { id: 'about', label: '关于', icon: 'ℹ️' },
]

async function apiGet(path: string) {
  const r = await fetch(`${API}${path}`)
  if (!r.ok) throw new Error(`GET ${path} ${r.status}`)
  return r.json()
}

async function apiPut(path: string, body: any) {
  const r = await fetch(`${API}${path}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await responseError(r, `PUT ${path} ${r.status}`))
  return r.json()
}

async function apiPost(path: string, body: any = {}) {
  const r = await fetch(`${API}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await responseError(r, `POST ${path} ${r.status}`))
  return r.json()
}

async function responseError(r: Response, fallback: string) {
  try { const data = await r.json(); return data?.detail || data?.message || fallback }
  catch { return (await r.text().catch(() => '')) || fallback }
}
const agentParams = reactive({ temperature: 0.3, maxTokens: 4096, maxToolRounds: 6, agentPrompt: '' })
const params = reactive({ temperature: 0.7, topP: 0.9, maxTokens: 8192, presencePenalty: 0 })
const streaming = ref(true)
const providers = ref<Provider[]>([])
const prompts = ref<any[]>([])
const editingProvider = ref<Provider | null>(null)
const editingProviderIndex = ref<number | null>(null)
const modelLoading = ref(false)
const modelLoadHint = ref('')
const modelLoadOk = ref(false)
const agentTools = ref<any[]>([])
const theme = ref('dark')
const codeFont = ref('JetBrains Mono')
const ligatures = ref(true)
const glass = ref(false)
const displayLimit = ref(30)
const displayLimitSelect = ref<string | number>(30)
const displayLimitCustom = ref(30)
const displayLimitOptions = [
  { label: '0（无限制）', value: 0 },
  { label: '10 条', value: 10 },
  { label: '20 条', value: 20 },
  { label: '30 条', value: 30 },
  { label: '40 条', value: 40 },
  { label: '50 条', value: 50 },
  { label: '✏️ 自定义', value: '__custom__' },
]
const displayLimitLabel = computed(() => {
  const opt = displayLimitOptions.find(o => o.value === displayLimitSelect.value)
  return opt ? opt.label : `自定义（${displayLimit.value} 条）`
})
function onSelectLimitItem(item: any) {
  displayLimitSelect.value = item.value
  if (item.value === '__custom__') {
    displayLimit.value = displayLimitCustom.value || 30
  } else {
    displayLimit.value = item.value
  }
  autoSave()
}
function onInputCustom(val: string) {
  const num = parseInt(val, 10)
  if (!isNaN(num) && num >= 0) { displayLimitCustom.value = num; displayLimit.value = num; autoSave() }
}
const storageUsed = ref(256)
const sessionCount = ref(0)
const devMode = ref(false)
const showNuke = ref(false)
const loadingSettings = ref(true)

const editingToolIdx = ref<number | null>(null)
const editingToolDesc = ref('')
const editingToolSchema = ref('')
const editingTool = computed(() => editingToolIdx.value !== null ? agentTools.value[editingToolIdx.value] : null)

function openToolSchema(i: number) {
  editingToolIdx.value = i
  const t = agentTools.value[i]
  editingToolDesc.value = t.description || ''
  editingToolSchema.value = typeof t.schema === 'string' ? t.schema : JSON.stringify(t.schema, null, 2)
}
function cancelToolSchema() { editingToolIdx.value = null; editingToolDesc.value = ''; editingToolSchema.value = '' }
function saveToolSchema() {
  if (editingToolIdx.value !== null) agentTools.value[editingToolIdx.value].description = editingToolDesc.value
  cancelToolSchema(); autoSave()
}

function providerKey(p: Provider, i: number) { return `${p.name || 'provider'}-${p.baseUrl || ''}-${i}` }

function normalizeModels(input: unknown): string[] {
  if (Array.isArray(input)) return Array.from(new Set(input.map(String).map(s => s.trim()).filter(Boolean)))
  if (typeof input === 'string') return Array.from(new Set(input.split(',').map(s => s.trim()).filter(Boolean)))
  return []
}

function addProvider() {
  modelLoadHint.value = ''; modelLoadOk.value = false
  editingProviderIndex.value = null
  editingProvider.value = { name: '', key: '', baseUrl: '', models: [], modelsStr: '', billingPath: '', jsonPath: '' }
}
function editProvider(i: number) {
  modelLoadHint.value = ''; modelLoadOk.value = false
  editingProviderIndex.value = i
  const p = providers.value[i]
  editingProvider.value = { ...p, models: normalizeModels(p.models), modelsStr: normalizeModels(p.models).join(',') }
}
function closeProviderEditor() { editingProvider.value = null; editingProviderIndex.value = null; modelLoadHint.value = ''; modelLoadOk.value = false }
function removeProvider(i: number) { providers.value.splice(i, 1); autoSave(); window.dispatchEvent(new CustomEvent('settings:providers-updated')) }

async function loadEditingProviderModels() {
  const p = editingProvider.value
  if (!p) return []
  if (!p.baseUrl?.trim()) { modelLoadOk.value = false; modelLoadHint.value = '请先填写 Base URL'; return [] }
  modelLoading.value = true; modelLoadOk.value = false; modelLoadHint.value = '正在请求 /v1/models ...'
  try {
    const data = await apiPost('/api/v1/settings/providers/models', { baseUrl: p.baseUrl.trim(), key: p.key || '' })
    const loaded = normalizeModels(data.models)
    const manual = normalizeModels(p.modelsStr)
    const merged = Array.from(new Set([...loaded, ...manual]))
    p.models = merged; p.modelsStr = merged.join(',')
    modelLoadOk.value = true; modelLoadHint.value = `已自动加载 ${loaded.length} 个模型${manual.length ? '，并合并手填模型' : ''}`
    return merged
  } catch (e: any) {
    const manual = normalizeModels(p.modelsStr)
    p.models = manual; modelLoadOk.value = false
    modelLoadHint.value = `自动加载失败：${e?.message || e}。已保留手填模型。`
    return manual
  } finally { modelLoading.value = false }
}

async function saveProvider() {
  if (!editingProvider.value) return
  const p = editingProvider.value
  await loadEditingProviderModels()
  const clean: Provider = {
    name: p.name?.trim() || '未命名 Provider', key: p.key || '', baseUrl: p.baseUrl?.trim() || '',
    models: normalizeModels(p.modelsStr || p.models), billingPath: p.billingPath || '', jsonPath: p.jsonPath || '',
  }
  if (editingProviderIndex.value !== null && editingProviderIndex.value >= 0) providers.value.splice(editingProviderIndex.value, 1, clean)
  else providers.value.push(clean)
  closeProviderEditor(); autoSave(); window.dispatchEvent(new CustomEvent('settings:providers-updated'))
}

function addPrompt() { prompts.value.push({ name: '新 Prompt', content: '', isDefault: false }); autoSave() }
function setDefaultPrompt(i: number) { prompts.value.forEach((p, idx) => { p.isDefault = idx === i }); autoSave() }

const editingPromptIndex = ref<number | null>(null)
const editingPrompt = reactive({ name: '', content: '' })
function editPrompt(i: number) { editingPromptIndex.value = i; const p = prompts.value[i]; editingPrompt.name = p.name || ''; editingPrompt.content = p.content || '' }
function cancelEditPrompt() { editingPromptIndex.value = null; editingPrompt.name = ''; editingPrompt.content = '' }
function savePrompt() {
  const i = editingPromptIndex.value
  if (i === null) return
  prompts.value[i].name = editingPrompt.name; prompts.value[i].content = editingPrompt.content
  cancelEditPrompt(); autoSave()
}
function removePrompt(i: number) { prompts.value.splice(i, 1); if (editingPromptIndex.value === i) cancelEditPrompt(); autoSave() }

function applySettings(data: any) {
  if (!data || typeof data !== 'object') return
  if (data.params) Object.assign(params, data.params)
  streaming.value = data.streaming !== false
  providers.value = Array.isArray(data.providers) ? data.providers.map((p: any) => ({ ...p, models: normalizeModels(p.models) })) : []
  prompts.value = Array.isArray(data.prompts) ? data.prompts : []
  agentTools.value = Array.isArray(data.agentTools) ? data.agentTools : []
  if (data.agentParams) Object.assign(agentParams, data.agentParams)
  theme.value = data.theme || 'dark'
  codeFont.value = data.codeFont || 'JetBrains Mono'
  ligatures.value = data.ligatures !== undefined ? !!data.ligatures : true
  glass.value = !!data.glass
  devMode.value = !!data.devMode
  const dl = data.displayLimit
  if (typeof dl === 'number' && dl >= 0) {
    displayLimit.value = dl
    if ([0, 10, 20, 30, 40, 50].includes(dl)) displayLimitSelect.value = dl
    else { displayLimitSelect.value = '__custom__'; displayLimitCustom.value = dl }
  }
}

async function nukeAll() {
  showNuke.value = false; storageUsed.value = 0
  try { const data = await apiPost('/api/v1/settings/reset'); applySettings(data.settings || data); alert('所有设置已重置为默认') }
  catch (e) { console.warn('设置重置失败', e); alert('设置重置失败，请查看控制台') }
}

async function loadSettings() {
  loadingSettings.value = true
  try { applySettings(await apiGet('/api/v1/settings')) }
  catch (e) { console.warn('设置加载失败，使用默认值', e) }
  finally { loadingSettings.value = false }
}

async function loadSessionCount() {
  try { const data = await apiGet('/api/v1/sessions'); sessionCount.value = Array.isArray(data.sessions) ? data.sessions.length : 0 }
  catch { sessionCount.value = 0 }
}

let saveTimer: ReturnType<typeof setTimeout> | null = null
function autoSave() {
  if (loadingSettings.value) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try {
      await apiPut('/api/v1/settings', {
        params: { ...params }, streaming: streaming.value,
        providers: providers.value.map(p => ({ ...p, models: normalizeModels(p.models) })),
        prompts: prompts.value, agentTools: agentTools.value, agentParams: { ...agentParams },
        theme: theme.value, codeFont: codeFont.value, ligatures: ligatures.value,
        glass: glass.value, devMode: devMode.value, displayLimit: displayLimit.value,
      })
      window.dispatchEvent(new CustomEvent('settings:providers-updated'))
    } catch (e) { console.warn('设置保存失败', e) }
  }, 500)
}

watch(params, autoSave, { deep: true })
watch(streaming, autoSave)
watch(providers, autoSave, { deep: true })
watch(prompts, autoSave, { deep: true })
watch(agentTools, autoSave, { deep: true })
watch(agentParams, autoSave, { deep: true })
watch(theme, autoSave)
watch(codeFont, autoSave)
watch(ligatures, autoSave)
watch(glass, autoSave)
watch(devMode, autoSave)
watch(displayLimit, autoSave)

function onResize() { isMobile.value = window.innerWidth < 768 }

onMounted(() => { window.addEventListener('resize', onResize); loadSettings(); loadSessionCount() })
onUnmounted(() => { window.removeEventListener('resize', onResize); if (saveTimer) clearTimeout(saveTimer) })
</script>

<style scoped>
.settings-page{height:100%;overflow:hidden;display:flex;flex-direction:column}
.set-layout{display:flex;height:100%}
.set-layout.mobile{flex-direction:column}
.set-tabs{width:160px;background:var(--surface);border-right:1px solid var(--border-light);display:flex;flex-direction:column;flex-shrink:0;overflow-y:auto}
.mobile .set-tabs{width:100%;flex-direction:row;border-right:none;border-bottom:1px solid var(--border-light);overflow-x:auto;flex-shrink:0}
.set-tab{display:flex;align-items:center;gap:8px;padding:12px 16px;cursor:pointer;color:var(--text2);font-size:13px;transition:all .15s;white-space:nowrap}.set-tab:hover{background:var(--surface-alt);color:var(--text)}.set-tab.active{background:var(--primary);color:#fff}
.mobile .set-tab{padding:10px 14px;font-size:12px;gap:4px}
.set-tab-icon{font-size:15px}
.set-content{flex:1;overflow-y:auto;padding:16px}
.set-section{max-width:680px}
.set-title{font-size:18px;font-weight:600;margin-bottom:12px}
.set-card{background:var(--surface);border:1px solid var(--border-light);border-radius:10px;overflow:hidden;margin-bottom:12px}
.set-card-header{padding:12px 14px;font-size:13px;font-weight:600;border-bottom:1px solid var(--border-light);display:flex;align-items:center;justify-content:space-between;gap:10px}
.set-body{padding:12px 14px}
.set-list{padding:0}
.set-empty{padding:16px 14px;color:var(--text2);font-size:12px}
.set-list-item{display:flex;align-items:center;gap:8px;padding:8px 14px;border-bottom:1px solid var(--border-light);font-size:13px;transition:background .1s}.set-list-item:hover{background:var(--surface-alt)}.set-list-item:last-child{border-bottom:none}.set-list-item.default{background:rgba(124,58,237,.08)}
.set-list-item-main{flex:1;min-width:0}.set-list-item-name{font-weight:500}.set-list-item-meta{font-size:11px;color:var(--text2);margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.set-list-item-edit{background:var(--surface-alt);border:none;color:var(--text2);padding:4px 10px;border-radius:6px;font-size:11px;cursor:pointer;white-space:nowrap}.set-list-item-edit:hover:not(:disabled){color:var(--text)}.set-list-item-edit:disabled{opacity:.55;cursor:not-allowed}
.set-list-item-del{background:transparent;border:none;color:var(--text3);cursor:pointer;font-size:12px;width:24px;height:24px;display:flex;align-items:center;justify-content:center;border-radius:50%}.set-list-item-del:hover{background:var(--error);color:#fff}
.set-list-item-tags{display:flex;gap:3px;flex-wrap:wrap;margin-top:3px}
.set-model-tag{font-size:10px;padding:1px 5px;border-radius:3px;background:var(--primary);color:#fff;opacity:.8;white-space:nowrap}.set-model-tag.more{opacity:.5}
.set-add-btn{background:var(--primary);border:none;color:#fff;padding:4px 10px;border-radius:6px;font-size:11px;cursor:pointer}
.set-field{margin-bottom:10px}.set-field label{display:block;font-size:12px;color:var(--text2);margin-bottom:4px}
.set-inline-row{display:flex;gap:8px;align-items:center}.set-inline-row .set-inp{flex:1}.set-refresh-btn{height:34px;padding:0 12px}
.set-dropdown-wrp{flex:1;min-width:140px}.set-input-wrp{width:120px}
.set-textarea{width:100%;padding:10px 12px;border-radius:6px;background:var(--bg);border:1px solid var(--border-light);color:var(--text);font-size:13px;font-family:monospace;resize:vertical;min-height:60px;outline:none}.set-textarea:focus{border-color:var(--primary)}
.set-textarea.code{background:#0d1117;font-size:12px;color:var(--text2)}
.set-slider-row{margin-bottom:10px}.set-slider-row label{display:block;font-size:12px;color:var(--text2);margin-bottom:4px}.set-slider-row input{width:100%}.set-slider-hint{display:block;font-size:11px;color:var(--text3);margin-top:2px;line-height:1.4}
.set-radio-row{margin-bottom:8px}.set-radio-row label{font-size:13px;color:var(--text);display:flex;align-items:center;gap:6px;cursor:pointer}
.set-toggle-row{display:flex;align-items:center;justify-content:space-between;padding:6px 0}.set-toggle-row span{font-size:13px}
.set-toggle{width:40px;height:22px;border-radius:11px;background:var(--surface-alt);border:none;cursor:pointer;position:relative;transition:background .2s}.set-toggle.on{background:var(--primary)}.set-toggle-knob{position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:#fff;transition:transform .2s}.set-toggle.on .set-toggle-knob{transform:translateX(18px)}
.set-stat-row{display:flex;justify-content:space-between;padding:6px 0;font-size:13px;border-bottom:1px solid var(--border-light)}.set-stat-row:last-child{border:none}
.set-warning-text{font-size:12px;color:var(--text2);margin-bottom:8px}
.set-danger-btn{background:var(--error);border:none;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;cursor:pointer}
.set-hint{font-size:11px;color:var(--text3);margin-top:6px;line-height:1.45}.set-hint.ok{color:var(--success)}
.set-tag-default{font-size:9px;padding:1px 6px;border-radius:4px;background:var(--primary);color:#fff;margin-left:6px}
.set-prompt-content{min-height:200px;font-family:'JetBrains Mono','Fira Code',monospace;font-size:13px;line-height:1.65;background:#0d1117!important;color:#e6edf3!important;border-color:var(--border-light)!important}
.set-checkbox{display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px;flex:1}.set-checkbox input{accent-color:var(--primary)}
.set-tool-box{max-height:320px;overflow-y:auto;padding:0}.set-tool-item{display:flex;gap:8px;padding:8px 14px;border-bottom:1px solid var(--border-light);font-size:13px;transition:background .1s}.set-tool-item:hover{background:var(--surface-alt)}.set-tool-item:last-child{border-bottom:none}.set-tool-item-main{flex:1;min-width:0}.set-tool-item-desc{font-size:11px;color:var(--text3);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-left:22px}.set-tool-box .set-empty{padding:16px 14px;color:var(--text2);font-size:12px}
.set-schema-modal{max-width:560px}
.set-modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px}
.set-modal{background:var(--surface);border-radius:14px;padding:20px;max-width:440px;width:100%;max-height:80vh;overflow-y:auto}.set-modal-title{font-size:16px;font-weight:600;margin-bottom:12px}
.set-modal-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:12px}
.set-btn{padding:8px 16px!important;border-radius:6px!important;font-size:13px!important;border:none!important;cursor:pointer}.set-btn:disabled{opacity:.6;cursor:not-allowed}.ai-btn--ghost{background:var(--surface-alt);color:var(--text2)}.ai-btn--primary{background:var(--primary);color:#fff}
@media (max-width: 767px){.set-content{padding:12px}.set-section{max-width:none}.set-modal{max-width:100%}.set-inline-row{flex-direction:column;align-items:stretch}.set-refresh-btn{height:32px}}
</style>

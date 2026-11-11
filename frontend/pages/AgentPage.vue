<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <!-- 页头 -->
      <header class="ui-hero ag-hero">
        <div class="ui-hero-main">
          <div class="ui-eyebrow">AGENT STUDIO</div>
          <h1 class="ui-title">智能体</h1>
          <p class="ui-sub">运行时参数、能力开关与工具注册表。所有改动即时生效，无需重启。</p>
        </div>
        <div class="ui-head-actions">
          <button class="ui-btn" @click="load" :disabled="loading">
            <RefreshCw :size="14" :class="{ spin: loading }" /> 刷新
          </button>
          <button class="ui-btn ui-btn--primary" @click="router.push('/settings')">
            <SlidersHorizontal :size="14" /> 调整参数
          </button>
        </div>
      </header>

      <!-- 视图切换 -->
      <div class="ag-tabs">
        <div class="ui-seg" role="tablist" aria-label="智能体视图">
          <button
            type="button"
            role="tab"
            class="ui-seg-item"
            :class="{ active: activeTab === 'runtime' }"
            :aria-selected="activeTab === 'runtime'"
            @click="activeTab = 'runtime'"
          >运行时</button>
          <button
            type="button"
            role="tab"
            class="ui-seg-item"
            :class="{ active: activeTab === 'persona' }"
            :aria-selected="activeTab === 'persona'"
            @click="activeTab = 'persona'"
          >角色人设</button>
          <button
            type="button"
            role="tab"
            class="ui-seg-item"
            :class="{ active: activeTab === 'skills' }"
            :aria-selected="activeTab === 'skills'"
            @click="activeTab = 'skills'"
          >技能</button>
        </div>
      </div>

      <!-- 运行时 -->
      <div v-show="activeTab === 'runtime'" class="ag-pane">
        <!-- 运行时身份 -->
        <section class="ui-card ui-card--glow agent-card">
          <div class="agent-avatar">
            <Bot :size="24" />
          </div>
          <div class="agent-body">
            <div class="agent-name">
              {{ agentName }}
              <span class="ui-badge ui-badge--ok"><span class="dot"></span>运行中</span>
            </div>
            <div class="agent-meta">
              <span><Cpu :size="11" /> {{ modelLabel }}</span>
              <span><GitBranch :size="11" /> v{{ version }}</span>
              <span><Clock :size="11" /> 已运行 {{ uptime }}</span>
            </div>
          </div>
        </section>

        <!-- 指标 -->
        <div class="ui-grid ui-grid--4 ag-stats">
          <div class="ui-stat">
            <div class="ui-stat-label">可用工具</div>
            <div class="ui-stat-value">{{ toolCount }}</div>
            <div class="ui-stat-hint">已启用的 Tool Registry 条目</div>
          </div>
          <div class="ui-stat">
            <div class="ui-stat-label">已启用技能</div>
            <div class="ui-stat-value">{{ skills.filter(s => s.enabled).length }}<span class="stat-unit">/{{ skills.length }}</span></div>
            <div class="ui-stat-hint">本地 Agent Skills 指南</div>
          </div>
          <div class="ui-stat">
            <div class="ui-stat-label">会话总数</div>
            <div class="ui-stat-value">{{ sessionCount }}</div>
            <div class="ui-stat-hint">后端累计统计</div>
          </div>
          <div class="ui-stat">
            <div class="ui-stat-label">当前模型</div>
            <div class="ui-stat-value stat-text">{{ modelLabel }}</div>
            <div class="ui-stat-hint">顶栏可随时切换</div>
          </div>
        </div>

        <!-- 运行时参数 -->
        <section class="ui-section">
          <div class="ui-section-head">
            <div>
              <div class="ui-section-title">运行时参数</div>
              <div class="ui-section-sub">决定采样行为与工具调用深度，修改后立即作用于下一次请求。</div>
            </div>
            <div class="ui-section-actions">
              <span class="ui-badge ui-badge--primary">即时生效</span>
            </div>
          </div>

          <div class="ui-grid ui-grid--2 ag-params">
            <div class="ui-card param" v-for="p in params" :key="p.label">
              <div class="param-icon" :style="{ color: p.color, background: p.bg }">
                <component :is="p.icon" :size="15" />
              </div>
              <div class="param-body">
                <div class="param-value">{{ p.value }}</div>
                <div class="param-label">{{ p.label }}</div>
              </div>
            </div>
          </div>
        </section>

        <!-- 系统提示词 -->
        <section class="ui-section">
          <div class="ui-section-head">
            <div>
              <div class="ui-section-title"><ScrollText :size="15" /> 当前 System Prompt</div>
              <div class="ui-section-sub">Agent 专属提示词，留空时使用全局默认提示词。</div>
            </div>
            <div class="ui-section-actions">
              <button class="ui-btn ui-btn--sm" @click="router.push('/prompt')">
                <FileText :size="12" /> 提示词库
              </button>
            </div>
          </div>
          <pre class="prompt-box">{{ agentPrompt || defaultPrompt || '（未设置）' }}</pre>
        </section>

        <!-- 快捷入口 -->
        <section class="ui-section ag-last">
          <div class="ui-section-head">
            <div>
              <div class="ui-section-title">快捷入口</div>
              <div class="ui-section-sub">常用能力面板，一键直达。</div>
            </div>
          </div>

          <div class="ui-grid ui-grid--3">
            <button class="ui-card ui-card--hover quick" @click="router.push('/tools')">
              <span class="quick-ico"><Wrench :size="17" /></span>
              <span class="quick-body">
                <span class="quick-title">工具中心</span>
                <span class="quick-desc">启停工具、查看参数、直接试跑</span>
              </span>
              <ArrowRight :size="14" class="quick-arrow" />
            </button>
            <button class="ui-card ui-card--hover quick" @click="router.push('/plugins')">
              <span class="quick-ico"><Puzzle :size="17" /></span>
              <span class="quick-body">
                <span class="quick-title">技能中心</span>
                <span class="quick-desc">浏览与安装本地能力包</span>
              </span>
              <ArrowRight :size="14" class="quick-arrow" />
            </button>
            <button class="ui-card ui-card--hover quick" @click="router.push('/memory')">
              <span class="quick-ico"><Brain :size="17" /></span>
              <span class="quick-body">
                <span class="quick-title">兴趣与记忆</span>
                <span class="quick-desc">告诉助手你长期关注什么</span>
              </span>
              <ArrowRight :size="14" class="quick-arrow" />
            </button>
          </div>
        </section>
      </div>

      <!-- 角色人设 -->
      <div v-show="activeTab === 'persona'" class="ag-pane">
        <PersonaPanel />
      </div>

      <!-- 技能 -->
      <div v-show="activeTab === 'skills'" class="ag-pane">
        <!-- 技能开关 -->
        <section class="ui-section">
          <div class="ui-section-head">
            <div>
              <div class="ui-section-title"><Puzzle :size="15" /> 本地技能（Agent Skills）</div>
              <div class="ui-section-sub">Markdown 工作指南，只在相关任务时按需读取，不执行任何代码。</div>
            </div>
            <div class="ui-section-actions">
              <span class="ui-badge">{{ skills.filter(s => s.enabled).length }} 个已启用</span>
            </div>
          </div>

          <div v-if="loading" class="skill-grid">
            <div v-for="i in 3" :key="i" class="ui-skeleton" style="height: 104px"></div>
          </div>

          <div v-else-if="!skills.length" class="ui-empty">
            <div class="ui-empty-icon">🧩</div>
            <div class="ui-empty-title">还没有安装技能</div>
            <div class="ui-empty-desc">在项目的 skills/ 目录下创建 &lt;id&gt;/SKILL.md 即可被自动发现。</div>
          </div>

          <div v-else class="skill-grid">
            <article v-for="s in skills" :key="s.id" :class="['ui-card', 'ui-card--hover', 'skill', { off: !s.enabled }]">
              <div class="skill-hd">
                <span class="skill-name">{{ s.name }}</span>
                <button
                  :class="['ui-switch', { on: s.enabled }]"
                  :disabled="savingSkill === s.id"
                  @click="toggleSkill(s)"
                ></button>
              </div>
              <p class="skill-desc">{{ s.description || '（无描述）' }}</p>
              <div class="skill-ft">
                <code>{{ s.id }}</code>
                <span class="ui-badge">{{ s.category }}</span>
              </div>
            </article>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, inject } from 'vue'
import { useRouter } from 'vue-router'
import {
  RefreshCw, SlidersHorizontal, Bot, Cpu, GitBranch, Clock, Puzzle, ScrollText,
  FileText, Wrench, Brain, ArrowRight, Thermometer, Layers, Repeat, Hash,
} from 'lucide-vue-next'
import PersonaPanel from '@/components/agent/PersonaPanel.vue'

const router = useRouter()
const currentModel = inject<any>('currentModel', ref(''))

const activeTab = ref('runtime')
const loading = ref(true)
const skills = ref<any[]>([])
const savingSkill = ref('')
const settings = ref<any>({})
const status = ref<any>({})
const toolCount = ref(0)

const version = computed(() => status.value?.version || '2.1.0')
const sessionCount = computed(() => status.value?.stats?.sessions ?? 0)

const uptime = computed(() => {
  const s = status.value?.stats?.uptime_seconds || 0
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h >= 24) return `${Math.floor(h / 24)} 天 ${h % 24} 小时`
  if (h > 0) return `${h} 小时 ${m} 分`
  return `${m} 分钟`
})

const modelLabel = computed(() => currentModel?.value || settings.value?.providers?.[0]?.models?.[0] || '未选择模型')
const agentName = computed(() => settings.value?.agentParams?.agentName || 'Personal AI Agent')
const agentPrompt = computed(() => settings.value?.agentParams?.agentPrompt || '')
const defaultPrompt = computed(() => {
  const list = settings.value?.prompts || []
  return list.find((p: any) => p.isDefault)?.content || list[0]?.content || ''
})

const params = computed(() => {
  const ap = settings.value?.agentParams || {}
  return [
    { label: 'Temperature', value: ap.temperature ?? '—', icon: Thermometer, color: 'var(--warn)', bg: 'color-mix(in srgb, var(--warn) 14%, transparent)' },
    { label: 'Max Tokens', value: ap.maxTokens ?? '—', icon: Hash, color: 'var(--info)', bg: 'color-mix(in srgb, var(--info) 14%, transparent)' },
    { label: '工具调用轮数', value: ap.maxToolRounds ?? '—', icon: Repeat, color: 'var(--primary)', bg: 'var(--primary-soft)' },
    { label: 'Top P', value: ap.topP ?? '—', icon: Layers, color: 'var(--success)', bg: 'color-mix(in srgb, var(--success) 14%, transparent)' },
  ]
})

async function load() {
  loading.value = true
  try {
    const [sRes, kRes, stRes, tRes] = await Promise.all([
      fetch('/api/v1/settings').then((r) => r.json()).catch(() => ({})),
      fetch('/api/v1/skills').then((r) => r.json()).catch(() => ({ skills: [] })),
      fetch('/api/v1/status').then((r) => r.json()).catch(() => ({})),
      fetch('/api/v1/tools').then((r) => r.json()).catch(() => ({ tools: [] })),
    ])
    settings.value = sRes || {}
    skills.value = kRes.skills || []
    status.value = stRes || {}
    toolCount.value = (tRes.tools || []).filter((t: any) => t.enabled).length
  } finally {
    loading.value = false
  }
}

async function toggleSkill(s: any) {
  savingSkill.value = s.id
  const next = skills.value.map((item) =>
    item.id === s.id ? { ...item, enabled: !item.enabled } : item,
  )
  try {
    const r = await fetch('/api/v1/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabledSkills: next.filter((i) => i.enabled).map((i) => i.id) }),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    skills.value = next
  } catch (e: any) {
    alert(`保存失败：${e?.message || e}`)
  } finally {
    savingSkill.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
/* ============================================================
   Agent Studio — Aurora Console
   ============================================================ */
/* 中文：============================================================ Agent Studio — Aurora Console ============================================================ */
.ag-hero { margin-bottom: 18px; }

/* ---------------- 视图切换 ---------------- */
.ag-tabs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}
.ag-pane { min-width: 0; }
.ag-pane > .ui-section:last-child { margin-bottom: 0; }

/* ---------------- 运行时身份卡 ---------------- */
.agent-card {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 18px 20px;
  margin-bottom: 14px;
  background:
    radial-gradient(80% 130% at 0% 0%, var(--primary-soft) 0%, transparent 58%),
    var(--surface);
}

.agent-avatar {
  width: 52px;
  height: 52px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 14px;
  color: var(--primary);
  background: color-mix(in srgb, var(--primary) 16%, transparent);
  border: 1px solid color-mix(in srgb, var(--primary) 30%, transparent);
  box-shadow: 0 0 26px color-mix(in srgb, var(--primary) 20%, transparent);
}

.agent-body { flex: 1 1 240px; min-width: 0; }

.agent-name {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
  font-size: 17px;
  font-weight: 720;
  letter-spacing: -0.022em;
  line-height: 1.3;
}
.agent-name .dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--success);
  display: inline-block;
  margin-right: 4px;
  box-shadow: 0 0 8px color-mix(in srgb, var(--success) 70%, transparent);
}

.agent-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 7px;
  font-size: 11.5px;
  color: var(--text3);
}
.agent-meta span { display: flex; align-items: center; gap: 4px; }

/* ---------------- 指标 ---------------- */
.ag-stats { margin-bottom: 18px; }
.stat-unit {
  font-size: 14px;
  font-weight: 620;
  color: var(--text3);
  letter-spacing: 0;
}
.stat-text {
  font-size: 15px;
  line-height: 1.45;
  word-break: break-word;
}

/* ---------------- 参数 ---------------- */
.ag-params { gap: 12px; }
.param {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px 16px;
}
.param-icon {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 10px;
}
.param-body { min-width: 0; }
.param-value {
  font-size: 19px;
  font-weight: 720;
  letter-spacing: -0.025em;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.param-label {
  margin-top: 2px;
  font-size: 11px;
  color: var(--text3);
  letter-spacing: 0.01em;
}

/* ---------------- 技能 ---------------- */
.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.skill {
  display: flex;
  flex-direction: column;
  padding: 16px;
  border-radius: var(--r-md);
  transition: opacity var(--t-mid), border-color var(--t-mid), transform var(--t-mid);
}
.skill:hover { transform: translateY(-1px); }
.skill.off { opacity: 0.55; }
.skill.off:hover { transform: none; }

.skill-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.skill-name {
  font-size: 12.5px;
  font-weight: 650;
  letter-spacing: -0.01em;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.skill-desc {
  margin-top: 8px;
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--text2);
  flex: 1;
  min-height: 38px;
}
.skill-ft {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.skill-ft code {
  font-size: 10.5px;
  color: var(--text3);
  background: var(--surface-alt);
  padding: 2px 7px;
  border-radius: var(--r-xs);
  max-width: 62%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ---------------- System Prompt ---------------- */
/* 中文：---------------- 系统提示词 ---------------- */
.prompt-box {
  margin: 0;
  padding: 16px;
  max-height: 260px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.75;
  color: var(--text2);
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: 12px;
}

/* ---------------- 快捷入口 ---------------- */
.quick {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px 16px;
  text-align: left;
  color: var(--text2);
  transition: color var(--t-fast), border-color var(--t-mid), transform var(--t-mid), box-shadow var(--t-mid);
}
.quick:hover {
  color: var(--text);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}
.quick-ico {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: var(--primary);
  background: var(--primary-soft);
  border: 1px solid color-mix(in srgb, var(--primary) 24%, transparent);
}
.quick-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.quick-title {
  font-size: 12.5px;
  font-weight: 640;
  color: var(--text);
  letter-spacing: -0.01em;
}
.quick-desc {
  font-size: 11px;
  color: var(--text3);
  line-height: 1.5;
}
.quick-arrow { margin-left: auto; flex-shrink: 0; color: var(--text3); transition: transform var(--t-fast), color var(--t-fast); }
.quick:hover .quick-arrow { color: var(--primary); transform: translateX(2px); }

.ag-last { margin-bottom: 0; }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* AIOS-MOBILE */
/* 中文：AIOS-MOBILE */
@media (max-width: 767px) {
  .ag-tabs { margin-bottom: 12px; }

  .agent-card { padding: 15px; gap: 14px; margin-bottom: 12px; }
  .agent-avatar { width: 46px; height: 46px; border-radius: 12px; }
  .agent-name { font-size: 16px; }
  .agent-meta { gap: 10px; font-size: 10.5px; }

  .ag-stats { margin-bottom: 13px; }
  .stat-text { font-size: 13.5px; }

  .ag-params { gap: 10px; }
  .param { padding: 13px 14px; }
  .param-value { font-size: 17px; }

  .skill-grid { grid-template-columns: minmax(0, 1fr); gap: 10px; }
  .skill { padding: 14px; }
  .skill:hover { transform: none; }
  .skill-desc { min-height: 0; }

  .prompt-box { max-height: 200px; padding: 13px; font-size: 11.5px; }

  .quick { padding: 13px 14px; }
  .quick:hover { transform: none; }
  .quick-arrow { display: none; }
}
/* /AIOS-MOBILE */
/* 中文：/AIOS-MOBILE */
</style>

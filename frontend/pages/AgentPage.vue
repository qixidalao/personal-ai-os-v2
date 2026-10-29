<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <header class="ui-head">
        <div>
          <div class="ui-eyebrow">Agent Studio</div>
          <h1 class="ui-title">智能体</h1>
          <p class="ui-sub">查看当前智能体的运行配置、能力开关与本地技能。所有改动即时生效，无需重启。</p>
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

      <!-- 概览 -->
      <section class="hero ui-card ui-card--glow">
        <div class="hero-left">
          <div class="hero-avatar">
            <Bot :size="26" />
          </div>
          <div class="hero-info">
            <div class="hero-name">
              {{ agentName }}
              <span class="ui-badge ui-badge--ok"><span class="dot"></span>运行中</span>
            </div>
            <div class="hero-meta">
              <span><Cpu :size="11" /> {{ modelLabel }}</span>
              <span><GitBranch :size="11" /> v{{ version }}</span>
              <span><Clock :size="11" /> 已运行 {{ uptime }}</span>
            </div>
          </div>
        </div>

        <div class="hero-stats">
          <div class="hs">
            <div class="hs-value">{{ toolCount }}</div>
            <div class="hs-label">可用工具</div>
          </div>
          <div class="hs">
            <div class="hs-value">{{ skills.filter(s => s.enabled).length }}/{{ skills.length }}</div>
            <div class="hs-label">启用技能</div>
          </div>
          <div class="hs">
            <div class="hs-value">{{ sessionCount }}</div>
            <div class="hs-label">会话总数</div>
          </div>
        </div>
      </section>

      <!-- 参数 -->
      <div class="ui-grid ui-grid--4" style="margin-top: 14px">
        <div class="pcard" v-for="p in params" :key="p.label">
          <div class="pcard-icon" :style="{ color: p.color, background: p.bg }">
            <component :is="p.icon" :size="14" />
          </div>
          <div class="pcard-val">{{ p.value }}</div>
          <div class="pcard-label">{{ p.label }}</div>
        </div>
      </div>

      <!-- 技能 -->
      <section class="ui-card" style="margin-top: 22px">
        <div class="ui-card-hd">
          <div>
            <div class="ui-card-title"><Puzzle :size="15" /> 本地技能（Agent Skills）</div>
            <div class="ui-card-desc">Markdown 工作指南，只在相关任务时按需读取，不执行任何代码。</div>
          </div>
          <span class="ui-badge">{{ skills.filter(s => s.enabled).length }} 个已启用</span>
        </div>

        <div v-if="loading" class="skill-grid">
          <div v-for="i in 3" :key="i" class="ui-skeleton" style="height: 92px"></div>
        </div>

        <div v-else-if="!skills.length" class="ui-empty">
          <div class="ui-empty-icon">🧩</div>
          <div class="ui-empty-title">还没有安装技能</div>
          <div class="ui-empty-desc">在项目的 skills/ 目录下创建 &lt;id&gt;/SKILL.md 即可被自动发现。</div>
        </div>

        <div v-else class="skill-grid">
          <article v-for="s in skills" :key="s.id" :class="['skill', { off: !s.enabled }]">
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

      <!-- 系统提示词 -->
      <section class="ui-card" style="margin-top: 14px">
        <div class="ui-card-hd">
          <div>
            <div class="ui-card-title"><ScrollText :size="15" /> 当前 System Prompt</div>
            <div class="ui-card-desc">Agent 专属提示词，留空时使用全局默认提示词。</div>
          </div>
          <button class="ui-btn ui-btn--sm" @click="router.push('/prompt')">
            <FileText :size="12" /> 提示词库
          </button>
        </div>
        <pre class="prompt-box">{{ agentPrompt || defaultPrompt || '（未设置）' }}</pre>
      </section>

      <!-- 快捷入口 -->
      <div class="ui-grid ui-grid--3" style="margin-top: 14px">
        <button class="quick" @click="router.push('/tools')">
          <Wrench :size="17" />
          <div>
            <div class="quick-title">工具中心</div>
            <div class="quick-desc">启停工具、查看参数、直接试跑</div>
          </div>
          <ArrowRight :size="14" class="quick-arrow" />
        </button>
        <button class="quick" @click="router.push('/plugins')">
          <Puzzle :size="17" />
          <div>
            <div class="quick-title">技能中心</div>
            <div class="quick-desc">浏览与安装本地能力包</div>
          </div>
          <ArrowRight :size="14" class="quick-arrow" />
        </button>
        <button class="quick" @click="router.push('/memory')">
          <Brain :size="17" />
          <div>
            <div class="quick-title">兴趣与记忆</div>
            <div class="quick-desc">告诉助手你长期关注什么</div>
          </div>
          <ArrowRight :size="14" class="quick-arrow" />
        </button>
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

const router = useRouter()
const currentModel = inject<any>('currentModel', ref(''))

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
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
  padding: 22px;
}

.hero-left { display: flex; align-items: center; gap: 15px; min-width: 0; }

.hero-avatar {
  width: 54px; height: 54px;
  border-radius: var(--r-md);
  display: grid; place-items: center;
  background: var(--grad-primary);
  color: #fff;
  box-shadow: 0 6px 22px var(--primary-glow);
  flex-shrink: 0;
}

.hero-name {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 17px;
  font-weight: 720;
  letter-spacing: -0.02em;
}
.hero-name .dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--success);
  display: inline-block;
  margin-right: 4px;
}
.hero-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--text3);
  flex-wrap: wrap;
}
.hero-meta span { display: flex; align-items: center; gap: 4px; }

.hero-stats { display: flex; gap: 26px; }
.hs { text-align: right; }
.hs-value { font-size: 19px; font-weight: 720; letter-spacing: -0.02em; line-height: 1.2; }
.hs-label { font-size: 10.5px; color: var(--text3); margin-top: 1px; }

.pcard {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface);
  transition: border-color var(--t-mid), transform var(--t-mid);
}
.pcard:hover { border-color: var(--border-strong); transform: translateY(-1px); }
.pcard-icon {
  width: 28px; height: 28px;
  border-radius: var(--r-xs);
  display: grid; place-items: center;
  margin-bottom: 5px;
}
.pcard-val { font-size: 17px; font-weight: 700; letter-spacing: -0.02em; }
.pcard-label { font-size: 10.5px; color: var(--text3); }

.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.skill {
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  padding: 14px;
  background: var(--surface-2);
  transition: border-color var(--t-mid), opacity var(--t-mid);
}
.skill:hover { border-color: var(--border-strong); }
.skill.off { opacity: 0.55; }

.skill-hd { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.skill-name { font-size: 12.5px; font-weight: 650; }
.skill-desc {
  font-size: 11.5px;
  color: var(--text2);
  line-height: 1.6;
  margin-top: 7px;
  min-height: 36px;
}
.skill-ft { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 10px; }
.skill-ft code { font-size: 10px; background: var(--surface-alt); color: var(--text3); padding: 1px 6px; }

.prompt-box {
  font-size: 12px;
  line-height: 1.75;
  color: var(--text2);
  background: var(--bg);
  max-height: 220px;
  overflow: auto;
  white-space: pre-wrap;
}

.quick {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface);
  color: var(--text2);
  text-align: left;
  transition: all var(--t-mid);
}
.quick:hover {
  border-color: color-mix(in srgb, var(--primary) 42%, transparent);
  color: var(--text);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}
.quick-title { font-size: 12.5px; font-weight: 640; color: var(--text); }
.quick-desc { font-size: 11px; color: var(--text3); margin-top: 2px; }
.quick-arrow { margin-left: auto; color: var(--text3); }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 700px) {
  .hero-stats { gap: 18px; }
  .hero { padding: 18px; }
}
</style>

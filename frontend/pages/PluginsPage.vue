<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <!-- 页头 -->
      <header class="ui-hero sk-hero">
        <div class="ui-hero-main">
          <div class="ui-eyebrow">SKILL MARKET</div>
          <h1 class="ui-title">技能中心</h1>
          <p class="ui-sub">
            Agent Skills 是一份按需读取的 Markdown 工作指南。助手只在相关任务里读它，
            不会执行其中的代码，所以可以放心把方法论沉淀进来。
          </p>
        </div>
        <div class="ui-head-actions">
          <button class="ui-btn" @click="load" :disabled="loading">
            <RefreshCw :size="14" :class="{ spin: loading }" /> 刷新
          </button>
          <button class="ui-btn ui-btn--primary" @click="router.push('/agent')">
            <Bot :size="14" /> 到智能体配置
          </button>
        </div>
      </header>

      <!-- 指标 -->
      <div class="ui-grid ui-grid--3 sk-stats">
        <div class="ui-stat">
          <div class="ui-stat-label stat-label"><Puzzle :size="12" /> 已安装技能</div>
          <div class="ui-stat-value">{{ skills.length }}</div>
          <div class="ui-stat-hint">skills/ 目录下可发现的指南</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label stat-label"><Power :size="12" /> 已启用</div>
          <div class="ui-stat-value">{{ enabledCount }}</div>
          <div class="ui-stat-hint">助手当前会读取的技能</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label stat-label"><Layers :size="12" /> 分类</div>
          <div class="ui-stat-value">{{ categories.length }}</div>
          <div class="ui-stat-hint">按使用场景归类的技能族</div>
        </div>
      </div>

      <!-- 分类筛选 -->
      <div class="ui-toolbar sk-filter">
        <button :class="['ui-chip', { active: cat === '' }]" @click="cat = ''">全部</button>
        <button
          v-for="c in categories"
          :key="c"
          :class="['ui-chip', { active: cat === c }]"
          @click="cat = c"
        >{{ c }}</button>
        <span class="sk-count">显示 {{ filtered.length }} / 共 {{ skills.length }}</span>
      </div>

      <!-- 技能列表 -->
      <section class="ui-section">
        <div class="ui-section-head">
          <div>
            <div class="ui-section-title">能力市场</div>
            <div class="ui-section-sub">打开开关即生效，助手会在匹配的任务里自动读取对应指南。</div>
          </div>
          <div class="ui-section-actions">
            <span class="ui-badge">{{ enabledCount }} 个已启用</span>
          </div>
        </div>

        <div v-if="loading" class="skill-grid">
          <div v-for="i in 3" :key="i" class="ui-skeleton" style="height: 152px"></div>
        </div>

        <div v-else-if="!filtered.length" class="ui-empty">
          <div class="ui-empty-icon">🧩</div>
          <div class="ui-empty-title">这里还没有技能</div>
          <div class="ui-empty-desc">按下面的三步添加一个 SKILL.md，刷新后就会出现在这里。</div>
        </div>

        <div v-else class="skill-grid">
          <article v-for="s in filtered" :key="s.id" :class="['ui-card', 'ui-card--hover', 'skcard', { off: !s.enabled }]">
            <div class="skcard-hd">
              <div class="skcard-title">
                <span class="skcard-glyph">{{ glyphOf(s.category) }}</span>
                <div class="skcard-title-text">
                  <div class="skcard-name">{{ s.name }}</div>
                  <code class="skcard-id">{{ s.id }}</code>
                </div>
              </div>
              <button
                :class="['ui-switch', { on: s.enabled }]"
                :disabled="saving === s.id"
                @click="toggle(s)"
              ></button>
            </div>

            <p class="skcard-desc">{{ s.description || '（无描述）' }}</p>

            <div class="skcard-ft">
              <span class="ui-badge">{{ s.category }}</span>
              <button class="ui-btn ui-btn--sm ui-btn--ghost" @click="readGuide(s)">
                <BookOpen :size="12" /> 读取指南
              </button>
            </div>
          </article>
        </div>
      </section>

      <!-- 新增技能说明 -->
      <section class="ui-section sk-last">
        <div class="ui-section-head">
          <div>
            <div class="ui-section-title"><PlusCircle :size="15" /> 新增一个技能</div>
            <div class="ui-section-sub">后端启动时会扫描 skills/*/SKILL.md，无需重启即可热加载。</div>
          </div>
          <div class="ui-section-actions">
            <span class="ui-badge ui-badge--primary">3 步完成</span>
          </div>
        </div>

        <div class="new-grid">
          <ol class="steps">
            <li><b>建目录</b><code>skills/my-skill/</code></li>
            <li><b>写指南</b><code>SKILL.md</code>，顶部用 YAML frontmatter 写 name / description / category</li>
            <li><b>刷新本页</b>并打开开关，助手就能在相关任务里读到它</li>
          </ol>
          <pre class="sample">---
name: 我的技能
description: 一句话说明什么时候该用它
category: general
---

这里写具体的工作方法、检查清单、示例。</pre>
        </div>
      </section>
    </div>

    <!-- 指南预览 -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="guide" class="modal-mask" @click.self="guide = null">
          <div class="modal">
            <div class="modal-hd">
              <div class="modal-hd-main">
                <div class="modal-title">{{ guide.name }}</div>
                <code class="modal-id">{{ guide.id }}</code>
              </div>
              <button class="ui-btn ui-btn--ghost ui-btn--icon" @click="guide = null"><X :size="15" /></button>
            </div>
            <div class="modal-bd">
              <div v-if="guideLoading" class="ui-skeleton" style="height: 120px"></div>
              <pre v-else class="guide-text">{{ guideText }}</pre>
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
  RefreshCw, Puzzle, Power, Layers, BookOpen, PlusCircle, X, Bot,
} from 'lucide-vue-next'

const router = useRouter()
const skills = ref<any[]>([])
const loading = ref(true)
const cat = ref('')
const saving = ref('')
const guide = ref<any>(null)
const guideText = ref('')
const guideLoading = ref(false)

const categories = computed(() => {
  const set = new Set<string>()
  for (const s of skills.value) if (s.category) set.add(s.category)
  return [...set].sort()
})
const enabledCount = computed(() => skills.value.filter((s) => s.enabled).length)
const filtered = computed(() => (cat.value ? skills.value.filter((s) => s.category === cat.value) : skills.value))

function glyphOf(category?: string) {
  const map: Record<string, string> = {
    research: '🔎', discovery: '📡', frontend: '🎨', writing: '✍️',
    coding: '💻', data: '📊', general: '🧩',
  }
  return map[category || 'general'] || '🧩'
}

async function load() {
  loading.value = true
  try {
    const r = await fetch('/api/v1/skills')
    const data = await r.json()
    skills.value = data.skills || []
  } catch {
    skills.value = []
  } finally {
    loading.value = false
  }
}

async function toggle(s: any) {
  saving.value = s.id
  const next = skills.value.map((x) => (x.id === s.id ? { ...x, enabled: !x.enabled } : x))
  try {
    const r = await fetch('/api/v1/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabledSkills: next.filter((x) => x.enabled).map((x) => x.id) }),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    skills.value = next
  } catch (e: any) {
    alert(`保存失败：${e?.message || e}`)
  } finally {
    saving.value = ''
  }
}

async function readGuide(s: any) {
  guide.value = s
  guideText.value = ''
  guideLoading.value = true
  try {
    const r = await fetch('/api/v1/tools/call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'read_skill', arguments: { skill_id: s.id } }),
    })
    const data = await r.json()
    const result = data?.result
    guideText.value =
      typeof result === 'string'
        ? result
        : result?.content || JSON.stringify(result ?? data, null, 2)
  } catch (e: any) {
    guideText.value = `读取失败：${e?.message || e}`
  } finally {
    guideLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* ============================================================
   Skill Market — Aurora Console
   ============================================================ */
.sk-hero { margin-bottom: 18px; }
.sk-stats { margin-bottom: 18px; }

.stat-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.stat-label svg { color: var(--primary); flex-shrink: 0; }

/* ---------------- 分类筛选 ---------------- */
.sk-filter { align-items: center; }
.sk-count {
  margin-left: auto;
  font-size: 11px;
  color: var(--text3);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* ---------------- 技能卡 ---------------- */
.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.skcard {
  display: flex;
  flex-direction: column;
  padding: 16px;
  border-radius: var(--r-md);
  transition: border-color var(--t-mid), box-shadow var(--t-mid), opacity var(--t-mid), transform var(--t-mid);
}
.skcard:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }
.skcard.off { opacity: 0.55; }
.skcard.off:hover { transform: none; box-shadow: none; }

.skcard-hd {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.skcard-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
.skcard-glyph {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  font-size: 16px;
  border-radius: 10px;
  background: var(--surface-alt);
  border: 1px solid var(--border-light);
}
.skcard-title-text { min-width: 0; }
.skcard-name {
  font-size: 13px;
  font-weight: 650;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.skcard-id {
  display: block;
  margin-top: 2px;
  padding: 0;
  background: transparent;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.skcard-desc {
  margin-top: 11px;
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--text2);
  flex: 1;
  min-height: 38px;
}

.skcard-ft {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.skcard-ft .ui-btn { color: var(--text2); }
.skcard-ft .ui-btn:hover { color: var(--text); }

/* ---------------- 新增技能 ---------------- */
.new-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
  gap: 16px;
  align-items: start;
}

.steps {
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: step;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.steps li {
  position: relative;
  padding-left: 34px;
  font-size: 12px;
  line-height: 1.65;
  color: var(--text2);
  counter-increment: step;
}
.steps li::before {
  content: counter(step);
  position: absolute;
  left: 0;
  top: 0;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  color: var(--primary);
  background: var(--primary-soft);
  border: 1px solid color-mix(in srgb, var(--primary) 26%, transparent);
}
.steps b { color: var(--text); font-weight: 640; margin-right: 6px; }
.steps code {
  font-size: 10.5px;
  padding: 2px 6px;
  border-radius: var(--r-xs);
  background: var(--surface-alt);
  color: var(--text2);
}

.sample {
  margin: 0;
  padding: 14px;
  max-height: 220px;
  overflow: auto;
  font-size: 11px;
  line-height: 1.7;
  color: var(--text2);
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.sk-last { margin-bottom: 0; }

/* ---------------- 指南预览弹窗 ---------------- */
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
  width: min(94vw, 720px);
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
.modal-title { font-size: 14px; font-weight: 680; letter-spacing: -0.01em; }
.modal-id {
  display: block;
  margin-top: 3px;
  padding: 0;
  background: transparent;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text3);
}
.modal-bd { padding: 18px; overflow-y: auto; }
.guide-text {
  margin: 0;
  padding: 14px;
  font-size: 11.5px;
  line-height: 1.8;
  color: var(--text2);
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.fade-enter-active, .fade-leave-active { transition: opacity 180ms var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* AIOS-MOBILE */
/* 中文：AIOS-MOBILE */
@media (max-width: 767px) {
  .sk-hero { margin-bottom: 16px; }
  .sk-stats { margin-bottom: 13px; }

  .sk-filter { gap: 6px; }
  .sk-count { display: none; }

  .skill-grid { grid-template-columns: minmax(0, 1fr); gap: 10px; }
  .skcard { padding: 14px; }
  .skcard:hover { transform: none; box-shadow: none; }
  .skcard-desc { min-height: 0; }

  .new-grid { grid-template-columns: minmax(0, 1fr); gap: 14px; }
  .steps li { font-size: 11.5px; }
  .sample { max-height: 200px; }

  .modal-mask { padding: 12px; }
  .modal { width: 100%; max-height: 88vh; }
  .modal-hd { padding: 12px 14px; }
  .modal-bd { padding: 14px; }
}
/* /AIOS-MOBILE */
/* 中文：/AIOS-MOBILE */
</style>

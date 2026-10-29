<template>
  <div class="ui-page">
    <div class="ui-page-inner">
      <header class="ui-head">
        <div>
          <div class="ui-eyebrow">Skills</div>
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

      <div class="stat-row">
        <div class="stat">
          <div class="stat-icon" style="color: var(--primary); background: var(--primary-soft)"><Puzzle :size="15" /></div>
          <div><div class="stat-value">{{ skills.length }}</div><div class="stat-label">已安装技能</div></div>
        </div>
        <div class="stat">
          <div class="stat-icon" style="color: var(--success); background: color-mix(in srgb, var(--success) 14%, transparent)"><Power :size="15" /></div>
          <div><div class="stat-value">{{ enabledCount }}</div><div class="stat-label">已启用</div></div>
        </div>
        <div class="stat">
          <div class="stat-icon" style="color: var(--info); background: color-mix(in srgb, var(--info) 14%, transparent)"><Layers :size="15" /></div>
          <div><div class="stat-value">{{ categories.length }}</div><div class="stat-label">分类</div></div>
        </div>
      </div>

      <div class="filters">
        <button :class="['ui-chip', { active: cat === '' }]" @click="cat = ''">全部</button>
        <button
          v-for="c in categories"
          :key="c"
          :class="['ui-chip', { active: cat === c }]"
          @click="cat = c"
        >{{ c }}</button>
      </div>

      <div v-if="loading" class="skill-grid">
        <div v-for="i in 3" :key="i" class="ui-skeleton" style="height: 150px"></div>
      </div>

      <div v-else-if="!filtered.length" class="ui-empty">
        <div class="ui-empty-icon">🧩</div>
        <div class="ui-empty-title">这里还没有技能</div>
        <div class="ui-empty-desc">按下面的三步添加一个 SKILL.md，刷新后就会出现在这里。</div>
      </div>

      <div v-else class="skill-grid">
        <article v-for="s in filtered" :key="s.id" :class="['skcard', { off: !s.enabled }]">
          <div class="skcard-hd">
            <div class="skcard-title">
              <span class="skcard-glyph">{{ glyphOf(s.category) }}</span>
              <div>
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
            <button class="link-btn" @click="readGuide(s)">
              <BookOpen :size="12" /> 读取指南
            </button>
          </div>
        </article>
      </div>

      <section class="ui-card" style="margin-top: 20px">
        <div class="ui-card-hd">
          <div>
            <div class="ui-card-title"><PlusCircle :size="15" /> 新增一个技能</div>
            <div class="ui-card-desc">后端启动时会扫描 skills/*/SKILL.md，无需重启即可热加载。</div>
          </div>
        </div>
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
      </section>
    </div>

    <!-- 指南预览 -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="guide" class="modal-mask" @click.self="guide = null">
          <div class="modal">
            <div class="modal-hd">
              <div>
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
.stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
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

.filters { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 16px; }

.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.skcard {
  display: flex;
  flex-direction: column;
  padding: 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface);
  transition: border-color var(--t-mid), box-shadow var(--t-mid), opacity var(--t-mid), transform var(--t-mid);
}
.skcard:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); transform: translateY(-1px); }
.skcard.off { opacity: 0.55; }

.skcard-hd { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.skcard-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
.skcard-glyph {
  width: 34px; height: 34px;
  border-radius: var(--r-sm);
  background: var(--surface-alt);
  display: grid; place-items: center;
  font-size: 16px;
  flex-shrink: 0;
}
.skcard-name { font-size: 13px; font-weight: 650; letter-spacing: -0.01em; }
.skcard-id {
  font-size: 10px;
  color: var(--text3);
  background: transparent;
  padding: 0;
  font-family: var(--font-mono);
}

.skcard-desc {
  font-size: 11.5px;
  color: var(--text2);
  line-height: 1.65;
  margin-top: 11px;
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
.link-btn {
  display: inline-flex; align-items: center; gap: 4px;
  border: none; background: transparent;
  color: var(--text3);
  font-size: 11px;
  font-weight: 560;
  transition: color var(--t-fast);
}
.link-btn:hover { color: var(--primary); }

.steps { margin: 0 0 14px; padding-left: 20px; }
.steps li { font-size: 12px; color: var(--text2); line-height: 2; }
.steps code { font-size: 11px; background: var(--surface-alt); padding: 1px 6px; margin-left: 4px; }
.sample { font-size: 11px; line-height: 1.7; color: var(--text2); background: var(--bg); }

.modal-mask {
  position: fixed; inset: 0; z-index: 1500;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
  background: var(--overlay);
  backdrop-filter: blur(5px);
}
.modal {
  width: min(94vw, 680px);
  max-height: 86vh;
  display: flex; flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.modal-hd {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
  padding: 15px 18px;
  border-bottom: 1px solid var(--border-light);
}
.modal-title { font-size: 14px; font-weight: 680; }
.modal-id { font-size: 10.5px; color: var(--text3); background: transparent; padding: 0; }
.modal-bd { padding: 16px 18px; overflow-y: auto; }
.guide-text {
  font-size: 11.5px;
  line-height: 1.8;
  color: var(--text2);
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg);
}

.fade-enter-active, .fade-leave-active { transition: opacity 180ms var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>

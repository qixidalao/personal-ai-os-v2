<template>
  <main class="cap-page">
    <header class="cap-hero">
      <div><div class="eyebrow">PERSONAL AI OS · EXTENSIONS</div><h1>能力中心</h1><p>组合 Agent Skills 与本地工具，让 AI 在需要时使用合适的能力。</p></div>
      <button class="refresh" :disabled="loading || saving" @click="loadAll">{{ loading ? '读取中…' : '↻ 刷新' }}</button>
    </header>
    <div v-if="error" class="notice error">{{ error }}</div>
    <div v-if="message" class="notice success">{{ message }}</div>
    <section class="cap-grid">
      <article class="panel">
        <div class="panel-head"><div><span class="panel-icon">🧭</span><h2>Agent Skills</h2><p>按需读取的 Markdown 指南，不会执行技能文件代码。</p></div><span class="count">{{ enabledSkillCount }}/{{ skills.length }} 启用</span></div>
        <div v-if="skills.length" class="items">
          <label v-for="skill in skills" :key="skill.id" class="item">
            <div class="item-copy"><div class="item-title">{{ skill.name }} <span class="tag">{{ categoryLabel(skill.category) }}</span></div><p>{{ skill.description }}</p><code>{{ skill.id }}</code></div>
            <input v-model="skill.enabled" type="checkbox" :aria-label="`启用${skill.name}`" />
          </label>
        </div>
        <div v-else class="empty">还没有可用技能。</div>
      </article>
      <article class="panel">
        <div class="panel-head"><div><span class="panel-icon">🔌</span><h2>本地工具</h2><p>这些已注册工具会作为函数提供给 Agent；关闭后模型不会收到它的定义。</p></div><span class="count">{{ enabledToolCount }}/{{ tools.length }} 启用</span></div>
        <div v-if="tools.length" class="items">
          <label v-for="tool in tools" :key="tool.name" class="item">
            <div class="item-copy"><div class="item-title">{{ tool.name }} <span class="tag">{{ categoryLabel(tool.category) }}</span></div><p>{{ tool.description || '没有描述' }}</p><code v-if="!tool.registered">尚未加载到注册表</code></div>
            <input v-model="tool.enabled" type="checkbox" :aria-label="`启用${tool.name}`" :disabled="!tool.registered" />
          </label>
        </div>
        <div v-else class="empty">读取工具列表失败或没有已注册工具。</div>
      </article>
    </section>
    <footer class="cap-footer"><span>社区插件会在服务器上运行代码；此页只管理仓库内工具与只读技能，未启用未经审查的远程代码安装。</span><button class="save" :disabled="loading || saving" @click="saveAll">{{ saving ? '保存中…' : '保存能力配置' }}</button></footer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
interface Skill { id: string; name: string; description: string; category: string; enabled: boolean }
interface Tool { name: string; description: string; category: string; schema: any; enabled: boolean; registered: boolean; showSchema?: boolean }
const skills = ref<Skill[]>([])
const tools = ref<Tool[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const enabledSkillCount = computed(() => skills.value.filter(x => x.enabled).length)
const enabledToolCount = computed(() => tools.value.filter(x => x.enabled).length)
const categoryLabels: Record<string, string> = { research: '研究', discovery: '兴趣发现', frontend: '前端', filesystem: '文件', search: '搜索', shell: 'Shell', browser: '浏览器', python: 'Python', media: '媒体', skills: '技能' }
function categoryLabel(value: string) { return categoryLabels[value] || value || '通用' }
async function loadAll() {
  loading.value = true; error.value = ''; message.value = ''
  try {
    const [skillResponse, toolResponse] = await Promise.all([fetch('/api/v1/skills'), fetch('/api/v1/tools')])
    if (!skillResponse.ok || !toolResponse.ok) throw new Error('能力目录读取失败')
    const [skillData, toolData] = await Promise.all([skillResponse.json(), toolResponse.json()])
    skills.value = skillData.skills || []; tools.value = toolData.tools || []
  } catch (e: any) { error.value = e?.message || '读取失败' }
  finally { loading.value = false }
}
async function saveAll() {
  saving.value = true; error.value = ''; message.value = ''
  try {
    const response = await fetch('/api/v1/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      enabledSkills: skills.value.filter(s => s.enabled).map(s => s.id),
      agentTools: tools.value.map(t => ({ name: t.name, description: t.description, schema: JSON.stringify(t.schema || {}), enabled: !!t.enabled, showSchema: !!t.showSchema })),
    }) })
    if (!response.ok) throw new Error(`保存失败 HTTP ${response.status}`)
    await loadAll()
    message.value = '能力配置已保存；新配置会用于下一条对话。'
  } catch (e: any) { error.value = e?.message || '保存失败' }
  finally { saving.value = false }
}
onMounted(loadAll)
</script>

<style scoped>
.cap-page{height:100%;overflow:auto;padding:clamp(18px,4vw,42px);color:var(--text);box-sizing:border-box}.cap-hero{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;max-width:1180px;margin:0 auto 22px}.eyebrow{font-size:10px;letter-spacing:.16em;color:var(--primary);font-weight:800}.cap-hero h1{margin:7px 0;font-size:clamp(24px,4vw,34px)}.cap-hero p,.panel-head p{margin:0;color:var(--text-secondary);font-size:13px;line-height:1.6}.refresh,.save{border:1px solid var(--border-light);border-radius:10px;padding:9px 13px;background:var(--surface);color:var(--text);cursor:pointer}.cap-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;max-width:1180px;margin:auto}.panel{min-width:0;border:1px solid var(--border-light);background:color-mix(in srgb,var(--surface) 94%,var(--primary) 6%);border-radius:16px;overflow:hidden}.panel-head{display:flex;justify-content:space-between;gap:12px;padding:18px;border-bottom:1px solid var(--border-light)}.panel-icon{font-size:20px}.panel-head h2{display:inline;margin:0 0 0 8px;font-size:17px}.count,.tag{font-size:11px;color:var(--text-secondary);white-space:nowrap}.items{display:flex;flex-direction:column}.item{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:14px 18px;border-bottom:1px solid var(--border-light);cursor:pointer}.item:last-child{border-bottom:0}.item:hover{background:rgba(127,127,127,.06)}.item-copy{min-width:0}.item-title{font-size:13px;font-weight:700}.tag{margin-left:7px;padding:3px 7px;border:1px solid var(--border-light);border-radius:999px}.item p{margin:6px 0;color:var(--text-secondary);font-size:12px;line-height:1.5}.item code{font-size:10px;color:var(--text3)}input[type=checkbox]{width:18px;height:18px;accent-color:var(--primary);flex:none}.empty{padding:24px;color:var(--text-secondary);font-size:13px}.cap-footer{max-width:1180px;margin:16px auto 0;display:flex;justify-content:space-between;align-items:center;gap:16px;color:var(--text-secondary);font-size:11px;line-height:1.5}.save{background:var(--primary);color:white;border-color:transparent;font-weight:700;white-space:nowrap}.save:disabled,.refresh:disabled{opacity:.6;cursor:wait}.notice{max-width:1180px;margin:0 auto 12px;padding:10px 13px;border-radius:9px;font-size:12px}.notice.error{color:var(--error);background:color-mix(in srgb,var(--error) 12%,transparent)}.notice.success{color:var(--success);background:color-mix(in srgb,var(--success) 12%,transparent)}@media(max-width:820px){.cap-grid{grid-template-columns:1fr}.cap-footer{align-items:flex-start;flex-direction:column}.save{width:100%}}
</style>

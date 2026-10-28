<template>
  <main class="memory-page">
    <header class="hero"><div><div class="eyebrow">PERSONAL CONTEXT</div><h1>兴趣与记忆</h1><p>由你明确填写的兴趣可以帮助助手做相关联想和个性化网络发现。</p></div><span class="hero-icon">🧠</span></header>
    <section class="card">
      <div class="card-title"><div><h2>我的兴趣</h2><p>这些内容只作为对话上下文；你可以随时修改或关闭。</p></div><label class="switch"><input v-model="enabled" type="checkbox"><span>允许用于个性化</span></label></div>
      <label class="field-label" for="interests">每行一个兴趣、爱好或长期关注领域</label>
      <textarea id="interests" v-model="draft" rows="7" placeholder="例如：开源 AI Agent、前端渲染、独立游戏"></textarea>
      <div class="field-foot"><span>{{ parsed.length }}/30 项 · 每项最多 80 字</span><button class="save" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存兴趣' }}</button></div>
      <div v-if="error" class="status error">{{ error }}</div><div v-if="message" class="status success">{{ message }}</div>
    </section>
    <section class="card ideas"><h2>快速添加灵感</h2><p>点选后会加到上方列表，你决定保存哪些。</p><div class="chips"><button v-for="idea in suggestions" :key="idea" :disabled="parsed.includes(idea)" @click="addIdea(idea)">＋ {{ idea }}</button></div></section>
    <aside class="privacy"><span>🔒</span><p>兴趣不会自动从聊天中推断。启用后，HHS 会在相关问题中把你保存的兴趣提供给模型；联网搜索仍由你提出相关需求后才会触发。</p></aside>
  </main>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
const draft = ref('')
const enabled = ref(true)
const saving = ref(false)
const error = ref('')
const message = ref('')
const suggestions = ['开源 AI Agent', '前端交互与渲染', '智能体 Skills 与插件', '新奇开源项目', '游戏与游戏设计', '数码硬件', '桌面自动化', '科学与太空']
const parsed = computed(() => [...new Set(draft.value.split(/[\n,，]/).map(x => x.trim().slice(0, 80)).filter(Boolean))].slice(0, 30))
function addIdea(value: string) { if (parsed.value.length < 30 && !parsed.value.includes(value)) draft.value = [...parsed.value, value].join('\n') }
async function load() {
  error.value = ''
  try { const response = await fetch('/api/v1/settings'); if (!response.ok) throw new Error(`读取失败 HTTP ${response.status}`); const data = await response.json(); draft.value = Array.isArray(data.userInterests) ? data.userInterests.join('\n') : ''; enabled.value = data.interestsEnabled !== false }
  catch (e: any) { error.value = e?.message || '无法读取兴趣设置' }
}
async function save() {
  saving.value = true; error.value = ''; message.value = ''
  try { const response = await fetch('/api/v1/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ userInterests: parsed.value, interestsEnabled: enabled.value }) }); if (!response.ok) throw new Error(`保存失败 HTTP ${response.status}`); draft.value = parsed.value.join('\n'); message.value = '兴趣偏好已保存，下一条对话开始生效。' }
  catch (e: any) { error.value = e?.message || '保存失败' }
  finally { saving.value = false }
}
onMounted(load)
</script>
<style scoped>
.memory-page{height:100%;overflow:auto;box-sizing:border-box;padding:clamp(18px,5vw,48px);max-width:900px;margin:auto;color:var(--text)}.hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}.eyebrow{font-size:10px;letter-spacing:.16em;color:var(--primary);font-weight:800}.hero h1{font-size:clamp(24px,4vw,34px);margin:7px 0}.hero p,.card-title p,.ideas p{color:var(--text-secondary);font-size:13px;line-height:1.6;margin:0}.hero-icon{font-size:40px}.card{border:1px solid var(--border-light);border-radius:16px;padding:20px;background:color-mix(in srgb,var(--surface) 94%,var(--primary) 6%);margin-bottom:14px}.card-title{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:22px}.card h2{font-size:16px;margin:0 0 5px}.switch{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text-secondary);white-space:nowrap}.switch input{accent-color:var(--primary);width:16px;height:16px}.field-label{display:block;font-size:12px;font-weight:700;margin-bottom:8px}textarea{width:100%;box-sizing:border-box;resize:vertical;border:1px solid var(--border-light);border-radius:10px;padding:12px;background:var(--surface);color:var(--text);font:inherit;font-size:13px;line-height:1.7;outline:none}textarea:focus{border-color:var(--primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--primary) 18%,transparent)}.field-foot{display:flex;align-items:center;justify-content:space-between;margin-top:10px;color:var(--text3);font-size:11px}.save{background:var(--primary);color:white;border:0;border-radius:9px;padding:9px 14px;font-weight:700;cursor:pointer}.save:disabled{opacity:.6}.ideas h2{margin-bottom:5px}.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.chips button{border:1px solid var(--border-light);background:var(--surface);border-radius:999px;padding:7px 10px;color:var(--text-secondary);font-size:11px;cursor:pointer}.chips button:hover:not(:disabled){color:var(--primary);border-color:var(--primary)}.chips button:disabled{opacity:.45;cursor:default}.privacy{display:flex;gap:10px;align-items:flex-start;color:var(--text3);font-size:11px;line-height:1.6;padding:4px 2px}.privacy p{margin:0}.status{margin-top:10px;font-size:12px}.error{color:var(--error)}.success{color:var(--success)}@media(max-width:560px){.card-title{align-items:flex-start;flex-direction:column}.hero-icon{font-size:30px}}
</style>

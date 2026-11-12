<template>
  <div class="ui-page">
    <div class="ui-page-inner mem-page">
      <!-- 页头 -->
      <header class="ui-hero mem-hero">
        <div class="ui-hero-main">
          <div class="ui-eyebrow">PERSONAL CONTEXT</div>
          <h1 class="ui-title">兴趣与记忆</h1>
          <p class="ui-sub">由你明确填写的兴趣可以帮助助手做相关联想和个性化网络发现。</p>
        </div>
        <div class="ui-head-actions">
          <span class="mem-hero-icon">🧠</span>
        </div>
      </header>

      <!-- 指标 -->
      <div class="ui-grid ui-grid--3 mem-stats">
        <div class="ui-stat">
          <div class="ui-stat-label">已保存兴趣</div>
          <div class="ui-stat-value">{{ parsed.length }}<span class="mem-unit"> / 30</span></div>
          <div class="ui-stat-hint">每项最多 80 字</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label">个性化联想</div>
          <div class="ui-stat-value mem-state" :class="{ off: !enabled }">{{ enabled ? '已开启' : '已关闭' }}</div>
          <div class="ui-stat-hint">可随时在下方关闭</div>
        </div>
        <div class="ui-stat">
          <div class="ui-stat-label">数据来源</div>
          <div class="ui-stat-value mem-state">仅手动</div>
          <div class="ui-stat-hint">不会从聊天中推断</div>
        </div>
      </div>

      <!-- 兴趣 -->
      <section class="ui-section mem-section">
        <div class="ui-section-head">
          <div>
            <div class="ui-section-title">我的兴趣</div>
            <div class="ui-section-sub">这些内容只作为对话上下文；你可以随时修改或关闭。</div>
          </div>
          <div class="ui-section-actions">
            <label class="mem-switch">
              <input v-model="enabled" class="mem-switch-input" type="checkbox" />
              <span class="ui-switch" :class="{ on: enabled }"></span>
              <span class="mem-switch-label">允许用于个性化</span>
            </label>
          </div>
        </div>

        <div class="ui-field mem-field">
          <label class="ui-label" for="interests">每行一个兴趣、爱好或长期关注领域</label>
          <textarea
            id="interests"
            v-model="draft"
            class="ui-textarea mem-textarea"
            rows="7"
            placeholder="例如：开源 AI Agent、前端渲染、独立游戏"
          ></textarea>
        </div>

        <div class="mem-actions">
          <span class="mem-count">{{ parsed.length }}/30 项 · 每项最多 80 字</span>
          <button class="ui-btn ui-btn--primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存兴趣' }}</button>
        </div>

        <div v-if="error" class="mem-status mem-status--bad">{{ error }}</div>
        <div v-if="message" class="mem-status mem-status--ok">{{ message }}</div>
      </section>

      <!-- 快速添加灵感 -->
      <section class="ui-section mem-section">
        <div class="ui-section-head">
          <div>
            <div class="ui-section-title">快速添加灵感</div>
            <div class="ui-section-sub">点选后会加到上方列表，你决定保存哪些。</div>
          </div>
        </div>
        <div class="mem-chips">
          <button
            v-for="idea in suggestions"
            :key="idea"
            class="ui-chip mem-chip"
            :disabled="parsed.includes(idea)"
            @click="addIdea(idea)"
          >＋ {{ idea }}</button>
        </div>
      </section>

      <!-- 隐私说明 -->
      <aside class="mem-note">
        <span class="mem-note-icon">🔒</span>
        <p>兴趣不会自动从聊天中推断。启用后，AIOS 会在相关问题中把你保存的兴趣提供给模型；联网搜索仍由你提出相关需求后才会触发。</p>
      </aside>
    </div>
  </div>
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
/* ============================================================
   Personal Context — Aurora Console
   ============================================================ */
/* 中文：============================================================ Personal Context — Aurora Console ============================================================ */
.mem-page { max-width: 980px; }
.mem-stats { margin-bottom: 18px; }
.mem-hero-icon {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  font-size: 20px;
  border-radius: 14px;
  background: color-mix(in srgb, var(--surface) 86%, transparent);
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-sm);
}
.mem-unit { font-size: 12px; font-weight: 600; color: var(--text3); letter-spacing: 0; }
.mem-state { font-size: 18px; letter-spacing: 0; }
.mem-state.off { color: var(--text3); }

/* ---------------- 开关 ---------------- */
.mem-switch {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
  color: var(--text2);
  white-space: nowrap;
}
.mem-switch-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
.mem-switch:hover .mem-switch-label { color: var(--text); }

/* ---------------- 输入区 ---------------- */
.mem-field { margin-bottom: 10px; }
.mem-textarea {
  min-height: 168px;
  font-size: 13px;
  line-height: 1.75;
  padding: 12px 14px;
}
.mem-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.mem-count { font-size: 11px; color: var(--text3); }

.mem-status {
  margin-top: 12px;
  padding: 9px 12px;
  border-radius: var(--r-sm);
  font-size: 12px;
  line-height: 1.55;
  border: 1px solid transparent;
}
.mem-status--bad {
  color: var(--error);
  background: color-mix(in srgb, var(--error) 10%, transparent);
  border-color: color-mix(in srgb, var(--error) 26%, transparent);
}
.mem-status--ok {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 10%, transparent);
  border-color: color-mix(in srgb, var(--success) 26%, transparent);
}

/* ---------------- 灵感 chip ---------------- */
.mem-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.mem-chip {
  height: 30px;
  padding: 0 12px;
  font-size: 11.5px;
  cursor: pointer;
  color: var(--text2);
}
.mem-chip:hover:not(:disabled) {
  color: var(--primary);
  border-color: color-mix(in srgb, var(--primary) 40%, transparent);
  background: var(--primary-soft);
}
.mem-chip:disabled {
  opacity: 0.42;
  cursor: default;
  color: var(--text3);
  border-style: dashed;
}

/* ---------------- 隐私说明 ---------------- */
.mem-note {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface-2);
  color: var(--text2);
}
.mem-note-icon { font-size: 14px; line-height: 1.6; flex-shrink: 0; }
.mem-note p { margin: 0; font-size: 11.5px; line-height: 1.7; color: var(--text3); }

/* AIOS-MOBILE */
/* 中文：AIOS-MOBILE */
@media (max-width: 767px) {
  .mem-page { max-width: 100%; }
  .mem-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .mem-stats .ui-stat { padding: 10px; }
  .mem-stats .ui-stat-value { font-size: 16px; }
  .mem-stats .ui-stat-hint { display: none; }
  .mem-state { font-size: 13px; }
  .mem-hero-icon { font-size: 28px; }

  .mem-textarea { min-height: 150px; }
  .mem-actions { justify-content: flex-start; }
  .mem-actions .ui-btn { width: 100%; }
  .mem-chip { height: 34px; padding: 0 13px; }
  .mem-note { padding: 12px 14px; }
}
/* /AIOS-MOBILE */
/* 中文：/AIOS-MOBILE */
</style>

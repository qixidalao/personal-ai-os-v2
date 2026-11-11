<template>
  <aside :class="['dock', { 'dock--open': true }]">
    <div class="dock-head">
      <div class="dock-head-main">
        <div class="dock-eyebrow">CONTEXT</div>
        <div class="dock-title">上下文坞</div>
      </div>
      <button class="dock-close" @click="$emit('close')" title="收起">
        <X :size="15" />
      </button>
    </div>

    <div class="dock-scroll">
      <section class="dock-sec">
        <div class="dock-sec-title">运行状态</div>
        <div class="dock-rows">
          <div class="dock-row">
            <span class="dock-row-label">后端服务</span>
            <span :class="['dock-badge', online ? 'ok' : 'bad']">{{ online ? '在线' : '离线' }}</span>
          </div>
          <div class="dock-row">
            <span class="dock-row-label">当前模型</span>
            <span class="dock-row-value mono">{{ currentModel || '—' }}</span>
          </div>
          <div class="dock-row">
            <span class="dock-row-label">会话总数</span>
            <span class="dock-row-value">{{ sessions.length }}</span>
          </div>
        </div>
      </section>

      <section class="dock-sec">
        <div class="dock-sec-title">快捷操作</div>
        <div class="dock-actions">
          <button class="ui-btn ui-btn--primary ui-btn--block" @click="$emit('new-chat')">
            <Plus :size="14" /> 新对话
          </button>
          <button class="ui-btn ui-btn--ghost ui-btn--block" @click="$emit('open-palette')">
            <Command :size="14" /> 命令面板 <span class="ui-kbd">⌘K</span>
          </button>
        </div>
      </section>

      <section class="dock-sec">
        <div class="dock-sec-head">
          <div class="dock-sec-title">最近对话</div>
          <span class="dock-sec-count">{{ sessions.length }}</span>
        </div>
        <div v-if="loading" class="dock-skel">
          <div class="ui-skeleton" style="height: 42px; margin-bottom: 6px"></div>
          <div class="ui-skeleton" style="height: 42px"></div>
        </div>
        <button
          v-for="s in sessions.slice(0, 7)"
          :key="s.id"
          :class="['dock-sess', { active: s.id === currentSession }]"
          @click="$emit('switch-session', s.id)"
        >
          <span class="dock-sess-icon">{{ s.icon || '💬' }}</span>
          <span class="dock-sess-body">
            <span class="dock-sess-title">{{ s.title || '新对话' }}</span>
            <span class="dock-sess-meta">{{ s.time || '--' }}</span>
          </span>
        </button>
        <div v-if="!loading && sessions.length === 0" class="dock-empty">还没有对话</div>
      </section>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { X, Plus, Command } from 'lucide-vue-next'

defineProps<{
  sessions: any[]
  currentSession: string
  currentModel: string
  online: boolean
  loading: boolean
}>()

defineEmits<{
  (e: 'close'): void
  (e: 'new-chat'): void
  (e: 'open-palette'): void
  (e: 'switch-session', id: string): void
}>()
</script>

<style scoped>
.dock {
  width: var(--dock-w, 316px);
  flex-shrink: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border-light);
  background: color-mix(in srgb, var(--surface) 72%, transparent);
  backdrop-filter: blur(18px);
  animation: dock-in 260ms var(--ease);
}
@keyframes dock-in {
  from { opacity: 0; transform: translateX(12px); }
  to { opacity: 1; transform: none; }
}

.dock-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--border-light);
}
.dock-eyebrow {
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: var(--text3);
  margin-bottom: 4px;
}
.dock-title { font-size: 14px; font-weight: 700; letter-spacing: -0.01em; }
.dock-close {
  width: 28px; height: 28px;
  display: grid; place-items: center;
  border: 1px solid var(--border-light);
  border-radius: 9px;
  background: transparent;
  color: var(--text2);
  transition: all var(--t-fast);
}
.dock-close:hover { color: var(--text); border-color: var(--border-strong); background: var(--surface-alt); }

.dock-scroll { flex: 1; overflow-y: auto; padding: 14px 14px 24px; }

.dock-sec { margin-bottom: 20px; }
.dock-sec-head { display: flex; align-items: center; justify-content: space-between; }
.dock-sec-title {
  font-size: 10.5px;
  font-weight: 750;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text3);
  margin-bottom: 10px;
}
.dock-sec-head .dock-sec-title { margin-bottom: 10px; }
.dock-sec-count {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text3);
  border: 1px solid var(--border-light);
  border-radius: var(--r-full);
  padding: 0 7px;
  line-height: 17px;
}

.dock-rows {
  border: 1px solid var(--border-light);
  border-radius: var(--r-md);
  background: var(--surface);
  overflow: hidden;
}
.dock-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 12px;
  font-size: 12px;
}
.dock-row + .dock-row { border-top: 1px solid var(--border-light); }
.dock-row-label { color: var(--text2); }
.dock-row-value { color: var(--text); font-weight: 600; }
.mono { font-family: var(--font-mono); font-size: 11.5px; }
.dock-badge {
  font-size: 10.5px; font-weight: 650;
  padding: 1px 8px; border-radius: var(--r-full);
}
.dock-badge.ok { color: var(--success); background: color-mix(in srgb, var(--success) 13%, transparent); }
.dock-badge.bad { color: var(--error); background: color-mix(in srgb, var(--error) 13%, transparent); }

.dock-actions { display: flex; flex-direction: column; gap: 7px; }

.dock-sess {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 9px;
  border-radius: var(--r-sm);
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  transition: all var(--t-fast);
}
.dock-sess:hover { background: var(--surface-alt); border-color: var(--border-light); }
.dock-sess.active {
  background: var(--primary-soft);
  border-color: color-mix(in srgb, var(--primary) 26%, transparent);
}
.dock-sess-icon { font-size: 14px; flex-shrink: 0; }
.dock-sess-body { display: flex; flex-direction: column; min-width: 0; gap: 1px; }
.dock-sess-title {
  font-size: 12.5px; font-weight: 560; color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.dock-sess-meta { font-size: 10.5px; color: var(--text3); font-family: var(--font-mono); }
.dock-empty { font-size: 12px; color: var(--text3); padding: 8px 2px; }
.dock-skel { padding-top: 2px; }
</style>

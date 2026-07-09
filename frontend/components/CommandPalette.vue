<template>
  <Teleport to="body">
    <div v-if="visible" class="cp-overlay" @click.self="close">
      <div class="cp-modal">
        <input class="cp-input" v-model="query" placeholder="搜索命令..." ref="inputRef" @keydown.escape="close" />
        <div class="cp-results" v-if="results.length">
          <div class="cp-item" v-for="r in results" :key="r.label" @click="run(r)">
            <span class="cp-icon">{{ r.icon }}</span>
            <span>{{ r.label }}</span>
          </div>
        </div>
        <div class="cp-empty" v-else-if="query">无匹配命令</div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const visible = ref(false)
const query = ref('')
const inputRef = ref<HTMLInputElement>()

const commands = [
  { icon: '💬', label: '新建对话', action: () => router.push('/chat') },
  { icon: '📝', label: '打开 Workspace', action: () => router.push('/workspace') },
  { icon: '⚙️', label: '打开设置', action: () => router.push('/settings') },
  { icon: '🔍', label: '全局搜索', action: () => router.push('/search') },
  { icon: '🧠', label: '记忆管理', action: () => router.push('/memory') },
  { icon: '🔧', label: '工具中心', action: () => router.push('/tools') },
]

const results = ref(commands)

watch(query, (val) => {
  if (!val) { results.value = commands; return }
  results.value = commands.filter(c => c.label.includes(val))
})

watch(visible, (v) => {
  if (v) nextTick(() => inputRef.value?.focus())
  else query.value = ''
})

function close() { visible.value = false }
function run(cmd: any) { close(); cmd.action() }

defineExpose({ open: () => { visible.value = true } })
</script>

<style scoped>
.cp-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:1000;display:flex;align-items:flex-start;justify-content:center;padding-top:15vh}
.cp-modal{width:90%;max-width:480px;background:var(--surface);border-radius:12px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.4)}
.cp-input{width:100%;padding:14px 16px;background:transparent;border:none;color:var(--text);font-size:15px;font-family:inherit;border-bottom:1px solid var(--border-light)}
.cp-input:focus{outline:none}
.cp-results{max-height:300px;overflow-y:auto}
.cp-item{display:flex;align-items:center;gap:10px;padding:10px 16px;cursor:pointer;font-size:14px;transition:background 0.15s}
.cp-item:hover,.cp-item:focus{background:var(--surface-alt)}
.cp-item:last-child{border-radius:0 0 12px 12px}
.cp-icon{width:24px;text-align:center}
.cp-empty{padding:20px;text-align:center;color:var(--text2);font-size:14px}
</style>

<template>
  <div class="app-shell" :class="{mobile:isMobile}">
    <aside v-if="!isMobile" class="app-sidebar">
      <div class="sb-header"><span class="sb-logo">🧠</span><span class="sb-title">AI OS</span></div>
      <div class="sb-search">
        <span class="sb-search-icon">🔍</span>
        <input v-model="searchQuery" placeholder="搜索会话..." class="sb-search-inp"/>
        <button :class="['sb-select-btn', selectMode?'on':'']" @click="toggleSelectMode" title="多选">{{ selectMode?'✓':'☑' }}</button>
      </div>
      <nav class="sb-nav">
        <div class="sb-tags">
          <span v-for="t in tags" :key="t" :class="['sb-tag',{active:activeTag===t}]" @click="activeTag=activeTag===t?'':t">{{t}}</span>
        </div>
        <div class="sb-list" v-if="!loading">
          <div v-for="s in filteredSessions" :key="s.id" :class="['sb-item',{active:s.id===currentSession&&!selectMode}]" @click="selectMode?toggleSelect(s.id):switchSession(s.id)">
            <template v-if="selectMode">
              <span :class="['sb-cb', selectedIds.includes(s.id)?'sb-cb--on':'']" @click.stop="toggleSelect(s.id)">{{ selectedIds.includes(s.id)?'✓':'' }}</span>
            </template>
            <span class="sb-item-icon">{{s.icon||'💬'}}</span>
            <div class="sb-item-content">
              <div class="sb-item-title">{{s.title||'新对话'}}</div>
              <div class="sb-item-meta">{{s.time||''}} · {{s.preview||''}}</div>
            </div>
            <span v-if="s.tag" :class="['sb-item-tag',s.tag]">{{s.tag}}</span>
            <button v-if="!selectMode" class="sb-item-del" @click.stop="confirmDelete(s.id)" title="删除">✕</button>
          </div>
          <div v-if="filteredSessions.length===0" class="sb-empty">暂无会话</div>
        </div>
        <div v-else class="sb-loading">加载中...</div>
      </nav>
      <div class="sb-footer">
        <div v-if="selectMode" class="sb-actions">
          <button class="sb-del-btn" :disabled="selectedIds.length===0" @click="deleteSelected">🗑 删除选中 ({{ selectedIds.length }})</button>
          <button class="sb-del-all" @click="confirmDeleteAll">💣 全部删除</button>
        </div>
        <button v-else class="sb-new-btn" @click="newChat">+ 新对话</button>
      </div>
    </aside>

    <div class="app-main">
      <header class="app-topbar">
        <button v-if="isMobile" class="tb-btn" @click="showDrawer=true">☰</button>
        <div v-if="isMobile" class="tb-title">🧠 AI OS</div>
        <div v-else class="tb-spacer"></div>
        <div class="tb-center">
          <div class="model-picker-wrap">
            <button class="tb-model-btn" @click="showModelPicker=!showModelPicker">
              <span class="tb-model-icon">🤖</span>
              <span class="tb-model-name">{{ currentModel || '选择模型' }}</span>
              <span class="tb-model-arrow">▾</span>
            </button>
            <div v-if="showModelPicker" class="model-picker-drop" @click.stop>
              <div v-for="m in models" :key="m" :class="['model-picker-item',{active:m===currentModel}]" @click="currentModel=m;showModelPicker=false">
                <span>{{m}}</span>
                <span class="model-tag">{{m.includes('本地')?'本地':'云端'}}</span>
              </div>
            </div>
          </div>
          <span :class="['tb-status', online?'online':'offline']">
            <span class="tb-status-dot"></span>
          </span>
          <div v-if="tokenUsed>0" class="tb-token-bar">
            <div class="tb-token-fill" :style="{width:tokenPercent+'%',background:tokenPercent>90?'var(--error)':tokenPercent>70?'var(--warn)':'var(--primary)'}"></div>
          </div>
        </div>
        <div class="tb-actions">
          <button class="tb-btn" :title="route.path === '/settings' ? '关闭设置' : '设置'" @click="toggleSettings">{{ route.path === '/settings' ? '✕' : '⚙️' }}</button>
        </div>
        </header>
      <router-view />
    </div>

    <Teleport to="body">
      <div v-if="isMobile&&showDrawer" class="dr-overlay" @click="showDrawer=false"></div>
      <aside v-if="isMobile" :class="['dr-panel',showDrawer?'dr-open':'']">
        <div class="sb-header">
          <span class="sb-logo">🧠</span><span class="sb-title">AI OS</span>
          <button class="tb-btn" style="margin-left:auto" @click="showDrawer=false">✕</button>
        </div>
        <div class="sb-search">
          <input v-model="searchQuery" placeholder="搜索会话..." class="dr-search"/>
          <button :class="['sb-select-btn', selectMode?'on':'']" @click="toggleSelectMode" title="多选">{{ selectMode?'✓':'☑' }}</button>
        </div>
        <div class="sb-tags" style="padding:4px 12px">
          <span v-for="t in tags" :key="t" :class="['sb-tag',{active:activeTag===t}]" @click="activeTag=activeTag===t?'':t">{{t}}</span>
        </div>
        <div class="dr-list" v-if="!loading">
          <div v-for="s in filteredSessions" :key="s.id" :class="['sb-item',{active:s.id===currentSession&&!selectMode}]" @click="selectMode?toggleSelect(s.id):(showDrawer=false,switchSession(s.id))">
            <template v-if="selectMode">
              <span :class="['sb-cb', selectedIds.includes(s.id)?'sb-cb--on':'']" @click.stop="toggleSelect(s.id)">{{ selectedIds.includes(s.id)?'✓':'' }}</span>
            </template>
            <span class="sb-item-icon">{{s.icon||'💬'}}</span>
            <div class="sb-item-content"><div class="sb-item-title">{{s.title}}</div><div class="sb-item-meta">{{s.time}}</div></div>
            <button v-if="!selectMode" class="sb-item-del" @click.stop="confirmDelete(s.id);showDrawer=false" title="删除">✕</button>
          </div>
          <div v-if="filteredSessions.length===0" class="sb-empty">暂无会话</div>
        </div>
        <div class="dr-footer">
          <div v-if="selectMode" class="sb-actions">
            <button class="sb-del-btn" :disabled="selectedIds.length===0" @click="deleteSelected">🗑 删除选中 ({{ selectedIds.length }})</button>
            <button class="sb-del-all" @click="confirmDeleteAll">💣 全部删除</button>
          </div>
          <button v-else class="sb-new-btn" @click="showDrawer=false;newChat()">+ 新对话</button>
        </div>
      </aside>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const isMobile = ref(window.innerWidth < 768)
const showDrawer = ref(false)
const searchQuery = ref('')
const activeTag = ref('')
const showModelPicker = ref(false)
const showAgentPanel = ref(false)
const online = ref(true)
const tokenUsed = ref(4500)
const tokenPercent = computed(() => Math.min(100, tokenUsed.value/8192*100))

const models = ref<string[]>([])
const currentModel = ref('')

const API = window.location.origin
const tags = ['工作','代码','闲聊','研究']
const sessions = ref<any[]>([])
const messagesMap = ref<Record<string,any[]>>({})
const currentSession = ref('')
const loading = ref(true)

// 多选删除状态
const selectMode = ref(false)
const selectedIds = ref<string[]>([])

function toggleSettings() {
  if (route.path === '/settings') {
    router.push('/chat')
  } else {
    router.push('/settings')
  }
}

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedIds.value = []
}

function toggleSelect(id: string) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

async function apiGet(path: string) {
  const r = await fetch(`${API}${path}`)
  return r.json()
}
async function apiPost(path: string, body: any) {
  const r = await fetch(`${API}${path}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})
  return r.json()
}
async function apiPut(path: string, body: any) {
  const r = await fetch(`${API}${path}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})
  return r.json()
}
async function apiDel(path: string) {
  const r = await fetch(`${API}${path}`, {method:'DELETE'})
  if (!r.ok) { const t = await r.text().catch(()=>''); throw new Error(t || `DELETE ${path} ${r.status}`) }
  return r.json().catch(()=>({}))
}

async function loadFromServer() {
  try {
    const data = await apiGet('/api/v1/sessions')
    sessions.value = data.sessions || []
    if (sessions.value.length > 0) {
      const firstId = sessions.value[0].id
      const d2 = await apiGet(`/api/v1/sessions/${firstId}`)
      messagesMap.value[firstId] = d2.session?.messages || []
      currentSession.value = firstId
    }
    if (sessions.value.length === 0) {
      await newChat()
    }
  } catch(e) {
    console.error('加载失败', e)
    sessions.value = [{id:'s_default',icon:'💬',title:'离线模式',preview:'无法连接后端',time:'--'}]
    currentSession.value = 's_default'
  }
  loading.value = false
}

async function loadMessages(sessionId: string) {
  try {
    const d = await apiGet(`/api/v1/sessions/${sessionId}`)
    messagesMap.value[sessionId] = d.session?.messages || []
  } catch(e) {
    messagesMap.value[sessionId] = []
  }
}

async function saveMessages(sessionId: string) {
  const msgs = messagesMap.value[sessionId] || []
  try { await apiPut(`/api/v1/sessions/${sessionId}/messages`, msgs) } catch(e) {}
}

function getCurrentMessages() { return messagesMap.value[currentSession.value] || [] }
function setCurrentMessages(msgs: any[]) {
  messagesMap.value[currentSession.value] = JSON.parse(JSON.stringify(msgs))
  saveMessages(currentSession.value)
}

async function switchSession(id: string) {
  if (id === currentSession.value) return
  await saveMessages(currentSession.value)
  if (!messagesMap.value[id]) await loadMessages(id)
  currentSession.value = id
  showDrawer.value = false
}

async function newChat() {
  const now = new Date().toLocaleTimeString()
  const id = 's' + Date.now().toString(36)
  try {
    const d = await apiPost('/api/v1/sessions', {id, title:'新对话', icon:'💬', time:now})
    const meta = d.session?.meta || {id, title:'新对话', icon:'💬', time:now}
    sessions.value.unshift(meta)
    messagesMap.value[id] = []
    currentSession.value = id
  } catch(e) {
    sessions.value.unshift({id, icon:'💬', title:'新对话', preview:'', time:now})
    messagesMap.value[id] = []
    currentSession.value = id
  }
}

function confirmDelete(id: string) {
  if (!confirm(`删除会话「${sessions.value.find(s=>s.id===id)?.title||''}」？`)) return
  deleteOne(id)
}

async function deleteOne(id: string) {
  try {
    await apiDel(`/api/v1/sessions/${id}`)
    sessions.value = sessions.value.filter(s => s.id !== id)
    delete messagesMap.value[id]
    if (id === currentSession.value) {
      if (sessions.value.length > 0) await switchSession(sessions.value[0].id)
      else await newChat()
    }
  } catch(e) {
    console.error('删除失败', e)
  }
}

async function deleteSelected() {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  if (!confirm(`确定删除选中的 ${ids.length} 个会话吗？`)) return
  for (const id of ids) {
    try { await apiDel(`/api/v1/sessions/${id}`) } catch(e) { console.error('删除失败', id, e) }
  }
  sessions.value = sessions.value.filter(s => !ids.includes(s.id))
  ids.forEach(id => delete messagesMap.value[id])
  selectedIds.value = []
  selectMode.value = false
  if (ids.includes(currentSession.value)) {
    if (sessions.value.length > 0) await switchSession(sessions.value[0].id)
    else await newChat()
  }
}

async function confirmDeleteAll() {
  if (!confirm(`确定删除全部 ${sessions.value.length} 个会话吗？此操作不可恢复！`)) return
  const allIds = sessions.value.map(s => s.id)
  for (const id of allIds) {
    try { await apiDel(`/api/v1/sessions/${id}`) } catch(e) { console.error('删除失败', id, e) }
  }
  sessions.value = []
  messagesMap.value = {}
  selectedIds.value = []
  selectMode.value = false
  await newChat()
}

provide('sessionId', currentSession)
provide('getMessages', getCurrentMessages)
provide('setMessages', setCurrentMessages)
provide('sessions', sessions)
provide('currentSession', currentSession)
provide('currentModel', currentModel)
provide('models', models)
provide('loadModels', loadModels)
provide('updateSessionTitle', updateSessionTitle)

async function updateSessionTitle(sessionId: string, title: string) {
  const session = sessions.value.find((s: any) => s.id === sessionId)
  if (session) {
    session.title = title
    try {
      await apiPatch(`/api/v1/sessions/${sessionId}/meta`, { title })
    } catch(e) { console.warn('更新标题失败', e) }
  }
}

async function apiPatch(path: string, body: any) {
  const r = await fetch(`${API}${path}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) })
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(t || `PATCH ${path} ${r.status}`)
  }
  return r.json().catch(() => ({}))
}

const filteredSessions = computed(() => sessions.value.filter((s:any) => {
  if(activeTag.value && s.tag !== activeTag.value) return false
  if(searchQuery.value && s.title && !s.title.includes(searchQuery.value)) return false
  return true
}))

async function loadModels() {
  try {
    const data = await apiGet('/api/v1/settings')
    const allModels: string[] = []
    if (data.providers && Array.isArray(data.providers)) {
      for (const p of data.providers) {
        if (p.models && Array.isArray(p.models)) {
          for (const m of p.models) {
            if (!allModels.includes(m)) allModels.push(m)
          }
        }
      }
    }
    if (allModels.length > 0) {
      models.value = allModels
      if (!currentModel.value || !allModels.includes(currentModel.value)) {
        currentModel.value = allModels[0]
      }
    } else {
      models.value = ['GPT-4o']
      currentModel.value = 'GPT-4o'
    }
  } catch(e) {
    console.warn('模型列表加载失败', e)
    models.value = ['GPT-4o']
    currentModel.value = 'GPT-4o'
  }
}

function onResize(){isMobile.value=window.innerWidth<768}

watch(() => route.path, (path) => {
  if (path === '/' || path === '/chat') loadModels()
})

function onProvidersUpdated() { loadModels() }

onMounted(() => {
  window.addEventListener('resize', onResize)
  window.addEventListener('settings:providers-updated', onProvidersUpdated as EventListener)
  loadFromServer()
  loadModels()
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('settings:providers-updated', onProvidersUpdated as EventListener)
})
</script>

<style>
:root{--primary:#7c3aed;--primary-light:#a855f7;--bg:#0f172a;--surface:#1e293b;--surface-alt:#334155;--text:#f1f5f9;--text2:#94a3b8;--text3:#64748b;--border-light:#334155;--error:#ef4444;--warn:#f59e0b;--success:#22c55e}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC','PingFang SC',system-ui,sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased}
::-webkit-scrollbar{width:3px}::-webkit-scrollbar-thumb{background:var(--surface-alt);border-radius:2px}
::selection{background:var(--primary);color:#fff}
#app{height:100%}button{cursor:pointer;font-family:inherit}
</style>

<style scoped>
.app-shell{height:100%;display:flex}.app-shell.mobile{flex-direction:column}
.app-sidebar{width:260px;background:var(--surface);display:flex;flex-direction:column;flex-shrink:0;border-right:1px solid var(--border-light)}
.sb-header{padding:16px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--border-light)}
.sb-logo{font-size:22px}.sb-title{font-size:16px;font-weight:700}
.sb-search{display:flex;align-items:center;padding:8px 12px;gap:6px;background:var(--bg);margin:8px 12px;border-radius:8px;font-size:13px}
.sb-search-inp{flex:1;background:transparent;border:none;color:var(--text);font-size:13px;outline:none;font-family:inherit}
.sb-select-btn{width:24px;height:24px;border:none;background:transparent;color:var(--text3);border-radius:4px;font-size:13px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.sb-select-btn:hover{color:var(--text)}.sb-select-btn.on{color:var(--primary);background:rgba(124,58,237,.15)}
.sb-nav{flex:1;overflow-y:auto;padding:4px 0}
.sb-tags{display:flex;gap:4px;padding:4px 12px;flex-wrap:wrap}
.sb-tag{padding:3px 10px;border-radius:6px;font-size:11px;background:var(--surface-alt);color:var(--text2);cursor:pointer;transition:all .1s}.sb-tag:hover,.sb-tag.active{background:var(--primary);color:#fff}
.sb-list{padding:4px 8px}.sb-loading{padding:20px;text-align:center;color:var(--text3);font-size:13px}
.sb-empty{padding:20px;text-align:center;color:var(--text3);font-size:12px}
.sb-item{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;cursor:pointer;position:relative}
.sb-item:hover{background:var(--surface-alt)}.sb-item.active{background:rgba(124,58,237,.15)}
.sb-item-icon{font-size:15px;flex-shrink:0;width:20px;text-align:center}
.sb-item-content{flex:1;min-width:0}
.sb-item-title{font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sb-item-meta{font-size:10px;color:var(--text3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sb-item-del{width:20px;height:20px;border:none;background:transparent;color:var(--text3);border-radius:4px;font-size:11px;cursor:pointer;opacity:0;transition:opacity .15s;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.sb-item:hover .sb-item-del{opacity:.6}.sb-item .sb-item-del:hover{opacity:1;color:var(--error);background:rgba(239,68,68,.1)}
.sb-cb{width:18px;height:18px;border-radius:4px;border:1px solid var(--border-light);background:transparent;display:flex;align-items:center;justify-content:center;font-size:11px;color:transparent;cursor:pointer;flex-shrink:0;transition:all .1s}
.sb-cb--on{background:var(--primary);border-color:var(--primary);color:#fff}
.sb-footer{padding:8px;border-top:1px solid var(--border-light)}
.sb-actions{display:flex;flex-direction:column;gap:6px}
.sb-new-btn{width:100%;padding:10px;border-radius:8px;background:var(--primary);color:#fff;border:none;font-size:13px;font-weight:500;cursor:pointer;transition:opacity .15s}
.sb-new-btn:hover{opacity:.9}
.sb-del-btn{width:100%;padding:8px;border-radius:8px;background:var(--error);color:#fff;border:none;font-size:12px;cursor:pointer}
.sb-del-btn:disabled{opacity:.4;cursor:not-allowed}
.sb-del-all{width:100%;padding:8px;border-radius:8px;background:transparent;color:var(--text3);border:1px solid var(--border-light);font-size:12px;cursor:pointer}
.sb-del-all:hover{color:var(--error);border-color:var(--error)}
.app-main{flex:1;display:flex;flex-direction:column;min-width:0;overflow:hidden}
.app-topbar{height:44px;display:flex;align-items:center;gap:6px;padding:0 8px;background:var(--bg);border-bottom:1px solid var(--border-light);flex-shrink:0}
.tb-btn{width:32px;height:32px;border:none;background:transparent;color:var(--text2);border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:14px;cursor:pointer;flex-shrink:0}
.tb-btn:hover{background:var(--surface)}.tb-title{font-size:14px;font-weight:600;flex:1;text-align:center;white-space:nowrap}.tb-spacer{flex:1}
.tb-center{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;min-width:0}
.tb-actions{display:flex;align-items:center;gap:4px;flex-shrink:0}
.tb-model-btn{display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:6px;background:var(--surface);border:1px solid var(--border-light);color:var(--text);font-size:12px;cursor:pointer;white-space:nowrap}
.tb-status{display:flex;align-items:center;gap:4px;font-size:11px;margin-right:10px}.tb-status.online{color:#22c55e}.tb-status.offline{color:#ef4444}.tb-status-dot{width:6px;height:6px;border-radius:50%;display:inline-block}.tb-status.online .tb-status-dot{background:#22c55e}.tb-status.offline .tb-status-dot{background:#ef4444}
.tb-token-bar{width:60px;height:4px;background:var(--surface-alt);border-radius:2px;overflow:hidden}.tb-token-fill{height:100%;transition:width .3s}
.dr-overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:900}
.dr-panel{position:fixed;top:0;bottom:0;left:0;width:280px;max-width:85vw;background:var(--surface);z-index:901;transform:translateX(-100%);transition:transform .3s ease;display:flex;flex-direction:column;overflow-y:auto}.dr-panel.dr-open{transform:translateX(0)}
.dr-search{flex:1;background:transparent;border:none;color:var(--text);font-size:13px;outline:none;font-family:inherit}
.model-picker-wrap{position:relative;max-width:160px}
.model-picker-drop{position:absolute;top:100%;left:50%;transform:translateX(-50%);margin-top:4px;min-width:140px;max-width:280px;max-height:300px;overflow-y:auto;background:var(--surface);border:1px solid var(--border-light);border-radius:10px;z-index:100;box-shadow:0 8px 30px rgba(0,0,0,.3);white-space:nowrap}
.model-picker-item{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;cursor:pointer;font-size:13px;transition:background .15s;gap:8px}.model-picker-item:hover{background:var(--surface-alt)}.model-picker-item.active{color:var(--primary)}
.model-tag{font-size:10px;padding:1px 6px;border-radius:4px;background:var(--surface-alt);color:var(--text3)}
.dr-list{padding:4px 8px;flex:1;overflow-y:auto}.dr-footer{padding:8px;border-top:1px solid var(--border-light)}
</style>

<template>
  <div class="ai-dropdown" ref="triggerRef">
    <div v-if="label" class="ai-dropdown__trigger ai-dropdown__trigger--label" @click.stop="toggleMenu">
      <span>{{ label }}</span>
      <span class="ai-dropdown__arrow" :class="{ up: open }">▾</span>
    </div>
    <div v-else class="ai-dropdown__trigger" @click.stop="toggleMenu">
      <slot name="trigger" />
    </div>
    <Teleport to="body">
      <div v-if="open" ref="menuRef" class="ai-dropdown__menu" :style="menuStyle" @click.stop>
        <div v-for="(item, i) in items" :key="i" class="ai-dropdown__item" @click="select(item)">
          <span v-if="item.icon" class="ai-dropdown__item-icon">{{ item.icon }}</span>
          <div>
            <div class="ai-dropdown__item-label">{{ item.label }}</div>
            <div v-if="item.desc" class="ai-dropdown__item-desc">{{ item.desc }}</div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'

const props = defineProps<{ items: any[]; label?: string }>()
const emit = defineEmits(['select'])
const open = ref(false)
const triggerRef = ref<HTMLElement>()
const menuRef = ref<HTMLElement>()
const menuStyle = ref<any>({})
let rafId = 0

function updateMenuPos() {
  if (!open.value || !triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  if (rect.bottom < 0 || rect.top > window.innerHeight) { open.value = false; return }
  const estH = Math.min(props.items.length * 44 + 12, 320)
  const spaceBelow = window.innerHeight - rect.bottom - 4
  const spaceAbove = rect.top - 4
  const base = { minWidth: `${Math.max(rect.width, 180)}px`, maxHeight: `${Math.min(estH, 320)}px`, overflowY: 'auto' as const }
  if (spaceBelow >= estH || spaceBelow >= spaceAbove) menuStyle.value = { position: 'fixed', top: `${rect.bottom + 4}px`, left: `${rect.left}px`, ...base }
  else menuStyle.value = { position: 'fixed', top: `${Math.max(4, rect.top - estH)}px`, left: `${rect.left}px`, ...base }
}
function onScrollRAF() { if (open.value) updateMenuPos() }
function onScroll() { if (!open.value) return; if (rafId) cancelAnimationFrame(rafId); rafId = requestAnimationFrame(onScrollRAF) }
function toggleMenu() { open.value = !open.value; if (open.value) nextTick(() => updateMenuPos()) }
function select(item: any) { open.value = false; emit('select', item) }
function onGlobalDown(e: MouseEvent) { if (!open.value) return; const target = e.target as Node; if (triggerRef.value?.contains(target)) return; if (menuRef.value?.contains(target)) return; open.value = false }
watch(open, (val) => {
  if (val) { window.addEventListener('scroll', onScroll, true); window.addEventListener('resize', onScroll) }
  else { window.removeEventListener('scroll', onScroll, true); window.removeEventListener('resize', onScroll); if (rafId) { cancelAnimationFrame(rafId); rafId = 0 } }
})
onMounted(() => window.addEventListener('mousedown', onGlobalDown, true))
onUnmounted(() => { window.removeEventListener('mousedown', onGlobalDown, true); window.removeEventListener('scroll', onScroll, true); window.removeEventListener('resize', onScroll); if (rafId) { cancelAnimationFrame(rafId); rafId = 0 } })
</script>

<style scoped>
.ai-dropdown{position:relative;display:inline-flex}.ai-dropdown__trigger{cursor:pointer}.ai-dropdown__trigger--label{display:flex;align-items:center;gap:8px;padding:8px 14px;border-radius:8px;background:var(--surface);border:1px solid var(--border-light);color:var(--text);font-size:13px;min-width:140px;justify-content:space-between;transition:border .2s;user-select:none}.ai-dropdown__trigger--label:hover{border-color:var(--primary)}.ai-dropdown__arrow{font-size:10px;color:var(--text3);transition:transform .2s}.ai-dropdown__arrow.up{transform:rotate(180deg)}.ai-dropdown__menu{padding:4px 0;background:var(--surface);border:1px solid var(--border-light);border-radius:10px;overflow:hidden;z-index:9999;box-shadow:0 8px 30px rgba(0,0,0,.3)}.ai-dropdown__item{display:flex;align-items:center;gap:10px;padding:10px 14px;cursor:pointer;transition:background .15s;font-size:13px}.ai-dropdown__item:hover{background:var(--surface-alt)}.ai-dropdown__item-icon{width:20px;text-align:center}.ai-dropdown__item-label{color:var(--text)}.ai-dropdown__item-desc{font-size:11px;color:var(--text2)}
</style>

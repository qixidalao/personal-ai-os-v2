<template>
  <div class="ai-tooltip-wrap" @mouseenter="show=true" @mouseleave="show=false">
    <slot/>
    <div v-if="show&&text" class="ai-tooltip">{{text}}</div>
  </div>
</template>
<script setup lang="ts">
import {ref} from 'vue'
defineProps<{text:string}>()
const show=ref(false)
</script>
<style scoped>
.ai-tooltip-wrap{position:relative;display:inline-flex}
.ai-tooltip{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);margin-bottom:6px;padding:4px 10px;border-radius:6px;background:var(--surface-alt);color:var(--text);font-size:11px;white-space:nowrap;pointer-events:none}
</style>

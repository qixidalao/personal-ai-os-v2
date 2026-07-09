<template>
  <Teleport to="body">
    <div v-if="modelValue" class="dr-overlay" :class="{show:modelValue}" @click.self="$emit('update:modelValue',false)"/>
    <aside :class="['dr-panel', side, modelValue?'dr-open':'']">
      <slot/>
    </aside>
  </Teleport>
</template>
<script setup lang="ts">
defineProps<{modelValue:boolean,side?:string}>()
defineEmits(['update:modelValue'])
</script>
<style scoped>
.dr-overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:900;opacity:0;transition:opacity .3s;pointer-events:none}
.dr-overlay.show{opacity:1;pointer-events:auto}
.dr-panel{position:fixed;top:0;bottom:0;width:280px;max-width:85vw;background:var(--surface);z-index:901;transition:transform .3s ease;overflow-y:auto;display:flex;flex-direction:column}
.dr-panel.left{left:0;transform:translateX(-100%)}
.dr-panel.right{right:0;transform:translateX(100%)}
.dr-panel.dr-open{transform:translateX(0)}
</style>

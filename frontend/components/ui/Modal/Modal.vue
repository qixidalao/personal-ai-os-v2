<template>
  <Teleport to="body">
    <div v-if="modelValue" class="ai-modal-overlay" @click.self="$emit('update:modelValue',false)">
      <div :class="['ai-modal',sizeClass]">
        <div v-if="title" class="ai-modal__header">
          <div class="ai-modal__title">{{title}}</div>
          <button class="ai-modal__close" @click="$emit('update:modelValue',false)">✕</button>
        </div>
        <div class="ai-modal__body"><slot/></div>
        <div v-if="$slots.footer" class="ai-modal__footer"><slot name="footer"/></div>
      </div>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
defineProps<{modelValue:boolean,title?:string,size?:string}>()
defineEmits(['update:modelValue'])
import {computed} from 'vue'
const sizeClass=computed(()=>{return ''})
</script>
<style scoped>
.ai-modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000;display:flex;align-items:center;justify-content:center;padding:24px;animation:fadeIn .2s}
@keyframes fadeIn{from{opacity:0}}
.ai-modal{background:var(--surface);border-radius:16px;padding:20px;max-width:420px;width:100%;max-height:80vh;overflow-y:auto;animation:modalUp .3s ease}
@keyframes modalUp{from{opacity:0;transform:translateY(30px)}}
.ai-modal__header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.ai-modal__title{font-size:16px;font-weight:600}
.ai-modal__close{width:28px;height:28px;border-radius:50%;background:transparent;color:var(--text2);cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center}
.ai-modal__close:hover{background:var(--surface-alt)}
.ai-modal__body{font-size:14px;color:var(--text2);line-height:1.6}
.ai-modal__footer{margin-top:16px;display:flex;gap:8px;justify-content:flex-end}
</style>

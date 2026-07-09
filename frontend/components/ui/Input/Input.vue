<template>
  <textarea v-if="type==='textarea'" :class="['ai-input','ai-input--textarea']" :value="modelValue" :placeholder="placeholder" :rows="rows" :disabled="disabled" @input="$emit('update:modelValue',($event.target as any).value)" @keydown="$emit('keydown',$event)"/>
  <input v-else :type="type" :class="['ai-input']" :value="modelValue" :placeholder="placeholder" :disabled="disabled" @input="$emit('update:modelValue',($event.target as any).value)"/>
</template>
<script setup lang="ts">
defineProps<{modelValue?:string,type?:string,placeholder?:string,rows?:number,disabled?:boolean}>()
defineEmits(['update:modelValue','keydown'])
</script>
<style scoped>
.ai-input{width:100%;padding:10px 14px;border-radius:10px;background:var(--surface);border:1px solid var(--border-light);color:var(--text);font-size:14px;font-family:inherit;outline:none;transition:border .2s}
.ai-input:focus{border-color:var(--primary)}
.ai-input::placeholder{color:var(--text3)}
.ai-input:disabled{opacity:.5}
.ai-input--textarea{resize:none;min-height:42px;line-height:1.5}
</style>

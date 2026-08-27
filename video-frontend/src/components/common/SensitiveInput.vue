<script setup lang="ts">
/** 敏感字段输入：密码框渲染 + 显示/隐藏切换（设计 ④c） */
import { ref } from 'vue'

defineProps<{
  modelValue: string
  placeholder?: string
}>()

const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()
const show = ref(false)
</script>

<template>
  <div class="relative">
    <input
      :type="show ? 'text' : 'password'"
      :value="modelValue"
      :placeholder="placeholder || '••••••'"
      class="w-full rounded-md border border-border bg-surface px-3 py-2 pr-16 text-sm text-text outline-none transition-colors focus:border-accent"
      autocomplete="off"
      spellcheck="false"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <button
      type="button"
      class="absolute right-2 top-1/2 -translate-y-1/2 rounded px-2 py-0.5 text-xs text-primary hover:bg-surface-2"
      @click="show = !show"
    >
      {{ show ? '隐藏' : '显示' }}
    </button>
  </div>
</template>

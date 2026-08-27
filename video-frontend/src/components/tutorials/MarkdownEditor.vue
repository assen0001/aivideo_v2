<script setup lang="ts">
/** Markdown 编辑器：md-editor-v3 路由级懒加载（仅发布/编辑页加载，设计 §8 性能） */
import { defineAsyncComponent, type Component } from 'vue'

// md-editor-v3 v5+ 是命名导出 { MdEditor }，不是 default
const MdEditor = defineAsyncComponent(async () => {
  await import('md-editor-v3/lib/style.css')
  const mod = (await import('md-editor-v3')) as unknown as { MdEditor: Component }
  return mod.MdEditor
})
const modelValue = defineModel<string>({ default: '' })
</script>

<template>
  <MdEditor v-model="modelValue" :style="{ height: '60vh' }" language="zh-CN" />
</template>

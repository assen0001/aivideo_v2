<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: string
}>()

const map: Record<string, { label: string; cls: string; dot: string }> = {
  等待: { label: '等待', cls: 'bg-surface-2 text-text-2 border-border', dot: 'bg-text-3' },
  进行中: { label: '进行中', cls: 'bg-amber-50 text-amber-700 border-amber-200', dot: 'bg-accent breathe' },
  完成: { label: '完成', cls: 'bg-green-50 text-green-700 border-green-200', dot: 'bg-success' },
  失败: { label: '失败', cls: 'bg-red-50 text-red-700 border-red-200', dot: 'bg-danger' },
  待生成: { label: '待生成', cls: 'bg-surface-2 text-text-2 border-border', dot: 'bg-text-3' },
  生成中: { label: '生成中', cls: 'bg-amber-50 text-amber-700 border-amber-200', dot: 'bg-accent breathe' },
}

const conf = computed(() => map[props.status] || { label: props.status, cls: 'bg-surface-2 text-text-2 border-border', dot: 'bg-text-3' })
</script>

<template>
  <span class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium" :class="conf.cls">
    <span class="h-1.5 w-1.5 rounded-full" :class="conf.dot" />
    {{ conf.label }}
  </span>
</template>

<script setup lang="ts">
const props = defineProps<{
  page: number
  pageSize: number
  total: number
}>()

const emit = defineEmits<{ (e: 'change', page: number): void }>()

const totalPages = Math.max(1, Math.ceil(props.total / props.pageSize))

function go(p: number) {
  if (p >= 1 && p <= totalPages && p !== props.page) emit('change', p)
}
</script>

<template>
  <div class="flex items-center justify-center gap-2 pt-4 text-sm">
    <button
      class="rounded-full border border-border px-3 py-1 text-text-2 hover:bg-surface-2 disabled:opacity-40"
      :disabled="page <= 1"
      @click="go(page - 1)"
    >
      上一页
    </button>
    <span class="px-2 text-text-2">第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 条</span>
    <button
      class="rounded-full border border-border px-3 py-1 text-text-2 hover:bg-surface-2 disabled:opacity-40"
      :disabled="page >= totalPages"
      @click="go(page + 1)"
    >
      下一页
    </button>
  </div>
</template>

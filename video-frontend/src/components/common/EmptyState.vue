<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  description?: string
}>(), {
  title: '暂无内容',
  description: '',
})
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
    <div class="flex h-16 w-16 items-center justify-center rounded-full bg-surface-2 text-3xl">🎬</div>
    <p class="font-medium text-text-2">{{ title }}</p>
    <p v-if="description" class="max-w-sm text-sm text-text-3">{{ description }}</p>
    <div v-if="$slots.default" class="mt-2">
      <slot />
    </div>
  </div>
</template>

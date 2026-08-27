<script setup lang="ts">
withDefaults(defineProps<{
  src: string
  poster?: string
}>(), {
  poster: '',
})
</script>

<template>
  <div v-if="src" class="flex w-full items-center justify-center">
    <video
      :src="src"
      :poster="poster"
      controls
      preload="metadata"
      class="rounded-lg bg-black object-contain"
      :style="{
        maxHeight: '70vh',
        maxWidth: '100%',
        height: 'auto',
        width: 'auto',
        display: 'block',
      }"
    />
  </div>
  <div v-else class="flex aspect-video w-full items-center justify-center rounded-lg bg-surface-2 text-text-3">
    暂无成片
  </div>
</template>

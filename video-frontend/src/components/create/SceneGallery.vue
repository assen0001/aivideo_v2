<script setup lang="ts">
import type { Scene } from '@/types'

defineProps<{
  scenes: Scene[]
}>()

const emit = defineEmits<{ (e: 'preview', url: string): void }>()
</script>

<template>
  <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
    <figure
      v-for="s in scenes"
      :key="s.scene_no"
      class="group cursor-zoom-in overflow-hidden rounded-lg border border-border bg-surface shadow-sm"
      @click="s.image_url && emit('preview', s.image_url)"
    >
      <img
        v-if="s.image_url"
        :src="s.image_url"
        :alt="`分镜 ${s.scene_no}`"
        loading="lazy"
        class="aspect-video w-full object-cover transition-transform group-hover:scale-105"
      />
      <div v-else class="flex aspect-video w-full items-center justify-center bg-surface-2 text-text-3">未生成</div>
      <figcaption class="px-2 py-1.5 text-xs text-text-2">分镜 {{ s.scene_no }}</figcaption>
    </figure>
  </div>
</template>

<script setup lang="ts">
import type { Scene } from '@/types'

defineProps<{
  scenes: Scene[]
}>()
</script>

<template>
  <div class="grid gap-4 sm:grid-cols-2">
    <div v-for="s in scenes" :key="s.scene_no" class="overflow-hidden rounded-lg border border-border bg-surface shadow-sm">
      <video v-if="s.video_url" :src="s.video_url" controls preload="metadata" class="aspect-video w-full bg-black" />
      <div v-else class="flex aspect-video w-full items-center justify-center bg-surface-2 text-sm text-text-3">未生成片段</div>
      <p class="px-3 py-2 text-xs text-text-2">分镜 {{ s.scene_no }} · {{ s.duration }}s</p>
    </div>
  </div>
</template>

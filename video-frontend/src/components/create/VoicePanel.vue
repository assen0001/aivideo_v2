<script setup lang="ts">
import type { Scene } from '@/types'

defineProps<{
  scenes: Scene[]
}>()
</script>

<template>
  <div class="grid gap-3 sm:grid-cols-2">
    <div v-for="s in scenes" :key="s.scene_no" class="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2.5 shadow-sm">
      <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs font-bold text-primary">#{{ s.scene_no }}</span>
      <div class="min-w-0 flex-1">
        <audio v-if="s.voice_path" :src="s.voice_path" controls preload="none" class="h-8 w-full" />
        <p v-else class="text-xs text-text-3">未生成配音</p>
      </div>
      <span v-if="s.voice_duration" class="shrink-0 text-xs text-text-3">{{ s.voice_duration.toFixed(1) }}s</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Scene } from '@/types'

const props = defineProps<{
  scene: Scene
}>()

const voiceDur = computed(() => (props.scene.voice_duration ? `${props.scene.voice_duration.toFixed(1)}s` : '—'))
</script>

<template>
  <div class="grid gap-4 rounded-lg border border-border bg-surface-2 p-4 md:grid-cols-[220px_1fr]">
    <div>
      <img v-if="scene.image_url" :src="scene.image_url" :alt="`分镜 ${scene.scene_no}`" loading="lazy" class="aspect-video w-full rounded-md object-cover" />
      <div v-else class="flex aspect-video w-full items-center justify-center rounded-md bg-surface text-text-3">无图</div>
    </div>
    <div class="min-w-0 space-y-2 text-sm">
      <div class="flex flex-wrap items-center gap-2">
        <span class="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs text-white">#{{ scene.scene_no }}</span>
        <span class="text-xs text-text-3">{{ scene.camera }} · 时长 {{ scene.duration }}s · 配音 {{ voiceDur }}</span>
      </div>
      <p class="text-text"><span class="text-text-3">描述：</span>{{ scene.description }}</p>
      <p class="text-text"><span class="text-text-3">旁白：</span>{{ scene.narration }}</p>
      <p class="text-text"><span class="text-text-3">字幕：</span>{{ scene.subtitle }}</p>
      <div v-if="scene.video_url || scene.voice_path" class="grid gap-2 sm:grid-cols-2">
        <video v-if="scene.video_url" :src="scene.video_url" controls preload="metadata" class="w-full rounded-md bg-black" />
        <audio v-if="scene.voice_path" :src="scene.voice_path" controls preload="none" class="w-full" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { formatTime } from '@/utils/format'
import type { Tutorial } from '@/types'

const props = defineProps<{
  tutorial: Tutorial
  last?: boolean
}>()

const router = useRouter()
</script>

<template>
  <article class="relative flex gap-4">
    <!-- 时间轴节点 -->
    <div class="flex flex-col items-center">
      <span class="mt-1.5 flex h-3 w-3 shrink-0 rounded-full border-2 border-accent bg-surface" />
      <span v-if="!last" class="w-px flex-1 bg-border" />
    </div>

    <div
      class="mb-4 min-w-0 flex-1 cursor-pointer rounded-lg border border-border bg-surface p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
      @click="router.push(`/tutorials/${tutorial.id}`)"
    >
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="font-medium text-text">{{ tutorial.title }}</h3>
        <span v-if="tutorial.tags" class="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-primary">{{ tutorial.tags }}</span>
      </div>
      <p v-if="tutorial.summary" class="mt-1 line-clamp-2 text-sm text-text-2">{{ tutorial.summary }}</p>
      <p class="mt-2 text-xs text-text-3">{{ formatTime(tutorial.created_at) }}</p>
    </div>
  </article>
</template>

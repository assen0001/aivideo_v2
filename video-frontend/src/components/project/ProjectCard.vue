<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import StatusBadge from '@/components/common/StatusBadge.vue'
import type { Project } from '@/types'

const props = defineProps<{
  project: Project
}>()

const router = useRouter()

const cover = computed(() => props.project.cover_url || '')

function open() {
  router.push(`/projects/${props.project.project_id}`)
}
</script>

<template>
  <article
    class="group cursor-pointer overflow-hidden rounded-lg bg-surface shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-md"
    @click="open"
  >
    <div class="relative aspect-video overflow-hidden bg-surface-2">
      <img v-if="cover" :src="cover" :alt="project.name" loading="lazy" class="h-full w-full object-cover transition-transform group-hover:scale-105" />
      <div v-else class="flex h-full w-full items-center justify-center text-4xl text-text-3">🎬</div>
      <div class="absolute right-2 top-2">
        <StatusBadge :status="project.status" />
      </div>
    </div>
    <div class="p-4">
      <h3 class="truncate font-medium text-text">{{ project.name }}</h3>
      <p class="mt-0.5 truncate text-xs text-text-3">{{ project.topic }}</p>
      <div class="mt-3 flex items-center justify-between text-xs text-text-3">
        <span>{{ project.scene_count }} 个分镜</span>
        <span>{{ project.created_at }}</span>
      </div>
    </div>
  </article>
</template>

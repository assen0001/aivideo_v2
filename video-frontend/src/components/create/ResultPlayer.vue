<script setup lang="ts">
import AppVideo from '@/components/common/AppVideo.vue'

defineProps<{
  videoUrl: string
  downloadUrl: string
  name: string
}>()
</script>

<template>
  <div class="space-y-4">
    <AppVideo :src="videoUrl" />
    <div class="flex flex-wrap gap-3">
      <a
        v-if="videoUrl"
        :href="downloadUrl"
        class="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-accent-hover"
      >
        ⬇ 下载成片
      </a>
    </div>
    <p class="text-xs text-text-3">{{ name }}</p>
  </div>
</template>

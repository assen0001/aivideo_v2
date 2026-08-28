<script setup lang="ts">
import { computed } from 'vue'
import AppVideo from '@/components/common/AppVideo.vue'
import { useRecompose } from '@/composables/useRecompose'

const props = defineProps<{
  videoUrl: string
  downloadUrl: string
  name: string
  projectId?: string
}>()

const emit = defineEmits<{ recomposed: [] }>()

const { recomposing, recomposedTs, trigger } = useRecompose(() => props.projectId || '')

/** 重新合成成功后加时间戳，强制视频组件重新加载（URL 路径不变，需破缓存） */
const displayVideoUrl = computed(() => (recomposedTs.value ? `${props.videoUrl}?ts=${recomposedTs.value}` : props.videoUrl))

function onRecompose() {
  trigger(() => emit('recomposed'))
}
</script>

<template>
  <div class="space-y-4">
    <AppVideo :src="displayVideoUrl" />
    <div class="flex flex-wrap gap-3">
      <a
        v-if="videoUrl"
        :href="downloadUrl"
        class="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-accent-hover"
      >
        ⬇ 下载成片
      </a>
      <button
        v-if="projectId"
        :disabled="recomposing"
        class="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-5 py-2.5 text-sm font-medium text-text-2 transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50"
        @click="onRecompose"
      >
        {{ recomposing ? '合成中…' : '🔄 重新合成视频' }}
      </button>
    </div>
    <p class="text-xs text-text-3">{{ name }}</p>
  </div>
</template>

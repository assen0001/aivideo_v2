<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import AppVideo from '@/components/common/AppVideo.vue'
import { useToastStore } from '@/stores/toast'
import * as projectApi from '@/api/projects'

const props = defineProps<{
  videoUrl: string
  downloadUrl: string
  name: string
  projectId?: string
}>()

const emit = defineEmits<{ recomposed: [] }>()

const toast = useToastStore()
const recomposing = ref(false)
/** 重新合成成功后加时间戳，强制视频组件重新加载（URL 路径不变，需破缓存） */
const videoTs = ref(0)
const displayVideoUrl = computed(() => (videoTs.value ? `${props.videoUrl}?ts=${videoTs.value}` : props.videoUrl))
let pollTimer: ReturnType<typeof setInterval> | null = null

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

/** 重新合成：调接口 → 3s 轮询状态 → 完成时通知父组件刷新（物理文件已覆盖，DB 记录已更新） */
async function onRecompose() {
  if (!props.projectId || recomposing.value) return
  recomposing.value = true
  try {
    await projectApi.recomposeProject(props.projectId)
    toast.show('success', '已开始重新合成，请稍候…')
  } catch {
    recomposing.value = false
    return // 错误已由 http 拦截器 toast
  }

  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const st = await projectApi.getProjectStatus(props.projectId!)
      if (st.status === '完成') {
        stopPolling()
        recomposing.value = false
        videoTs.value = Date.now()
        toast.show('success', '重新合成完成')
        emit('recomposed')
      } else if (st.status === '失败') {
        stopPolling()
        recomposing.value = false
        toast.show('error', st.error_msg || '重新合成失败，已保留原成片')
      }
      // 进行中：继续轮询
    } catch {
      // 轮询出错：继续等下一轮
    }
  }, 3000)
}

onBeforeUnmount(stopPolling)
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

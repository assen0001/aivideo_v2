<script setup lang="ts">
import { computed } from 'vue'
import type { TestStatus } from '@/types'
import AppButton from '@/components/common/AppButton.vue'

const props = defineProps<{
  vendor: string
  result: TestStatus | null
  running: boolean
}>()

const emit = defineEmits<{ (e: 'close'): void; (e: 'retry'): void }>()

const vendorNames: Record<string, string> = {
  llm: '大语言模型',
  t2i: '文生图',
  i2v: '图生视频',
  tts: '语音合成',
}

const stageTexts: Record<string, string> = {
  pending: '任务准备中…',
  system_stats: '正在检查服务状态…',
  generate: '正在生成测试内容…',
  fetch: '正在获取生成结果…',
  done: '已完成',
  error: '失败',
}

const title = computed(() => `${vendorNames[props.vendor] || '服务'} · 连通性测试`)
const stageText = computed(() => stageTexts[props.result?.stage || 'pending'])

function fmtSize(bytes?: number): string {
  if (!bytes) return '—'
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes > 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

function fmtTime(ms?: number): string {
  if (!ms) return '—'
  if (ms > 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

/** media 标签无法携带 Authorization header，给预览 URL 附加 token 查询参数 */
function authUrl(url?: string): string {
  if (!url) return ''
  if (url.startsWith('/api/') && !url.includes('token=')) {
    const token = localStorage.getItem('token') || ''
    return `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`
  }
  return url
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- 运行中 -->
    <div v-if="running" class="flex items-center gap-3 py-6">
      <span class="inline-block h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      <div>
        <p class="text-sm font-medium text-text">{{ stageText }}</p>
        <p v-if="result?.elapsed_ms" class="text-xs text-text-3">已耗时 {{ fmtTime(result.elapsed_ms) }}</p>
      </div>
    </div>

    <!-- 成功 -->
    <template v-else-if="result?.status === 'success'">
      <div class="flex items-center gap-2 rounded-md bg-green-50 px-4 py-3">
        <span class="text-lg">✅</span>
        <div>
          <p class="text-sm font-semibold text-green-700">测试通过</p>
          <p class="text-xs text-green-600">耗时 {{ fmtTime(result.elapsed_ms) }}</p>
        </div>
      </div>

      <!-- LLM 响应摘要 -->
      <div v-if="result.response?.content_preview" class="rounded-md bg-surface-2 px-4 py-3">
        <p class="mb-1 text-xs text-text-3">模型回复</p>
        <p class="text-sm text-text">{{ result.response.content_preview }}</p>
        <p v-if="result.response.model" class="mt-1 text-xs text-text-3">模型：{{ result.response.model }}</p>
      </div>

      <!-- ComfyUI 状态 -->
      <div v-if="result.response?.gpu" class="rounded-md bg-surface-2 px-4 py-3">
        <p class="text-xs text-text-3">GPU：{{ result.response.gpu }}</p>
        <p class="text-xs text-text-3">
          显存剩余：{{ result.response.vram_free_mb ?? 0 }} MB · ComfyUI v{{ result.response.comfyui_version }}
        </p>
      </div>

      <!-- 产物预览 -->
      <div v-if="result.artifacts?.length" class="space-y-2">
        <p class="text-xs text-text-3">生成产物（{{ result.artifacts.length }}）</p>
        <template v-for="a in result.artifacts" :key="a.url">
          <img
            v-if="a.type === 'image'"
            :src="authUrl(a.url)"
            class="max-h-48 w-full rounded-md border border-border object-contain"
            alt="测试产物"
          />
          <video
            v-else-if="a.type === 'video'"
            :src="authUrl(a.url)"
            controls
            class="max-h-48 w-full rounded-md border border-border bg-black"
          />
          <audio v-else-if="a.type === 'audio'" :src="authUrl(a.url)" controls class="w-full" />
          <p v-else class="text-xs text-text-3">{{ a.filename }}（{{ fmtSize(a.size_bytes) }}）</p>
        </template>
      </div>
    </template>

    <!-- 失败 -->
    <template v-else-if="result?.status === 'error'">
      <div class="flex items-start gap-2 rounded-md bg-red-50 px-4 py-3">
        <span class="text-lg leading-6">❌</span>
        <div class="min-w-0">
          <p class="text-sm font-semibold text-red-700">测试失败</p>
          <p class="mt-1 whitespace-pre-wrap break-all text-xs text-red-600">{{ result.detail || '未知错误' }}</p>
        </div>
      </div>
    </template>

    <!-- 无结果 -->
    <p v-else class="py-4 text-sm text-text-3">暂无测试结果</p>

    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <AppButton v-if="result?.status === 'error' && !running" type="secondary" size="sm" @click="emit('retry')">
        重新测试
      </AppButton>
      <AppButton type="primary" size="sm" :disabled="running" @click="emit('close')">关闭</AppButton>
    </div>
  </div>
</template>

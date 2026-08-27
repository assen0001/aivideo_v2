<script setup lang="ts">
import { computed } from 'vue'
import { useProjectStore } from '@/stores/project'
import type { ProjectStatus, Scene, StepDef } from '@/types'

const store = useProjectStore()
/**
 * 外部可控的选中阶段 + 状态覆盖
 * - activeKey: 不传时跟随 store 当前进行中阶段（创作页）
 * - status: 详情页传入本项目自身状态，避免被 store 全局状态（可能正在跑别的项目）污染
 * - scenes: 分镜列表（可选），用于展示各阶段「已生成 N/M」实时计数角标
 */
const props = defineProps<{
  activeKey?: string
  status?: ProjectStatus | null
  scenes?: Scene[]
  /** V2.4：项目为「无配音」时语音合成节点置灰（跳过该阶段） */
  voiceSkipped?: boolean
}>()
const emit = defineEmits<{ (e: 'select', key: string): void }>()

// V2.4：语音合成前置到文生图之前（progress 与后端 generation.STEP_PROGRESS 同步）
const STEPS: StepDef[] = [
  { key: 'script', label: '剧本创作', progress: 5 },
  { key: 'voice', label: '语音合成', progress: 20 },
  { key: 'images', label: '文生图', progress: 35 },
  { key: 'videos', label: '图生视频', progress: 60 },
  { key: 'compose', label: '视频合成', progress: 85 },
]
const STEP_INDEX: Record<string, number> = { script: 0, voice: 1, images: 2, videos: 3, compose: 4, done: 4 }

/** 实际使用的状态：props.status 优先（详情页），否则用 store（创作页轮询） */
const effStatus = computed<ProjectStatus | null>(() => props.status ?? store.status)
const effStep = computed(() => effStatus.value?.current_step || '')

/** 分镜级实时计数：各阶段已生成 N / 总 M（V2.1 分镜级写库后轮询可见） */
const sceneStats = computed(() => {
  const list = props.scenes || []
  const total = list.length
  return {
    total,
    images: list.filter((s) => s.image_url).length,
    videos: list.filter((s) => s.video_url).length,
    voice: list.filter((s) => s.voice_path).length,
  }
})

const flow = computed(() => {
  const s = effStatus.value?.status
  const step = effStep.value || ''
  const idx = STEP_INDEX[step] ?? -1
  return STEPS.map((sdef, i) => {
    // V2.4：无配音项目 → 语音合成节点置灰（跳过，不可交互）
    if (sdef.key === 'voice' && props.voiceSkipped) {
      return { ...sdef, state: 'skipped' as const }
    }
    if (s === '完成') return { ...sdef, state: 'done' as const }
    if (s === '失败') {
      if (i === idx) return { ...sdef, state: 'failed' as const }
      return { ...sdef, state: i < idx ? ('done' as const) : ('pending' as const) }
    }
    if (s === '进行中') {
      if (i === idx) return { ...sdef, state: 'running' as const }
      return { ...sdef, state: i < idx ? ('done' as const) : ('pending' as const) }
    }
    return { ...sdef, state: 'pending' as const }
  })
})
const progress = computed(() => effStatus.value?.progress_percent || 0)
const isGenerating = computed(() => effStatus.value?.status === '进行中')
const currentKey = computed(() => props.activeKey ?? effStep.value ?? 'script')

const stateIcon: Record<string, string> = {
  pending: '○',
  running: '●',
  done: '✓',
  failed: '✗',
  skipped: '—',
}

const stateCls: Record<string, string> = {
  pending: 'text-text-3 border-border',
  running: 'text-accent border-accent breathe',
  done: 'text-success border-success',
  failed: 'text-danger border-danger',
  skipped: 'text-text-3/60 border-border/60',
}

function selectStep(key: string) {
  emit('select', key)
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between gap-2 overflow-x-auto pb-1">
      <template v-for="(s, i) in flow" :key="s.key">
        <div class="flex shrink-0 items-center gap-2">
          <button
            type="button"
            class="flex items-center gap-2 rounded-full px-1 py-0.5 transition-colors"
            :class="s.state === 'skipped' ? 'cursor-not-allowed opacity-70' : 'hover:bg-surface-2'"
            :title="s.state === 'skipped' ? '本项目为无配音，已跳过该阶段' : `点击仅显示「${s.label}」阶段`"
            :disabled="s.state === 'skipped'"
            @click="selectStep(s.key)"
          >
            <span
              class="flex h-9 w-9 items-center justify-center rounded-full border-2 text-sm font-bold transition-all"
              :class="stateCls[s.state]"
            >
              <!-- running：动态旋转 spinner（比静态 ● 更直观） -->
              <span v-if="s.state === 'running'" class="spinner-ring" role="img" aria-label="处理中" />
              <span v-else>{{ stateIcon[s.state] }}</span>
            </span>
            <span
              class="text-sm font-medium transition-colors"
              :class="[
                s.state === 'pending' || s.state === 'skipped' ? 'text-text-3' : 'text-text',
                s.key === currentKey ? 'underline decoration-accent decoration-2 underline-offset-4' : '',
              ]"
            >{{ s.label }}</span>
            <!-- 分镜级实时计数角标（仅在有数据时显示） -->
            <span
              v-if="sceneStats.total && s.key === 'images' && sceneStats.images > 0"
              class="rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium leading-none text-primary"
            >{{ sceneStats.images }}/{{ sceneStats.total }}</span>
            <span
              v-else-if="sceneStats.total && s.key === 'videos' && sceneStats.videos > 0"
              class="rounded-full bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium leading-none text-accent"
            >{{ sceneStats.videos }}/{{ sceneStats.total }}</span>
            <span
              v-else-if="sceneStats.total && s.key === 'voice' && sceneStats.voice > 0"
              class="rounded-full bg-success/10 px-1.5 py-0.5 text-[10px] font-medium leading-none text-success"
            >{{ sceneStats.voice }}/{{ sceneStats.total }}</span>
          </button>
          <span v-if="i < flow.length - 1" class="h-px w-6 bg-border sm:w-10" />
        </div>
      </template>
    </div>

    <!-- 整体进度条 -->
    <div class="mt-4">
      <div class="mb-1 flex items-center justify-between text-xs text-text-3">
        <span>总进度</span>
        <span>{{ progress }}%</span>
      </div>
      <div class="h-2 overflow-hidden rounded-full bg-surface-2">
        <div
          class="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-all duration-500"
          :style="{ width: `${progress}%` }"
        />
      </div>
      <p v-if="isGenerating" class="mt-1 text-xs text-text-3">正在创作中，页面隐藏时将暂停轮询…</p>
    </div>
  </div>
</template>

<style scoped>
/* running 动态旋转图标（圆环 spinner，颜色继承 stateCls 的 text-accent） */
.spinner-ring {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 9999px;
  animation: wb-spin 0.7s linear infinite;
}
@keyframes wb-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
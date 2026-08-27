<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useToastStore } from '@/stores/toast'
import * as projectApi from '@/api/projects'
import StepFlow from '@/components/create/StepFlow.vue'
import ConfigForm from '@/components/create/ConfigForm.vue'
import SceneGallery from '@/components/create/SceneGallery.vue'
import SceneVideos from '@/components/create/SceneVideos.vue'
import VoicePanel from '@/components/create/VoicePanel.vue'
import ResultPlayer from '@/components/create/ResultPlayer.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppCard from '@/components/common/AppCard.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import type { Project, Scene } from '@/types'

const store = useProjectStore()
const router = useRouter()
const toast = useToastStore()

const submitting = ref(false)
const stopping = ref(false)
const detail = ref<Project | null>(null)
const lightbox = ref('')
const busyProjectId = ref('')
/** 是否已提交（提交后隐藏输入区，只保留流程进度） */
const submitted = ref(false)

/** 是否有其他项目在创作中（单并发置灰） */
const othersBusy = computed(() => {
  if (store.isGenerating && store.currentProjectId) return false
  return busyProjectId.value !== '' && busyProjectId.value !== store.currentProjectId
})

const status = computed(() => store.status)
const scenes = computed<Scene[]>(() => detail.value?.scenes || [])

/** 阶段内容选中：null 表示跟随当前进行中阶段；点击阶段名后锁定为该阶段 */
const userStepKey = ref<string | null>(null)
/** 默认跟随当前进行中阶段；后端完成态 current_step='done' → 映射到 'compose'（成片）；未开始 fallback 'compose' */
const defaultStepKey = computed(() => {
  const step = status.value?.current_step
  if (!step || step === 'done') return 'compose'
  return step
})
const activeStepKey = computed(() => userStepKey.value || defaultStepKey.value)
const hasScript = computed(() => !!status.value && (status.value.current_step !== '' || status.value.status === '完成'))
const stageLabelMap: Record<string, string> = {
  script: '剧本创作',
  images: '文生图',
  videos: '图生视频',
  voice: '语音合成',
  compose: '视频合成',
}

/** 用户点击阶段：锁定/切换；点击同一阶段时清空（回到跟随状态） */
function onStepSelect(key: string) {
  userStepKey.value = userStepKey.value === key ? null : key
}

async function checkBusy() {
  try {
    const res = await projectApi.listProjects({ page: 1, page_size: 12, status: '进行中' })
    const item = res.items[0]
    busyProjectId.value = item ? item.project_id : ''
  } catch {
    busyProjectId.value = ''
  }
}

async function submit() {
  submitting.value = true
  try {
    await store.createAndGenerate()
    toast.show('success', '创作任务已启动')
    submitted.value = true
    await loadDetail()
  } catch {
    /* 错误已 toast */
  } finally {
    submitting.value = false
  }
}

/** 新建创作：重置 store + 表单，回到输入区 */
async function startNew() {
  store.reset()
  store.configForm = {
    name: '',
    topic: '',
    ratio: '16:9',
    resolution: '普清360P',
    fps: 16,
    style: '写实',
    voice: 'none',
    targetDuration: 30,
  }
  detail.value = null
  submitted.value = false
  await checkBusy()
}

async function loadDetail() {
  if (!store.currentProjectId) return
  try {
    detail.value = await projectApi.getProject(store.currentProjectId)
  } catch {
    detail.value = null
  }
}

function goProgress() {
  if (busyProjectId.value) {
    router.push(`/projects/${busyProjectId.value}`)
  } else if (store.currentProjectId) {
    router.push(`/projects/${store.currentProjectId}`)
  }
}

/** 主动停止生成：仅在「进行中」时可点。后端在下一个 step/轮询检查点中断并写「失败」。 */
async function stopGeneration() {
  if (!store.currentProjectId) return
  stopping.value = true
  try {
    await projectApi.stopGenerate(store.currentProjectId)
    toast.show('success', '已发送停止指令，任务即将终止')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    toast.show('error', err.response?.data?.message || '停止失败')
  } finally {
    stopping.value = false
  }
}

// 轮询状态变化 → 刷新详情（展示中间产物）
store.$subscribe(() => {
  if (store.status?.status === '进行中' || store.status?.status === '完成' || store.status?.status === '失败') {
    loadDetail()
  }
})

onMounted(async () => {
  await checkBusy()
  await store.restoreRecent()
  if (store.currentProjectId) {
    await loadDetail()
    if (store.isGenerating) {
      store.startPolling(store.currentProjectId)
    }
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- 单并发提示 -->
    <div v-if="othersBusy" class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-5 py-3">
      <p class="text-sm text-amber-700">当前有项目在创作中，同一时间仅允许 1 个项目生成</p>
      <button class="rounded-full bg-amber-600 px-4 py-1.5 text-sm text-white hover:bg-amber-700" @click="goProgress">
        查看进度 →
      </button>
    </div>

    <AppCard v-if="!submitted && !store.currentProjectId">
      <h2 class="mb-5 flex items-center gap-2 text-lg font-semibold text-text">
        <span class="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-white">✦</span>
        开始创作
      </h2>
      <ConfigForm />
      <div class="mt-6 flex flex-wrap items-center gap-3">
        <AppButton :loading="submitting" :disabled="othersBusy || store.isGenerating" @click="submit">
          {{ othersBusy ? '已有项目在创作中' : store.isGenerating ? '创作中…' : '开始创作' }}
        </AppButton>
        <button v-if="store.isGenerating" class="text-sm text-primary hover:underline" @click="goProgress">查看进度 →</button>
      </div>
    </AppCard>

    <!-- 流程条（提交后只展示流程与产物，不再显示输入区） -->
    <AppCard v-if="submitted || store.currentProjectId">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 class="font-semibold text-text">创作流程</h3>
        <div class="flex items-center gap-3">
          <StatusBadge v-if="status" :status="status.status" />
          <button
            v-if="store.isGenerating"
            class="rounded-full border border-danger bg-danger/10 px-3 py-1 text-xs font-medium text-danger transition-colors hover:bg-danger hover:text-white disabled:opacity-50"
            :disabled="stopping"
            @click="stopGeneration"
          >
            {{ stopping ? '停止中…' : '■ 停止生成' }}
          </button>
          <button v-if="!store.isGenerating" class="rounded-full border border-border bg-surface px-3 py-1 text-xs text-text-2 hover:bg-surface-2" @click="startNew">+ 新建创作</button>
        </div>
      </div>
      <StepFlow :scenes="scenes" :voice-skipped="store.configForm.voice === 'none'" @select="onStepSelect" />

      <!-- 失败错误卡片 -->
      <div v-if="status?.status === '失败'" class="mt-4 rounded-lg border border-red-200 bg-red-50 p-4">
        <p class="text-sm font-medium text-danger">生成失败</p>
        <p class="mt-1 text-sm text-red-700">{{ status.error_msg || '未知错误' }}</p>
        <div class="mt-3">
          <button class="text-sm text-text-2 hover:underline" @click="startNew">回到开始创作</button>
        </div>
      </div>
    </AppCard>

    <!-- 阶段产物（点击阶段切换，同一时间仅显示一个，避免内容过多卡顿） -->
    <template v-if="detail && scenes.length">
      <!-- ① 剧本分镜卡片 -->
      <AppCard v-if="activeStepKey === 'script' && hasScript">
        <h3 class="mb-4 font-semibold text-text">① 剧本分镜</h3>
        <div class="grid gap-3 md:grid-cols-2">
          <div v-for="s in scenes" :key="s.scene_no" class="rounded-lg border border-border bg-surface-2 p-4">
            <div class="mb-1 flex items-center gap-2">
              <span class="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs text-white">#{{ s.scene_no }}</span>
              <span class="text-xs text-text-3">{{ s.camera }} · {{ s.duration }}s</span>
            </div>
            <p class="text-sm text-text">{{ s.description }}</p>
            <p class="mt-1.5 text-xs text-text-2">旁白：{{ s.narration }}</p>
          </div>
        </div>
      </AppCard>

      <!-- ② 图片网格 -->
      <AppCard v-else-if="activeStepKey === 'images' && scenes.some((s) => s.image_url)">
        <h3 class="mb-4 font-semibold text-text">② 分镜图片</h3>
        <SceneGallery :scenes="scenes" @preview="lightbox = $event" />
      </AppCard>

      <!-- ③ 视频片段 -->
      <AppCard v-else-if="activeStepKey === 'videos' && scenes.some((s) => s.video_url)">
        <h3 class="mb-4 font-semibold text-text">③ 分镜视频</h3>
        <SceneVideos :scenes="scenes" />
      </AppCard>

      <!-- ④ 配音 -->
      <AppCard v-else-if="activeStepKey === 'voice' && scenes.some((s) => s.voice_path)">
        <h3 class="mb-4 font-semibold text-text">④ 分镜配音</h3>
        <VoicePanel :scenes="scenes" />
      </AppCard>

      <!-- ⑤ 成片 -->
      <AppCard v-else-if="activeStepKey === 'compose' && detail.final_video_url">
        <h3 class="mb-4 font-semibold text-text">⑤ 成片</h3>
        <ResultPlayer :video-url="detail.final_video_url" :download-url="detail.download_url" :name="detail.name" />
      </AppCard>

      <!-- 选中阶段暂无产物的占位提示 -->
      <AppCard v-else>
        <p class="py-8 text-center text-sm text-text-3">
          「{{ stageLabelMap[activeStepKey] || activeStepKey }}」阶段尚未产出内容，请稍候或切换其他阶段查看
        </p>
      </AppCard>
    </template>

    <!-- 灯箱 -->
    <Teleport to="body">
      <div v-if="lightbox" class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6" @click="lightbox = ''">
        <img :src="lightbox" class="max-h-full max-w-full rounded-lg" alt="分镜大图" />
      </div>
    </Teleport>
  </div>
</template>

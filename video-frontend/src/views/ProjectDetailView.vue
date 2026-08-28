<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as projectApi from '@/api/projects'
import { useProjectStore } from '@/stores/project'
import { useToastStore } from '@/stores/toast'
import AppButton from '@/components/common/AppButton.vue'
import AppCard from '@/components/common/AppCard.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppVideo from '@/components/common/AppVideo.vue'
import AppSkeleton from '@/components/common/AppSkeleton.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import StepFlow from '@/components/create/StepFlow.vue'
import { useRecompose } from '@/composables/useRecompose'
import { voiceLabel } from '@/constants/voice'
import type { Project, ProjectStatus } from '@/types'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const toast = useToastStore()

const projectId = route.params.id as string
const detail = ref<Project | null>(null)
const loading = ref(true)
const showDelete = ref(false)
const deleting = ref(false)
/** 本项目自己的状态（避免被 store 全局状态污染：用户在别的页跑新任务时，详情页进度仍应显示该项目自身） */
const localStatus = ref<ProjectStatus | null>(null)
let pollTimer: number | null = null
/** 阶段内容选中：点击阶段名切换显示，默认「视频合成」 */
const activeStepKey = ref('compose')

/** 重新合成视频（V2.7）：复用现有分镜素材只重跑 compose，替换成片 */
const { recomposing, recomposedTs, trigger } = useRecompose(() => projectId)
/** 成片播放地址：重新合成成功后拼 ?ts= 破除浏览器缓存（路径不变） */
const displayFinalUrl = computed(() => {
  const url = detail.value?.final_video_url
  if (!url) return ''
  return recomposedTs.value ? `${url}?ts=${recomposedTs.value}` : url
})

const scenes = computed(() => detail.value?.scenes || [])
const configItems = computed(() => {
  const d = detail.value
  if (!d) return []
  return [
    { label: '比例', value: d.ratio },
    { label: '分辨率', value: d.resolution },
    { label: '帧率', value: `${d.fps} fps` },
    { label: '风格', value: d.style },
    { label: '音色', value: voiceLabel(d.voice) },
    { label: '目标时长', value: `${d.target_duration}s` },
  ]
})

async function load() {
  loading.value = true
  try {
    detail.value = await projectApi.getProject(projectId)
  } catch {
    toast.show('error', '项目不存在或已删除')
    router.push('/projects')
  } finally {
    loading.value = false
  }
}

/** 拉取本项目状态（写入 localStatus，不污染 store）；进行中时启动 3s 轮询 */
async function loadStatus() {
  try {
    localStatus.value = await projectApi.getProjectStatus(projectId)
    if (localStatus.value?.status === '进行中') {
      if (pollTimer === null) pollTimer = window.setInterval(loadStatus, 3000)
    } else if (pollTimer !== null) {
      window.clearInterval(pollTimer)
      pollTimer = null
    }
  } catch {
    /* 忽略网络错误，保留上次状态 */
  }
}

async function confirmDelete() {
  deleting.value = true
  try {
    const res = await projectApi.deleteProject(projectId)
    toast.show('success', `${res.message}，释放约 ${res.freed_mb} MB`)
    showDelete.value = false
    router.push('/projects')
  } finally {
    deleting.value = false
  }
}

/** 重新合成完成：刷新详情（final_video_url 已更新，视频组件靠 displayFinalUrl 的 ?ts= 破缓存） */
async function refreshAfterRecompose() {
  await load()
  await loadStatus()
}

onMounted(() => {
  load()
  loadStatus()
})

onUnmounted(() => {
  if (pollTimer !== null) window.clearInterval(pollTimer)
})
</script>

<template>
  <div class="space-y-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-text">{{ detail?.name || '项目详情' }}</h2>
        <p v-if="detail" class="text-xs text-text-3">{{ detail.project_id }} · {{ detail.created_at }}</p>
      </div>
      <div v-if="detail" class="flex flex-wrap items-center gap-2">
        <StatusBadge :status="detail.status" />
        <AppButton size="sm" type="secondary" @click="router.push('/projects')">返回</AppButton>
        <AppButton v-if="detail.final_video_url" size="sm" type="secondary">
          <a :href="detail.download_url" class="inline-flex items-center gap-1">⬇ 下载</a>
        </AppButton>
        <!-- V2.4: 删除按钮放宽为「非进行中」状态均显示（等待/完成/失败），便于清理项目；进行中隐藏防止误删正在运行的任务 -->
        <AppButton v-if="detail.status !== '进行中'" size="sm" type="danger" @click="showDelete = true">🗑 删除</AppButton>
      </div>
    </div>

    <AppSkeleton v-if="loading" :rows="8" />

    <template v-else-if="detail">
      <!-- 流程条（点击阶段名切换下方内容，默认「视频合成」） -->
      <AppCard>
        <StepFlow :active-key="activeStepKey" :status="localStatus" :scenes="scenes" :voice-skipped="detail?.voice === 'none'" @select="activeStepKey = $event" />
        <p v-if="detail.error_msg" class="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          失败原因：{{ detail.error_msg }}
        </p>
      </AppCard>

      <!-- ① 剧本创作：分镜文案 -->
      <AppCard v-if="activeStepKey === 'script'">
        <h3 class="mb-4 font-semibold text-text">① 剧本创作 · 分镜文案</h3>
        <div v-if="scenes.length" class="space-y-3">
          <div v-for="s in scenes" :key="s.scene_no" class="rounded-lg border border-border bg-surface-2 p-4">
            <div class="mb-1 flex items-center gap-2">
              <span class="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs text-white">#{{ s.scene_no }}</span>
              <span class="text-xs text-text-3">{{ s.camera }} · 时长 {{ s.duration }}s</span>
            </div>
            <p class="text-sm text-text"><span class="text-text-3">描述：</span>{{ s.description }}</p>
            <p class="mt-1 text-sm text-text"><span class="text-text-3">旁白：</span>{{ s.narration }}</p>
            <p v-if="s.subtitle" class="mt-1 text-sm text-text"><span class="text-text-3">字幕：</span>{{ s.subtitle }}</p>
          </div>
        </div>
        <p v-else class="text-sm text-text-3">暂无文案数据</p>
      </AppCard>

      <!-- ② 文生图：分镜图片 -->
      <AppCard v-else-if="activeStepKey === 'images'">
        <h3 class="mb-4 font-semibold text-text">② 文生图 · 分镜图片</h3>
        <div v-if="scenes.some(s => s.image_url)" class="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          <figure v-for="s in scenes" :key="s.scene_no" class="overflow-hidden rounded-lg border border-border bg-surface-2">
            <img v-if="s.image_url" :src="s.image_url" :alt="`分镜 ${s.scene_no}`" loading="lazy" class="aspect-video w-full object-cover" />
            <figcaption class="px-3 py-2 text-xs text-text-3">#{{ s.scene_no }} {{ s.camera }}</figcaption>
          </figure>
        </div>
        <p v-else class="text-sm text-text-3">暂无图片数据</p>
      </AppCard>

      <!-- ③ 图生视频：分镜视频 -->
      <AppCard v-else-if="activeStepKey === 'videos'">
        <h3 class="mb-4 font-semibold text-text">③ 图生视频 · 分镜视频</h3>
        <div v-if="scenes.some(s => s.video_url)" class="grid gap-3 sm:grid-cols-2">
          <div v-for="s in scenes" :key="s.scene_no" class="overflow-hidden rounded-lg border border-border bg-surface-2">
            <video v-if="s.video_url" :src="s.video_url" controls preload="metadata" class="aspect-video w-full bg-black" />
            <p class="px-3 py-2 text-xs text-text-3">#{{ s.scene_no }} {{ s.camera }} · {{ s.duration }}s</p>
          </div>
        </div>
        <p v-else class="text-sm text-text-3">暂无视频数据</p>
      </AppCard>

      <!-- ④ 语音合成：分镜配音 -->
      <AppCard v-else-if="activeStepKey === 'voice'">
        <h3 class="mb-4 font-semibold text-text">④ 语音合成 · 分镜配音</h3>
        <div v-if="scenes.some(s => s.voice_path)" class="space-y-2">
          <div v-for="s in scenes" :key="s.scene_no" class="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface-2 px-4 py-3">
            <span class="text-xs text-text-3">#{{ s.scene_no }} {{ s.camera }}</span>
            <audio v-if="s.voice_path" :src="s.voice_path" controls preload="none" class="h-9 w-56" />
            <span class="text-xs text-text-3">{{ s.voice_duration ? s.voice_duration.toFixed(1) + 's' : '—' }}</span>
          </div>
        </div>
        <p v-else class="text-sm text-text-3">暂无配音数据</p>
      </AppCard>

      <!-- ⑤ 视频合成（默认显示）：成片 + 配置信息合在此处 -->
      <AppCard v-else>
        <h3 class="mb-4 font-semibold text-text">⑤ 视频合成</h3>

        <!-- 成片播放 -->
        <div v-if="detail.final_video_url">
          <h4 class="mb-2 text-sm font-medium text-text-2">成片</h4>
          <AppVideo :src="displayFinalUrl" />
        </div>
        <p v-else class="text-sm text-text-3">成片尚未生成</p>

        <!-- 配置信息 -->
        <div class="mt-6">
          <h4 class="mb-3 text-sm font-medium text-text-2">配置信息</h4>
          <div class="flex flex-wrap gap-2">
            <span v-for="c in configItems" :key="c.label" class="rounded-full bg-surface-2 px-3 py-1 text-xs text-text-2">
              {{ c.label }}：{{ c.value }}
            </span>
          </div>
        </div>

        <!-- 重新合成视频（V2.7）：复用现有分镜素材只重跑 compose，替换成片 -->
        <div v-if="detail.status === '完成' || detail.status === '失败'" class="mt-6">
          <AppButton :disabled="recomposing" @click="trigger(refreshAfterRecompose)">
            {{ recomposing ? '合成中…' : '🔄 重新合成视频' }}
          </AppButton>
          <p class="mt-2 text-xs text-text-3">使用现有分镜视频/语音/字幕重新合成，替换当前成片。</p>
        </div>
      </AppCard>
    </template>

    <!-- 删除确认 -->
    <AppModal v-if="showDelete" title="删除项目" @close="showDelete = false">
      <p class="text-text">删除后该项目的数据库记录与磁盘文件将<b class="text-danger">不可恢复</b>。</p>
      <p class="mt-2 text-sm text-text-2">将删除 1 个项目，释放约 {{ detail ? '计算中' : '0' }} MB。</p>
      <div class="mt-5 flex justify-end gap-2">
        <AppButton type="secondary" @click="showDelete = false">取消</AppButton>
        <AppButton type="danger" :loading="deleting" @click="confirmDelete">确认删除</AppButton>
      </div>
    </AppModal>
  </div>
</template>

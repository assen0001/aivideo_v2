/** 创作 store：当前表单 / 五步流程 / 3s 轮询 / 最近项目恢复 */
import { defineStore } from 'pinia'
import * as projectApi from '@/api/projects'
import { useToastStore } from '@/stores/toast'
import type { ProjectConfig, ProjectStatus, StepDef } from '@/types'

// V2.4：语音合成前置到文生图之前；progress 权重同步后端 generation.STEP_PROGRESS
export const STEPS: StepDef[] = [
  { key: 'script', label: '剧本创作', progress: 5 },
  { key: 'voice', label: '语音合成', progress: 20 },
  { key: 'images', label: '文生图', progress: 35 },
  { key: 'videos', label: '图生视频', progress: 60 },
  { key: 'compose', label: '视频合成', progress: 85 },
]

const STEP_INDEX: Record<string, number> = { script: 0, voice: 1, images: 2, videos: 3, compose: 4, done: 4 }

export const useProjectStore = defineStore('project', {
  state: () => ({
    configForm: {
      name: '',
      topic: '',
      ratio: '16:9',
      resolution: '普清360P',
      fps: 16,
      style: '写实',
      voice: 'none',
      targetDuration: 30,
    },
    currentProjectId: localStorage.getItem('current_project_id') || '',
    status: null as ProjectStatus | null,
    polling: false,
    pollTimer: null as number | null,
  }),
  getters: {
    isGenerating(): boolean {
      return this.status?.status === '进行中'
    },
    currentStepIndex(): number {
      const step = this.status?.current_step || ''
      return STEP_INDEX[step] ?? -1
    },
    /** 五步状态数组：pending / running / done / failed */
    stepFlow(): { key: string; label: string; state: 'pending' | 'running' | 'done' | 'failed' }[] {
      const status = this.status?.status
      const step = this.status?.current_step || ''
      const idx = STEP_INDEX[step] ?? -1
      return STEPS.map((s, i) => {
        if (status === '完成') return { ...s, state: 'done' as const }
        if (status === '失败') {
          if (i === idx) return { ...s, state: 'failed' as const }
          return { ...s, state: i < idx ? 'done' as const : 'pending' as const }
        }
        if (status === '进行中') {
          if (i === idx) return { ...s, state: 'running' as const }
          return { ...s, state: i < idx ? 'done' as const : 'pending' as const }
        }
        return { ...s, state: 'pending' as const }
      })
    },
  },
  actions: {
    /** 创建并启动生成（name 由后端 LLM 根据 topic 自动生成，前端用 topic 前缀占位） */
    async createAndGenerate() {
      const toast = useToastStore()
      const cfg = this.configForm
      if (!cfg.topic.trim()) {
        toast.show('warning', '请填写视频主题')
        throw new Error('topic required')
      }
      const res = await projectApi.createProject({
        name: cfg.topic.trim().slice(0, 20) || '新作品',
        topic: cfg.topic.trim(),
        config: {
          ratio: cfg.ratio,
          resolution: cfg.resolution,
          fps: Number(cfg.fps),
          style: cfg.style,
          voice: cfg.voice,
          targetDuration: Number(cfg.targetDuration),
        },
      })
      this.currentProjectId = res.project_id
      localStorage.setItem('current_project_id', res.project_id)
      const gen = await projectApi.startGenerate(res.project_id)
      if (gen.status === 'started') {
        this.startPolling(res.project_id)
      }
      return res.project_id
    },
    /** 3s 轮询（页面隐藏暂停） */
    startPolling(projectId: string) {
      this.stopPolling()
      this.currentProjectId = projectId
      localStorage.setItem('current_project_id', projectId)
      this.polling = true
      this.fetchStatus(projectId)
      this.pollTimer = window.setInterval(() => {
        if (!document.hidden) {
          this.fetchStatus(projectId)
        }
      }, 3000)
      document.addEventListener('visibilitychange', this.onVisibility)
    },
    onVisibility() {
      if (!this.currentProjectId) return
      if (!document.hidden && this.polling) {
        this.fetchStatus(this.currentProjectId)
      }
    },
    async fetchStatus(projectId: string) {
      try {
        const res = await projectApi.getProjectStatus(projectId)
        this.status = res
        if (res.status === '完成' || res.status === '失败') {
          this.stopPolling()
        }
      } catch {
        /* 网络错误保留状态 */
      }
    },
    stopPolling() {
      this.polling = false
      if (this.pollTimer) {
        window.clearInterval(this.pollTimer)
        this.pollTimer = null
      }
      document.removeEventListener('visibilitychange', this.onVisibility)
    },
    /** 刷新恢复最近项目 */
    async restoreRecent() {
      if (!this.currentProjectId) return
      try {
        await this.fetchStatus(this.currentProjectId)
      } catch {
        this.currentProjectId = ''
        localStorage.removeItem('current_project_id')
      }
    },
    reset() {
      this.stopPolling()
      this.status = null
      this.currentProjectId = ''
      localStorage.removeItem('current_project_id')
    },
    /** 查看最近项目详情（详情页/项目页使用） */
    projectConfig(): ProjectConfig | null {
      return null
    },
  },
})

/** 配置 store：启动拉取一次，保存后刷新缓存；外部 API 连通性测试轮询 */
import { defineStore } from 'pinia'
import * as settingsApi from '@/api/settings'
import { useToastStore } from '@/stores/toast'
import type { TestStatus } from '@/types'

const POLL_INTERVAL = 2000

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    settings: {} as Record<string, string>,
    sensitiveKeys: [] as string[],
    loaded: false,
  }),
  getters: {
    isSensitive: (state) => (key: string) => state.sensitiveKeys.includes(key),
  },
  actions: {
    async fetchSettings(force = false) {
      if (this.loaded && !force) return this.settings
      const res = await settingsApi.getSettings()
      this.settings = res.settings
      this.sensitiveKeys = res.sensitive_keys || []
      this.loaded = true
      return this.settings
    },
    async saveSettings(values: Record<string, string>) {
      const res = await settingsApi.saveSettings(values)
      // 合并到本地缓存
      this.settings = { ...this.settings, ...values }
      const toast = useToastStore()
      toast.show('success', res.message || '保存成功，已生效')
      return res
    },

    /**
     * 运行外部 API 连通性测试并轮询至结束。
     * 返回最终 TestStatus；轮询期间抛错则返回 error 状态。
     */
    async runTest(vendor: string, formValues: Record<string, string>): Promise<TestStatus> {
      // 只传当前分组相关字段，避免把无关表单值带到后端
      const fieldSets: Record<string, string[]> = {
        llm: ['llm_api_base', 'llm_api_key', 'llm_model'],
        t2i: ['t2i_url', 't2i_token', 't2i_timeout', 't2i_poll_interval'],
        i2v: ['i2v_url', 'i2v_token', 'i2v_timeout', 'i2v_poll_interval'],
        tts: ['tts_base_url', 'tts_username', 'tts_password'],
      }
      const keys = fieldSets[vendor] || []
      const payload: Record<string, string> = {}
      for (const k of keys) {
        const v = (formValues[k] ?? '').trim()
        if (v) payload[k] = v
      }

      const { task_id } = await settingsApi.submitTest(vendor, payload)
      // i2v 首次加载模型可能较久，放宽轮询次数
      const maxTries = vendor === 'i2v' ? 170 : vendor === 't2i' ? 55 : 25
      let last: TestStatus | null = null
      for (let i = 0; i < maxTries; i++) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL))
        last = await settingsApi.pollTest(vendor, task_id)
        if (last.status !== 'running') return last
      }
      return {
        task_id,
        vendor: vendor as TestStatus['vendor'],
        status: 'error',
        stage: 'error',
        elapsed_ms: 0,
        detail: '测试超时，请稍后重试（后端任务可能仍在执行）',
      }
    },
  },
})

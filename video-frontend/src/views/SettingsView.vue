<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useToastStore } from '@/stores/toast'
import SettingsGroup from '@/components/settings/SettingsGroup.vue'
import TestResultModal from '@/components/settings/TestResultModal.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppModal from '@/components/common/AppModal.vue'
import type { TestStatus } from '@/types'

const settingsStore = useSettingsStore()
const toast = useToastStore()

const form = reactive<Record<string, string>>({})
const saving = ref(false)

// 测试状态
const testVendor = ref('')
const testing = ref(false)
const testResult = ref<TestStatus | null>(null)
const showTestModal = ref(false)

function setValue(key: string, value: string) {
  form[key] = value
}

type FieldDef = { key: string; label: string; type: 'text' | 'number' | 'sensitive' }
interface GroupDef {
  title: string
  icon: string
  description: string
  fields: FieldDef[]
  /** 外部 API vendor 标识（提供「测试」按钮） */
  testable?: string
}

const groups: GroupDef[] = [
  {
    title: '大语言模型',
    icon: '🧠',
    description: '剧本与分镜生成使用的 LLM 服务',
    testable: 'llm',
    fields: [
      { key: 'llm_api_base', label: 'API Base', type: 'text' },
      { key: 'llm_api_key', label: 'API Key', type: 'sensitive' },
      { key: 'llm_model', label: '模型名', type: 'text' },
    ],
  },
  {
    title: '文生图',
    icon: '🎨',
    description: 'ComfyUI z-image-turbo 文生图服务',
    testable: 't2i',
    fields: [
      { key: 't2i_url', label: '服务地址', type: 'text' },
      { key: 't2i_token', label: 'Token', type: 'sensitive' },
      { key: 't2i_timeout', label: '超时(秒)', type: 'number' },
      { key: 't2i_poll_interval', label: '轮询间隔(秒)', type: 'number' },
    ],
  },
  {
    title: '图生视频',
    icon: '🎞️',
    description: 'ComfyUI Wan2.2 图生视频服务',
    testable: 'i2v',
    fields: [
      { key: 'i2v_url', label: '服务地址', type: 'text' },
      { key: 'i2v_token', label: 'Token', type: 'sensitive' },
      { key: 'i2v_timeout', label: '超时(秒)', type: 'number' },
      { key: 'i2v_poll_interval', label: '轮询间隔(秒)', type: 'number' },
    ],
  },
  {
    title: '语音合成',
    icon: '🎙️',
    description: 'IndexTTS 配音服务',
    testable: 'tts',
    fields: [
      { key: 'tts_base_url', label: '服务地址', type: 'text' },
      { key: 'tts_username', label: '用户名', type: 'text' },
      { key: 'tts_password', label: '密码', type: 'sensitive' },
    ],
  },
  {
    title: '上传限制',
    icon: '📦',
    description: '资产上传的大小限制与扩展名白名单',
    fields: [
      { key: 'upload_doc_img_limit_mb', label: '文档/图片上限(MB)', type: 'number' },
      { key: 'upload_media_limit_mb', label: '音视频上限(MB)', type: 'number' },
      { key: 'upload_allow_ext', label: '扩展名白名单（逗号分隔）', type: 'text' },
    ],
  },
]

/** vendor → 测试前必须非空的字段 */
const REQUIRED_FIELDS: Record<string, string[]> = {
  llm: ['llm_api_base', 'llm_model'],
  t2i: ['t2i_url'],
  i2v: ['i2v_url'],
  tts: ['tts_base_url'],
}

async function runTest(vendor: string) {
  const missing = (REQUIRED_FIELDS[vendor] || []).filter((k) => !(form[k] ?? '').trim())
  if (missing.length) {
    toast.show('error', `请先填写：${missing.join('、')}`)
    return
  }
  testVendor.value = vendor
  testResult.value = null
  showTestModal.value = true
  testing.value = true
  try {
    testResult.value = await settingsStore.runTest(vendor, { ...form })
  } catch (e) {
    testResult.value = {
      task_id: '',
      vendor: vendor as TestStatus['vendor'],
      status: 'error',
      stage: 'error',
      elapsed_ms: 0,
      detail: (e as Error)?.message || '请求失败',
    }
  } finally {
    testing.value = false
  }
}

function validate(): string {
  const numeric = ['t2i_timeout', 't2i_poll_interval', 'i2v_timeout', 'i2v_poll_interval', 'upload_doc_img_limit_mb', 'upload_media_limit_mb']
  for (const k of numeric) {
    const v = (form[k] ?? '').trim()
    if (v !== '' && (Number.isNaN(Number(v)) || Number(v) <= 0)) {
      return `字段 ${k} 必须为数字且大于 0`
    }
  }
  if (!(form.upload_allow_ext ?? '').trim()) {
    return '扩展名白名单不能为空'
  }
  return ''
}

async function save() {
  const err = validate()
  if (err) {
    toast.show('error', err)
    return
  }
  saving.value = true
  try {
    await settingsStore.saveSettings({ ...form })
  } catch {
    /* toast by interceptor */
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const s = await settingsStore.fetchSettings()
  for (const key of Object.keys(s)) {
    form[key] = s[key] ?? ''
  }
})
</script>

<template>
  <div class="mx-auto max-w-3xl space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-text">系统配置</h2>
        <p class="text-sm text-text-3">修改后立即生效，正在生成中的任务按修改前参数执行</p>
      </div>
      <AppButton :loading="saving" @click="save">保存配置</AppButton>
    </div>

    <SettingsGroup
      v-for="g in groups"
      :key="g.title"
      :title="g.title"
      :icon="g.icon"
      :description="g.description"
      :fields="g.fields"
      :model="form"
      :sensitive-keys="settingsStore.sensitiveKeys"
      :testable="!!g.testable"
      :testing="testing && testVendor === g.testable"
      @update:model="setValue"
      @test="g.testable && runTest(g.testable)"
    />

    <AppModal v-if="showTestModal" title="外部 API 测试" width="max-w-xl" @close="showTestModal = false">
      <TestResultModal
        :vendor="testVendor"
        :result="testResult"
        :running="testing"
        @close="showTestModal = false"
        @retry="runTest(testVendor)"
      />
    </AppModal>
  </div>
</template>

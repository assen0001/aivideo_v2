<script setup lang="ts">
import { ref } from 'vue'
import { useToastStore } from '@/stores/toast'
import * as assetApi from '@/api/assets'
import type { Asset } from '@/types'

const emit = defineEmits<{ (e: 'uploaded', assets: Asset[]): void }>()

const toast = useToastStore()
const dragging = ref(false)
const uploading = ref(false)
const progressText = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

interface FileItem {
  name: string
  size: number
  state: 'pending' | 'success' | 'error'
  reason?: string
}

const queue = ref<FileItem[]>([])

async function handleFiles(files: FileList | File[]) {
  const list = Array.from(files)
  if (!list.length) return
  queue.value = [...list.map((f) => ({ name: f.name, size: f.size, state: 'pending' as const })), ...queue.value.filter((q) => q.state !== 'success')]

  uploading.value = true
  progressText.value = '上传中…'
  try {
    const res = await assetApi.uploadAssets(list)
    if (res.items?.length) {
      queue.value = queue.value.map((q) =>
        res.items.some((it) => it.file_name === q.name) ? { ...q, state: 'success' as const } : q,
      )
      emit('uploaded', res.items)
    }
    for (const f of res.failures || []) {
      queue.value = queue.value.map((q) =>
        q.name === f.file_name ? { ...q, state: 'error' as const, reason: f.reason } : q,
      )
      toast.show('error', `${f.file_name}：${f.reason}`)
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    toast.show('error', err.response?.data?.message || '上传失败')
    queue.value = queue.value.map((q) => ({ ...q, state: 'error' as const, reason: '上传失败' }))
  } finally {
    uploading.value = false
    progressText.value = ''
  }
}

function onDrop(e: DragEvent) {
  dragging.value = false
  if (e.dataTransfer?.files) handleFiles(e.dataTransfer.files)
}

function onPick(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) handleFiles(input.files)
  input.value = ''
}
</script>

<template>
  <div>
    <div
      class="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors"
      :class="dragging ? 'border-accent bg-accent/5' : 'border-border bg-surface-2/50 hover:border-primary'"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
      @click="fileInput?.click()"
    >
      <span class="text-3xl">📁</span>
      <p class="text-sm text-text-2">拖拽文件到此处，或点击选择文件（可多选）</p>
      <p class="text-xs text-text-3">大小与扩展名白名单由系统配置决定</p>
      <input ref="fileInput" type="file" multiple class="hidden" @change="onPick" />
    </div>

    <div v-if="queue.length" class="mt-3 space-y-2">
      <div v-for="(q, i) in queue" :key="i" class="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
        <span class="min-w-0 flex-1 truncate text-text">{{ q.name }}</span>
        <span v-if="q.state === 'success'" class="text-success">✓ 已上传</span>
        <span v-else-if="q.state === 'error'" class="text-danger">{{ q.reason || '失败' }}</span>
        <span v-else class="text-text-3">等待</span>
      </div>
      <p v-if="uploading" class="text-xs text-text-3">{{ progressText }}</p>
    </div>
  </div>
</template>

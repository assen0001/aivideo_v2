<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as assetApi from '@/api/assets'
import { useSettingsStore } from '@/stores/settings'
import { useToastStore } from '@/stores/toast'
import UploadDropzone from '@/components/assets/UploadDropzone.vue'
import AssetCard from '@/components/assets/AssetCard.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppModal from '@/components/common/AppModal.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import Pagination from '@/components/common/Pagination.vue'
import { formatSize } from '@/utils/format'
import type { Asset } from '@/types'

const settingsStore = useSettingsStore()
const toast = useToastStore()

const items = ref<Asset[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const hasMore = ref(false)
const type = ref('全部')
const keyword = ref('')
const loading = ref(false)

const renameTarget = ref<Asset | null>(null)
const renameName = ref('')
const deleteTarget = ref<Asset | null>(null)
const deleting = ref(false)

const types = ['全部', '文档', '图片', '音视频']

async function load() {
  loading.value = true
  try {
    const res = await assetApi.listAssets({ type: type.value, keyword: keyword.value, page: page.value, page_size: pageSize })
    items.value = res.items
    total.value = res.total
    hasMore.value = res.has_more
  } finally {
    loading.value = false
  }
}

function changeType(t: string) {
  type.value = t
  page.value = 1
  load()
}

function search() {
  page.value = 1
  load()
}

function onUploaded() {
  page.value = 1
  load()
}

function openRename(a: Asset) {
  renameTarget.value = a
  renameName.value = a.file_name
}

async function submitRename() {
  if (!renameTarget.value) return
  const name = renameName.value.trim()
  if (!name) {
    toast.show('warning', '文件名不能为空')
    return
  }
  try {
    await assetApi.renameAsset(renameTarget.value.id, name)
    toast.show('success', '已重命名')
    renameTarget.value = null
    load()
  } catch {
    /* toast by interceptor */
  }
}

function openDelete(a: Asset) {
  deleteTarget.value = a
}

async function submitDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    const res = await assetApi.deleteAsset(deleteTarget.value.id)
    toast.show('success', `${res.message}，释放约 ${res.freed_mb} MB`)
    deleteTarget.value = null
    load()
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  settingsStore.fetchSettings().catch(() => {})
  load()
})
</script>

<template>
  <div class="space-y-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-lg font-semibold text-text">资产库</h2>
      <p class="text-xs text-text-3">
        文档/图片 ≤ {{ settingsStore.settings.upload_doc_img_limit_mb || 10 }}MB · 音视频 ≤ {{ settingsStore.settings.upload_media_limit_mb || 30 }}MB
      </p>
    </div>

    <UploadDropzone @uploaded="onUploaded" />

    <!-- 类型 Tab + 搜索 -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="flex rounded-full bg-surface-2 p-1 text-sm">
        <button
          v-for="t in types"
          :key="t"
          class="rounded-full px-4 py-1.5 transition-colors"
          :class="type === t ? 'bg-surface font-medium text-primary shadow-sm' : 'text-text-2'"
          @click="changeType(t)"
        >
          {{ t }}
        </button>
      </div>
      <div class="flex min-w-0 flex-1 items-center gap-2 sm:max-w-md">
        <input
          v-model="keyword"
          class="min-w-0 flex-1 rounded-full border border-border bg-surface px-4 py-2 text-sm outline-none focus:border-accent"
          placeholder="搜索文件名"
          @keyup.enter="search"
        />
        <AppButton type="secondary" size="sm" class="shrink-0 whitespace-nowrap px-4" @click="search">搜索</AppButton>
      </div>
    </div>

    <!-- 列表 -->
    <div v-if="loading" class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
      <div v-for="i in 8" :key="i" class="skeleton aspect-video rounded-lg" />
    </div>

    <div v-else-if="items.length" class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
      <AssetCard v-for="a in items" :key="a.id" :asset="a" @rename="openRename" @delete="openDelete" />
    </div>

    <EmptyState v-else title="还没有资产" description="拖拽或点击上传你的素材文件" />

    <Pagination v-if="total > pageSize" :page="page" :page-size="pageSize" :total="total" @change="(p) => { page = p; load() }" />

    <!-- 重命名弹窗 -->
    <AppModal v-if="renameTarget" title="重命名" @close="renameTarget = null">
      <div class="space-y-3">
        <p class="text-xs text-text-3">仅可修改文件名，扩展名不可变更</p>
        <input v-model="renameName" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" @keyup.enter="submitRename" />
        <div class="flex justify-end gap-2">
          <AppButton type="secondary" @click="renameTarget = null">取消</AppButton>
          <AppButton @click="submitRename">保存</AppButton>
        </div>
      </div>
    </AppModal>

    <!-- 删除确认 -->
    <AppModal v-if="deleteTarget" title="删除资产" @close="deleteTarget = null">
      <p class="text-text">确定删除「{{ deleteTarget.file_name }}」？</p>
      <p class="mt-2 text-sm text-text-2">
        大小 {{ formatSize(deleteTarget.file_size) }}，删除后不可恢复。
      </p>
      <div class="mt-5 flex justify-end gap-2">
        <AppButton type="secondary" @click="deleteTarget = null">取消</AppButton>
        <AppButton type="danger" :loading="deleting" @click="submitDelete">确认删除</AppButton>
      </div>
    </AppModal>
  </div>
</template>

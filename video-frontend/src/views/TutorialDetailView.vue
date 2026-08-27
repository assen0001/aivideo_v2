<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as tutorialApi from '@/api/tutorials'
import { useToastStore } from '@/stores/toast'
import MarkdownView from '@/components/tutorials/MarkdownView.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppSkeleton from '@/components/common/AppSkeleton.vue'
import { formatTimeFull } from '@/utils/format'
import type { Tutorial } from '@/types'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const id = Number(route.params.id)
const tutorial = ref<Tutorial | null>(null)
const loading = ref(true)
const showDelete = ref(false)

async function load() {
  loading.value = true
  try {
    tutorial.value = await tutorialApi.getTutorial(id)
  } catch {
    toast.show('error', '教程不存在')
    router.push('/tutorials')
  } finally {
    loading.value = false
  }
}

function goEdit() {
  router.push({ path: '/tutorials/edit', query: { id: String(id) } })
}

async function confirmDelete() {
  await tutorialApi.deleteTutorial(id)
  toast.show('success', '已删除')
  showDelete.value = false
  router.push('/tutorials')
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <AppSkeleton v-if="loading" :rows="10" />

    <template v-else-if="tutorial">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 class="font-brand text-2xl font-bold text-text">{{ tutorial.title }}</h1>
          <p class="mt-1 text-xs text-text-3">
            {{ tutorial.tags || '未分类' }} · {{ formatTimeFull(tutorial.created_at) }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <AppButton size="sm" type="secondary" @click="router.push('/tutorials')">返回</AppButton>
          <AppButton size="sm" type="secondary" @click="goEdit">编辑</AppButton>
          <AppButton size="sm" type="danger" @click="showDelete = true">删除</AppButton>
        </div>
      </div>

      <!-- 内容区：占满主区全宽，方便一行显示更多文本 -->
      <div class="w-full rounded-lg border border-border bg-surface p-6 shadow-sm">
        <MarkdownView :content="tutorial.content || ''" />
      </div>
    </template>

    <AppModal v-if="showDelete" title="删除教程" @close="showDelete = false">
      <p class="text-text">确定删除「{{ tutorial?.title }}」？此操作不可恢复。</p>
      <div class="mt-5 flex justify-end gap-2">
        <AppButton type="secondary" @click="showDelete = false">取消</AppButton>
        <AppButton type="danger" @click="confirmDelete">确认删除</AppButton>
      </div>
    </AppModal>
  </div>
</template>

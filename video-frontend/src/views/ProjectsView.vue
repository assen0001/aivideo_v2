<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as projectApi from '@/api/projects'
import ProjectCard from '@/components/project/ProjectCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppSkeleton from '@/components/common/AppSkeleton.vue'
import type { Project } from '@/types'

const router = useRouter()

const items = ref<Project[]>([])
const total = ref(0)
const page = ref(1)
const hasMore = ref(false)
const loading = ref(false)
const loadingMore = ref(false)
const status = ref('')
const keyword = ref('')
const keywordInput = ref('')

const statusOptions = [
  { label: '全部', value: '' },
  { label: '等待', value: '等待' },
  { label: '进行中', value: '进行中' },
  { label: '完成', value: '完成' },
  { label: '失败', value: '失败' },
]

async function load(reset = false) {
  if (reset) {
    page.value = 1
    items.value = []
  }
  loading.value = reset
  loadingMore.value = !reset
  try {
    const res = await projectApi.listProjects({
      page: page.value,
      page_size: 12,
      status: status.value,
      keyword: keyword.value,
    })
    items.value = reset ? res.items : [...items.value, ...res.items]
    total.value = res.total
    hasMore.value = res.has_more
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function search() {
  keyword.value = keywordInput.value.trim()
  load(true)
}

function changeStatus(v: string) {
  status.value = v
  load(true)
}

function onScroll() {
  const el = document.documentElement
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 200 && hasMore.value && !loadingMore.value) {
    page.value += 1
    load()
  }
}

onMounted(() => {
  load(true)
  window.addEventListener('scroll', onScroll)
})
</script>

<template>
  <div class="space-y-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-lg font-semibold text-text">项目列表</h2>
      <AppButton size="sm" @click="router.push('/create')">+ 新建创作</AppButton>
    </div>

    <!-- 筛选 -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="flex rounded-full bg-surface-2 p-1 text-sm">
        <button
          v-for="opt in statusOptions"
          :key="opt.value"
          class="rounded-full px-4 py-1.5 transition-colors"
          :class="status === opt.value ? 'bg-surface font-medium text-primary shadow-sm' : 'text-text-2'"
          @click="changeStatus(opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
      <div class="flex min-w-0 flex-1 items-center gap-2 sm:max-w-md">
        <input
          v-model="keywordInput"
          class="min-w-0 flex-1 rounded-full border border-border bg-surface px-4 py-2 text-sm outline-none focus:border-accent"
          placeholder="搜索项目名称 / 主题"
          @keyup.enter="search"
        />
        <AppButton type="secondary" size="sm" class="shrink-0 whitespace-nowrap px-4" @click="search">搜索</AppButton>
      </div>
    </div>

    <!-- 列表 -->
    <div v-if="loading" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <AppSkeleton v-for="i in 6" :key="i" :rows="4" />
    </div>

    <div v-else-if="items.length" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <ProjectCard v-for="p in items" :key="p.project_id" :project="p" />
    </div>

    <EmptyState v-else title="还没有项目" description="去创作页开始你的第一个 AI 视频吧">
      <AppButton @click="router.push('/create')">去创作</AppButton>
    </EmptyState>

    <p v-if="loadingMore" class="py-4 text-center text-sm text-text-3">加载中…</p>
    <p v-else-if="!hasMore && items.length" class="py-4 text-center text-sm text-text-3">已加载全部 {{ total }} 个项目</p>
  </div>
</template>

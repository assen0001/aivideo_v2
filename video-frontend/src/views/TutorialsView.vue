<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as tutorialApi from '@/api/tutorials'
import TutorialCard from '@/components/tutorials/TutorialCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import type { Tutorial } from '@/types'

const router = useRouter()
const items = ref<Tutorial[]>([])
const loading = ref(true)
const activeTag = ref('')

const tags = computed(() => {
  const set = new Set<string>()
  items.value.forEach((t) => (t.tags || '').split(/[,，\s]+/).filter(Boolean).forEach((x) => set.add(x)))
  return Array.from(set)
})

const filtered = computed(() => {
  if (!activeTag.value) return items.value
  return items.value.filter((t) => (t.tags || '').includes(activeTag.value))
})

async function load() {
  loading.value = true
  try {
    items.value = await tutorialApi.listTutorials()
  } finally {
    loading.value = false
  }
}

function goEdit() {
  router.push('/tutorials/edit')
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-lg font-semibold text-text">教程</h2>
      <AppButton size="sm" @click="goEdit">＋ 发布教程</AppButton>
    </div>

    <!-- 标签筛选 -->
    <div v-if="tags.length" class="flex flex-wrap gap-2">
      <button
        class="rounded-full px-3 py-1 text-sm transition-colors"
        :class="activeTag === '' ? 'bg-accent text-white' : 'bg-surface-2 text-text-2 hover:bg-border'"
        @click="activeTag = ''"
      >
        全部
      </button>
      <button
        v-for="tag in tags"
        :key="tag"
        class="rounded-full px-3 py-1 text-sm transition-colors"
        :class="activeTag === tag ? 'bg-accent text-white' : 'bg-surface-2 text-text-2 hover:bg-border'"
        @click="activeTag = tag"
      >
        {{ tag }}
      </button>
    </div>

    <div v-if="loading" class="space-y-4">
      <div v-for="i in 4" :key="i" class="skeleton h-20 rounded-lg" />
    </div>

    <div v-else-if="filtered.length" class="mt-2">
      <TutorialCard v-for="(t, i) in filtered" :key="t.id" :tutorial="t" :last="i === filtered.length - 1" />
    </div>

    <EmptyState v-else title="暂无教程" description="点击右上角发布第一篇教程" />
  </div>
</template>

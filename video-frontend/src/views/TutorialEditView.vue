<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as tutorialApi from '@/api/tutorials'
import { useToastStore } from '@/stores/toast'
import MarkdownEditor from '@/components/tutorials/MarkdownEditor.vue'
import AppButton from '@/components/common/AppButton.vue'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const editId = route.query.id ? Number(route.query.id) : null
const saving = ref(false)
const form = ref({ title: '', summary: '', tags: '', cover: '', content: '' })

async function load() {
  if (!editId) return
  try {
    const t = await tutorialApi.getTutorial(editId)
    form.value = {
      title: t.title,
      summary: t.summary,
      tags: t.tags,
      cover: t.cover,
      content: t.content || '',
    }
  } catch {
    toast.show('error', '教程不存在')
    router.push('/tutorials')
  }
}

async function save() {
  if (!form.value.title.trim()) {
    toast.show('warning', '标题不能为空')
    return
  }
  saving.value = true
  try {
    const payload = {
      title: form.value.title.trim(),
      summary: form.value.summary.trim(),
      tags: form.value.tags.trim(),
      cover: form.value.cover.trim(),
      content: form.value.content,
    }
    if (editId) {
      await tutorialApi.updateTutorial(editId, payload)
      toast.show('success', '已保存')
    } else {
      await tutorialApi.createTutorial(payload)
      toast.show('success', '发布成功')
    }
    router.push('/tutorials')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="w-full space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-text">{{ editId ? '编辑教程' : '发布教程' }}</h2>
      <div class="flex gap-2">
        <AppButton type="secondary" @click="router.push('/tutorials')">取消</AppButton>
        <AppButton :loading="saving" @click="save">{{ editId ? '保存' : '发布' }}</AppButton>
      </div>
    </div>

    <div class="grid gap-4 sm:grid-cols-2">
      <div>
        <label class="mb-1 block text-sm text-text-2">标题 *</label>
        <input v-model="form.title" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" placeholder="教程标题" />
      </div>
      <div>
        <label class="mb-1 block text-sm text-text-2">标签（逗号分隔）</label>
        <input v-model="form.tags" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" placeholder="如：项目文档, 教程" />
      </div>
      <div class="sm:col-span-2">
        <label class="mb-1 block text-sm text-text-2">摘要</label>
        <input v-model="form.summary" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" placeholder="一句话摘要" />
      </div>
      <div class="sm:col-span-2">
        <label class="mb-1 block text-sm text-text-2">封面地址（可选）</label>
        <input v-model="form.cover" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" placeholder="https://…" />
      </div>
    </div>

    <div>
      <label class="mb-1 block text-sm text-text-2">正文（Markdown）</label>
      <MarkdownEditor v-model="form.content" />
    </div>
  </div>
</template>

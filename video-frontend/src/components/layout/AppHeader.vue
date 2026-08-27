<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

defineProps<{
  collapsed: boolean
}>()

const emit = defineEmits<{ (e: 'toggle'): void; (e: 'open-mobile'): void }>()
const route = useRoute()

const title = computed(() => (route.meta.title as string) || '')
</script>

<template>
  <header class="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-bg/80 px-4 backdrop-blur sm:px-6">
    <button
      class="hidden h-9 w-9 items-center justify-center rounded-full text-text-2 hover:bg-surface-2 lg:flex"
      aria-label="折叠侧栏"
      @click="emit('toggle')"
    >
      {{ collapsed ? '»' : '«' }}
    </button>
    <button
      class="flex h-9 w-9 items-center justify-center rounded-full text-text-2 hover:bg-surface-2 lg:hidden"
      aria-label="打开菜单"
      @click="emit('open-mobile')"
    >
      ☰
    </button>
    <div class="text-sm text-text-3">
      <span class="text-text-2">工作台</span>
      <span v-if="title" class="mx-1.5">/</span>
      <span class="font-medium text-text">{{ title }}</span>
    </div>
  </header>
</template>

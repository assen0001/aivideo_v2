<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

withDefaults(defineProps<{
  title?: string
  width?: string
}>(), {
  title: '',
  width: 'max-w-lg',
})

const emit = defineEmits<{ (e: 'close'): void }>()

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/40" @click="emit('close')" />
      <div
        class="relative w-full rounded-lg bg-surface p-6 shadow-lg"
        :class="width"
        role="dialog"
        aria-modal="true"
      >
        <div v-if="title" class="mb-4 flex items-center justify-between">
          <h3 class="text-lg font-semibold text-text">{{ title }}</h3>
          <button class="text-text-3 hover:text-text" aria-label="关闭" @click="emit('close')">✕</button>
        </div>
        <slot />
      </div>
    </div>
  </Teleport>
</template>

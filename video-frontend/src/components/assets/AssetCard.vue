<script setup lang="ts">
import { computed } from 'vue'
import { formatSize, formatTime } from '@/utils/format'
import type { Asset } from '@/types'

const props = defineProps<{
  asset: Asset
}>()

const emit = defineEmits<{ (e: 'rename', asset: Asset): void; (e: 'delete', asset: Asset): void }>()

const typeCls: Record<string, string> = {
  文档: 'bg-orange-100 text-orange-700',
  图片: 'bg-amber-100 text-amber-700',
  音视频: 'bg-cyan-100 text-cyan-700',
  其他: 'bg-surface-2 text-text-2',
}

const isImage = computed(() => props.asset.file_type === '图片')
const isMedia = computed(() => props.asset.file_type === '音视频')
</script>

<template>
  <div class="overflow-hidden rounded-lg border border-border bg-surface shadow-sm transition-all hover:shadow-md">
    <div class="relative aspect-video bg-surface-2">
      <img v-if="isImage && asset.url" :src="asset.url" :alt="asset.file_name" loading="lazy" class="h-full w-full object-cover" />
      <video v-else-if="isMedia && asset.url" :src="asset.url" preload="metadata" class="h-full w-full object-cover" />
      <div v-else class="flex h-full items-center justify-center text-3xl text-text-3">📄</div>
      <span class="absolute left-2 top-2 rounded-full px-2 py-0.5 text-xs font-medium" :class="typeCls[asset.file_type] || typeCls['其他']">
        {{ asset.file_type }}
      </span>
    </div>
    <div class="p-3">
      <p class="truncate text-sm font-medium text-text" :title="asset.file_name">{{ asset.file_name }}</p>
      <p class="mt-0.5 text-xs text-text-3">{{ formatSize(asset.file_size) }} · {{ formatTime(asset.created_at) }}</p>
      <div class="mt-3 flex items-center gap-2 text-xs">
        <a v-if="asset.url" :href="asset.url" target="_blank" rel="noopener" class="rounded-full bg-surface-2 px-3 py-1 text-primary hover:bg-border">打开</a>
        <button class="rounded-full bg-surface-2 px-3 py-1 text-text-2 hover:bg-border" @click="emit('rename', asset)">重命名</button>
        <button class="ml-auto rounded-full bg-red-50 px-3 py-1 text-danger hover:bg-red-100" @click="emit('delete', asset)">删除</button>
      </div>
    </div>
  </div>
</template>

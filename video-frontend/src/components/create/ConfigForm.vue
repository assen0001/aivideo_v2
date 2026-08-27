<script setup lang="ts">
import { useProjectStore } from '@/stores/project'
import { VOICES } from '@/constants/voice'

const store = useProjectStore()

const ratios = ['16:9', '9:16', '1:1']
// V2.4：分辨率只选等级，横屏/竖屏由后端按画面比例自动决定
const resolutions = ['普清360P', '高清720P', '超清1080P']
const fpsList = [16, 24, 30]
const styles = ['写实', '动画', '动漫', '3D', '赛博朋克', '水墨风', '像素风', '油画风']
// V2.5：配音音色来自 @/constants/voice（value=文件名，8 项含无配音），默认无配音 → 跳过语音合成
const voices = VOICES
// 视频时长：3 秒 ~ 3 分钟（180 秒），间隔 1 秒
const DURATION_MIN = 3
const DURATION_MAX = 180

function fmtDuration(s: number): string {
  if (s >= 60) {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return sec ? `${m} 分 ${sec} 秒` : `${m} 分钟`
  }
  return `${s} 秒`
}
</script>

<template>
  <div class="grid gap-5 sm:grid-cols-2">
    <div class="sm:col-span-2">
      <label class="mb-1 block text-sm font-medium text-text-2">视频主题</label>
      <textarea v-model="store.configForm.topic" rows="3" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent" placeholder="描述你想创作的内容主题，AI 将据此生成剧本" />
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium text-text-2">画面比例</label>
      <select v-model="store.configForm.ratio" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent">
        <option v-for="r in ratios" :key="r" :value="r">{{ r }}</option>
      </select>
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium text-text-2">分辨率</label>
      <select v-model="store.configForm.resolution" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent">
        <option v-for="r in resolutions" :key="r" :value="r">{{ r }}</option>
      </select>
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium text-text-2">帧率</label>
      <select v-model="store.configForm.fps" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent">
        <option v-for="f in fpsList" :key="f" :value="f">{{ f }} fps</option>
      </select>
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium text-text-2">画面风格</label>
      <select v-model="store.configForm.style" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent">
        <option v-for="s in styles" :key="s" :value="s">{{ s }}</option>
      </select>
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium text-text-2">配音音色</label>
      <select v-model="store.configForm.voice" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent">
        <option v-for="v in voices" :key="v.value" :value="v.value">{{ v.label }}</option>
      </select>
    </div>
    <div class="sm:col-span-2">
      <label class="mb-1 flex items-center justify-between text-sm font-medium text-text-2">
        <span>视频时长</span>
        <span class="font-semibold text-primary">{{ fmtDuration(store.configForm.targetDuration) }}</span>
      </label>
      <input
        v-model.number="store.configForm.targetDuration"
        type="range"
        :min="DURATION_MIN"
        :max="DURATION_MAX"
        step="1"
        class="w-full accent-accent"
      />
      <div class="mt-1 flex justify-between text-xs text-text-3">
        <span>3 秒</span>
        <span>3 分钟</span>
      </div>
    </div>
  </div>
</template>

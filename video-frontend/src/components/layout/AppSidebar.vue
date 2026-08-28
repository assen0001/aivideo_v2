<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import UserMenu from './UserMenu.vue'

const props = defineProps<{
  collapsed: boolean
  mobileOpen: boolean
}>()

const emit = defineEmits<{ (e: 'toggle'): void; (e: 'close-mobile'): void }>()
const route = useRoute()

const navs = [
  { path: '/create', label: '创作', icon: '✦' },
  { path: '/projects', label: '项目', icon: '▦' },
  { path: '/assets-list', label: '资产', icon: '◫' },
  { path: '/tutorials', label: '教程', icon: '☰' },
  { path: '/settings', label: '配置', icon: '⚙' },
]

const activePath = computed(() => {
  const p = route.path
  if (p.startsWith('/projects')) return '/projects'
  if (p.startsWith('/tutorials')) return '/tutorials'
  return p
})

const systemState = ref('检测中')

async function checkSystem() {
  try {
    const res = await fetch('/api/system/status')
    const j = await res.json()
    systemState.value = j.status === 'ok' ? '服务正常' : '服务异常'
  } catch {
    systemState.value = '离线'
  }
}

let systemTimer = 0

onMounted(() => {
  checkSystem()
  systemTimer = window.setInterval(checkSystem, 60000)
})

onUnmounted(() => {
  window.clearInterval(systemTimer)
})
</script>

<template>
  <aside
    class="fixed inset-y-0 left-0 z-40 flex-col border-r border-border bg-surface transition-all duration-200 lg:static lg:flex"
    :class="[collapsed ? 'w-[72px]' : 'w-[240px]', mobileOpen ? 'flex' : 'hidden']"
  >
    <div class="flex h-16 items-center gap-3 border-b border-border px-4">
      <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-lg text-white shadow-sm">🎬</div>
      <div v-if="!collapsed" class="min-w-0">
        <p class="truncate font-brand text-base font-bold text-text">视频智造平台</p>
        <p class="truncate text-xs text-text-3">aivideo.site</p>
      </div>
    </div>

    <nav class="flex-1 space-y-1 px-3 py-4">
      <RouterLink
        v-for="n in navs"
        :key="n.path"
        :to="n.path"
        class="flex items-center gap-3 rounded-full px-4 py-2.5 text-sm transition-all"
        :class="activePath === n.path ? 'bg-surface-2 font-medium text-primary shadow-sm' : 'text-text-2 hover:bg-surface-2'"
        @click="emit('close-mobile')"
      >
        <span class="w-5 text-center" :class="activePath === n.path ? 'text-accent' : ''">{{ n.icon }}</span>
        <span v-if="!collapsed">{{ n.label }}</span>
        <span
          v-if="activePath === n.path"
          class="ml-auto h-1.5 w-1.5 rounded-full bg-accent"
          :class="{ 'breathe': false }"
        />
      </RouterLink>
    </nav>

    <div class="border-t border-border px-4 py-3">
      <div v-if="!collapsed" class="mb-3 flex items-center gap-2 text-xs text-text-3">
        <span class="h-1.5 w-1.5 rounded-full" :class="systemState === '服务正常' ? 'bg-success' : 'bg-warning'" />
        系统状态：{{ systemState }}
      </div>
      <UserMenu :collapsed="collapsed" />
    </div>
  </aside>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import AppToast from '@/components/common/AppToast.vue'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'

const auth = useAuthStore()
const settings = useSettingsStore()

onMounted(() => {
  // 应用启动：拉取一次配置缓存（设计 §8 性能要求）
  if (auth.token) {
    settings.fetchSettings().catch(() => {})
  }
})
</script>

<template>
  <RouterView />
  <AppToast />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'

const collapsed = ref(false)
const mobileOpen = ref(false)
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <!-- 移动端遮罩 -->
    <div
      v-if="mobileOpen"
      class="fixed inset-0 z-30 bg-black/30 lg:hidden"
      @click="mobileOpen = false"
    />
    <AppSidebar :collapsed="collapsed" :mobile-open="mobileOpen" @toggle="collapsed = !collapsed" @close-mobile="mobileOpen = false" />
    <!-- 右侧主区独立滚动（侧栏按窗口高度独立显示） -->
    <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
      <AppHeader :collapsed="collapsed" @toggle="collapsed = !collapsed" @open-mobile="mobileOpen = true" />
      <main class="mx-auto w-full max-w-[1280px] flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>

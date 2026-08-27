<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

defineProps<{
  collapsed: boolean
}>()

const auth = useAuthStore()
const router = useRouter()
const toast = useToastStore()

const open = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const showProfile = ref(false)
const showPassword = ref(false)
const showLogout = ref(false)

const profileForm = ref({ nickname: '', avatar: '', email: '' })
const pwdForm = ref({ old_password: '', new_password: '', confirm: '' })

// 点击外部区域空白处时关闭弹出小窗口
function handleDocumentClick(e: MouseEvent) {
  if (!open.value) return
  const target = e.target as Node | null
  if (menuRef.value && target && !menuRef.value.contains(target)) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('click', handleDocumentClick)
})

function openProfile() {
  profileForm.value = {
    nickname: auth.user?.nickname || '',
    avatar: auth.user?.avatar || '',
    email: auth.user?.email || '',
  }
  open.value = false
  showProfile.value = true
}

async function saveProfile() {
  await auth.updateMe(profileForm.value)
  toast.show('success', '资料已更新')
  showProfile.value = false
}

async function savePassword() {
  if (pwdForm.value.new_password !== pwdForm.value.confirm) {
    toast.show('error', '两次输入的密码不一致')
    return
  }
  await auth.changePassword(pwdForm.value.old_password, pwdForm.value.new_password, pwdForm.value.confirm)
}

function confirmLogout() {
  showLogout.value = false
  auth.logout()
}
</script>

<template>
  <div ref="menuRef" class="relative">
    <button
      class="flex w-full items-center gap-2.5 rounded-full p-1.5 text-left hover:bg-surface-2"
      :title="auth.user?.username || '用户'"
      @click="open = !open"
    >
      <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-white">
        {{ (auth.user?.nickname || auth.user?.username || 'U').slice(0, 1) }}
      </span>
      <span v-if="!collapsed" class="min-w-0">
        <span class="block truncate text-sm font-medium text-text">{{ auth.user?.nickname || auth.user?.username }}</span>
        <span class="block text-xs text-text-3">管理员</span>
      </span>
    </button>

    <Transition name="menu">
      <div v-if="open" class="absolute bottom-full left-0 z-50 mb-2 w-52 overflow-hidden rounded-lg bg-surface shadow-md border border-border">
        <button class="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-text hover:bg-surface-2" @click="openProfile">👤 用户资料</button>
        <button class="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-text hover:bg-surface-2" @click="showPassword = true; open = false">🔒 修改密码</button>
        <a class="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-text hover:bg-surface-2" href="https://aivideo.site" target="_blank" rel="noopener">🌐 进入官网</a>
        <button class="flex w-full items-center gap-2 border-t border-border px-4 py-2.5 text-sm text-danger hover:bg-red-50" @click="showLogout = true; open = false">⏻ 退出登录</button>
      </div>
    </Transition>

    <!-- 资料弹窗 -->
    <div v-if="showProfile">
      <Teleport to="body">
        <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/40" @click="showProfile = false" />
          <div class="relative w-full max-w-md rounded-lg bg-surface p-6 shadow-lg">
            <h3 class="mb-4 text-lg font-semibold">用户资料</h3>
            <div class="space-y-3">
              <div>
                <label class="mb-1 block text-sm text-text-2">昵称</label>
                <input v-model="profileForm.nickname" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" />
              </div>
              <div>
                <label class="mb-1 block text-sm text-text-2">头像地址（可选）</label>
                <input v-model="profileForm.avatar" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" />
              </div>
              <div>
                <label class="mb-1 block text-sm text-text-2">邮箱</label>
                <input v-model="profileForm.email" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" />
              </div>
              <div class="flex justify-end gap-2 pt-2">
                <button class="rounded-full border border-border px-4 py-2 text-sm text-text-2 hover:bg-surface-2" @click="showProfile = false">取消</button>
                <button class="rounded-full bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover" @click="saveProfile">保存</button>
              </div>
            </div>
          </div>
        </div>
      </Teleport>
    </div>

    <!-- 改密弹窗 -->
    <div v-if="showPassword">
      <Teleport to="body">
        <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/40" @click="showPassword = false" />
          <div class="relative w-full max-w-md rounded-lg bg-surface p-6 shadow-lg">
            <h3 class="mb-4 text-lg font-semibold">修改密码</h3>
            <div class="space-y-3">
              <div>
                <label class="mb-1 block text-sm text-text-2">原密码</label>
                <input v-model="pwdForm.old_password" type="password" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" />
              </div>
              <div>
                <label class="mb-1 block text-sm text-text-2">新密码</label>
                <input v-model="pwdForm.new_password" type="password" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" />
              </div>
              <div>
                <label class="mb-1 block text-sm text-text-2">确认新密码</label>
                <input v-model="pwdForm.confirm" type="password" class="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-accent" />
              </div>
              <div class="flex justify-end gap-2 pt-2">
                <button class="rounded-full border border-border px-4 py-2 text-sm text-text-2 hover:bg-surface-2" @click="showPassword = false">取消</button>
                <button class="rounded-full bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover" @click="savePassword">修改</button>
              </div>
            </div>
          </div>
        </div>
      </Teleport>
    </div>

    <!-- 退出确认 -->
    <div v-if="showLogout">
      <Teleport to="body">
        <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/40" @click="showLogout = false" />
          <div class="relative w-full max-w-sm rounded-lg bg-surface p-6 shadow-lg text-center">
            <p class="mb-5 text-text">确定要退出登录吗？</p>
            <div class="flex justify-center gap-3">
              <button class="rounded-full border border-border px-5 py-2 text-sm text-text-2 hover:bg-surface-2" @click="showLogout = false">取消</button>
              <button class="rounded-full bg-danger px-5 py-2 text-sm text-white" @click="confirmLogout">退出</button>
            </div>
          </div>
        </div>
      </Teleport>
    </div>
  </div>
</template>

<style scoped>
.menu-enter-active,
.menu-leave-active {
  transition: all 0.15s ease;
}
.menu-enter-from,
.menu-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>

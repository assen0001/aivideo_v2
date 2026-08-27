<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import * as authApi from '@/api/auth'

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

type Mode = 'init' | 'login' | 'reset'

const mode = ref<Mode>('login')
const loading = ref(false)
const inlineError = ref('')

const form = ref({ username: '', password: '', confirm: '', new_password: '', code: '' })
const captcha = ref({ id: '', svg: '' })

const isInit = computed(() => mode.value === 'init')
const isLogin = computed(() => mode.value === 'login')
const isReset = computed(() => mode.value === 'reset')

async function refreshCaptcha() {
  try {
    const res = await authApi.getCaptcha()
    captcha.value = { id: res.captcha_id, svg: res.svg }
  } catch {
    /* ignore */
  }
}

async function onMountedInit() {
  const need = await auth.init()
  mode.value = need ? 'init' : 'login'
  if (!need) refreshCaptcha()
}

onMounted(onMountedInit)

function switchMode(m: Mode) {
  mode.value = m
  inlineError.value = ''
  if (m === 'login') refreshCaptcha()
}

async function submitInit() {
  inlineError.value = ''
  if (form.value.password !== form.value.confirm) {
    inlineError.value = '两次输入的密码不一致'
    return
  }
  if (form.value.password.length < 6) {
    inlineError.value = '密码长度不能少于 6 位'
    return
  }
  loading.value = true
  try {
    await auth.setup(form.value.username, form.value.password, form.value.confirm)
    toast.show('success', '初始化成功，欢迎使用')
    router.push('/create')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    inlineError.value = err.response?.data?.message || '初始化失败'
  } finally {
    loading.value = false
  }
}

async function submitLogin() {
  inlineError.value = ''
  if (!captcha.value.id) {
    await refreshCaptcha()
  }
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password, captcha.value.id, form.value.code)
    toast.show('success', '登录成功')
    router.push('/create')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    inlineError.value = err.response?.data?.message || '登录失败'
    refreshCaptcha() // 失败自动刷新验证码，不清空输入
  } finally {
    loading.value = false
  }
}

async function submitReset() {
  inlineError.value = ''
  if (form.value.new_password !== form.value.confirm) {
    inlineError.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    const res = await authApi.resetPassword({ username: form.value.username, new_password: form.value.new_password, confirm: form.value.confirm })
    toast.show('success', res.message || '重置成功，请使用新密码登录')
    switchMode('login')
    form.value.password = ''
    form.value.new_password = ''
    form.value.confirm = ''
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    inlineError.value = err.response?.data?.message || '重置失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center px-4">
    <!-- 官网 LOGO（左上角固定，渐变设计款） -->
    <a
      href="https://aivideo.site/"
      target="_blank"
      rel="noopener"
      class="group fixed left-6 top-5 z-10 flex items-center gap-2.5"
      title="访问官网 aivideo.site"
    >
      <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent text-2xl text-white shadow-md transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:scale-105">🎬</span>
      <span class="text-3xl font-bold leading-none tracking-tight">
        <span class="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">aivideo</span>
        <span class="text-text-3">.site</span>
      </span>
    </a>
    <!-- 暖光晕背景 -->
    <div class="pointer-events-none fixed inset-0">
      <div class="absolute -left-24 -top-24 h-96 w-96 rounded-full bg-accent/10 blur-3xl" />
      <div class="absolute bottom-0 right-0 h-96 w-96 rounded-full bg-primary/10 blur-3xl" />
    </div>

    <div class="relative w-full max-w-md">
      <div class="mb-8 text-center">
        <div class="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-2xl text-white shadow-md">🎬</div>
        <h1 class="font-brand text-2xl font-bold text-text">视频智造平台</h1>
        <p class="mt-1 text-sm text-text-2">本地视频智造工作台 · V2.0</p>
      </div>

      <div class="rounded-lg border border-border bg-surface/80 p-8 shadow-lg backdrop-blur">
        <!-- 模式切换 -->
        <div class="mb-6 flex rounded-full bg-surface-2 p-1 text-sm">
          <button
            v-if="isInit"
            class="flex-1 rounded-full py-2 font-medium text-primary"
          >
            初始化
          </button>
          <template v-else>
            <button
              class="flex-1 rounded-full py-2 transition-colors"
              :class="isLogin ? 'bg-surface font-medium text-primary shadow-sm' : 'text-text-2'"
              @click="switchMode('login')"
            >
              登录
            </button>
            <button
              class="flex-1 rounded-full py-2 transition-colors"
              :class="isReset ? 'bg-surface font-medium text-primary shadow-sm' : 'text-text-2'"
              @click="switchMode('reset')"
            >
              重置密码
            </button>
          </template>
        </div>

        <!-- 初始化 -->
        <form v-if="isInit" class="space-y-4" @submit.prevent="submitInit">
          <div>
            <label class="mb-1 block text-sm text-text-2">用户名</label>
            <input v-model="form.username" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent" placeholder="设置管理员用户名" autocomplete="username" />
          </div>
          <div>
            <label class="mb-1 block text-sm text-text-2">密码</label>
            <input v-model="form.password" type="password" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent" placeholder="至少 6 位" autocomplete="new-password" />
          </div>
          <div>
            <label class="mb-1 block text-sm text-text-2">确认密码</label>
            <input v-model="form.confirm" type="password" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent" placeholder="再次输入密码" autocomplete="new-password" />
          </div>
          <p v-if="inlineError" class="text-sm text-danger">{{ inlineError }}</p>
          <button type="submit" class="w-full rounded-full bg-accent py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50" :disabled="loading">
            {{ loading ? '创建中…' : '创建并进入工作台' }}
          </button>
        </form>

        <!-- 登录 -->
        <form v-else-if="isLogin" class="space-y-4" @submit.prevent="submitLogin">
          <div>
            <label class="mb-1 block text-sm text-text-2">用户名</label>
            <input v-model="form.username" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent" placeholder="请输入用户名" autocomplete="username" />
          </div>
          <div>
            <label class="mb-1 block text-sm text-text-2">密码</label>
            <input v-model="form.password" type="password" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent" placeholder="请输入密码" autocomplete="current-password" />
          </div>
          <div>
            <label class="mb-1 block text-sm text-text-2">验证码</label>
            <div class="flex gap-2">
              <input v-model="form.code" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm tracking-widest outline-none focus:border-accent" placeholder="4 位数字" maxlength="4" inputmode="numeric" />
              <button
                type="button"
                class="shrink-0 rounded-md border border-border bg-surface-2 px-2"
                title="点击刷新验证码"
                @click="refreshCaptcha"
                v-html="captcha.svg"
              />
            </div>
          </div>
          <p v-if="inlineError" class="text-sm text-danger">{{ inlineError }}</p>
          <button type="submit" class="w-full rounded-full bg-accent py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50" :disabled="loading">
            {{ loading ? '登录中…' : '登 录' }}
          </button>
        </form>

        <!-- 重置 -->
        <form v-else class="space-y-4" @submit.prevent="submitReset">
          <div>
            <label class="mb-1 block text-sm text-text-2">用户名</label>
            <input v-model="form.username" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent" placeholder="请输入用户名" />
          </div>
          <div>
            <label class="mb-1 block text-sm text-text-2">新密码</label>
            <input v-model="form.new_password" type="password" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent" placeholder="至少 6 位" />
          </div>
          <div>
            <label class="mb-1 block text-sm text-text-2">确认新密码</label>
            <input v-model="form.confirm" type="password" class="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-accent" placeholder="再次输入新密码" />
          </div>
          <p v-if="inlineError" class="text-sm text-danger">{{ inlineError }}</p>
          <button type="submit" class="w-full rounded-full bg-accent py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50" :disabled="loading">
            {{ loading ? '提交中…' : '重置密码' }}
          </button>
        </form>
      </div>

      <p class="mt-6 text-center text-xs text-text-3">一站式全流程AI长视频创作平台</p>
    </div>
  </div>
</template>

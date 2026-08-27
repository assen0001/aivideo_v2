/** 认证 store：token / user / needSetup / 登录 / 登出 / 401 处理 */
import { defineStore } from 'pinia'
import * as authApi from '@/api/auth'
import { useToastStore } from '@/stores/toast'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null as User | null,
    needSetup: false,
  }),
  actions: {
    /** 启动时判定初始化 or 常规登录 */
    async init() {
      try {
        const res = await authApi.getStatus()
        this.needSetup = res.need_setup
      } catch {
        this.needSetup = false
      }
      return this.needSetup
    },
    async setup(username: string, password: string, confirm: string) {
      const res = await authApi.setup({ username, password, confirm })
      this.applyAuth(res)
    },
    async login(username: string, password: string, captchaId: string, code: string) {
      const res = await authApi.login({ username, password, captcha_id: captchaId, code })
      this.applyAuth(res)
    },
    applyAuth(res: { token: string; user: User }) {
      this.token = res.token
      this.user = res.user
      this.needSetup = false
      localStorage.setItem('token', res.token)
    },
    async fetchMe() {
      if (!this.token) return
      try {
        this.user = await authApi.getMe()
      } catch {
        /* 401 由拦截器处理 */
      }
    },
    async updateMe(data: { nickname: string; avatar: string; email: string }) {
      const res = await authApi.updateMe(data)
      this.user = res.user
    },
    async changePassword(oldPassword: string, newPassword: string, confirm: string) {
      await authApi.changePassword({ old_password: oldPassword, new_password: newPassword, confirm })
      // 改密成功 → 清 token + toast + 回登录（强制重登 ④a）
      this.clearAuth()
      const toast = useToastStore()
      toast.show('success', '密码已修改，请重新登录')
      setTimeout(() => {
        window.location.href = '/login'
      }, 800)
    },
    logout() {
      try {
        authApi.logout().catch(() => {})
      } catch {
        /* 幂等 */
      }
      this.clearAuth()
      window.location.href = '/login'
    },
    handle401() {
      // 401 全局拦截：清 token → toast → 回登录页
      this.clearAuth()
      const toast = useToastStore()
      toast.show('warning', '登录已过期，请重新登录')
      setTimeout(() => {
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login'
        }
      }, 600)
    },
    clearAuth() {
      this.token = ''
      this.user = null
      this.needSetup = false
      localStorage.removeItem('token')
      localStorage.removeItem('current_project_id')
    },
  },
})

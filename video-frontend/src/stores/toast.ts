/** 全局 toast 队列（auto-dismiss 3s） */
import { defineStore } from 'pinia'

export interface ToastItem {
  id: number
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
}

let seq = 0

export const useToastStore = defineStore('toast', {
  state: () => ({
    list: [] as ToastItem[],
  }),
  actions: {
    show(type: ToastItem['type'], message: string) {
      const id = ++seq
      this.list.push({ id, type, message })
      setTimeout(() => this.remove(id), 3000)
    },
    success(message: string) {
      this.show('success', message)
    },
    error(message: string) {
      this.show('error', message)
    },
    warning(message: string) {
      this.show('warning', message)
    },
    remove(id: number) {
      this.list = this.list.filter((t) => t.id !== id)
    },
  },
})

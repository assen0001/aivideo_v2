/** 配置 API */
import http from './http'
import type { SettingsResponse, TestStatus } from '@/types'

export function getSettings() {
  return http.get<never, SettingsResponse>('/settings')
}

export function saveSettings(settings: Record<string, string>) {
  return http.put<never, { message: string }>('/settings', { settings })
}

/** 提交外部 API 连通性测试（vendor: llm | t2i | i2v | tts） */
export function submitTest(vendor: string, settings?: Record<string, string>) {
  return http.post<never, { task_id: string; status: string }>(`/settings/test/${vendor}`, { settings })
}

/** 轮询测试结果 */
export function pollTest(vendor: string, taskId: string) {
  return http.get<never, TestStatus>(`/settings/test/${vendor}/${taskId}`)
}

/** 测试产物预览 URL（需鉴权，直接 <img>/<video>/<audio> 引用带 token） */
export function testPreviewUrl(taskId: string, filename: string): string {
  const token = localStorage.getItem('token') || ''
  return `/api/settings/test/preview/${taskId}/${filename}?token=${encodeURIComponent(token)}`
}

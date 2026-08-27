/** 资产 API */
import http from './http'
import type { Asset, Page, UploadResult } from '@/types'

export function uploadAssets(files: File[]) {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  return http.post<never, UploadResult>('/assets/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function listAssets(params: { type?: string; keyword?: string; page?: number; page_size?: number } = {}) {
  return http.get<never, Page<Asset>>('/assets', { params })
}

export function renameAsset(id: number, file_name: string) {
  return http.put<never, { message: string; file_name: string }>(`/assets/${id}`, { file_name })
}

export function deleteAsset(id: number) {
  return http.delete<never, { message: string; freed_mb: number }>(`/assets/${id}`)
}

/** 教程 API */
import http from './http'
import type { Tutorial } from '@/types'

export function listTutorials(tag = '') {
  return http.get<never, Tutorial[]>('/tutorials', { params: tag ? { tag } : {} })
}

export function getTutorial(id: number) {
  return http.get<never, Tutorial>(`/tutorials/${id}`)
}

export function createTutorial(data: { title: string; summary: string; cover: string; content: string; tags: string }) {
  return http.post<never, { message: string; id: number }>('/tutorials', data)
}

export function updateTutorial(id: number, data: { title: string; summary: string; cover: string; content: string; tags: string }) {
  return http.put<never, { message: string }>(`/tutorials/${id}`, data)
}

export function deleteTutorial(id: number) {
  return http.delete<never, { message: string }>(`/tutorials/${id}`)
}

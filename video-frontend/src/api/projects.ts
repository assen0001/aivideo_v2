/** 项目 API */
import http from './http'
import type { Page, Project, ProjectStatus } from '@/types'

export interface ProjectCreatePayload {
  name: string
  topic: string
  config: {
    ratio: string
    resolution: string
    fps: number
    style: string
    voice: string
    targetDuration: number
  }
}

export function createProject(data: ProjectCreatePayload) {
  return http.post<never, { project_id: string; status: string }>('/projects', data)
}

export function startGenerate(projectId: string) {
  return http.post<never, { project_id: string; status: string }>(`/projects/${projectId}/generate`)
}

/** 用户主动停止生成（仅对「进行中」项目生效） */
export function stopGenerate(projectId: string) {
  return http.post<never, { project_id: string; status: string }>(`/projects/${projectId}/stop`)
}

/** 重新合成视频（V2.7）：复用现有分镜素材只重跑 compose，替换成片 */
export function recomposeProject(projectId: string) {
  return http.post<never, { project_id: string; status: string }>(`/projects/${projectId}/recompose`)
}

export function getProjectStatus(projectId: string) {
  return http.get<never, ProjectStatus>(`/projects/${projectId}/status`)
}

export function getProject(projectId: string) {
  return http.get<never, Project>(`/projects/${projectId}`)
}

export function listProjects(params: { page?: number; page_size?: number; status?: string; keyword?: string } = {}) {
  return http.get<never, Page<Project>>('/projects', { params })
}

export function deleteProject(projectId: string) {
  return http.delete<never, { message: string; freed_mb: number }>(`/projects/${projectId}`)
}

export function downloadUrl(projectId: string) {
  return `/api/projects/${projectId}/download`
}

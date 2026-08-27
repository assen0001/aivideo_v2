/** 认证 / 用户 API */
import http from './http'
import type { User } from '@/types'

export interface AuthResult {
  token: string
  user: User
}

export function getStatus() {
  return http.get<never, { need_setup: boolean }>('/auth/status')
}

export function setup(data: { username: string; password: string; confirm: string }) {
  return http.post<never, AuthResult>('/auth/setup', data, { skipToast: true } as never)
}

export function getCaptcha() {
  return http.post<never, { captcha_id: string; svg: string }>('/auth/captcha')
}

export function login(data: { username: string; password: string; captcha_id: string; code: string }) {
  return http.post<never, AuthResult>('/auth/login', data, { skipToast: true } as never)
}

export function logout() {
  return http.post<never, { message: string }>('/auth/logout')
}

export function resetPassword(data: { username: string; new_password: string; confirm: string }) {
  return http.post<never, { message: string }>('/auth/reset-password', data, { skipToast: true } as never)
}

export function getMe() {
  return http.get<never, User>('/users/me')
}

export function updateMe(data: { nickname: string; avatar: string; email: string }) {
  return http.put<never, { message: string; user: User }>('/users/me', data)
}

export function changePassword(data: { old_password: string; new_password: string; confirm: string }) {
  return http.put<never, { message: string }>('/users/me/password', data)
}

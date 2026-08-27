/** V2.0 前端类型定义（字段与后端 API 同名字段，snake_case，设计 §9） */

export interface User {
  id: number
  username: string
  nickname: string
  avatar: string
  email: string
  created_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface ProjectConfig {
  ratio: string
  resolution: string
  fps: number
  style: string
  voice: string
  target_duration: number
  scene_count: number
}

export interface Scene {
  id: number
  project_id: string
  scene_no: number
  duration: number
  description: string
  narration: string
  subtitle: string
  t2i_prompt: string
  i2v_prompt: string
  camera: string
  image_url: string
  video_url: string
  voice_path: string
  voice_duration: number
  status: string
}

export interface Project {
  id: number
  project_id: string
  name: string
  topic: string
  ratio: string
  resolution: string
  fps: number
  style: string
  voice: string
  target_duration: number
  status: string
  error_msg: string
  scene_count: number
  cover_url: string
  final_video_url: string
  download_url: string
  config?: ProjectConfig
  scenes?: Scene[]
  created_at: string
  updated_at: string
}

export interface Asset {
  id: number
  file_name: string
  file_type: string
  ext: string
  file_size: number
  file_path: string
  url: string
  created_at: string
}

export interface Tutorial {
  id: number
  title: string
  summary: string
  cover: string
  content?: string
  tags: string
  is_published: number
  sort_order: number
  created_at: string
  updated_at: string
}

export interface SettingsResponse {
  settings: Record<string, string>
  sensitive_keys: string[]
}

/** 外部 API 连通性测试结果（配置页测试按钮用） */
export interface TestArtifact {
  type: 'image' | 'audio' | 'video' | 'file'
  filename: string
  size_bytes: number
  url: string
}

export interface TestStatus {
  task_id: string
  vendor: 'llm' | 't2i' | 'i2v' | 'tts'
  status: 'running' | 'success' | 'error'
  stage: 'pending' | 'system_stats' | 'generate' | 'fetch' | 'done' | 'error'
  elapsed_ms: number
  detail?: string
  response?: {
    model?: string
    content_preview?: string
    gpu?: string
    vram_free_mb?: number
    comfyui_version?: string
  }
  artifacts?: TestArtifact[]
}

export interface ProjectStatus {
  project_id: string
  status: string
  current_step: string
  progress_percent: number
  error_msg: string
}

export interface UploadResult {
  items: Asset[]
  failures: { file_name: string; reason: string }[]
}

/** 创作流程步骤定义 */
export interface StepDef {
  key: string
  label: string
  progress: number
}

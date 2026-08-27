/** 配音音色常量（V2.5：value=音色文件名，与后端 VoiceStyle 枚举、static/speaker/*.mp3 一一对应） */

export interface VoiceOption {
  label: string
  value: string
}

export const VOICES: VoiceOption[] = [
  { label: '无配音', value: 'none' },
  { label: '阿飞（男声）', value: 'afei' },
  { label: '阿伟（男声）', value: 'awei' },
  { label: '阿哲（男声）', value: 'aze' },
  { label: '娜娜（女声）', value: 'nana' },
  { label: '莉莉（女声）', value: 'lili' },
  { label: '文君（女声）', value: 'wenjun' },
  { label: '小花（童声）', value: 'xiaohua' },
]

const VOICE_LABEL_MAP: Record<string, string> = Object.fromEntries(
  VOICES.map((v) => [v.value, v.label]),
)

/** 音色 value → 中文显示名；未知值回退「无配音」 */
export function voiceLabel(value?: string): string {
  if (!value) return '无配音'
  return VOICE_LABEL_MAP[value] ?? '无配音'
}

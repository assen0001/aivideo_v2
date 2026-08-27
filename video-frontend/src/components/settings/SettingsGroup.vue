<script setup lang="ts">
import SensitiveInput from '@/components/common/SensitiveInput.vue'
import AppButton from '@/components/common/AppButton.vue'

interface FieldDef {
  key: string
  label: string
  type: 'text' | 'number' | 'sensitive'
  placeholder?: string
}

defineProps<{
  title: string
  description?: string
  fields: FieldDef[]
  model: Record<string, string>
  sensitiveKeys: string[]
  icon?: string
  /** 是否显示「测试」按钮（外部 API 配置分组用） */
  testable?: boolean
  /** 测试按钮 loading 状态 */
  testing?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:model', key: string, value: string): void
  (e: 'test'): void
}>()

function isSensitive(f: FieldDef): boolean {
  return f.type === 'sensitive'
}

function onInput(key: string, value: string) {
  emit('update:model', key, value)
}
</script>

<template>
  <section class="rounded-lg border border-border bg-surface p-5 shadow-sm">
    <div class="mb-4 flex items-center gap-2">
      <span class="flex h-8 w-8 items-center justify-center rounded-full bg-surface-2 text-primary">{{ icon || '⚙' }}</span>
      <div class="min-w-0 flex-1">
        <h3 class="font-semibold text-text">{{ title }}</h3>
        <p v-if="description" class="truncate text-xs text-text-3">{{ description }}</p>
      </div>
      <AppButton
        v-if="testable"
        type="secondary"
        size="sm"
        :loading="testing"
        @click="emit('test')"
      >
        测试
      </AppButton>
    </div>
    <div class="grid gap-4 sm:grid-cols-2">
      <div v-for="f in fields" :key="f.key">
        <label class="mb-1 block text-sm text-text-2">{{ f.label }}</label>
        <SensitiveInput
          v-if="isSensitive(f)"
          :model-value="model[f.key] ?? ''"
          :placeholder="f.placeholder || '••••••'"
          @update:model-value="onInput(f.key, $event)"
        />
        <input
          v-else
          :type="f.type === 'number' ? 'number' : 'text'"
          :value="model[f.key] ?? ''"
          :placeholder="f.placeholder || ''"
          class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
          @input="onInput(f.key, ($event.target as HTMLInputElement).value)"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  hover?: boolean
  padding?: string
}>(), {
  hover: false,
  padding: 'p-5',
})
</script>

<template>
  <div
    class="rounded-lg bg-surface shadow-sm transition-all duration-200"
    :class="[padding, hover ? 'hover:-translate-y-1 hover:shadow-md' : '']"
  >
    <slot />
  </div>
</template>

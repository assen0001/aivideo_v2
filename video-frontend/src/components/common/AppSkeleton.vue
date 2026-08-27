<script setup lang="ts">
withDefaults(defineProps<{
  rows?: number
}>(), {
  rows: 3,
})
</script>

<template>
  <div class="space-y-3">
    <div v-for="i in rows" :key="i" class="skeleton h-5 rounded-md" :style="{ width: `${100 - i * 11}%` }" />
  </div>
</template>

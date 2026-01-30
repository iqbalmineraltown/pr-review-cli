<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  score?: number
}>()

const badgeClass = computed(() => {
  switch (props.level) {
    case 'CRITICAL':
      return 'bg-critical text-white'
    case 'HIGH':
      return 'bg-high text-white'
    case 'MEDIUM':
      return 'bg-medium text-black'
    case 'LOW':
      return 'bg-low text-white'
    default:
      return 'bg-gray-500 text-white'
  }
})

const priorityLabel = computed(() => {
  switch (props.level) {
    case 'CRITICAL':
      return '🔴 Critical'
    case 'HIGH':
      return '🟠 High'
    case 'MEDIUM':
      return '🟡 Medium'
    case 'LOW':
      return '🟢 Low'
  }
})
</script>

<template>
  <span
    class="inline-flex items-center px-2 py-1 rounded-md text-xs font-semibold"
    :class="badgeClass"
  >
    {{ priorityLabel }}
    <span v-if="score !== undefined" class="ml-1 opacity-80">({{ score }})</span>
  </span>
</template>

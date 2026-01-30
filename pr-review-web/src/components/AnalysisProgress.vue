<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAnalysisStore } from '@/stores/analysis'

const props = defineProps<{
  analyzing: boolean
  progress: number
  status: string | null
}>()

const analysisStore = useAnalysisStore()
const logsContainer = ref<HTMLElement | null>(null)

const progressWidth = computed(() => `${props.progress}%`)

// Auto-scroll to bottom when new logs arrive
function scrollToBottom() {
  if (logsContainer.value) {
    logsContainer.value.scrollTop = logsContainer.value.scrollHeight
  }
}

// Watch for new logs and scroll
import { watch } from 'vue'
watch(() => analysisStore.logs.length, () => {
  setTimeout(scrollToBottom, 10)
})

function getLogIcon(type: string) {
  switch (type) {
    case 'success': return '✓'
    case 'error': return '✗'
    case 'progress': return '⏳'
    case 'info': return 'ℹ'
    default: return '•'
  }
}

function getLogColor(type: string) {
  switch (type) {
    case 'success': return 'text-green-400'
    case 'error': return 'text-red-400'
    case 'progress': return 'text-blue-400'
    case 'info': return 'text-gray-400'
    default: return 'text-gray-400'
  }
}
</script>

<template>
  <div v-if="analyzing" class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <!-- Header -->
    <div class="px-6 py-4 border-b border-gray-700">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-lg font-semibold text-white">Analyzing PRs...</h3>
        <span class="text-2xl font-bold text-blue-400">{{ progressPercent }}%</span>
      </div>

      <!-- Progress Bar -->
      <div class="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
        <div
          class="bg-gradient-to-r from-blue-500 to-purple-500 h-3 transition-all duration-300 ease-out"
          :style="{ width: progressWidth }"
        ></div>
      </div>

      <p v-if="status" class="mt-3 text-sm text-gray-300">{{ status }}</p>

      <div class="mt-4 flex items-center gap-2 text-sm text-gray-400">
        <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
        <span>AI analysis in progress</span>
      </div>
    </div>

    <!-- Live Logs -->
    <div class="border-t border-gray-700">
      <div class="px-6 py-3 bg-gray-750 border-b border-gray-700">
        <h4 class="text-sm font-medium text-gray-300 flex items-center gap-2">
          <span>📋 Live Activity Log</span>
          <span class="text-xs text-gray-500">({{ analysisStore.logs.length }} messages)</span>
        </h4>
      </div>

      <div
        ref="logsContainer"
        class="px-6 py-4 bg-gray-900 max-h-80 overflow-y-auto font-mono text-sm"
      >
        <div
          v-for="(log, index) in analysisStore.logs"
          :key="index"
          class="flex gap-3 mb-1"
          :class="getLogColor(log.type)"
        >
          <span class="text-xs opacity-50 flex-shrink-0">
            {{ new Date(log.timestamp).toLocaleTimeString('en-US', {
              hour12: false,
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit'
            }) }}
          </span>
          <span class="flex-shrink-0">{{ getLogIcon(log.type) }}</span>
          <span class="break-words">{{ log.message }}</span>
        </div>

        <div v-if="analysisStore.logs.length === 0" class="text-gray-500 italic text-center py-4">
          Waiting for updates...
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bg-gray-750 {
  background-color: #2d3748;
}

.max-h-80::-webkit-scrollbar {
  width: 8px;
}

.max-h-80::-webkit-scrollbar-track {
  background: #1a202c;
}

.max-h-80::-webkit-scrollbar-thumb {
  background: #4a5568;
  border-radius: 4px;
}

.max-h-80::-webkit-scrollbar-thumb:hover {
  background: #718096;
}
</style>

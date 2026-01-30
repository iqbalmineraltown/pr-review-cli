<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import Prism from 'prismjs'
import 'prismjs/themes/prism-tomorrow.css'
import 'prismjs/components/prism-diff' // Load diff language support
import 'prismjs/components/prism-javascript'
import 'prismjs/components/prism-typescript'
import 'prismjs/components/prism-python'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-yaml'
import 'prismjs/components/prism-bash'
import 'prismjs/components/prism-markdown'

const props = defineProps<{
  diff: string
  maxHeight?: string
}>()

const diffContent = ref<HTMLElement | null>(null)
const isTruncated = ref(false)
const isExpanded = ref(false)

const MAX_PREVIEW_LENGTH = 10000 // Characters
const MAX_FULL_LENGTH = 100000 // Match backend limit

const displayDiff = computed(() => {
  if (!isExpanded.value && props.diff.length > MAX_PREVIEW_LENGTH) {
    isTruncated.value = true
    return props.diff.slice(0, MAX_PREVIEW_LENGTH) + '\n\n... (diff truncated, click "Show Full Diff" to see more)'
  }
  isTruncated.value = false
  return props.diff
})

const isTooLarge = computed(() => {
  return props.diff.length > MAX_FULL_LENGTH
})

function toggleExpand() {
  isExpanded.value = !isExpanded.value
  nextTick(() => {
    highlightDiff()
  })
}

function highlightDiff() {
  if (diffContent.value) {
    Prism.highlightAllUnder(diffContent.value)
  }
}

onMounted(() => {
  highlightDiff()
})

watch(() => props.diff, () => {
  highlightDiff()
})
</script>

<template>
  <div class="diff-viewer bg-gray-950 rounded-lg overflow-hidden border border-gray-700">
    <!-- Warning for large diffs -->
    <div v-if="isTooLarge" class="bg-yellow-900/30 border-b border-yellow-700 px-4 py-2 text-yellow-300 text-sm">
      ⚠️ This diff is very large ({{ diff.length.toLocaleString() }} characters). Manual review recommended.
    </div>

    <!-- Toolbar -->
    <div class="bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center justify-between">
      <span class="text-sm text-gray-300">
        {{ diff.length.toLocaleString() }} characters
      </span>
      <button
        v-if="isTruncated || isExpanded"
        @click="toggleExpand"
        class="text-sm text-blue-400 hover:text-blue-300 transition"
      >
        {{ isExpanded ? '▼ Collapse' : '▶ Show Full Diff' }}
      </button>
    </div>

    <!-- Diff content -->
    <div
      ref="diffContent"
      class="diff-content overflow-auto p-4 text-sm font-mono leading-relaxed"
      :style="{ maxHeight: maxHeight || '500px' }"
    >
      <pre
        v-if="diff"
        class="!bg-transparent !p-0 !m-0"
      ><code class="language-diff">{{ displayDiff }}</code></pre>
      <p v-else class="text-gray-500 italic">No diff available</p>
    </div>
  </div>
</template>

<style scoped>
.diff-content :deep(pre) {
  margin: 0;
  padding: 0;
  background: transparent;
}

.diff-content :deep(code) {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'source-code-pro', monospace;
  font-size: 13px;
  line-height: 1.6;
}
</style>

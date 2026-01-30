<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { usePRsStore } from '@/stores/prs'
import { useAnalysisStore } from '@/stores/analysis'
import RiskBadge from '@/components/RiskBadge.vue'
import AnalysisProgress from '@/components/AnalysisProgress.vue'
import DiffViewer from '@/components/DiffViewer.vue'
import type { PRWithPriority } from '@/types/api'
import { prsApi } from '@/api/prs'

const prsStore = usePRsStore()
const analysisStore = useAnalysisStore()

// Form state
const workspaceInput = ref('')
const repoInput = ref('')
const showConfig = ref(true) // Default to show

// Available prompts
const prompts = ref<string[]>(['default'])

// Expanded PR for detail view
const expandedPRId = ref<string | null>(null)

// Load config on mount
onMounted(async () => {
  try {
    const config = await prsApi.getConfig()
    if (config.workspace) {
      workspaceInput.value = config.workspace
    }
    prompts.value = config.prompts.map((p: any) => p.name)
    console.log('Config loaded successfully:', config.workspace)
  } catch (err) {
    console.error('Failed to load config:', err)
  }
})

async function handleFetchPRs() {
  if (!workspaceInput.value.trim()) {
    alert('Please enter a workspace name')
    return
  }

  await prsStore.fetchPRs(workspaceInput.value, repoInput.value || undefined)
}

async function handleAnalyze() {
  if (!workspaceInput.value.trim()) {
    alert('Please enter a workspace name')
    return
  }

  await analysisStore.startAnalysis({
    workspace: workspaceInput.value,
    repo: repoInput.value || undefined,
    prompt: analysisStore.selectedPrompt
  })

  // Update PRs store with results
  if (analysisStore.results.length > 0) {
    prsStore.setPRs(analysisStore.results)
  }
}

function toggleExpand(prId: string) {
  if (expandedPRId.value === prId) {
    expandedPRId.value = null
  } else {
    expandedPRId.value = prId
  }
}

function sortByPriority(prs: PRWithPriority[]) {
  return [...prs].sort((a, b) => b.priority_score - a.priority_score)
}

const sortedResults = computed(() => {
  if (analysisStore.results.length === 0) return []
  return sortByPriority(analysisStore.results)
})

function getDiffForPR(pr: PRWithPriority) {
  // For now, we'll create a placeholder diff
  // In production, you'd fetch this from the API
  return `diff --git a/src/example.ts b/src/example.ts
index abc123..def456 100644
--- a/src/example.ts
+++ b/src/example.ts
@@ -1,5 +1,10 @@
 // Example changes
-export const oldFunction = () => {
-  return 'old'
+export const newFunction = () => {
+  return 'new'
+}
+
+export const additionalFunction = () => {
+  return 'additional'
 }
`
}

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

function formatDate(dateString: string | Date) {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 60) {
    return `${diffMins}m ago`
  } else if (diffHours < 24) {
    return `${diffHours}h ago`
  } else if (diffDays < 7) {
    return `${diffDays}d ago`
  } else {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }
}
</script>

<template>
  <div class="container mx-auto px-4 py-8 max-w-7xl">
    <!-- Header -->
    <header class="mb-8">
      <h1 class="text-4xl font-bold text-white mb-2">PR Review CLI</h1>
      <p class="text-gray-400">AI-powered pull request review assistant</p>
    </header>

    <!-- Configuration Panel -->
    <div class="bg-gray-800 rounded-lg p-6 mb-6 border border-gray-700">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-semibold">Configuration</h2>
        <button
          @click="showConfig = !showConfig"
          class="text-gray-400 hover:text-white transition"
        >
          {{ showConfig ? '▼' : '▶' }}
        </button>
      </div>

      <div v-show="showConfig" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">
              Bitbucket Workspace *
            </label>
            <input
              v-model="workspaceInput"
              type="text"
              placeholder="my-workspace"
              class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">
              Repository (optional)
            </label>
            <input
              v-model="repoInput"
              type="text"
              placeholder="my-repo"
              class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">
              Analysis Prompt
            </label>
            <select
              v-model="analysisStore.selectedPrompt"
              class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option v-for="prompt in prompts" :key="prompt" :value="prompt">
                {{ prompt }}
              </option>
            </select>
          </div>
        </div>

        <div class="flex gap-3">
          <button
            @click="handleFetchPRs"
            :disabled="prsStore.loading"
            class="px-4 py-2 bg-gray-600 hover:bg-gray-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white rounded-md transition"
          >
            {{ prsStore.loading ? 'Loading...' : 'Fetch PRs' }}
          </button>

          <button
            @click="handleAnalyze"
            :disabled="analysisStore.analyzing"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-md transition"
          >
            {{ analysisStore.analyzing ? 'Analyzing...' : 'Analyze PRs' }}
          </button>
        </div>
      </div>
    </div>

    <!-- PR Fetch Progress -->
    <div v-if="prsStore.loading" class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden mb-6">
      <div class="px-6 py-4 border-b border-gray-700">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-lg font-semibold text-white">Fetching PRs...</h3>
          <span class="text-2xl font-bold text-green-400">{{ prsStore.fetchProgressPercent }}%</span>
        </div>

        <!-- Progress Bar -->
        <div class="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
          <div
            class="bg-gradient-to-r from-green-500 to-emerald-500 h-3 transition-all duration-300 ease-out"
            :style="{ width: prsStore.fetchProgressPercent + '%' }"
          ></div>
        </div>

        <p v-if="prsStore.fetchStatus" class="mt-3 text-sm text-gray-300">{{ prsStore.fetchStatus }}</p>

        <div class="mt-4 flex items-center gap-2 text-sm text-gray-400">
          <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span>Fetching PRs from Bitbucket</span>
        </div>
      </div>

      <!-- Live Logs -->
      <div v-if="prsStore.logs.length > 0" class="border-t border-gray-700">
        <div class="px-6 py-3 bg-gray-750 border-b border-gray-700">
          <h4 class="text-sm font-medium text-gray-300 flex items-center gap-2">
            <span>📋 Activity Log</span>
            <span class="text-xs text-gray-500">({{ prsStore.logs.length }} messages)</span>
          </h4>
        </div>

        <div class="px-6 py-4 bg-gray-900 max-h-60 overflow-y-auto font-mono text-sm">
          <div
            v-for="(log, index) in prsStore.logs"
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
        </div>
      </div>
    </div>

    <!-- Analysis Progress -->
    <AnalysisProgress
      :analyzing="analysisStore.analyzing"
      :progress="analysisStore.progressPercent"
      :status="analysisStore.status"
    />

    <!-- Error Display -->
    <div v-if="prsStore.error || analysisStore.error" class="bg-red-900/30 border border-red-700 rounded-lg p-4 mb-6">
      <p class="text-red-300">
        {{ prsStore.error || analysisStore.error }}
      </p>
    </div>

    <!-- Fetched PRs Table (shown before analysis) -->
    <div v-if="prsStore.prs.length > 0 && sortedResults.length === 0" class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-700">
        <h2 class="text-xl font-semibold">
          Fetched PRs
          <span class="text-gray-400 text-sm font-normal ml-2">
            ({{ prsStore.prs.length }} PR{{ prsStore.prs.length !== 1 ? 's' : '' }})
          </span>
        </h2>
        <p class="text-sm text-gray-400 mt-1">
          Click "Analyze PRs" to get AI-powered priority scoring and detailed analysis
        </p>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-gray-750">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                PR
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider w-32">
                Author
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider w-32">
                Created
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider w-32">
                Updated
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider w-32">
                Actions
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-700">
            <tr
              v-for="pr in prsStore.prs"
              :key="pr.id"
              class="hover:bg-gray-750 transition"
            >
              <td class="px-6 py-4">
                <div>
                  <div class="text-sm font-medium text-white">{{ pr.title }}</div>
                  <div class="text-sm text-gray-400">
                    {{ pr.workspace }}/{{ pr.repo_slug }} #{{ pr.id }}
                  </div>
                  <div class="text-xs text-gray-500 mt-1">
                    {{ pr.source_branch }} → {{ pr.destination_branch }}
                  </div>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                {{ pr.author }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                {{ formatDate(pr.created_on) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                {{ formatDate(pr.updated_on) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <a
                  :href="pr.link"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-blue-400 hover:text-blue-300 transition"
                >
                  Open in Bitbucket
                </a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Results Table -->
    <div v-if="sortedResults.length > 0" class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-700">
        <h2 class="text-xl font-semibold">
          Analysis Results
          <span class="text-gray-400 text-sm font-normal ml-2">
            ({{ sortedResults.length }} PR{{ sortedResults.length !== 1 ? 's' : '' }})
          </span>
        </h2>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-gray-750">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider w-16">
                Priority
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                PR
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider w-24">
                Author
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider w-28">
                Risk Level
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider w-28">
                Quality Score
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider w-32">
                Actions
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-700">
            <template v-for="item in sortedResults" :key="item.pr.id">
              <!-- Summary Row -->
              <tr
                class="hover:bg-gray-750 transition cursor-pointer"
                @click="toggleExpand(item.pr.id)"
              >
                <td class="px-6 py-4 whitespace-nowrap">
                  <span class="text-lg font-bold text-white">{{ item.priority_score }}</span>
                </td>
                <td class="px-6 py-4">
                  <div class="flex items-center gap-2">
                    <span class="text-gray-400">{{ expandedPRId === item.pr.id ? '▼' : '▶' }}</span>
                    <div>
                      <div class="text-sm font-medium text-white">{{ item.pr.title }}</div>
                      <div class="text-sm text-gray-400">
                        {{ item.pr.workspace }}/{{ item.pr.repo_slug }} #{{ item.pr.id }}
                      </div>
                      <div class="text-xs text-gray-500 mt-1">
                        {{ item.pr.source_branch }} → {{ item.pr.destination_branch }}
                      </div>
                    </div>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                  {{ item.pr.author }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <RiskBadge :level="item.risk_level" :score="item.priority_score" />
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span
                    class="text-sm font-semibold"
                    :class="{
                      'text-green-400': item.analysis.overall_quality_score >= 70,
                      'text-yellow-400': item.analysis.overall_quality_score >= 50 && item.analysis.overall_quality_score < 70,
                      'text-red-400': item.analysis.overall_quality_score < 50
                    }"
                  >
                    {{ item.analysis.overall_quality_score }}/100
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                  <a
                    :href="item.pr.link"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-blue-400 hover:text-blue-300 transition"
                    @click.stop
                  >
                    Open in Bitbucket
                  </a>
                </td>
              </tr>

              <!-- Expanded Detail Row -->
              <tr v-if="expandedPRId === item.pr.id" class="bg-gray-900">
                <td colspan="6" class="px-6 py-4">
                  <div class="space-y-6">
                    <!-- Analysis Summary -->
                    <div>
                      <h3 class="text-lg font-semibold mb-3">AI Analysis Results</h3>

                      <!-- Good Points -->
                      <div v-if="item.analysis.good_points.length > 0" class="mb-4">
                        <h4 class="text-sm font-medium text-green-400 mb-2">✓ Good Points</h4>
                        <ul class="list-disc list-inside space-y-1 text-sm text-gray-300">
                          <li v-for="(point, idx) in item.analysis.good_points" :key="idx">
                            {{ point }}
                          </li>
                        </ul>
                      </div>

                      <!-- Attention Required -->
                      <div v-if="item.analysis.attention_required.length > 0" class="mb-4">
                        <h4 class="text-sm font-medium text-yellow-400 mb-2">⚠ Attention Required</h4>
                        <ul class="list-disc list-inside space-y-1 text-sm text-gray-300">
                          <li v-for="(item2, idx) in item.analysis.attention_required" :key="idx">
                            {{ item2 }}
                          </li>
                        </ul>
                      </div>

                      <!-- Risk Factors -->
                      <div v-if="item.analysis.risk_factors.length > 0" class="mb-4">
                        <h4 class="text-sm font-medium text-red-400 mb-2">⚡ Risk Factors</h4>
                        <ul class="list-disc list-inside space-y-1 text-sm text-gray-300">
                          <li v-for="(risk, idx) in item.analysis.risk_factors" :key="idx">
                            {{ risk }}
                          </li>
                        </ul>
                      </div>

                      <div class="text-sm text-gray-400">
                        Estimated review time: <span class="text-white">{{ item.analysis.estimated_review_time }}</span>
                      </div>
                    </div>

                    <!-- Diff Viewer -->
                    <div>
                      <h3 class="text-lg font-semibold mb-3">Code Diff</h3>
                      <DiffViewer :diff="getDiffForPR(item)" max-height="400px" />
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="prsStore.prs.length === 0" class="bg-gray-800 rounded-lg p-12 border border-gray-700 text-center">
      <div class="text-gray-400 mb-4">
        <svg
          class="w-16 h-16 mx-auto mb-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <p class="text-lg">No PRs fetched yet</p>
        <p class="text-sm mt-2">
          Enter your Bitbucket workspace and click "Fetch PRs" to get started
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bg-gray-750 {
  background-color: #2d3748;
}

.max-h-60::-webkit-scrollbar {
  width: 8px;
}

.max-h-60::-webkit-scrollbar-track {
  background: #1a202c;
}

.max-h-60::-webkit-scrollbar-thumb {
  background: #4a5568;
  border-radius: 4px;
}

.max-h-60::-webkit-scrollbar-thumb:hover {
  background: #718096;
}
</style>

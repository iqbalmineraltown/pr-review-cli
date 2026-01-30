<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { prsApi } from '@/api/prs'
import DiffViewer from '@/components/DiffViewer.vue'
import RiskBadge from '@/components/RiskBadge.vue'
import type { BitbucketPR, PRDiff, PRAnalysis } from '@/types/api'

const route = use Route()
const pr = ref<BitbucketPR | null>(null)
const diff = ref<PRDiff | null>(null)
const analysis = ref<PRAnalysis | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const prId = route.params.id as string
const workspace = route.query.workspace as string
const repo = route.query.repo as string

onMounted(async () => {
  if (!workspace || !repo) {
    error.value = 'Missing workspace or repo parameter'
    loading.value = false
    return
  }

  try {
    loading.value = true
    const response = await prsApi.getPRDetail(prId, workspace, repo)
    pr.value = response.pr
    diff.value = response.diff
  } catch (err: any) {
    error.value = err.message || 'Failed to load PR details'
    console.error('Failed to load PR details:', err)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="container mx-auto px-4 py-8 max-w-7xl">
    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-red-900/30 border border-red-700 rounded-lg p-4">
      <p class="text-red-300">{{ error }}</p>
    </div>

    <!-- Content -->
    <div v-else-if="pr" class="space-y-6">
      <!-- Header -->
      <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 class="text-3xl font-bold text-white mb-2">{{ pr.title }}</h1>
        <p class="text-gray-400 mb-4">{{ pr.description || 'No description' }}</p>

        <div class="flex flex-wrap gap-4 text-sm text-gray-300">
          <div>
            <span class="text-gray-400">Author:</span> {{ pr.author }}
          </div>
          <div>
            <span class="text-gray-400">Branches:</span>
            {{ pr.source_branch }} → {{ pr.destination_branch }}
          </div>
          <div>
            <span class="text-gray-400">Workspace:</span> {{ pr.workspace }}/{{ pr.repo_slug }}
          </div>
          <div>
            <span class="text-gray-400">Created:</span> {{ new Date(pr.created_on).toLocaleString() }}
          </div>
        </div>

        <div class="mt-4">
          <a
            :href="pr.link"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-md transition"
          >
            Open in Bitbucket
            <svg class="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>
      </div>

      <!-- Diff Viewer -->
      <div v-if="diff" class="bg-gray-800 rounded-lg border border-gray-700">
        <div class="px-6 py-4 border-b border-gray-700">
          <h2 class="text-xl font-semibold">Code Diff</h2>
          <p class="text-sm text-gray-400 mt-1">
            {{ diff.files_changed.length }} file(s) changed,
            {{ diff.additions }} addition(s),
            {{ diff.deletions }} deletion(s)
          </p>
        </div>
        <div class="p-6">
          <DiffViewer :diff="diff.diff_content" max-height="600px" />
        </div>
      </div>

      <!-- Analysis Results (if available) -->
      <div v-if="analysis" class="bg-gray-800 rounded-lg border border-gray-700">
        <div class="px-6 py-4 border-b border-gray-700">
          <h2 class="text-xl font-semibold">AI Analysis Results</h2>
        </div>

        <div class="p-6 space-y-6">
          <!-- Quality Score -->
          <div>
            <h3 class="text-lg font-medium mb-2">Overall Quality Score</h3>
            <div class="flex items-center gap-4">
              <div class="text-4xl font-bold" :class="{
                'text-green-400': analysis.overall_quality_score >= 70,
                'text-yellow-400': analysis.overall_quality_score >= 50 && analysis.overall_quality_score < 70,
                'text-red-400': analysis.overall_quality_score < 50
              }">
                {{ analysis.overall_quality_score }}/100
              </div>
              <div class="text-gray-400">
                Estimated review time: {{ analysis.estimated_review_time }}
              </div>
            </div>
          </div>

          <!-- Good Points -->
          <div v-if="analysis.good_points.length > 0">
            <h3 class="text-lg font-medium mb-2 text-green-400">✓ Good Points</h3>
            <ul class="list-disc list-inside space-y-1 text-gray-300">
              <li v-for="(point, index) in analysis.good_points" :key="index">
                {{ point }}
              </li>
            </ul>
          </div>

          <!-- Attention Required -->
          <div v-if="analysis.attention_required.length > 0">
            <h3 class="text-lg font-medium mb-2 text-yellow-400">⚠ Attention Required</h3>
            <ul class="list-disc list-inside space-y-1 text-gray-300">
              <li v-for="(item, index) in analysis.attention_required" :key="index">
                {{ item }}
              </li>
            </ul>
          </div>

          <!-- Risk Factors -->
          <div v-if="analysis.risk_factors.length > 0">
            <h3 class="text-lg font-medium mb-2 text-red-400">⚡ Risk Factors</h3>
            <ul class="list-disc list-inside space-y-1 text-gray-300">
              <li v-for="(risk, index) in analysis.risk_factors" :key="index">
                {{ risk }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

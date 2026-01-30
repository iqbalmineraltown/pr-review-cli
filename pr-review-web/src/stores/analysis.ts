/**
 * Analysis State Management Store
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PRWithPriority, WebSocketProgressMessage } from '@/types/api'
import { prsApi } from '@/api/prs'
import { AnalysisWebSocket } from '@/api/websocket'

interface LogEntry {
  timestamp: Date
  message: string
  type: 'info' | 'success' | 'error' | 'progress'
}

export const useAnalysisStore = defineStore('analysis', () => {
  // State
  const analyzing = ref(false)
  const progress = ref(0)
  const status = ref<string | null>(null)
  const results = ref<PRWithPriority[]>([])
  const error = ref<string | null>(null)
  const analysisId = ref<string | null>(null)
  const selectedPrompt = ref('default')
  const logs = ref<LogEntry[]>([])

  // WebSocket client
  let wsClient: AnalysisWebSocket | null = null

  // Computed
  const progressPercent = computed(() => {
    return Math.round(progress.value)
  })

  // Helper function to add logs
  function addLog(message: string, type: LogEntry['type'] = 'info') {
    logs.value.push({
      timestamp: new Date(),
      message,
      type
    })
    // Keep only last 100 logs
    if (logs.value.length > 100) {
      logs.value = logs.value.slice(-100)
    }
  }

  // Actions
  async function startAnalysis(params: { workspace: string; repo?: string; prompt?: string; maxPrs?: number }) {
    analyzing.value = true
    progress.value = 0
    status.value = 'Initializing...'
    error.value = null
    results.value = []
    logs.value = []

    addLog('🚀 Starting analysis...', 'info')

    try {
      // Initialize WebSocket connection
      if (!wsClient) {
        wsClient = new AnalysisWebSocket()
        wsClient.connect({
          onConnected: () => {
            addLog('✓ Connected to WebSocket', 'success')
          },
          onProgress: (current, total, msg) => {
            progress.value = (current / total) * 100
            status.value = msg
            addLog(`[${Math.round((current / total) * 100)}%] ${msg}`, 'progress')
          },
          onComplete: (analysisResults) => {
            results.value = analysisResults
            analyzing.value = false
            status.value = 'Complete!'
            progress.value = 100
            addLog(`✓ Analysis complete! Found ${analysisResults.length} PR(s)`, 'success')
          },
          onError: (err) => {
            error.value = err
            analyzing.value = false
            status.value = null
            addLog(`✗ Error: ${err}`, 'error')
          },
          onDisconnected: () => {
            addLog('WebSocket disconnected', 'info')
          }
        })
      }

      addLog(`📡 Connecting to analysis service...`, 'info')

      // Trigger analysis
      const response = await prsApi.analyzePRs({
        workspace: params.workspace,
        repo_slug: params.repo,
        prompt: params.prompt || selectedPrompt.value,
        max_prs: params.maxPrs || 30
      })

      analysisId.value = response.analysis_id
      addLog(`📋 Analysis ID: ${response.analysis_id}`, 'info')

      // Subscribe to updates
      wsClient.subscribe(response.analysis_id)
      addLog('🔄 Subscribed to progress updates', 'info')

    } catch (err: any) {
      error.value = err.message || 'Failed to start analysis'
      analyzing.value = false
      status.value = null
      addLog(`✗ Failed to start: ${error.value}`, 'error')
      console.error('Failed to start analysis:', err)
    }
  }

  function stopAnalysis() {
    analyzing.value = false
    progress.value = 0
    status.value = null
    addLog('⏹ Analysis stopped by user', 'info')
    wsClient?.disconnect()
    wsClient = null
  }

  function setSelectedPrompt(prompt: string) {
    selectedPrompt.value = prompt
  }

  function clearResults() {
    results.value = []
    error.value = null
    progress.value = 0
    status.value = null
    logs.value = []
  }

  return {
    // State
    analyzing,
    progress,
    status,
    results,
    error,
    analysisId,
    selectedPrompt,
    logs,

    // Computed
    progressPercent,

    // Actions
    startAnalysis,
    stopAnalysis,
    setSelectedPrompt,
    clearResults
  }
})

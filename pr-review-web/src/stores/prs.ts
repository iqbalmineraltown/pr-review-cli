/**
 * PR State Management Store
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { BitbucketPR, PRWithPriority } from '@/types/api'
import { prsApi } from '@/api/prs'
import { AnalysisWebSocket } from '@/api/websocket'

interface LogEntry {
  timestamp: Date
  message: string
  type: 'info' | 'success' | 'error' | 'progress'
}

export const usePRsStore = defineStore('prs', () => {
  // State
  const prs = ref<BitbucketPR[]>([])
  const prsWithPriority = ref<PRWithPriority[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedPR = ref<BitbucketPR | PRWithPriority | null>(null)
  const workspace = ref<string | null>(null)
  const repoSlug = ref<string | null>(null)

  // Progress tracking
  const fetchProgress = ref(0)
  const fetchStatus = ref<string | null>(null)
  const logs = ref<LogEntry[]>([])

  // WebSocket client for fetch progress
  let wsClient: AnalysisWebSocket | null = null

  // Computed
  const prCount = computed(() => prs.value.length)
  const hasPRs = computed(() => prs.value.length > 0)
  const fetchProgressPercent = computed(() => Math.round(fetchProgress.value))

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
  async function fetchPRs(ws: string, repo?: string) {
    loading.value = true
    error.value = null
    fetchProgress.value = 0
    fetchStatus.value = 'Initializing...'
    logs.value = []

    addLog('🔍 Starting PR fetch...', 'info')

    try {
      // Initialize WebSocket connection for progress updates
      if (!wsClient) {
        wsClient = new AnalysisWebSocket()
        wsClient.connect({
          onConnected: () => {
            addLog('✓ Connected to WebSocket', 'success')
          },
          onProgress: (current, total, msg) => {
            fetchProgress.value = (current / total) * 100
            fetchStatus.value = msg
            addLog(`[${Math.round((current / total) * 100)}%] ${msg}`, 'progress')
          },
          onError: (err) => {
            addLog(`✗ WebSocket error: ${err}`, 'error')
          },
          onDisconnected: () => {
            addLog('WebSocket disconnected', 'info')
          }
        })
      }

      addLog(`📡 Fetching PRs from ${ws}...`, 'info')

      const response = await prsApi.listPRs({
        workspace: ws,
        repo
      })

      prs.value = response.prs
      workspace.value = ws
      repoSlug.value = repo || null

      fetchProgress.value = 100
      fetchStatus.value = `Found ${response.count} PR(s)`
      addLog(`✓ Successfully fetched ${response.count} PR(s)`, 'success')
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch PRs'
      fetchStatus.value = null
      addLog(`✗ Failed to fetch: ${error.value}`, 'error')
      console.error('Failed to fetch PRs:', err)
    } finally {
      loading.value = false
    }
  }

  function setPRs(newPRs: PRWithPriority[]) {
    prsWithPriority.value = newPRs
  }

  function setSelectedPR(pr: BitbucketPR | PRWithPriority | null) {
    selectedPR.value = pr
  }

  function setWorkspace(ws: string | null) {
    workspace.value = ws
  }

  function setRepoSlug(repo: string | null) {
    repoSlug.value = repo
  }

  function clear() {
    prs.value = []
    prsWithPriority.value = []
    selectedPR.value = null
    error.value = null
    fetchProgress.value = 0
    fetchStatus.value = null
    logs.value = []
  }

  return {
    // State
    prs,
    prsWithPriority,
    loading,
    error,
    selectedPR,
    workspace,
    repoSlug,
    fetchProgress,
    fetchStatus,
    logs,

    // Computed
    prCount,
    hasPRs,
    fetchProgressPercent,

    // Actions
    fetchPRs,
    setPRs,
    setSelectedPR,
    setWorkspace,
    setRepoSlug,
    clear
  }
})

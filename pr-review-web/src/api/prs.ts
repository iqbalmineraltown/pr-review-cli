/**
 * PR API Functions
 */

import apiClient from './client'
import type { BitbucketPR, PRWithPriority, AnalyzeRequest, AnalyzeResponse } from '@/types/api'

export const prsApi = {
  /**
   * List PRs assigned to current user
   */
  async listPRs(params: { workspace: string; repo?: string }) {
    const response = await apiClient.get<{ prs: BitbucketPR[]; count: number }>('/api/prs', {
      params
    })
    return response.data
  },

  /**
   * Trigger analysis of PRs
   */
  async analyzePRs(request: AnalyzeRequest) {
    const response = await apiClient.post<AnalyzeResponse>('/api/analyze', request)
    return response.data
  },

  /**
   * Get cached analysis results
   */
  async getAnalysisResults(analysisId: string) {
    const response = await apiClient.get<{ analysis_id: string; results: PRWithPriority[] }>(
      `/api/analyze/${analysisId}`
    )
    return response.data
  },

  /**
   * Get configuration
   */
  async getConfig() {
    const response = await apiClient.get<{ workspace: string | null; prompts: any[] }>('/api/config')
    return response.data
  },

  /**
   * List available prompts
   */
  async listPrompts() {
    const response = await apiClient.get<{ prompts: string[]; prompts_info: any[] }>('/api/prompts')
    return response.data
  }
}

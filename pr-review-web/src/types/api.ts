/**
 * API Type Definitions for PR Review Web Interface
 */

export interface BitbucketPR {
  id: string
  title: string
  description: string
  author: string
  source_branch: string
  destination_branch: string
  created_on: string
  updated_on: string
  link: string
  state: string
  workspace: string
  repo_slug: string
}

export interface PRDiff {
  pr_id: string
  files_changed: string[]
  additions: number
  deletions: number
  diff_content: string
}

export interface PRAnalysis {
  pr_id: string
  good_points: string[]
  attention_required: string[]
  risk_factors: string[]
  overall_quality_score: number
  estimated_review_time: string
  _skipped_reason?: string
  _diff_size?: number
}

export interface PRWithPriority {
  pr: BitbucketPR
  analysis: PRAnalysis
  priority_score: number
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
}

export interface AnalyzeRequest {
  workspace: string
  repo_slug?: string
  prompt?: string
  max_prs?: number
}

export interface AnalyzeResponse {
  analysis_id: string
  message: string
  websocket_url: string
}

export interface WebSocketProgressMessage {
  type: 'progress' | 'complete' | 'error' | 'subscribed' | 'pong'
  analysis_id?: string
  current?: number
  total?: number
  status?: string
  results?: PRWithPriority[]
  error?: string
  message?: string
}

export interface PromptInfo {
  name: string
  description: string
  tags: string[]
  path: string
}

export interface ConfigResponse {
  workspace: string | null
  prompts: PromptInfo[]
}

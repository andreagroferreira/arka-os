export interface OverviewData {
  agents: number
  skills: number
  departments: number
  tests: number
  commands: number
  workflows: number
  version: string
  budget: {
    allocated: number
    used: number
    percent_used: number
    is_unlimited: boolean
  }
  tasks: {
    total: number
    active: number
    queued: number
  }
  knowledge: {
    total_chunks: number
    total_files: number
  }
}

export interface Agent {
  id: string
  name: string
  role: string
  department: string
  tier: number
  disc: {
    primary: string
    secondary?: string
    description?: string
  }
  enneagram: {
    type: string
    wing?: string
    label?: string
  }
  big_five: {
    O: number
    C: number
    E: number
    A: number
    N: number
  }
  mbti: string
  expertise_domains: string[]
  frameworks: string[]
  authority?: {
    veto?: boolean
    approve_budget?: boolean
    approve_architecture?: boolean
    orchestrate?: boolean
    block_release?: boolean
    delegates_to?: string[]
    escalates_to?: string[]
  }
}

export interface Command {
  id: string
  command: string
  department: string
  description: string
  keywords?: string[]
}

export interface BudgetTier {
  tier: number
  allocated: number
  used: number
  remaining: number
  percent_used: number
  status: string
  is_unlimited: boolean
}

export interface Task {
  id: string
  title: string
  status: string
  agent: string
  department: string
  progress: number
  created_at: string
}

export interface TaskSummary {
  total: number
  active: number
  queued: number
  completed: number
}

export interface KnowledgeStats {
  total_chunks: number
  total_files: number
  vss_available?: boolean
  areas?: {
    name: string
    chunks: number
    files: number
  }[]
}

export interface KnowledgeSearchResult {
  id?: string
  text?: string
  content?: string
  heading?: string
  source?: string
  area?: string
  score: number
}

export interface IngestRequest {
  source: string
  type: 'youtube' | 'web' | 'pdf' | 'audio' | 'markdown'
}

export interface IngestResponse {
  task_id: string
  source_type: string
  status: string
}

export interface IngestTask {
  id: string
  title: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress_percent: number
  progress_message: string
  output_data?: {
    chunks_created?: number
    [key: string]: unknown
  }
  error?: string
  source_type?: string
  created_at?: string
}

export interface HealthCheck {
  name: string
  passed: boolean
  fix: string
}

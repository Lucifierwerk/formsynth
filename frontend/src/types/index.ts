export interface Option {
  value: string
  weight: number
  enabled: boolean
  go_to_page?: number | null  // target page index for branching (null = next page)
}

export interface TextPoolItem {
  value: string
  weight: number
  enabled: boolean
}

export interface Question {
  id: string
  entry_id: string
  title: string
  description?: string
  qtype: 'single' | 'multi' | 'text' | 'textarea'
  required: boolean
  enabled: boolean
  options: Option[]
  min_select: number
  max_select: number
  text_pool: TextPoolItem[]
  page_index: number  // which section/page (0-based)
}

export interface ParsedForm {
  form_id: string
  title: string
  description?: string
  questions: Question[]
  page_transitions: Record<string, number>
}

export interface JobConfig {
  url: string
  form_id: string
  questions: Question[]
  page_transitions: Record<string, number>
  total: number
  concurrency: number
  min_delay: number
  max_delay: number
  retry_count: number
  batch_size: number
  batch_pause: number
  profiles: string[]
}

export interface Job {
  id: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
  progress: number
  total: number
  success_count: number
  error_count: number
  created_at: string
  started_at?: string
  finished_at?: string
  config?: JobConfig
}

export interface LogEntry {
  ts: string
  level: 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR'
  message: string
  job_id: string
}

export type WSMessage =
  | { type: 'log'; ts: string; level: string; message: string; job_id: string }
  | { type: 'status'; status: string; progress: number; total: number; success_count: number; error_count: number }

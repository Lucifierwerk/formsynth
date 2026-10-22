import { create } from 'zustand'
import type { ParsedForm, Question, Job, LogEntry, JobConfig } from '../types'

interface AppState {
  // URL & form
  url: string
  setUrl: (u: string) => void
  form: ParsedForm | null
  setForm: (f: ParsedForm | null) => void
  questions: Question[]
  setQuestions: (qs: Question[]) => void
  updateQuestion: (id: string, patch: Partial<Question>) => void

  // Job settings
  jobSettings: {
    total: number
    concurrency: number
    min_delay: number
    max_delay: number
    retry_count: number
    batch_size: number
    batch_pause: number
    profiles: string[]
  }
  setJobSettings: (patch: Partial<AppState['jobSettings']>) => void

  // Active job
  activeJob: Job | null
  setActiveJob: (j: Job | null) => void
  updateJobStatus: (patch: Partial<Job>) => void

  // Logs
  logs: LogEntry[]
  appendLog: (e: LogEntry) => void
  clearLogs: () => void

  // UI
  activeTab: 'config' | 'logs' | 'analytics'
  setActiveTab: (t: AppState['activeTab']) => void
  parsing: boolean
  setParsing: (v: boolean) => void
}

export const useStore = create<AppState>((set) => ({
  url: '',
  setUrl: (url) => set({ url }),
  form: null,
  setForm: (form) => set({ form, questions: form?.questions ?? [] }),
  questions: [],
  setQuestions: (questions) => set({ questions }),
  updateQuestion: (id, patch) =>
    set((s) => ({
      questions: s.questions.map((q) => (q.id === id ? { ...q, ...patch } : q)),
    })),

  jobSettings: {
    total: 100,
    concurrency: 3,
    min_delay: 2,
    max_delay: 8,
    retry_count: 2,
    batch_size: 10,
    batch_pause: 5,
    profiles: [],
  },
  setJobSettings: (patch) =>
    set((s) => ({ jobSettings: { ...s.jobSettings, ...patch } })),

  activeJob: null,
  setActiveJob: (activeJob) => set({ activeJob }),
  updateJobStatus: (patch) =>
    set((s) => ({ activeJob: s.activeJob ? { ...s.activeJob, ...patch } : null })),

  logs: [],
  appendLog: (e) =>
    set((s) => ({ logs: [...s.logs.slice(-499), e] })),
  clearLogs: () => set({ logs: [] }),

  activeTab: 'config',
  setActiveTab: (activeTab) => set({ activeTab }),
  parsing: false,
  setParsing: (parsing) => set({ parsing }),
}))

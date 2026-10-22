import type { ParsedForm, Job, LogEntry, JobConfig } from '../types'

const BASE = '/api'

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const api = {
  parseForm: (url: string) =>
    req<{ success: boolean; form?: ParsedForm; error?: string }>('/forms/parse', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }),

  startJob: (config: JobConfig) =>
    req<{ job: Job }>('/jobs/start', {
      method: 'POST',
      body: JSON.stringify({ config }),
    }),

  pauseJob: (id: string) => req(`/jobs/${id}/pause`, { method: 'POST' }),
  resumeJob: (id: string) => req(`/jobs/${id}/resume`, { method: 'POST' }),
  stopJob: (id: string) => req(`/jobs/${id}/stop`, { method: 'POST' }),

  getJob: (id: string) => req<Job>(`/jobs/${id}`),

  getLogs: (id: string) => req<LogEntry[]>(`/jobs/${id}/logs`),
}

export function openJobWS(jobId: string): WebSocket {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  return new WebSocket(`${protocol}://${location.host}/api/ws/jobs/${jobId}/logs`)
}

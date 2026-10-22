import React from 'react'
import { Play, Pause, Square, Loader2, Zap, Download, Upload } from 'lucide-react'
import { useStore } from '../store'
import { api } from '../api'
import type { JobConfig } from '../types'
import clsx from 'clsx'

export function Toolbar() {
  const {
    url, setUrl, form, setForm, setQuestions,
    questions, jobSettings,
    activeJob, setActiveJob, updateJobStatus,
    clearLogs, appendLog,
    parsing, setParsing,
  } = useStore()

  const isRunning = activeJob?.status === 'running'
  const isPaused  = activeJob?.status === 'paused'
  const canControl = isRunning || isPaused

  async function handleParse() {
    if (!url.trim()) return
    setParsing(true)
    try {
      const res = await api.parseForm(url.trim())
      if (res.success && res.form) {
        setForm(res.form)
      } else {
        alert('Ошибка парсинга: ' + (res.error ?? 'Неизвестная ошибка'))
      }
    } catch (e: any) {
      alert('Ошибка сети: ' + e.message)
    } finally {
      setParsing(false)
    }
  }

  async function handleStart() {
    if (!form) return alert('Сначала спарсите форму')
    clearLogs()
    const config: JobConfig = {
      url,
      form_id: form.form_id,
      questions,
      page_transitions: form.page_transitions ?? {},
      ...jobSettings,
    }
    try {
      const res = await api.startJob(config)
      setActiveJob(res.job)
      const ws = new WebSocket(
        `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/ws/jobs/${res.job.id}/logs`
      )
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'log') {
          appendLog({ ts: msg.ts, level: msg.level, message: msg.message, job_id: msg.job_id })
        } else if (msg.type === 'status') {
          updateJobStatus(msg)
        }
      }
    } catch (e: any) {
      alert('Ошибка запуска: ' + e.message)
    }
  }

  async function handlePause() {
    if (!activeJob) return
    if (isPaused) {
      await api.resumeJob(activeJob.id)
      updateJobStatus({ status: 'running' })
    } else {
      await api.pauseJob(activeJob.id)
      updateJobStatus({ status: 'paused' })
    }
  }

  async function handleStop() {
    if (!activeJob) return
    await api.stopJob(activeJob.id)
    updateJobStatus({ status: 'cancelled' })
  }

  function handleExport() {
    const cfg = { url, form, questions, settings: jobSettings }
    const blob = new Blob([JSON.stringify(cfg, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `formsynth-config-${Date.now()}.json`
    a.click()
  }

  function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const cfg = JSON.parse(ev.target?.result as string)
        if (cfg.url) setUrl(cfg.url)
        if (cfg.form) { setForm(cfg.form); setQuestions(cfg.form.questions) }
        if (cfg.questions) setQuestions(cfg.questions)
      } catch { alert('Неверный формат файла конфигурации') }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  return (
    <header className="border-b border-border bg-surface/80 backdrop-blur sticky top-0 z-20">
      <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2 mr-2 shrink-0">
          <Zap size={18} className="text-accent" />
          <span className="font-mono text-sm font-medium text-text">FormSynth</span>
        </div>

        <input
          className="input flex-1 min-w-[260px] font-mono text-xs"
          placeholder="https://docs.google.com/forms/d/e/.../viewform"
          value={url}
          onChange={e => setUrl(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleParse()}
        />

        <button className="btn-primary flex items-center gap-2 shrink-0" onClick={handleParse} disabled={parsing || !url}>
          {parsing ? <Loader2 size={14} className="animate-spin" /> : null}
          {parsing ? 'Парсинг…' : 'Парсить'}
        </button>

        <div className="h-6 w-px bg-border mx-1" />

        <button
          className="btn-primary flex items-center gap-2 shrink-0"
          onClick={handleStart}
          disabled={!form || isRunning}
        >
          <Play size={14} />
          Старт
        </button>

        <button
          className={clsx('btn flex items-center gap-2 shrink-0', isPaused
            ? 'bg-accent/20 text-accent border border-accent/30 hover:bg-accent/30'
            : 'btn-ghost')}
          onClick={handlePause}
          disabled={!canControl}
        >
          <Pause size={14} />
          {isPaused ? 'Продолжить' : 'Пауза'}
        </button>

        <button className="btn-danger flex items-center gap-2 shrink-0" onClick={handleStop} disabled={!canControl}>
          <Square size={14} />
          Стоп
        </button>

        <div className="h-6 w-px bg-border mx-1" />

        <button className="btn-ghost flex items-center gap-2 shrink-0" title="Экспорт конфига" onClick={handleExport}>
          <Download size={14} />
        </button>

        <label className="btn-ghost flex items-center gap-2 shrink-0 cursor-pointer" title="Импорт конфига">
          <Upload size={14} />
          <input type="file" accept=".json" className="hidden" onChange={handleImport} />
        </label>
      </div>
    </header>
  )
}

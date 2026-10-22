import { useStore } from '../store'
import clsx from 'clsx'

const STATUS_LABEL: Record<string, string> = {
  running:   'Работает',
  paused:    'Пауза',
  completed: 'Завершено',
  failed:    'Ошибка',
  cancelled: 'Отменено',
  pending:   'Ожидание',
}

const STATUS_COLOR: Record<string, string> = {
  running:   'text-accent',
  paused:    'text-warn',
  completed: 'text-accent',
  failed:    'text-error',
  cancelled: 'text-muted',
  pending:   'text-muted',
}

export function JobStatusBar() {
  const { activeJob } = useStore()
  if (!activeJob) return null

  const pct = activeJob.total > 0
    ? Math.round((activeJob.progress / activeJob.total) * 100)
    : 0

  return (
    <div className="border-b border-border bg-surface/50 px-4 py-2">
      <div className="max-w-[1600px] mx-auto flex items-center gap-4">
        <span className={clsx('font-mono text-xs font-medium uppercase', STATUS_COLOR[activeJob.status])}>
          {activeJob.status === 'running' && (
            <span className="inline-block w-2 h-2 rounded-full bg-accent mr-1.5 animate-pulse-dot" />
          )}
          {STATUS_LABEL[activeJob.status] ?? activeJob.status}
        </span>

        <div className="flex-1 bg-border rounded-full h-1.5 overflow-hidden">
          <div
            className="h-full bg-accent transition-all duration-300 rounded-full"
            style={{ width: `${pct}%` }}
          />
        </div>

        <div className="flex items-center gap-4 font-mono text-xs shrink-0">
          <span className="text-muted">{activeJob.progress}/{activeJob.total}</span>
          <span className="text-accent">✓ {activeJob.success_count}</span>
          <span className="text-error">✗ {activeJob.error_count}</span>
          <span className="text-muted">{pct}%</span>
        </div>
      </div>
    </div>
  )
}

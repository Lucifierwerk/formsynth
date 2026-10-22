import { useEffect, useRef } from 'react'
import { Trash2 } from 'lucide-react'
import { useStore } from '../store'
import clsx from 'clsx'

const LEVEL_STYLE: Record<string, string> = {
  INFO:    'text-blue-400',
  SUCCESS: 'text-accent',
  WARNING: 'text-warn',
  ERROR:   'text-error',
}

const LEVEL_PREFIX: Record<string, string> = {
  INFO:    '[ИНФО]  ',
  SUCCESS: '[ОК]    ',
  WARNING: '[ПРЕДУПР]',
  ERROR:   '[ОШИБКА]',
}

export function LogsPanel() {
  const { logs, clearLogs } = useStore()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs.length])

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between mb-3 shrink-0">
        <h3 className="font-semibold text-text text-sm">
          Логи <span className="text-muted font-normal font-mono text-xs ml-2">{logs.length} записей</span>
        </h3>
        <button className="btn-ghost flex items-center gap-1 py-1 px-2 text-xs" onClick={clearLogs}>
          <Trash2 size={12} /> Очистить
        </button>
      </div>

      <div className="flex-1 overflow-y-auto bg-bg rounded-xl border border-border p-3 font-mono text-xs space-y-0.5 min-h-0">
        {logs.length === 0 && (
          <p className="text-muted text-center py-8 font-sans">Логи пусты. Запустите задачу для отображения активности.</p>
        )}
        {logs.map((entry, i) => (
          <div key={i} className="flex gap-2 leading-5 hover:bg-surface/50 px-1 rounded">
            <span className="text-muted/50 shrink-0 select-none">{entry.ts.slice(11, 19)}</span>
            <span className={clsx('shrink-0 select-none', LEVEL_STYLE[entry.level] ?? 'text-muted')}>
              {LEVEL_PREFIX[entry.level] ?? entry.level}
            </span>
            <span className="text-text/80 break-all">{entry.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

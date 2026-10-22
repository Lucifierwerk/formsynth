import { useStore } from '../store'
import clsx from 'clsx'

const AVAILABLE_PROFILES = [
  { id: 'young_male',       label: 'Молодой мужчина',    emoji: '🧑' },
  { id: 'young_female',     label: 'Молодая женщина',    emoji: '👩' },
  { id: 'premium_customer', label: 'Премиум-клиент',     emoji: '💎' },
  { id: 'budget_buyer',     label: 'Бюджетный',          emoji: '💰' },
  { id: 'event_customer',   label: 'Клиент мероприятия', emoji: '🎉' },
]

function NumField({
  label, value, onChange, min, max, step, unit
}: {
  label: string; value: number; onChange: (v: number) => void
  min?: number; max?: number; step?: number; unit?: string
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex items-center gap-1">
        <input
          type="number" className="input w-full" min={min} max={max} step={step ?? 1}
          value={value}
          onChange={e => onChange(Number(e.target.value))}
        />
        {unit && <span className="text-xs text-muted shrink-0">{unit}</span>}
      </div>
    </div>
  )
}

export function SettingsPanel() {
  const { jobSettings, setJobSettings } = useStore()

  function toggleProfile(id: string) {
    const p = jobSettings.profiles
    setJobSettings({
      profiles: p.includes(id) ? p.filter(x => x !== id) : [...p, id]
    })
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="font-semibold text-text mb-3 text-sm">Параметры запуска</h3>
        <div className="grid grid-cols-2 gap-3">
          <NumField label="Кол-во ответов" value={jobSettings.total}
            onChange={v => setJobSettings({ total: v })} min={1} max={10000} />
          <NumField label="Параллельность" value={jobSettings.concurrency}
            onChange={v => setJobSettings({ concurrency: v })} min={1} max={10} />
          <NumField label="Задержка мин" value={jobSettings.min_delay}
            onChange={v => setJobSettings({ min_delay: v })} min={0} step={0.5} unit="с" />
          <NumField label="Задержка макс" value={jobSettings.max_delay}
            onChange={v => setJobSettings({ max_delay: v })} min={0} step={0.5} unit="с" />
          <NumField label="Повторов" value={jobSettings.retry_count}
            onChange={v => setJobSettings({ retry_count: v })} min={0} max={5} />
          <NumField label="Размер пачки" value={jobSettings.batch_size}
            onChange={v => setJobSettings({ batch_size: v })} min={1} />
          <NumField label="Пауза пачки" value={jobSettings.batch_pause}
            onChange={v => setJobSettings({ batch_pause: v })} min={0} step={0.5} unit="с" />
        </div>
      </div>

      <div>
        <h3 className="font-semibold text-text mb-2 text-sm">Профили респондентов</h3>
        <p className="text-xs text-muted mb-3">
          Профили смещают веса ответов. Оставьте пустым для равномерного распределения.
        </p>
        <div className="flex flex-wrap gap-2">
          {AVAILABLE_PROFILES.map(p => {
            const active = jobSettings.profiles.includes(p.id)
            return (
              <button
                key={p.id}
                onClick={() => toggleProfile(p.id)}
                className={clsx(
                  'tag px-3 py-1.5 border cursor-pointer transition-all text-xs',
                  active
                    ? 'border-accent/50 bg-accent/10 text-accent'
                    : 'border-border bg-surface text-muted hover:border-border hover:text-text'
                )}
              >
                {p.emoji} {p.label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

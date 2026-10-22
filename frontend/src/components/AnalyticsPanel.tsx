import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts'
import { useStore } from '../store'

const COLORS = ['#5dfc8d', '#3bc6ff', '#f5a623', '#ff4d6d', '#b388ff', '#80deea']

export function AnalyticsPanel() {
  const { activeJob, questions } = useStore()

  const successCount = activeJob?.success_count ?? 0

  const questionStats = useMemo(() => {
    return questions
      .filter(q => q.options.length > 0)
      .map(q => {
        const total = Math.max(successCount, 1)
        const enabledOpts = q.options.filter(o => o.enabled)
        const totalW = enabledOpts.reduce((s, o) => s + o.weight, 0) || 1
        const data = enabledOpts.map(o => ({
          name: o.value.length > 22 ? o.value.slice(0, 22) + '…' : o.value,
          count: Math.round((o.weight / totalW) * total),
          weight: o.weight,
        }))
        return { question: q, data }
      })
  }, [questions, successCount])

  if (questions.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-muted text-sm">
        Спарсите форму для отображения аналитики
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Отправлено" value={activeJob?.success_count ?? 0} color="text-accent" />
        <Stat label="Ошибки" value={activeJob?.error_count ?? 0} color="text-error" />
        <Stat label="Прогресс" value={`${activeJob?.total ? Math.round((activeJob.progress / activeJob.total) * 100) : 0}%`} color="text-text" />
      </div>

      {questionStats.map(({ question, data }) => (
        <div key={question.id} className="card">
          <p className="text-xs font-medium text-text mb-3 line-clamp-1">{question.title}</p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
              <XAxis type="number" tick={{ fontSize: 10, fill: '#4a4f5c' }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#161920', border: '1px solid #252830', borderRadius: 8, fontSize: 11 }}
                labelStyle={{ color: '#e2e8f0' }}
                cursor={{ fill: '#252830' }}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted font-mono mt-1">расчётное распределение · {successCount} ответов</p>
        </div>
      ))}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div className="card text-center">
      <p className={`text-2xl font-mono font-medium ${color}`}>{value}</p>
      <p className="text-xs text-muted mt-1">{label}</p>
    </div>
  )
}

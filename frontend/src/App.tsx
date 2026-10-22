import { Toolbar } from './components/Toolbar'
import { JobStatusBar } from './components/JobStatusBar'
import { QuestionPanel } from './components/QuestionPanel'
import { SettingsPanel } from './components/SettingsPanel'
import { LogsPanel } from './components/LogsPanel'
import { AnalyticsPanel } from './components/AnalyticsPanel'
import { useStore } from './store'
import clsx from 'clsx'

const TABS = [
  { id: 'config',    label: 'Настройки' },
  { id: 'logs',      label: 'Логи' },
  { id: 'analytics', label: 'Аналитика' },
] as const

export default function App() {
  const { activeTab, setActiveTab } = useStore()

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <Toolbar />
      <JobStatusBar />

      {/* Tab bar */}
      <div className="border-b border-border bg-surface/30 px-4">
        <div className="max-w-[1600px] mx-auto flex gap-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={clsx(
                'px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
                activeTab === t.id
                  ? 'border-accent text-accent'
                  : 'border-transparent text-muted hover:text-text'
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <main className="flex-1 overflow-hidden">
        <div className="max-w-[1600px] mx-auto px-4 py-5 h-full">

          {activeTab === 'config' && (
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5 h-full">
              {/* Left — questions */}
              <div className="overflow-y-auto pr-1 space-y-3 animate-fade-in">
                <QuestionPanel />
              </div>
              {/* Right — settings */}
              <div className="overflow-y-auto animate-fade-in">
                <div className="card">
                  <SettingsPanel />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'logs' && (
            <div className="h-[calc(100vh-160px)] animate-fade-in">
              <LogsPanel />
            </div>
          )}

          {activeTab === 'analytics' && (
            <div className="overflow-y-auto animate-fade-in pb-8">
              <AnalyticsPanel />
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

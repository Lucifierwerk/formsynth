import { useState, useRef, useCallback } from 'react'
import { ChevronDown, ChevronRight, ToggleLeft, ToggleRight, Plus, X, AlertTriangle, ClipboardList } from 'lucide-react'
import { useStore } from '../store'
import type { Question, Option, TextPoolItem } from '../types'
import clsx from 'clsx'

const QTYPE_LABEL: Record<string, { label: string; color: string }> = {
  single:   { label: 'Один вариант',    color: 'bg-blue-500/20 text-blue-300' },
  multi:    { label: 'Несколько',        color: 'bg-purple-500/20 text-purple-300' },
  text:     { label: 'Текст',            color: 'bg-yellow-500/20 text-yellow-300' },
  textarea: { label: 'Параграф',         color: 'bg-orange-500/20 text-orange-300' },
}

// ── Option row for single/multi questions ─────────────────────────────────────

function OptionRow({ opt, onChange }: {
  opt: Option
  onChange: (patch: Partial<Option>) => void
}) {
  const hasNav    = opt.go_to_page != null
  const excluded  = opt.enabled && opt.weight === 0   // enabled but weight=0 → never picked
  const dimmed    = !opt.enabled || excluded

  return (
    <div className={clsx(
      'flex items-center gap-3 py-1.5 px-2 rounded-lg transition-colors',
      dimmed ? 'opacity-40' : ''
    )}>
      <button onClick={() => onChange({ enabled: !opt.enabled })} className="shrink-0 text-muted hover:text-accent transition-colors">
        {opt.enabled ? <ToggleRight size={16} className="text-accent" /> : <ToggleLeft size={16} />}
      </button>
      <span className="flex-1 text-sm text-text truncate font-sans">{opt.value || '—'}</span>
      {excluded && (
        <span className="text-xs text-muted shrink-0" title="Вес = 0: вариант никогда не выбирается">исключён</span>
      )}
      {hasNav && !excluded && (
        <span className="text-xs font-mono text-blue-400 shrink-0" title="Навигация к разделу">
          → р.{(opt.go_to_page ?? 0) + 1}
        </span>
      )}
      <div className="flex items-center gap-2 shrink-0">
        <input
          type="range" min={0} max={20} step={1}
          value={opt.weight}
          onChange={e => onChange({ weight: Number(e.target.value) })}
          className="w-20 accent-accent"
          disabled={!opt.enabled}
        />
        <span className="font-mono text-xs text-muted w-4 text-right">{opt.weight}</span>
      </div>
    </div>
  )
}

// ── Text pool editor for text/textarea questions ───────────────────────────────

function TextPoolEditor({ q }: { q: Question }) {
  const { updateQuestion } = useStore()
  const [draft, setDraft] = useState('')
  const [bulkMode, setBulkMode] = useState(false)
  const [bulkText, setBulkText] = useState('')
  const [probMode, setProbMode] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const pool = q.text_pool
  const totalWeight = pool.reduce((acc, it) => (
    acc + (it.enabled && it.weight > 0 ? it.weight : 0)
  ), 0)
  const enabledPositive = pool.filter(it => it.enabled && it.weight > 0)
  const isUniform = enabledPositive.length > 1
    ? enabledPositive.every(it => it.weight === enabledPositive[0].weight)
    : true
  const showProbControls = probMode || !isUniform

  const addItems = useCallback((raw: string) => {
    const lines = raw.split(/\r?\n/).map(s => s.trim()).filter(Boolean)
    if (!lines.length) return
    const existing = new Set(pool.map(i => i.value))
    const fresh: TextPoolItem[] = lines
      .filter(v => !existing.has(v))
      .map(v => ({ value: v, weight: 1, enabled: true }))
    if (fresh.length) updateQuestion(q.id, { text_pool: [...pool, ...fresh] })
  }, [pool, q.id, updateQuestion])

  function add() {
    const val = draft.trim()
    if (!val) return
    addItems(val)
    setDraft('')
    inputRef.current?.focus()
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData('text')
    if (!text.includes('\n')) return          // одна строка — обычная вставка
    e.preventDefault()
    addItems(text)
    setDraft('')
  }

  function commitBulk() {
    addItems(bulkText)
    setBulkText('')
    setBulkMode(false)
  }

  function remove(idx: number) {
    updateQuestion(q.id, { text_pool: pool.filter((_, i) => i !== idx) })
  }

  function updateItem(idx: number, patch: Partial<TextPoolItem>) {
    const next = pool.map((it, i) => i === idx ? { ...it, ...patch } : it)
    updateQuestion(q.id, { text_pool: next })
  }

  function clearAll() {
    updateQuestion(q.id, { text_pool: [] })
  }

  return (
    <div className="px-2 space-y-2.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="label">Пул ответов</span>
          {pool.length > 0 && (
            <span className="font-mono text-xs text-muted">{pool.length} вар.</span>
          )}
          {pool.length > 1 && isUniform && enabledPositive.length > 1 && (
            <span className="tag bg-muted/20 text-muted shrink-0" title="Все включённые варианты выбираются равновероятно">
              равновероятно
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {pool.length > 1 && (
            <button
              className={`text-xs transition-colors ${showProbControls ? 'text-accent' : 'text-muted hover:text-text'}`}
              onClick={() => setProbMode(v => !v)}
              title="Показать/скрыть настройку вероятностей"
            >
              Настроить вероятности
            </button>
          )}
          <button
            className={`text-xs transition-colors flex items-center gap-1 ${bulkMode ? 'text-accent' : 'text-muted hover:text-text'}`}
            onClick={() => setBulkMode(v => !v)}
            title="Вставить список"
          >
            <ClipboardList size={12} />
            Вставить списком
          </button>
          {pool.length > 0 && (
            <button className="text-xs text-muted hover:text-error transition-colors" onClick={clearAll}>
              очистить
            </button>
          )}
        </div>
      </div>

      {/* Bulk paste textarea */}
      {bulkMode && (
        <div className="space-y-1.5">
          <textarea
            autoFocus
            className="input font-mono text-xs resize-y w-full"
            rows={5}
            placeholder={"Вставьте список ответов (каждый с новой строки)…\n\nНапример:\nОтлично\nХорошо\nУдовлетворительно"}
            value={bulkText}
            onChange={e => setBulkText(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) commitBulk() }}
          />
          <div className="flex gap-2 justify-end">
            <button className="btn-ghost text-xs px-3 py-1" onClick={() => { setBulkMode(false); setBulkText('') }}>
              Отмена
            </button>
            <button className="btn-primary text-xs px-3 py-1" onClick={commitBulk}>
              Добавить ({bulkText.split('\n').filter(s => s.trim()).length})
            </button>
          </div>
        </div>
      )}

      {/* Empty state warning */}
      {pool.length === 0 && !bulkMode && (
        <div className="flex items-start gap-2 rounded-lg bg-warn/10 border border-warn/20 px-3 py-2">
          <AlertTriangle size={13} className="text-warn shrink-0 mt-0.5" />
          <p className="text-xs text-warn/80 leading-relaxed">
            Пул пуст — будет использован стандартный набор нейтральных фраз.
            Добавьте свои варианты ответов для этого вопроса.
          </p>
        </div>
      )}

      {/* Pool items */}
      {pool.length > 0 && (
        <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
          {pool.map((item, i) => {
            const excluded = item.enabled && item.weight === 0
            const dimmed = !item.enabled || excluded
            const pct = (item.enabled && item.weight > 0 && totalWeight > 0)
              ? Math.round((item.weight / totalWeight) * 100)
              : 0
            return (
            <div
              key={i}
              className={clsx(
                'group flex items-center gap-2 bg-surface/60 hover:bg-surface rounded-lg px-2.5 py-1.5 transition-colors',
                dimmed ? 'opacity-40' : '',
              )}
            >
              <span className="text-muted font-mono text-xs shrink-0 w-5 text-right select-none">{i + 1}.</span>
              <button
                onClick={() => updateItem(i, { enabled: !item.enabled })}
                className="shrink-0 text-muted hover:text-accent transition-colors"
                title={item.enabled ? 'Выключить вариант' : 'Включить вариант'}
              >
                {item.enabled ? <ToggleRight size={14} className="text-accent" /> : <ToggleLeft size={14} />}
              </button>
              <span className="flex-1 text-xs text-text break-words font-mono">{item.value}</span>
              {excluded && (
                <span className="text-xs text-muted shrink-0" title="Вес = 0: вариант никогда не выбирается">исключён</span>
              )}
              {showProbControls && (
                <div className="flex items-center gap-2 shrink-0">
                  <input
                    type="range" min={0} max={20} step={1}
                    value={item.weight}
                    onChange={e => updateItem(i, { weight: Number(e.target.value) })}
                    className="w-20 accent-accent"
                    disabled={!item.enabled}
                  />
                  <span className="font-mono text-xs text-muted w-12 text-right" title="Нормализованная вероятность среди включённых вариантов">
                    {pct}%
                  </span>
                </div>
              )}
              <button
                onClick={() => remove(i)}
                className="shrink-0 text-muted hover:text-error transition-colors opacity-0 group-hover:opacity-100"
                title="Удалить"
              >
                <X size={12} />
              </button>
            </div>
          )})}
        </div>
      )}

      {/* Single-item input */}
      {!bulkMode && (
        <div className="flex gap-2">
          <input
            ref={inputRef}
            className="input flex-1 text-xs font-mono"
            placeholder="Введите вариант или вставьте список (Ctrl+V)…"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && add()}
            onPaste={handlePaste}
          />
          <button
            className="btn-ghost px-3 py-1 text-accent hover:text-accent shrink-0"
            onClick={add}
            title="Добавить"
          >
            <Plus size={14} />
          </button>
        </div>
      )}
    </div>
  )
}

// ── Question card ─────────────────────────────────────────────────────────────

function QuestionCard({ q }: { q: Question }) {
  const { updateQuestion } = useStore()
  const [expanded, setExpanded] = useState(true)
  const info = QTYPE_LABEL[q.qtype] ?? { label: q.qtype, color: 'bg-muted/20 text-muted' }

  const isText = q.qtype === 'text' || q.qtype === 'textarea'
  const hasEmptyPool = isText && q.text_pool.length === 0
  const dimmed = !q.enabled

  function updateOption(idx: number, patch: Partial<Option>) {
    const options = q.options.map((o, i) => i === idx ? { ...o, ...patch } : o)
    updateQuestion(q.id, { options })
  }

  return (
    <div className={clsx('card animate-slide-up', dimmed ? 'opacity-50' : '')}>
      <button
        className="w-full flex items-center gap-3 text-left"
        onClick={() => setExpanded(e => !e)}
      >
        {expanded ? <ChevronDown size={14} className="text-muted shrink-0" /> : <ChevronRight size={14} className="text-muted shrink-0" />}
        <span className="flex-1 text-sm font-medium text-text line-clamp-1">{q.title}</span>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); updateQuestion(q.id, { enabled: !q.enabled }) }}
          className="shrink-0 text-muted hover:text-accent transition-colors"
          title={q.enabled ? 'Выключить вопрос' : 'Включить вопрос'}
        >
          {q.enabled ? <ToggleRight size={16} className="text-accent" /> : <ToggleLeft size={16} />}
        </button>
        {hasEmptyPool && !expanded && (
          <span title="Пул ответов пуст" className="shrink-0">
            <AlertTriangle size={13} className="text-warn shrink-0" />
          </span>
        )}
        <span className={clsx('tag shrink-0', info.color)}>{info.label}</span>
        {q.required && <span className="tag bg-error/20 text-error shrink-0">обязательный</span>}
      </button>

      {expanded && (
        <div className="mt-3 space-y-1">
          {(q.qtype === 'single' || q.qtype === 'multi') && q.options.length > 0 && (
            <>
              <div className="flex items-center justify-between px-2 mb-2">
                <span className="label">Варианты и веса</span>
                {q.qtype === 'multi' && (
                  <div className="flex items-center gap-3 text-xs text-muted font-mono">
                    <label className="flex items-center gap-1">
                      мин
                      <input type="number" min={1} max={q.options.length} value={q.min_select}
                        onChange={e => updateQuestion(q.id, { min_select: Number(e.target.value) })}
                        className="w-10 input text-center py-0.5 px-1" />
                    </label>
                    <label className="flex items-center gap-1">
                      макс
                      <input type="number" min={1} max={q.options.length} value={q.max_select}
                        onChange={e => updateQuestion(q.id, { max_select: Number(e.target.value) })}
                        className="w-10 input text-center py-0.5 px-1" />
                    </label>
                  </div>
                )}
              </div>
              {q.options.map((opt, i) => (
                <OptionRow key={i} opt={opt} onChange={p => updateOption(i, p)} />
              ))}
            </>
          )}

          {isText && <TextPoolEditor q={q} />}
        </div>
      )}
    </div>
  )
}

// ── Panel root ────────────────────────────────────────────────────────────────

export function QuestionPanel() {
  const { form, questions } = useStore()

  if (!form) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-muted text-sm gap-2">
        <span className="text-3xl opacity-20">⟳</span>
        <p>Вставьте ссылку на форму Google и нажмите «Парсить»</p>
      </div>
    )
  }

  const emptyPools = questions.filter(
    q => (q.qtype === 'text' || q.qtype === 'textarea') && q.text_pool.length === 0
  )

  // Group questions by page_index
  const pageMap = new Map<number, Question[]>()
  for (const q of questions) {
    const pi = q.page_index ?? 0
    if (!pageMap.has(pi)) pageMap.set(pi, [])
    pageMap.get(pi)!.push(q)
  }
  const sortedPages = Array.from(pageMap.keys()).sort((a, b) => a - b)
  const isMultiPage = sortedPages.length > 1

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-semibold text-text">{form.title}</h2>
          <p className="text-xs text-muted font-mono mt-0.5">
            {questions.length} вопр.
            {isMultiPage && ` · ${sortedPages.length} разделов`}
            {' · '}id: {form.form_id.slice(0, 24)}…
          </p>
        </div>
        {emptyPools.length > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-warn">
            <AlertTriangle size={13} />
            <span>{emptyPools.length} текст. {emptyPools.length === 1 ? 'вопрос' : 'вопроса'} без пула</span>
          </div>
        )}
      </div>

      {/* Pages */}
      {sortedPages.map((pageIdx, sectionNum) => (
        <div key={pageIdx}>
          {isMultiPage && (
            <div className="flex items-center gap-2 mb-2 mt-4 first:mt-0">
              <div className="h-px flex-1 bg-border" />
              <span className="text-xs font-mono text-muted px-2 shrink-0">
                Раздел {sectionNum + 1}
              </span>
              <div className="h-px flex-1 bg-border" />
            </div>
          )}
          {pageMap.get(pageIdx)!.map(q => (
            <div key={q.id} className="mb-3">
              <QuestionCard q={q} />
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

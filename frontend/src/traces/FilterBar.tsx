/** Search / filter bar for the traces list (thread_id, model, error, tool,
 * date range). Local draft state; Apply lifts it to the parent, Clear resets. */

import { useEffect, useState } from 'react'
import type { TraceFilters } from './api'

const MODELS = ['claude-sonnet-4-6', 'claude-haiku-4-5']

const inputCls =
  'w-full rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-sm text-zinc-800 placeholder:text-zinc-400 focus:border-accent focus:ring-2 focus:ring-accent/20 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100'
const labelCls =
  'mb-1 block text-[11px] font-medium tracking-wide text-zinc-500 uppercase dark:text-zinc-400'

export function FilterBar({
  value,
  onChange,
}: Readonly<{ value: TraceFilters; onChange: (f: TraceFilters) => void }>) {
  const [draft, setDraft] = useState<TraceFilters>(value)

  // Keep the draft in sync when the parent clears filters externally.
  useEffect(() => setDraft(value), [value])

  function apply(e: React.FormEvent) {
    e.preventDefault()
    const clean: TraceFilters = {}
    if (draft.thread_id?.trim()) clean.thread_id = draft.thread_id.trim()
    if (draft.model) clean.model = draft.model
    if (draft.had_error !== undefined) clean.had_error = draft.had_error
    if (draft.tool?.trim()) clean.tool = draft.tool.trim()
    if (draft.since) clean.since = draft.since
    if (draft.until) clean.until = draft.until
    onChange(clean)
  }

  function set<K extends keyof TraceFilters>(key: K, v: TraceFilters[K]) {
    setDraft((d) => ({ ...d, [key]: v }))
  }

  const errValue =
    draft.had_error === undefined ? '' : draft.had_error ? 'true' : 'false'

  return (
    <form
      onSubmit={apply}
      className="rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <div>
          <label className={labelCls} htmlFor="f-thread">
            Thread id
          </label>
          <input
            id="f-thread"
            className={inputCls}
            placeholder="hashed id"
            value={draft.thread_id ?? ''}
            onChange={(e) => set('thread_id', e.target.value)}
          />
        </div>
        <div>
          <label className={labelCls} htmlFor="f-model">
            Model
          </label>
          <select
            id="f-model"
            className={inputCls}
            value={draft.model ?? ''}
            onChange={(e) => set('model', e.target.value || undefined)}
          >
            <option value="">Any</option>
            {MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls} htmlFor="f-error">
            Error
          </label>
          <select
            id="f-error"
            className={inputCls}
            value={errValue}
            onChange={(e) =>
              set(
                'had_error',
                e.target.value === '' ? undefined : e.target.value === 'true',
              )
            }
          >
            <option value="">Any</option>
            <option value="true">Errored</option>
            <option value="false">Clean</option>
          </select>
        </div>
        <div>
          <label className={labelCls} htmlFor="f-tool">
            Tool
          </label>
          <input
            id="f-tool"
            className={inputCls}
            placeholder="search_knowledge_base"
            value={draft.tool ?? ''}
            onChange={(e) => set('tool', e.target.value)}
          />
        </div>
        <div>
          <label className={labelCls} htmlFor="f-since">
            Since
          </label>
          <input
            id="f-since"
            type="datetime-local"
            className={inputCls}
            value={draft.since ?? ''}
            onChange={(e) => set('since', e.target.value || undefined)}
          />
        </div>
        <div>
          <label className={labelCls} htmlFor="f-until">
            Until
          </label>
          <input
            id="f-until"
            type="datetime-local"
            className={inputCls}
            value={draft.until ?? ''}
            onChange={(e) => set('until', e.target.value || undefined)}
          />
        </div>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          type="submit"
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-strong"
        >
          Apply
        </button>
        <button
          type="button"
          onClick={() => {
            setDraft({})
            onChange({})
          }}
          className="rounded-md border border-zinc-200 px-3 py-1.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
        >
          Clear
        </button>
      </div>
    </form>
  )
}

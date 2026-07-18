/**
 * Data-flow registry — auto-discovered, mirroring the file-flow registry.
 *
 * Every file in `dataflows/` that default-exports a `DataFlowDescriptor` is
 * picked up via Vite's glob import. Wave B adds Money and Brokerage by
 * dropping one descriptor file each — no central list is edited, so parallel
 * flow changes never collide on a shared file.
 */

import type { DataFlowDescriptor } from './dataflow'

const modules = import.meta.glob<{ default: DataFlowDescriptor }>('./dataflows/*.ts', {
  eager: true,
})

/** All registered data flows, ordered for the sticker row. */
export const DATA_FLOWS: DataFlowDescriptor[] = Object.values(modules)
  .map((m) => m.default)
  .filter((d): d is DataFlowDescriptor => Boolean(d))
  .sort((a, b) => a.order - b.order)

const BY_KEY = new Map(DATA_FLOWS.map((f) => [f.key, f]))

export function getDataFlow(key: string): DataFlowDescriptor | undefined {
  return BY_KEY.get(key)
}

/** Keyword-route composer text to a data flow, or null when nothing matches.
 *  The shell checks data flows before file flows (prototype routing order). */
export function matchDataFlow(text: string): DataFlowDescriptor | null {
  for (const flow of DATA_FLOWS) {
    if (flow.keywords.test(text)) return flow
  }
  return null
}

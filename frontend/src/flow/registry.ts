/**
 * Flow registry — auto-discovered, NOT a hand-maintained array.
 *
 * Every file in `flows/` that default-exports a `FlowDescriptor` is picked up
 * here via Vite's glob import. A Wave-1 report is added by dropping one file
 * into `flows/`; no central list is edited, so parallel flow changes never
 * collide on a shared file (design Decision 8).
 */

import type { FlowDescriptor } from './types'

const modules = import.meta.glob<{ default: FlowDescriptor }>('./flows/*.ts', { eager: true })

/** All registered flows, ordered for the home screen. */
export const FLOWS: FlowDescriptor[] = Object.values(modules)
  .map((m) => m.default)
  .filter((d): d is FlowDescriptor => Boolean(d))
  .sort((a, b) => a.order - b.order)

const BY_KEY = new Map(FLOWS.map((f) => [f.key, f]))

export function getFlow(key: string): FlowDescriptor | undefined {
  return BY_KEY.get(key)
}

/** Keyword-route composer text to a flow, or null when nothing matches. */
export function matchFlow(text: string): FlowDescriptor | null {
  for (const flow of FLOWS) {
    if (flow.keywords.test(text)) return flow
  }
  return null
}

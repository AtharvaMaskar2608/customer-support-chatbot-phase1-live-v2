/**
 * Flow engine — pure, flow-agnostic logic. The React surface (FlowCard,
 * ChatShell) drives these helpers; keeping them pure keeps the engine
 * testable and the descriptors the only thing that varies per flow.
 */

import type { FilledValues, FlowDescriptor, SlotValue } from './types'

/** Sentinel `active` value for the terminal delivery step. */
export const DELIVERY_STEP = '__delivery__' as const
/** Sentinel `active` value while generating (card locked, no widget shown). */
export const LOCKED = null

export type ActiveStep = string | typeof DELIVERY_STEP | typeof LOCKED

/** A single flow's live state within the conversation. */
export interface FlowRun {
  flowKey: string
  values: FilledValues
  /** Slot key being prompted/edited, DELIVERY_STEP, or LOCKED (generating/done). */
  active: ActiveStep
}

/**
 * The first slot with no value, in canonical order — or DELIVERY_STEP when
 * every slot is filled. This is what makes seeding work: pre-fill any subset
 * (contiguous or not) and the engine simply asks the first remaining gap.
 */
export function firstUnfilled(descriptor: FlowDescriptor, values: FilledValues): ActiveStep {
  for (const slot of descriptor.slots) {
    if (values[slot.key] === undefined) return slot.key
  }
  return DELIVERY_STEP
}

/** Start a run, optionally seeded with pre-filled values (LLM-ready). Sticker
 *  entry passes no seed; a future free-text entry may seed several. */
export function startRun(descriptor: FlowDescriptor, seed: FilledValues = {}): FlowRun {
  const values: FilledValues = { ...seed }
  return { flowKey: descriptor.key, values, active: firstUnfilled(descriptor, values) }
}

/** Record a slot answer and advance to the next gap (or delivery). */
export function fillSlot(
  descriptor: FlowDescriptor,
  run: FlowRun,
  slotKey: string,
  value: SlotValue,
): FlowRun {
  const values: FilledValues = { ...run.values, [slotKey]: value }
  return { ...run, values, active: firstUnfilled(descriptor, values) }
}

/** Re-open an already-filled slot for editing (value retained until re-answered). */
export function editSlot(run: FlowRun, slotKey: string): FlowRun {
  return { ...run, active: slotKey }
}

/** Lock the card (delivery chosen → generating/done); filled slots stay as chips. */
export function lockRun(run: FlowRun): FlowRun {
  return { ...run, active: LOCKED }
}

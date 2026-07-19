/**
 * One-shot count-up: 0 → target over ~680ms with an ease-out cubic, matching
 * the prototype's hero reveal. Runs once on mount — data cards are immutable
 * messages, so the animation never replays on re-render.
 */

import { useEffect, useState } from 'react'

export function useCountUp(target: number, durationMs = 680): number {
  const [value, setValue] = useState(0)
  useEffect(() => {
    let raf = 0
    const t0 = performance.now()
    const step = (t: number) => {
      const p = Math.min(1, (t - t0) / durationMs)
      const eased = 1 - Math.pow(1 - p, 3)
      setValue(Math.round(target * eased))
      if (p < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
    // One-shot reveal on mount by design.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return value
}

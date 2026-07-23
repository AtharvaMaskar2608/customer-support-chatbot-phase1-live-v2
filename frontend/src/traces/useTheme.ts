import { useCallback, useState } from 'react'

/**
 * Operator light/dark toggle for the dashboard. The pre-paint script in
 * traces.html has already stamped `data-theme` from the OS / stored choice;
 * this hook mirrors and flips it, persisting the override to localStorage.
 */

const KEY = 'traces-theme'

function currentTheme(): 'light' | 'dark' {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function useTheme(): { theme: 'light' | 'dark'; toggle: () => void } {
  const [theme, setTheme] = useState<'light' | 'dark'>(currentTheme)
  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark'
      if (next === 'dark') document.documentElement.dataset.theme = 'dark'
      else delete document.documentElement.dataset.theme
      try {
        localStorage.setItem(KEY, next)
      } catch {
        /* localStorage may be unavailable — theme still applies for the session */
      }
      return next
    })
  }, [])
  return { theme, toggle }
}

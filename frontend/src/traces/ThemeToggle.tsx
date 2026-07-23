/** Small light/dark toggle button for the dashboard. */

export function ThemeToggle({
  theme,
  onToggle,
}: Readonly<{ theme: 'light' | 'dark'; onToggle: () => void }>) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label="Toggle theme"
      title="Toggle theme"
      className="grid size-8 place-items-center rounded-lg border border-zinc-200 text-zinc-500 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}

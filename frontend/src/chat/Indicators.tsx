/** Transient conversation indicators: typing dots and the narrated pill. */

export function Typing() {
  return (
    <div className="inline-flex items-center gap-1 self-start rounded-full bg-zinc-100 px-3.5 py-3 dark:bg-zinc-800">
      <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 dark:bg-zinc-500" />
      <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:0.15s] dark:bg-zinc-500" />
      <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:0.3s] dark:bg-zinc-500" />
    </div>
  )
}

/** Narrated-generation pill — a pulsing dot + the current flow-specific caption. */
export function NarratePill({ caption }: Readonly<{ caption: string }>) {
  return (
    <div className="inline-flex items-center gap-2.5 self-start rounded-full bg-zinc-100 px-4 py-2.5 text-[13.5px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
      <span className="size-2 animate-pulse rounded-full bg-accent" />
      {caption}
    </div>
  )
}

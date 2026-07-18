/**
 * The brokerage rate card (brokerage-flow) — a pricing reference, never
 * charges billed.
 *
 * Anatomy per the approved prototype (.bcard): header ("Your brokerage
 * rates" + grouped-by-rate subline) → one statement row per computed rate
 * cluster (label + coverage subline · percentage-primary or flat-₹ value
 * with the official phrasing beneath) → statutory-charges footer note.
 *
 * Clustering is computed from THIS response at render time — slabs are
 * per-client. If any desc fails to parse, or the slab would need more than
 * 6 rows, the card falls back to the plain per-segment list with upstream
 * text verbatim (brokerageCluster.ts owns that honesty valve).
 */

import type { DataCardProps } from '../../flow/dataflow'
import {
  brokerageClusters,
  clusterLabel,
  rateDisplay,
  type BrokerageData,
  type BrokerageGroup,
  type ClusteredItem,
} from './brokerageCluster'
import { DataCardFrame, HeroLabel } from './primitives'

export function BrokerageCard({ data }: Readonly<DataCardProps>) {
  // Sound narrow: the brokerage descriptor pairs this card with fetchBrokerage.
  const d = data as BrokerageData
  const clusters = brokerageClusters(d.groups)

  return (
    <DataCardFrame>
      {/* header */}
      <div className="px-4 pt-3.5 pb-[11px]">
        <HeroLabel>Your brokerage rates</HeroLabel>
        <div className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">
          What you pay to trade — grouped by rate
        </div>
      </div>

      {/* clustered statement rows, or the verbatim per-segment fallback */}
      {clusters ? (
        clusters.map((cluster) => (
          <ClusterRow key={`${cluster[0].rate.unit}|${cluster[0].rate.amt}`} cluster={cluster} />
        ))
      ) : (
        <SegmentList groups={d.groups} />
      )}

      {/* plan-vs-billed honesty */}
      <div className="border-t border-zinc-100 px-4 py-[11px] text-[11px] leading-normal text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
        Plus statutory charges (STT, exchange fees, GST, stamp duty). These are your plan&rsquo;s
        rates — a trade&rsquo;s actual charges are on its contract note.
      </div>
    </DataCardFrame>
  )
}

/** One rate cluster: "All futures / Stock · Index · …" left, "0.2% / ₹20
 *  per ₹10,000 traded" right. Every item in the cluster shares one rate, so
 *  the first item's rate speaks for all of them. */
function ClusterRow({ cluster }: Readonly<{ cluster: ClusteredItem[] }>) {
  const { main, cov } = clusterLabel(cluster)
  const { value, unit } = rateDisplay(cluster[0].rate)
  return (
    <div className="flex items-center justify-between gap-3 border-t border-zinc-100 px-4 py-3 dark:border-zinc-800">
      <div className="min-w-0">
        <div className="text-[13.5px] font-bold">{main}</div>
        {cov && <div className="mt-[3px] text-[11px] text-zinc-400 dark:text-zinc-500">{cov}</div>}
      </div>
      <div className="shrink-0 text-right">
        <div className="text-[15px] font-extrabold tracking-[-0.01em] tabular-nums">{value}</div>
        <div className="mt-0.5 text-[11px] text-zinc-400 tabular-nums dark:text-zinc-500">
          {unit}
        </div>
      </div>
    </div>
  )
}

/** Graceful fallback: segment headers on the track tint, upstream desc
 *  strings verbatim — shown whenever clustering declined to summarize. */
function SegmentList({ groups }: Readonly<{ groups: BrokerageGroup[] }>) {
  return (
    <>
      {groups.map((g) => (
        <div key={g.title}>
          <div className="bg-zinc-100 px-3.5 pt-[11px] pb-1.5 text-[10.5px] font-bold tracking-[0.07em] text-zinc-400 uppercase dark:bg-zinc-800 dark:text-zinc-500">
            {g.title}
          </div>
          {g.list.map((it) => (
            <div
              key={it.title}
              className="flex items-center justify-between gap-3 border-t border-zinc-100 px-4 py-3 dark:border-zinc-800"
            >
              <div className="min-w-0 text-[13.5px] font-bold">{it.title}</div>
              <div className="shrink-0 text-right text-[11px] text-zinc-400 tabular-nums dark:text-zinc-500">
                {it.desc}
              </div>
            </div>
          ))}
        </div>
      ))}
    </>
  )
}

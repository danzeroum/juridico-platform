import * as React from 'react'
import { cn } from '../lib/cn'
import { FRESHNESS_COLORS } from '@juridico/tokens'
import type { FreshnessBand } from '@juridico/tokens'

interface FreshnessSealProps {
  source: string
  lagDays: number
  band: FreshnessBand
  className?: string
}

const bandLabels: Record<FreshnessBand, string> = {
  fresh: 'fresco',
  stale: 'defasado',
  very_stale: 'muito defasado',
}

export function FreshnessSeal({ source, lagDays, band, className }: FreshnessSealProps) {
  const c = FRESHNESS_COLORS[band]
  const isVeryStale = band === 'very_stale'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[5px] font-mono text-[10px] font-medium border',
        className,
      )}
      style={{
        background: c.bg,
        color: c.text,
        borderColor: c.border,
      }}
      title={`${source}: dado de ${lagDays} dias atrás (${bandLabels[band]})`}
    >
      <span
        className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', isVeryStale && 'animate-pulse')}
        style={{ background: c.dot }}
        aria-hidden
      />
      {source} · {lagDays}d
      {isVeryStale && (
        <span className="sr-only"> — dado muito defasado, {lagDays} dias atrás</span>
      )}
    </span>
  )
}

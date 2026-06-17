import * as React from 'react'
import { cn } from '../lib/cn'
import type { ModelStatus } from '@juridico/tokens'

interface HeuristicBadgeProps {
  status: ModelStatus
  size?: 'sm' | 'md'
  className?: string
}

export function HeuristicBadge({ status, size = 'md', className }: HeuristicBadgeProps) {
  const isHeuristica = status === 'heuristica'
  const textSize = size === 'sm' ? 'text-[10px]' : 'text-[11px]'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-chip font-medium border',
        textSize,
        isHeuristica
          ? 'bg-riskMediumBg text-riskMediumText border-[#ecdcae]'
          : 'bg-riskLowBg text-riskLowText border-[#bfe3d0]',
        className,
      )}
    >
      {isHeuristica ? '⚠' : '✓'} {isHeuristica ? 'heurística' : 'calibrado'}
    </span>
  )
}

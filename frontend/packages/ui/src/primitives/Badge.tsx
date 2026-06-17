import * as React from 'react'
import { cn } from '../lib/cn'
import type { RiskLevel, AlertSeverity } from '@juridico/tokens'
import { RISK_COLORS } from '@juridico/tokens'

type BadgeVariant =
  | 'accent'
  | 'muted'
  | 'heuristica'
  | 'calibrado'
  | 'blocked'
  | 'beta'
  | 'live'
  | RiskLevel
  | AlertSeverity

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  dot?: boolean
}

function getVariantStyle(variant: BadgeVariant): string {
  switch (variant) {
    case 'accent':
      return 'bg-accentTintBg text-accent border-accentTintBorder'
    case 'muted':
      return 'bg-surfaceMuted text-textSecondary border-border'
    case 'heuristica':
      return 'bg-riskMediumBg text-riskMediumText border border-[#ecdcae]'
    case 'calibrado':
      return 'bg-riskLowBg text-riskLowText border border-[#bfe3d0]'
    case 'blocked':
      return 'bg-riskCriticalBg text-riskCriticalText border border-[#f0c2bd]'
    case 'beta':
      return 'bg-[#f0eeff] text-[#5b3fd4] border border-[#d5ccff]'
    case 'live':
      return 'bg-riskLowBg text-riskLowText border border-[#bfe3d0]'
    case 'BAIXO':
    case 'LOW':
      return 'bg-riskLowBg text-riskLowText border border-[#bfe3d0]'
    case 'MODERADO':
    case 'MEDIUM':
      return 'bg-riskMediumBg text-riskMediumText border border-[#ecdcae]'
    case 'ALTO':
    case 'HIGH':
      return 'bg-riskHighBg text-riskHighText border border-[#f0cdab]'
    case 'CRITICO':
    case 'CRITICAL':
      return 'bg-riskCriticalBg text-riskCriticalText border border-[#f0c2bd]'
    default:
      return 'bg-surfaceMuted text-textSecondary border-border'
  }
}

export function Badge({ variant = 'muted', dot, className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-chip text-[11px] font-medium border',
        getVariantStyle(variant),
        className,
      )}
      {...props}
    >
      {dot && (
        <span
          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
          style={{ background: 'currentColor' }}
          aria-hidden
        />
      )}
      {children}
    </span>
  )
}

// Mono chip for source citations (DATAJUD, PGFN, etc.)
interface MonoChipProps extends React.HTMLAttributes<HTMLSpanElement> {
  href?: string
}

export function MonoChip({ href, className, children, ...props }: MonoChipProps) {
  const cls = cn(
    'inline-flex items-center px-1.5 py-0.5 rounded-[4px] font-mono text-[10px] font-medium',
    'bg-surfaceMuted text-textSecondary border border-border',
    className,
  )
  if (href) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={cn(cls, 'hover:border-accentTintBorder hover:text-accent')}>
        {children}
      </a>
    )
  }
  return <span className={cls} {...props}>{children}</span>
}

export { RISK_COLORS }

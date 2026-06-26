'use client'
import * as React from 'react'
import { cn } from '../lib/cn'

export interface SegmentedOption {
  id: string
  label: string
}

interface SegmentedProps {
  options: SegmentedOption[]
  value: string
  onChange: (id: string) => void
  /** rótulo acessível do grupo */
  'aria-label'?: string
  className?: string
}

/**
 * Segmented — controle segmentado compacto (pill). Usado para alternâncias curtas
 * como tratamento do feed (Terminal/Timeline) ou cenário de demonstração.
 * Diferente de `Tabs` (que organiza painéis de conteúdo): aqui é uma escolha inline.
 */
export function Segmented({ options, value, onChange, className, ...rest }: SegmentedProps) {
  return (
    <div
      role="radiogroup"
      aria-label={rest['aria-label']}
      className={cn('inline-flex gap-0.5 bg-[#f1f3f6] border border-border rounded-[9px] p-0.5', className)}
    >
      {options.map((o) => {
        const active = o.id === value
        return (
          <button
            key={o.id}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.id)}
            className={cn(
              'px-3 py-1.5 rounded-[7px] text-[12px] font-semibold transition-colors',
              active ? 'bg-surface text-textPrimary shadow-sm' : 'text-textMuted hover:text-textSecondary',
            )}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

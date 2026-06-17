import * as React from 'react'
import { ExternalLink, AlertTriangle } from 'lucide-react'
import { cn } from '../lib/cn'

interface VerifiableCitationChipProps {
  docId: string
  href: string
  label?: string
  similarity?: number
  className?: string
}

export function VerifiableCitationChip({ docId, href, label, similarity, className }: VerifiableCitationChipProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-chip text-[11px] font-mono font-medium',
        'bg-accentTintBg text-accent border border-accentTintBorder',
        'hover:bg-accentTintBgAlt transition-colors duration-[120ms]',
        className,
      )}
      aria-label={`Jurisprudência ${docId} — abrir no DATAJUD (nova aba)`}
    >
      {label ?? docId}
      {similarity !== undefined && (
        <span className="text-[10px] opacity-70">{Math.round(similarity * 100)}%</span>
      )}
      <ExternalLink className="w-2.5 h-2.5 opacity-60" aria-hidden />
    </a>
  )
}

interface AntiHallucinationGuardProps {
  count: number
  threshold?: number
  className?: string
}

export function AntiHallucinationGuard({ count, threshold = 3, className }: AntiHallucinationGuardProps) {
  if (count >= threshold) return null
  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-[6px] bg-riskMediumBg border border-[#ecdcae]',
        className,
      )}
      role="alert"
    >
      <AlertTriangle className="w-3.5 h-3.5 text-riskMediumText flex-shrink-0" aria-hidden />
      <span className="text-[12px] text-riskMediumText font-medium">
        ⚠ {count} precedente{count !== 1 ? 's' : ''} — revisar com jurista
      </span>
    </div>
  )
}

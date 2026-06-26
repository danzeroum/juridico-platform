import * as React from 'react'
import { cn } from '../lib/cn'

export type Provenance = 'ia' | 'parcial' | 'template'

const META: Record<Provenance, { label: string; cls: string }> = {
  ia: { label: '✦ via IA', cls: 'bg-accentTintBg text-accent border-accentTintBorder' },
  parcial: { label: 'via IA · parcial', cls: 'bg-riskMediumBg text-riskMediumText border-[#ecdcae]' },
  template: { label: 'via template', cls: 'bg-surfaceMuted text-textSecondary border-border' },
}

interface ProvenanceTagProps {
  value: Provenance
  className?: string
}

/**
 * ProvenanceTag — origem do texto de uma seção da defesa.
 * - `ia`       → redigido pelo modelo (azul/accent)
 * - `parcial`  → IA sem reforço de fontes/jurisprudência (âmbar)
 * - `template` → LLM indisponível, gerado por template — exige revisão integral (neutro)
 */
export function ProvenanceTag({ value, className }: ProvenanceTagProps) {
  const m = META[value]
  return (
    <span className={cn('inline-flex items-center font-mono text-[10px] font-semibold px-2 py-0.5 rounded-chip border', m.cls, className)}>
      {m.label}
    </span>
  )
}

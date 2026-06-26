import * as React from 'react'
import { ExternalLink } from 'lucide-react'
import { cn } from '../lib/cn'
import { Badge } from '../primitives/Badge'
import { SectionLabel } from '../primitives/SectionLabel'

export type ProtocolStatus =
  | 'SIMULADO'
  | 'AGUARDA_CREDENCIAIS'
  | 'ENVIADO'
  | 'FALHA'
  | 'CANAL_NAO_SUPORTADO'

export type ProtocolMode = 'simulacao' | 'real' | 'na'

export interface ProtocolStatusCardProps {
  canal: string
  status: ProtocolStatus
  /** número emitido (SIM-… ou nº do portal). null quando não há. */
  numero?: string | null
  mensagem: string
  modo: ProtocolMode
  /** link p/ o portal externo (apenas ENVIADO) */
  url?: string | null
  enviadoEm?: string
  className?: string
}

/** badge variant + rótulo por estado */
const STATUS_META: Record<ProtocolStatus, { variant: React.ComponentProps<typeof Badge>['variant']; label: string }> = {
  SIMULADO: { variant: 'accent', label: 'SIMULADO' },
  AGUARDA_CREDENCIAIS: { variant: 'MODERADO', label: 'AGUARDA CRED.' },
  ENVIADO: { variant: 'BAIXO', label: 'ENVIADO' },
  FALHA: { variant: 'ALTO', label: 'FALHA' },
  CANAL_NAO_SUPORTADO: { variant: 'muted', label: 'NÃO SUPORTADO' },
}

const MODE_META: Record<ProtocolMode, { label: string; cls: string }> = {
  simulacao: { label: 'simulação', cls: 'bg-accentTintBg text-accent border-accentTintBorder' },
  real: { label: 'real', cls: 'bg-riskMediumBg text-riskMediumText border-[#ecdcae]' },
  na: { label: '—', cls: 'bg-surfaceMuted text-textFaint border-border' },
}

/**
 * ProtocolStatusCard — estado da submissão da defesa em um canal externo.
 *
 * Ação sensível: o `modo` (simulação / real) é exibido com destaque porque distingue
 * "nada saiu da plataforma" de "submissão real foi feita". Os 5 estados cobrem o ciclo
 * de protocolo + degradação de portal (sem credenciais / falha / canal não suportado).
 */
export function ProtocolStatusCard({
  canal,
  status,
  numero,
  mensagem,
  modo,
  url,
  enviadoEm,
  className,
}: ProtocolStatusCardProps) {
  const meta = STATUS_META[status]
  const mode = MODE_META[modo]
  return (
    <div className={cn('bg-surface border border-border rounded-card p-5', className)}>
      <div className="flex items-center justify-between gap-3 mb-3.5">
        <SectionLabel>Protocolo · {canal}</SectionLabel>
        <Badge variant={meta.variant} className="font-mono text-[10.5px]">{meta.label}</Badge>
      </div>

      {numero && (
        <>
          <p className="font-mono text-[11px] text-textFaint mb-0.5">número de protocolo</p>
          <p className="font-mono text-[17px] font-semibold text-textPrimary">{numero}</p>
        </>
      )}

      <p className="text-[13px] text-textSecondary leading-relaxed mt-3">{mensagem}</p>

      {status === 'ENVIADO' && url && (
        <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 mt-3.5 text-[12.5px] font-semibold text-accent hover:underline">
          Abrir no portal {canal} <ExternalLink className="w-3 h-3" aria-hidden />
        </a>
      )}

      <div className="flex items-center gap-2 mt-4 pt-3.5 border-t border-[#f0f2f5]">
        <span className="font-mono text-[10.5px] text-textFaint">modo:</span>
        <span className={cn('font-mono text-[10.5px] font-semibold px-2 py-0.5 rounded-[5px] border', mode.cls)}>{mode.label}</span>
        {enviadoEm && <span className="ml-auto font-mono text-[10.5px] text-textFaint">enviado_em: {enviadoEm}</span>}
      </div>
    </div>
  )
}

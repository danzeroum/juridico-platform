import * as React from 'react'
import { ShieldCheck, RefreshCw, Download } from 'lucide-react'
import { cn } from '../lib/cn'
import { Card, SectionLabel } from '../primitives/Card'
import { Button } from '../primitives/Button'

export interface MerkleProof {
  position: 'L' | 'R'
  hash: string
}

export interface MerklePanelProps {
  requestId: string
  leafHash: string
  merkleRoot: string
  proof: MerkleProof[]
  isIntact: boolean
  onReverify?: () => void
  onExportPdf?: () => void
  loading?: boolean
  className?: string
}

export function MerklePanel({
  requestId,
  leafHash,
  merkleRoot,
  proof,
  isIntact,
  onReverify,
  onExportPdf,
  loading,
  className,
}: MerklePanelProps) {
  return (
    <Card padding="none" className={cn('overflow-hidden', className)}>
      {/* Header */}
      <div className="px-5 py-3 bg-sidebarNavy flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-accent" aria-hidden />
          <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-white">
            Decision Ledger · Merkle
          </span>
        </div>
        <span
          className={cn(
            'text-[11px] font-medium px-2 py-0.5 rounded-chip',
            isIntact
              ? 'bg-riskLowBg text-riskLowText'
              : 'bg-riskCriticalBg text-riskCriticalText',
          )}
        >
          {isIntact ? '✓ íntegro' : '✗ divergência'}
        </span>
      </div>

      <div className="p-5 flex flex-col gap-4">
        {/* Identifiers */}
        <div className="grid grid-cols-1 gap-2">
          <HashRow label="request_id" value={requestId} />
          <HashRow label="leaf_hash" value={leafHash} />
          <HashRow label="merkle_root" value={merkleRoot} />
        </div>

        {/* Merkle proof */}
        <div>
          <SectionLabel className="mb-2">Prova de inclusão</SectionLabel>
          <div className="flex flex-col gap-1 bg-surfaceMuted rounded-[8px] p-3">
            {proof.map((step, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px] font-mono text-textSecondary">
                <span
                  className={cn(
                    'w-5 text-center font-bold rounded-[3px] px-1',
                    step.position === 'L' ? 'bg-accentTintBg text-accent' : 'bg-surfaceMuted text-textMuted',
                  )}
                >
                  {step.position}
                </span>
                <span className="truncate text-textMuted">{step.hash}</span>
              </div>
            ))}
            <div className="mt-1 pt-1 border-t border-border flex items-center gap-1 text-[11px] font-mono text-textSecondary">
              <span className="font-bold">↳</span>
              <span className="truncate">{merkleRoot}</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 flex-wrap">
          {onReverify && (
            <Button variant="secondary" size="sm" onClick={onReverify} loading={loading}>
              <RefreshCw className="w-3.5 h-3.5" aria-hidden />
              Reverificar
            </Button>
          )}
          {onExportPdf && (
            <Button variant="secondary" size="sm" onClick={onExportPdf}>
              <Download className="w-3.5 h-3.5" aria-hidden />
              Exportar prova (PDF · ANPD)
            </Button>
          )}
        </div>
      </div>
    </Card>
  )
}

function HashRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-semibold uppercase tracking-[0.04em] text-textSectionLabel">{label}</span>
      <span className="font-mono text-[11px] text-textSecondary break-all">{value}</span>
    </div>
  )
}

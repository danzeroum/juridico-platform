'use client'
import { useState } from 'react'
import { Card, SectionLabel, MerklePanel, Badge } from '@juridico/ui'
import type { MerkleProof } from '@juridico/ui'

const MOCK_DECISIONS = [
  { request_id: 'req_demo_001', product: 'LegalScore', cnpj: '00.000.000/0001-91', ts: '2026-06-17 14:32' },
  { request_id: 'req_demo_002', product: 'TaxPredict', cnpj: 'N/A', ts: '2026-06-17 13:15' },
  { request_id: 'req_demo_003', product: 'ConciliaIA', cnpj: '00.000.000/0001-91', ts: '2026-06-16 09:48' },
]

const PRODUCT_CODE: Record<string, string> = { LegalScore: 'LS', TaxPredict: 'TP', ConciliaIA: 'CC' }

const MOCK_PROOF: MerkleProof[] = [
  { position: 'L', hash: 'sha256:sib1aaaaaa...' },
  { position: 'R', hash: 'sha256:sib2bbbbbb...' },
  { position: 'L', hash: 'sha256:sib3cccccc...' },
]

export default function AuditoriaPage() {
  const [selected, setSelected] = useState(MOCK_DECISIONS[0].request_id)
  const decision = MOCK_DECISIONS.find((d) => d.request_id === selected)!

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-[20px] font-bold text-textPrimary">Auditoria · Decision Ledger</h1>

      <div className="grid grid-cols-3 gap-5">
        {/* Decision list */}
        <div className="flex flex-col gap-2">
          <SectionLabel className="mb-1">Decisões recentes</SectionLabel>
          {MOCK_DECISIONS.map((d) => (
            <button
              key={d.request_id}
              onClick={() => setSelected(d.request_id)}
              className={`text-left rounded-card border p-3 transition-colors ${
                selected === d.request_id
                  ? 'border-accentTintBorder bg-accentTintBg'
                  : 'border-border bg-surface hover:border-accentTintBorder'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-[3px] bg-surfaceMuted text-textSecondary">
                  {PRODUCT_CODE[d.product] ?? d.product}
                </span>
                <span className="text-[11px] text-textSecondary">{d.product}</span>
              </div>
              <p className="font-mono text-[11px] text-textMuted truncate">{d.request_id}</p>
              <p className="font-mono text-[10px] text-textFaint mt-0.5">{d.ts}</p>
            </button>
          ))}
        </div>

        {/* Merkle panel */}
        <div className="col-span-2">
          <MerklePanel
            requestId={decision.request_id}
            leafHash="sha256:a3f9e21b04cc7d88bce45f12abc..."
            merkleRoot="sha256:root1a2b3c4d5e6f7890abcdef..."
            proof={MOCK_PROOF}
            isIntact
            onReverify={() => {}}
            onExportPdf={() => {}}
          />
        </div>
      </div>
    </div>
  )
}

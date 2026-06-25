'use client'
import { useState } from 'react'
import { Card, SectionLabel, AlertList, Badge } from '@juridico/ui'
import type { AlertItem } from '@juridico/ui'
import type { AlertChannel, DeliveryStatus, AlertSeverity } from '@juridico/tokens'

const MOCK_ALERTS: AlertItem[] = [
  { id: '1', severity: 'CRITICAL', title: 'Arrecadação crítica — Manaus/AM', subjectRef: 'IBGE:1302603', channels: ['email', 'webhook'], deliveryStatus: 'done', createdAt: '2h' },
  { id: '2', severity: 'HIGH', title: 'Único proponente >50% — Órgão 0001', subjectRef: 'CNPJ:00.394.460/0007-94', channels: ['slack'], deliveryStatus: 'pending', createdAt: '5h' },
  { id: '3', severity: 'MEDIUM', title: 'DATAJUD defasado >30d', subjectRef: 'sistema', channels: ['email'], deliveryStatus: 'done', createdAt: '1d' },
  { id: '4', severity: 'LOW', title: 'Novo contrato indexado — PNCP', subjectRef: 'CNPJ:22.000.011/0001-12', channels: ['webhook'], deliveryStatus: 'done', createdAt: '2d' },
  { id: '5', severity: 'CRITICAL', title: 'Saneamento abaixo do mínimo — Teresina/PI', subjectRef: 'IBGE:2211001', channels: ['email', 'slack', 'whatsapp'], deliveryStatus: 'failed', createdAt: '3d' },
]

export default function AlertasPage() {
  const [filterSeverity, setFilterSeverity] = useState<AlertSeverity | null>(null)

  const severities: Array<AlertSeverity | null> = [null, 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-[20px] font-bold text-textPrimary">Central de Alertas</h1>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <span className="text-[12px] text-textMuted">Severidade:</span>
        {severities.map((s) => (
          <button
            key={s ?? 'all'}
            onClick={() => setFilterSeverity(s)}
            className={`px-3 py-1 rounded-pill text-[11px] font-medium border transition-colors ${
              filterSeverity === s
                ? 'bg-accent text-white border-accent'
                : 'bg-surface text-textSecondary border-border hover:border-accentTintBorder'
            }`}
          >
            {s ?? 'Todos'}
          </button>
        ))}
      </div>

      <Card padding="none">
        <div className="px-5 py-3 border-b border-[#f0f2f5] flex items-center justify-between">
          <SectionLabel>Alertas ({MOCK_ALERTS.length})</SectionLabel>
          <span className="text-[11px] text-textFaint">sem PII · subject_ref apenas</span>
        </div>
        <div className="px-5">
          <AlertList alerts={MOCK_ALERTS} filterSeverity={filterSeverity} />
        </div>
      </Card>
    </div>
  )
}

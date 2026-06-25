'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Card, SectionLabel, Badge, FreshnessSeal, Input, Button, Table, Thead, Tbody, Tr, Th, Td, EmptyState, ProblemJsonError } from '@juridico/ui'
import type { ProblemJson } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { lagToFreshnessBand } from '@juridico/tokens'
import { licitawatchApi } from '@/lib/api/licitawatch'
import { ApiError } from '@/lib/api/client'
import { AlertTriangle } from 'lucide-react'

type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

const RULES: { id: string; label: string; pct: number; severity: Severity; desc: string }[] = [
  { id: 'LL03', label: 'Único proponente', pct: 58, severity: 'CRITICAL', desc: '>50% dos processos com único participante' },
  { id: 'LL01', label: 'Mesmo vencedor', pct: 74, severity: 'HIGH', desc: '>70% dos contratos com mesmo fornecedor' },
  { id: 'LL02', label: 'Dispensa de licitação', pct: 34, severity: 'HIGH', desc: '>30% dos contratos dispensados' },
  { id: 'LL04', label: 'Prazo curto', pct: 12, severity: 'LOW', desc: '<20% com prazo curto — OK' },
]

function pctSeverity(pct: number, crit: number, high: number): Severity {
  if (pct >= crit) return 'CRITICAL'
  if (pct >= high) return 'HIGH'
  if (pct >= high * 0.6) return 'MEDIUM'
  return 'LOW'
}

const MOCK_CONTRATOS = [
  { objeto: 'Consultoria em TI', fornecedor: 'Tech Corp Ltda', modalidade: 'Dispensa', valor: 'R$ 480.000', prazo: '30d', anomalia: true },
  { objeto: 'Material de escritório', fornecedor: 'Papéis SA', modalidade: 'Pregão', valor: 'R$ 45.200', prazo: '15d', anomalia: false },
  { objeto: 'Manutenção predial', fornecedor: 'Tech Corp Ltda', modalidade: 'Concorrência', valor: 'R$ 920.000', prazo: '180d', anomalia: true },
]

const SEVERITY_COLORS = { LOW: '#1f8a5b', MEDIUM: '#b07d00', HIGH: '#cf6a1f', CRITICAL: '#c4382f' }

export default function LicitaWatchPage() {
  const { demoMode } = useShell()
  const [cnpj, setCnpj] = useState('')
  const [referencia, setReferencia] = useState('2026')

  const evalMutation = useMutation({
    mutationFn: () => licitawatchApi.evaluate(cnpj.replace(/\D/g, ''), referencia),
  })

  const hasResult = demoMode || evalMutation.isSuccess
  const apiData = evalMutation.data

  const rules = demoMode || !apiData
    ? RULES
    : [
        { id: 'LL01', label: 'Mesmo vencedor', pct: Math.round(apiData.indicadores.pct_mesmo_vencedor * 100), severity: pctSeverity(apiData.indicadores.pct_mesmo_vencedor * 100, 70, 50), desc: '>70% dos contratos com mesmo fornecedor' },
        { id: 'LL02', label: 'Dispensa de licitação', pct: Math.round(apiData.indicadores.pct_dispensa * 100), severity: pctSeverity(apiData.indicadores.pct_dispensa * 100, 50, 30), desc: '>30% dos contratos dispensados' },
        { id: 'LL03', label: 'Único proponente', pct: Math.round(apiData.indicadores.pct_unico_proponente * 100), severity: pctSeverity(apiData.indicadores.pct_unico_proponente * 100, 50, 30), desc: '>50% dos processos com único participante' },
        { id: 'LL04', label: 'Prazo curto', pct: Math.round(apiData.indicadores.pct_prazo_curto * 100), severity: pctSeverity(apiData.indicadores.pct_prazo_curto * 100, 40, 20), desc: '<20% com prazo curto — OK' },
      ]

  const totalContratos = demoMode || !apiData ? 247 : apiData.total_contratos

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!demoMode) evalMutation.mutate()
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">LW</span>
        <h1 className="text-[20px] font-bold text-textPrimary">LicitaWatch</h1>
      </div>

      <Card padding="md">
        <form onSubmit={onSubmit} className="flex items-end gap-3">
          <div className="flex-1">
            <Input mono label="CNPJ do órgão público" placeholder="00.394.460/0007-94" value={cnpj} onChange={(e) => setCnpj(e.target.value)} />
          </div>
          <div className="w-28">
            <Input mono label="Referência (ano)" placeholder="2026" value={referencia} onChange={(e) => setReferencia(e.target.value)} />
          </div>
          <Button type="submit" loading={evalMutation.isPending}>Avaliar órgão</Button>
        </form>
      </Card>

      {!demoMode && evalMutation.isError && evalMutation.error instanceof ApiError && (
        <ProblemJsonError error={evalMutation.error.problem as ProblemJson} />
      )}

      {!hasResult && !evalMutation.isPending && <EmptyState icon="📋" title="Informe o CNPJ de um órgão público para avaliar contratos e licitações" />}

      {hasResult && (
        <div className="flex flex-col gap-4">
          {/* Org header */}
          <Card padding="md">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[15px] font-semibold text-textPrimary">Prefeitura Municipal Demo</p>
                <p className="font-mono text-[12px] text-textMuted">{cnpj || '00.394.460/0007-94'}</p>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[12px] text-textSecondary"><strong>{totalContratos}</strong> contratos</span>
                  <span className="text-[12px] font-mono text-textSecondary">ref. {referencia}</span>
                </div>
              </div>
              <FreshnessSeal source="PNCP" lagDays={1} band={lagToFreshnessBand(1)} />
            </div>
          </Card>

          {/* Rule cards */}
          <div className="grid grid-cols-2 gap-3">
            {rules.map((r) => (
              <Card key={r.id} padding="md" className="flex flex-col gap-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px] font-bold text-textMuted">{r.id}</span>
                  <Badge variant={r.severity} dot>{r.severity}</Badge>
                </div>
                <div>
                  <p className="text-[14px] font-semibold text-textPrimary">{r.label}</p>
                  <p className="text-[11px] text-textMuted mt-0.5">{r.desc}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className="font-mono text-[28px] font-bold"
                    style={{ color: SEVERITY_COLORS[r.severity] }}
                  >
                    {r.pct}%
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-surfaceMuted overflow-hidden">
                  <div
                    className="h-1.5 rounded-full"
                    style={{ width: `${r.pct}%`, background: SEVERITY_COLORS[r.severity] }}
                  />
                </div>
              </Card>
            ))}
          </div>

          {/* Contracts table — amostra disponível no modo demo */}
          {demoMode && (
          <Card padding="none">
            <div className="px-5 py-3 border-b border-[#f0f2f5]">
              <SectionLabel>Contratos</SectionLabel>
            </div>
            <Table>
              <Thead>
                <Tr>
                  <Th>Objeto</Th><Th>Fornecedor</Th><Th>Modalidade</Th><Th>Valor</Th><Th>Prazo</Th><Th>Anomalia</Th>
                </Tr>
              </Thead>
              <Tbody>
                {MOCK_CONTRATOS.map((c, i) => (
                  <Tr key={i}>
                    <Td>{c.objeto}</Td>
                    <Td>{c.fornecedor}</Td>
                    <Td><Badge variant="muted">{c.modalidade}</Badge></Td>
                    <Td mono>{c.valor}</Td>
                    <Td mono>{c.prazo}</Td>
                    <Td>
                      {c.anomalia
                        ? <AlertTriangle className="w-4 h-4 text-riskCritical" aria-label="anomalia detectada" />
                        : <span className="text-[11px] text-riskLowText">OK</span>}
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Card>
          )}
        </div>
      )}
    </div>
  )
}

'use client'
import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Card, CardHeader, SectionLabel, Badge, TrustHeader, ScoreGauge,
  HeuristicBadge, MerklePanel, JobProgress, DegradationBanner,
  Tabs, TabPanel, Dropzone, EmptyState, Input, Button, Skeleton, ViewerBanner,
  RbacGate, FreshnessSeal,
} from '@juridico/ui'
import { lagToFreshnessBand } from '@juridico/tokens'
import { useShell } from '@/app/context/shell'
import { legalscoreApi } from '@/lib/api/legalscore'
import { ApiError } from '@/lib/api/client'
import { ProblemJsonError } from '@juridico/ui'
import type { ProblemJson } from '@juridico/ui'
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, LineChart, Line, Area, AreaChart, Tooltip } from 'recharts'
import { Upload, RefreshCw } from 'lucide-react'

const TABS = [
  { id: 'resumo', label: 'Resumo' },
  { id: 'grafo', label: 'Grafo societário' },
  { id: 'historico', label: 'Histórico' },
  { id: 'auditoria', label: 'Auditoria' },
  { id: 'metricas', label: 'Métricas do modelo' },
  { id: 'lote', label: 'Lote' },
]

const MOCK_BREAKDOWN = [
  { name: 'processos_ativos', label: 'Processos ativos', value: 0.65 },
  { name: 'divida_pgfn', label: 'Dívida PGFN', value: 0.82 },
  { name: 'regularidade_fiscal', label: 'Regularidade fiscal', value: 0.74 },
  { name: 'saude_financeira', label: 'Saúde financeira', value: 0.58 },
  { name: 'historico_societario', label: 'Histórico societário', value: 0.71 },
  { name: 'atividade_cnae', label: 'Atividade CNAE', value: 0.88 },
  { name: 'anomalias_rede', label: 'Anomalias de rede', value: 0.43 },
]

const MOCK_HISTORY = [
  { month: 'Jan', score: 612 }, { month: 'Fev', score: 625 }, { month: 'Mar', score: 618 },
  { month: 'Abr', score: 634 }, { month: 'Mai', score: 641 }, { month: 'Jun', score: 629 },
  { month: 'Jul', score: 648 }, { month: 'Ago', score: 656 }, { month: 'Set', score: 643 },
  { month: 'Out', score: 651 }, { month: 'Nov', score: 658 }, { month: 'Dez', score: 648 },
]

function factorColor(v: number): string {
  if (v >= 0.7) return '#1f8a5b'
  if (v >= 0.5) return '#b07d00'
  return '#c4382f'
}

export default function LegalScorePage() {
  const { role, demoMode } = useShell()
  const [cnpj, setCnpj] = useState('')
  const [activeTab, setActiveTab] = useState('resumo')
  const [simulateDegraded, setSimulateDegraded] = useState(false)

  const scoreMutation = useMutation({
    mutationFn: () => legalscoreApi.score(cnpj),
  })

  const hasResult = demoMode || scoreMutation.isSuccess
  const result = demoMode
    ? {
        score: simulateDegraded ? 521 : 648,
        risk_level: 'MODERADO' as const,
        confidence_interval: simulateDegraded ? [460, 590] : [610, 689] as [number, number],
        breakdown: MOCK_BREAKDOWN,
        engine: 'rust' as const,
        request_id: 'req_demo_001',
        lag_days: 4,
        source_date: '2026-06-13',
        is_partial: simulateDegraded,
      }
    : scoreMutation.data

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">LS</span>
        <h1 className="text-[20px] font-bold text-textPrimary">LegalScore</h1>
        <HeuristicBadge status="heuristica" />
        <Badge variant="accent" className="ml-auto text-[10px]">p95 &lt; 1,5s</Badge>
      </div>

      {role === 'viewer' && <ViewerBanner />}

      {/* Search bar */}
      <Card padding="md">
        <form
          onSubmit={(e) => { e.preventDefault(); scoreMutation.mutate() }}
          className="flex items-end gap-3"
        >
          <div className="flex-1">
            <Input
              mono
              label="CNPJ"
              placeholder="00.000.000/0000-00"
              value={cnpj}
              onChange={(e) => setCnpj(e.target.value)}
              aria-label="CNPJ para calcular score"
            />
          </div>

          <RbacGate role={role} requires="analyst">
            <Button type="submit" loading={scoreMutation.isPending}>
              Calcular score
            </Button>
          </RbacGate>

          <label className="flex items-center gap-1.5 text-[12px] text-textMuted cursor-pointer select-none">
            <input
              type="checkbox"
              checked={simulateDegraded}
              onChange={(e) => setSimulateDegraded(e.target.checked)}
              className="w-3.5 h-3.5 rounded"
            />
            simular fonte off
          </label>

          <RbacGate role={role} requires="analyst">
            <Button variant="secondary" type="button" size="sm" onClick={() => setActiveTab('lote')}>
              <Upload className="w-3.5 h-3.5" aria-hidden />
              Score em lote
            </Button>
          </RbacGate>
        </form>
      </Card>

      {/* Error */}
      {scoreMutation.isError && scoreMutation.error instanceof ApiError && (
        <ProblemJsonError error={scoreMutation.error.problem as ProblemJson} />
      )}

      {/* Empty state */}
      {!hasResult && !scoreMutation.isPending && (
        <EmptyState
          icon="⚖️"
          title="Calcule o score de risco"
          description="Informe o CNPJ acima e clique em Calcular score para obter o rating jurídico-financeiro."
        />
      )}

      {/* Loading */}
      {scoreMutation.isPending && (
        <div className="grid grid-cols-2 gap-4">
          <Skeleton height={300} className="rounded-card" />
          <Skeleton height={300} className="rounded-card" />
        </div>
      )}

      {/* Result */}
      {hasResult && result && (
        <div className="flex flex-col gap-4">
          {/* Degradation banner */}
          {(simulateDegraded || result.is_partial) && (
            <DegradationBanner
              message="Score parcial — circuit breaker ativo"
              detail="DATAJUD indisponível. IC alargado. Reconecte para refinar."
            />
          )}

          {/* Trust header */}
          <TrustHeader
            sources={[
              { name: 'Receita', lagDays: 2, band: lagToFreshnessBand(2) },
              { name: 'PGFN', lagDays: 31, band: lagToFreshnessBand(31) },
              {
                name: 'DATAJUD',
                lagDays: simulateDegraded ? 999 : 4,
                band: simulateDegraded ? 'very_stale' : lagToFreshnessBand(4),
              },
            ]}
            score={result.score}
            ciLow={result.confidence_interval[0]}
            ciHigh={result.confidence_interval[1]}
            modelStatus="heuristica"
            sourceNames={['DATAJUD', 'PGFN', 'Receita', 'CAGED', 'Neo4j']}
            extraSourceCount={2}
          />

          {/* Company card */}
          <Card padding="md">
            <div className="flex items-start justify-between gap-4">
              <div className="flex flex-col gap-1">
                <p className="text-[15px] font-semibold text-textPrimary">Empresa Demonstração S.A.</p>
                <p className="font-mono text-[12px] text-textSecondary">{cnpj || '00.000.000/0001-91'}</p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="LOW" dot>ATIVA</Badge>
                  <span className="text-[11px] text-textMuted">6201-5/00 · Médio porte</span>
                </div>
              </div>
              <div className="flex flex-col gap-1 items-end">
                <FreshnessSeal source="Receita" lagDays={2} band="fresh" />
                <FreshnessSeal source="PGFN" lagDays={31} band="stale" />
                <FreshnessSeal
                  source="DATAJUD"
                  lagDays={simulateDegraded ? 999 : 4}
                  band={simulateDegraded ? 'very_stale' : 'fresh'}
                />
              </div>
            </div>
          </Card>

          {/* Tabs */}
          <Tabs tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />

          <TabPanel id="resumo" activeTab={activeTab}>
            <div className="grid grid-cols-2 gap-4 mt-4">
              {/* Score card */}
              <Card padding="md" className="flex flex-col items-center">
                <ScoreGauge
                  score={result.score}
                  ciLow={result.confidence_interval[0]}
                  ciHigh={result.confidence_interval[1]}
                  size={240}
                />
                <div className="mt-4 w-full bg-surfaceMuted rounded-[8px] p-3 text-[12px] text-textSecondary">
                  <p className="font-semibold text-textPrimary mb-0.5">IC 95%: {result.confidence_interval[0]}–{result.confidence_interval[1]}</p>
                  <p className="text-textMuted">Engine: <span className="font-mono">{result.engine}</span></p>
                  <button
                    onClick={() => setActiveTab('auditoria')}
                    className="font-mono text-[11px] text-accent hover:underline mt-1 block"
                  >
                    {result.request_id} ↗ auditoria
                  </button>
                </div>
              </Card>

              {/* Factor breakdown */}
              <Card padding="md">
                <SectionLabel className="mb-3">Breakdown dos fatores</SectionLabel>
                <div className="flex flex-col gap-3">
                  {result.breakdown.map((f) => (
                    <div key={f.name} className="flex flex-col gap-1">
                      <div className="flex justify-between text-[12px]">
                        <span className="text-textSecondary">{f.label}</span>
                        <span className="font-mono font-medium" style={{ color: factorColor(f.value) }}>
                          {Math.round(f.value * 100)}%
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-surfaceMuted overflow-hidden">
                        <div
                          className="h-1.5 rounded-full transition-all"
                          style={{ width: `${f.value * 100}%`, background: factorColor(f.value) }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </TabPanel>

          <TabPanel id="grafo" activeTab={activeTab}>
            <Card padding="md" className="mt-4">
              <SectionLabel className="mb-3">Grafo societário</SectionLabel>
              <div
                className="flex items-center justify-center h-64 rounded-[8px] bg-surfaceMuted text-textFaint text-[13px]"
                aria-label="Grafo societário — dados do Neo4j"
              >
                Grafo societário (Neo4j) — implementar com D3/SVG
              </div>
            </Card>
          </TabPanel>

          <TabPanel id="historico" activeTab={activeTab}>
            <Card padding="md" className="mt-4">
              <SectionLabel className="mb-4">Histórico de score (12 meses)</SectionLabel>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={MOCK_HISTORY}>
                  <defs>
                    <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2f6fed" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#2f6fed" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#8a93a0' }} axisLine={false} tickLine={false} />
                  <YAxis domain={[500, 750]} tick={{ fontSize: 11, fill: '#8a93a0' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, border: '1px solid #e7eaee', borderRadius: 8 }}
                    formatter={(v: number) => [v, 'Score']}
                  />
                  <Area type="monotone" dataKey="score" stroke="#2f6fed" strokeWidth={2} fill="url(#scoreGrad)" dot={{ r: 3, fill: '#2f6fed' }} />
                </AreaChart>
              </ResponsiveContainer>
            </Card>
          </TabPanel>

          <TabPanel id="auditoria" activeTab={activeTab}>
            <div className="mt-4">
              <MerklePanel
                requestId={result.request_id}
                leafHash="sha256:a3f9e21b04cc7d88..."
                merkleRoot="sha256:root1a2b3c4d5e6f..."
                proof={[
                  { position: 'L', hash: 'sha256:sib1aaa...' },
                  { position: 'R', hash: 'sha256:sib2bbb...' },
                  { position: 'L', hash: 'sha256:sib3ccc...' },
                ]}
                isIntact
                onReverify={() => {}}
                onExportPdf={() => {}}
              />
            </div>
          </TabPanel>

          <TabPanel id="metricas" activeTab={activeTab}>
            <Card padding="md" className="mt-4">
              <DegradationBanner message="Métricas pendentes — validação em andamento" className="mb-4" />
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: 'AUC-ROC', value: '0.78', target: '≥ 0.80', ok: false },
                  { label: 'Brier Score', value: '0.17', target: '≤ 0.15', ok: false },
                  { label: 'KS Statistic', value: '0.41', target: '≥ 0.35', ok: true },
                  { label: 'Amostra', value: '12.4k', target: '≥ 10k', ok: true },
                ].map((m) => (
                  <div key={m.label} className="bg-surfaceMuted rounded-[8px] p-4">
                    <p className="text-[11px] text-textMuted mb-1">{m.label}</p>
                    <p className="font-mono text-[22px] font-bold text-textPrimary">{m.value}</p>
                    <p className={`text-[11px] mt-1 ${m.ok ? 'text-riskLowText' : 'text-riskCriticalText'}`}>
                      meta: {m.target} {m.ok ? '✓' : '✗'}
                    </p>
                  </div>
                ))}
              </div>
              <RbacGate role={role} requires="admin" className="mt-4">
                <Button variant="secondary" size="sm">
                  <RefreshCw className="w-3.5 h-3.5" aria-hidden />
                  Recalibrar modelo
                </Button>
              </RbacGate>
            </Card>
          </TabPanel>

          <TabPanel id="lote" activeTab={activeTab}>
            <Card padding="md" className="mt-4 flex flex-col gap-4">
              <SectionLabel>Análise em lote — até 1.000 CNPJs</SectionLabel>
              <RbacGate role={role} requires="analyst">
                <Dropzone
                  accept=".csv"
                  hint="CSV com coluna 'cnpj', até 1.000 linhas"
                  onFiles={(files) => console.log('batch upload', files[0]?.name)}
                />
              </RbacGate>
              {/* Mock jobs table */}
              <div className="flex flex-col gap-2">
                <SectionLabel>Jobs recentes</SectionLabel>
                <div className="bg-surfaceMuted rounded-[8px] p-4 text-[12px] text-textFaint text-center">
                  Nenhum job recente
                </div>
              </div>
            </Card>
          </TabPanel>
        </div>
      )}
    </div>
  )
}

'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Card, CardHeader, SectionLabel, Badge, JobProgress, Dropzone, EmptyState,
  Button, ViewerBanner, RbacGate, FreshnessSeal,
} from '@juridico/ui'
import { lagToFreshnessBand } from '@juridico/tokens'
import { useShell } from '@/app/context/shell'
import { contabiliaApi } from '@/lib/api/contabilia'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'
import { downloadDoc, slugifyFilename } from '@/lib/export/documents'
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, ReferenceLine, Cell, Tooltip } from 'recharts'
import { ChevronDown, ChevronRight, Download } from 'lucide-react'
import { cn } from '@juridico/ui'
import type { JobStep } from '@juridico/ui'

const SEVERITY_VARIANT: Record<string, string> = { CRITICO: 'CRITICAL', ALTO: 'HIGH', MEDIO: 'MEDIUM' }
const SEVERITY_STATUS: Record<string, string> = { CRITICO: 'SUSPEITO', ALTO: 'MARGINAL', MEDIO: 'MARGINAL' }

interface FindingView {
  id: string
  severity: string
  label: string
  status: string
  evidence: string
  source?: string
  lagDays?: number
}

type Stage = 'upload' | 'processing' | 'report'

const CHECKS = ['CC01', 'CC02', 'CC03', 'CC04', 'CC05', 'CC06', 'CC07', 'CC08']

const MOCK_FINDINGS = [
  {
    id: 'CC05', severity: 'CRITICAL' as const, label: 'Benford — dígitos suspeitos',
    status: 'SUSPEITO',
    evidence: 'Dígito 1 observado: 18% (esperado: 30,1%). χ² = 24.3, p < 0.001.',
    source: 'SICONFI', lagDays: 365,
  },
  {
    id: 'CC01', severity: 'HIGH' as const, label: 'Z-score de despesas > 3σ',
    status: 'MARGINAL',
    evidence: 'Despesas pessoal: Z = 3.8. Limite: ±3.',
    source: 'SICONFI', lagDays: 365,
  },
  {
    id: 'CC03', severity: 'MEDIUM' as const, label: 'Liquidez corrente abaixo do setor',
    status: 'MARGINAL',
    evidence: 'LC = 0.82 (setor: 1.20). Desvio: −31.7%.',
    source: 'Receita', lagDays: 2,
  },
  {
    id: 'CC07', severity: 'LOW' as const, label: 'EBITDA dentro do esperado',
    status: 'CONFORME',
    evidence: 'EBITDA = 18.4% (setor: 15–22%). Dentro da faixa.',
    source: 'Receita', lagDays: 2,
  },
]

const BENFORD_DATA = [
  { digit: '1', observed: 18, expected: 30.1 },
  { digit: '2', observed: 22, expected: 17.6 },
  { digit: '3', observed: 15, expected: 12.5 },
  { digit: '4', observed: 13, expected: 9.7 },
  { digit: '5', observed: 10, expected: 7.9 },
  { digit: '6', observed: 8, expected: 6.7 },
  { digit: '7', observed: 6, expected: 5.8 },
  { digit: '8', observed: 5, expected: 5.1 },
  { digit: '9', observed: 3, expected: 4.6 },
]

const MOCK_STEPS: JobStep[] = [
  { id: 'ocr', label: 'OCR e extração de texto', status: 'done' },
  { id: 'parse', label: 'Parsing e normalização', status: 'done' },
  { id: 'cc01', label: 'CC01 — Análise Z-score', status: 'done' },
  { id: 'cc05', label: 'CC05 — Benford', status: 'active' },
  { id: 'cc06', label: 'CC06–CC08 — Ratios setoriais', status: 'pending' },
  { id: 'pdf', label: 'Geração do laudo PDF', status: 'pending' },
]

export default function ContabilIAPage() {
  const { role, demoMode } = useShell()
  const [stage, setStage] = useState<Stage>('upload')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const uploadMutation = useMutation({
    mutationFn: (file: File) => contabiliaApi.upload(file),
    onSuccess: () => setStage('report'),
    onError: () => setStage('upload'),
  })

  const apiData = uploadMutation.data

  const findings: FindingView[] = demoMode || !apiData
    ? MOCK_FINDINGS
    : apiData.findings.map((f) => ({
        id: f.rule,
        severity: SEVERITY_VARIANT[f.severity] ?? 'LOW',
        label: f.description,
        status: SEVERITY_STATUS[f.severity] ?? 'CONFORME',
        evidence: f.detail,
      }))

  const reportId = demoMode || !apiData ? 'rep_demo_001' : apiData.report_id

  function onUpload(files: FileList) {
    if (demoMode) { setStage('processing'); return }
    const file = files[0]
    if (!file) return
    setStage('processing')
    uploadMutation.mutate(file)
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">CT</span>
        <h1 className="text-[20px] font-bold text-textPrimary">ContabilIA</h1>
        <Badge variant="accent" className="ml-auto text-[10px]">p95 &lt; 60s</Badge>
      </div>

      {role === 'viewer' && <ViewerBanner />}

      {/* Stage: upload */}
      {stage === 'upload' && (
        <Card padding="md" className="flex flex-col gap-5">
          <SectionLabel>Enviar demonstrações financeiras</SectionLabel>
          <RbacGate role={role} requires="analyst">
            <Dropzone
              accept=".csv"
              hint="CSV (conta,valor[,descricao]) · processamento em até 60s"
              onFiles={onUpload}
            />
          </RbacGate>

          <ApiErrorBanner error={uploadMutation.error} />

          <div className="grid grid-cols-4 gap-2">
            {CHECKS.map((c) => (
              <div key={c} className="bg-surfaceMuted rounded-[6px] px-3 py-2 text-center">
                <span className="font-mono text-[11px] font-bold text-textSecondary">{c}</span>
              </div>
            ))}
          </div>

          {demoMode && (
            <Button variant="secondary" onClick={() => setStage('processing')}>
              Simular análise (demo)
            </Button>
          )}
        </Card>
      )}

      {/* Stage: processing */}
      {stage === 'processing' && (
        <Card padding="md">
          <div className="flex flex-col gap-2 mb-4">
            <span className="font-mono text-[10px] text-textFaint">{demoMode ? '202 Accepted' : 'Processando…'}</span>
            <p className="font-mono text-[40px] font-bold text-accent">{demoMode ? '62%' : '…'}</p>
          </div>
          <JobProgress
            status="running"
            progress={demoMode ? 62 : 40}
            steps={MOCK_STEPS}
          />
          {demoMode && (
            <Button variant="secondary" size="sm" className="mt-4" onClick={() => setStage('report')}>
              Ver relatório (demo)
            </Button>
          )}
        </Card>
      )}

      {/* Stage: report */}
      {stage === 'report' && (
        <div className="flex flex-col gap-4">
          <Card padding="md">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-riskLowText mb-1">LAUDO PRONTO</p>
                <p className="font-mono text-[12px] text-textSecondary">report_id: {reportId}</p>
              </div>
              <div className="flex items-center gap-3">
                <FreshnessSeal source="SICONFI" lagDays={365} band={lagToFreshnessBand(365)} />
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    downloadDoc({
                      filename: slugifyFilename(`laudo-${reportId}`),
                      title: 'Laudo de auditoria contábil',
                      subtitle: `report_id: ${reportId} · fonte SICONFI`,
                      sections: findings.map((f) => ({
                        titulo: `${f.id} — ${f.label} [${f.status}]`,
                        conteudo: f.evidence,
                      })),
                      footer: 'Gerado por ContabilIA (Plataforma Jurídico-Contábil). Achados estatísticos — não substituem perícia.',
                    })
                  }
                >
                  <Download className="w-3.5 h-3.5" aria-hidden />
                  Baixar laudo (.doc)
                </Button>
              </div>
            </div>
          </Card>

          {/* Findings */}
          <Card padding="none">
            <CardHeader className="px-5 pt-4 pb-3 border-b border-[#f0f2f5] mb-0">
              <SectionLabel>Achados por severidade</SectionLabel>
            </CardHeader>
            <div className="divide-y divide-[#f0f2f5]">
              {findings.map((f) => (
                <div key={f.id}>
                  <button
                    onClick={() => toggle(f.id)}
                    className="w-full flex items-center gap-3 px-5 py-3 hover:bg-surfaceMuted/50 transition-colors"
                    aria-expanded={expanded.has(f.id)}
                  >
                    <span className="font-mono text-[10px] font-bold text-textMuted">{f.id}</span>
                    <Badge variant={f.severity as any} dot>{f.severity}</Badge>
                    <span className="flex-1 text-left text-[13px] font-medium text-textPrimary">{f.label}</span>
                    <Badge variant={f.status === 'SUSPEITO' ? 'CRITICO' : f.status === 'MARGINAL' ? 'MODERADO' : 'LOW'}>
                      {f.status}
                    </Badge>
                    {expanded.has(f.id)
                      ? <ChevronDown className="w-4 h-4 text-textMuted flex-shrink-0" />
                      : <ChevronRight className="w-4 h-4 text-textMuted flex-shrink-0" />}
                  </button>

                  {expanded.has(f.id) && (
                    <div className="px-5 pb-4 bg-surfaceMuted/30">
                      <div className="grid grid-cols-2 gap-4 text-[12px]">
                        <div>
                          <p className="text-textSectionLabel font-semibold text-[10px] uppercase tracking-[0.04em] mb-1">Evidência</p>
                          <p className="text-textSecondary">{f.evidence}</p>
                        </div>
                        {f.source != null && f.lagDays != null && (
                          <div>
                            <p className="text-textSectionLabel font-semibold text-[10px] uppercase tracking-[0.04em] mb-1">Fonte</p>
                            <FreshnessSeal source={f.source} lagDays={f.lagDays} band={lagToFreshnessBand(f.lagDays)} />
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>

          {/* Benford chart — distribuição de dígitos disponível no modo demo */}
          {demoMode && (
          <Card padding="md">
            <SectionLabel className="mb-4">Lei de Benford — CC05</SectionLabel>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={BENFORD_DATA} barCategoryGap="20%">
                <XAxis dataKey="digit" tick={{ fontSize: 11, fill: '#8a93a0' }} axisLine={false} tickLine={false} label={{ value: 'Primeiro dígito', position: 'insideBottom', offset: -2, fontSize: 11, fill: '#8a93a0' }} />
                <YAxis tick={{ fontSize: 11, fill: '#8a93a0' }} axisLine={false} tickLine={false} unit="%" />
                <Tooltip contentStyle={{ fontSize: 12, border: '1px solid #e7eaee', borderRadius: 8 }} formatter={(v: number) => [`${v.toFixed(1)}%`]} />
                <Bar dataKey="expected" name="Esperado" fill="#e7eaee" radius={[3, 3, 0, 0]} />
                <Bar dataKey="observed" name="Observado" radius={[3, 3, 0, 0]}>
                  {BENFORD_DATA.map((entry) => (
                    <Cell key={entry.digit} fill={Math.abs(entry.observed - entry.expected) > 5 ? '#c4382f' : '#2f6fed'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-textMuted mt-2 font-mono">χ² = 24.3 · p &lt; 0.001 · SUSPEITO</p>
          </Card>
          )}
        </div>
      )}
    </div>
  )
}

'use client'
import { useState } from 'react'
import {
  Card, CardHeader, SectionLabel, Badge, ProbabilityDonut, HeuristicBadge,
  DegradationBanner, EmptyState, Textarea, Button, ViewerBanner, RbacGate,
  VerifiableCitationChip,
} from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, ReferenceLine, Cell } from 'recharts'

interface JurisprudenciaHit {
  doc_id: string
  similarity: number
  tribunal: string
  ano: number
  decisao: 'FAVORAVEL' | 'PARCIAL' | 'DESFAVORAVEL' | 'DESCONHECIDO'
  ementa: string
  source_url?: string  // URL canônica retornada pelo backend; fallback via doc_id
}

const MATERIAS = ['PIS_COFINS', 'IRPJ', 'CSLL', 'ICMS', 'IPI', 'ISS', 'SIMPLES']

const MOCK_RESULT = {
  probability: 0.62,
  ci_lower: 0.51,
  ci_upper: 0.72,
  model_status: 'heuristica' as const,
  is_fallback: false,
  shap: [
    { name: 'Valor da autuação', impact: 0.08, label: 'Valor alto → +8%' },
    { name: 'Órgão autuante', impact: 0.06, label: 'PGFN → +6%' },
    { name: 'Similaridade precedentes', impact: 0.05, label: '3 precedentes favoráveis → +5%' },
    { name: 'Matéria tributária', impact: -0.04, label: 'PIS/COFINS cumulativo → −4%' },
    { name: 'Ano de autuação', impact: -0.03, label: '2021 → tendência desfavorável → −3%' },
  ],
  jurisprudencias: [
    { doc_id: 'TRF3-2023-001', similarity: 0.89, tribunal: 'TRF-3', ano: 2023, decisao: 'FAVORAVEL' as const, ementa: 'Exclusão do ICMS da base de cálculo do PIS/COFINS…', source_url: 'https://jurisprudencia.trf3.jus.br/juri/detalhe?uniforme=TRF3-2023-001' },
    { doc_id: 'CARF-2022-087', similarity: 0.76, tribunal: 'CARF', ano: 2022, decisao: 'PARCIAL' as const, ementa: 'Aproveitamento de créditos não-cumulativos…', source_url: 'https://carf.fazenda.gov.br/sincon/public/pages/ConsultarJurisprudencia/listarJurisprudenciaCarf.jsf?numeroAcordao=CARF-2022-087' },
    { doc_id: 'STJ-2021-334', similarity: 0.71, tribunal: 'STJ', ano: 2021, decisao: 'FAVORAVEL' as const, ementa: 'Tese do século — RE 574.706/PR…', source_url: 'https://processo.stj.jus.br/processo/pesquisa/?tipoPesquisa=tipoPesquisaNumeroRegistro&termo=STJ-2021-334' },
  ] satisfies JurisprudenciaHit[],
}

function DecisaoChip({ decisao }: { decisao: string }) {
  const map: Record<string, string> = {
    FAVORAVEL: 'LOW', PARCIAL: 'MODERADO', DESFAVORAVEL: 'ALTO', DESCONHECIDO: 'muted',
  }
  return <Badge variant={map[decisao] as any}>{decisao}</Badge>
}

export default function TaxPredictPage() {
  const { role, demoMode } = useShell()
  const [descricao, setDescricao] = useState('')
  const [materia, setMateria] = useState('PIS_COFINS')
  const [showFallback, setShowFallback] = useState(false)
  const [hasResult, setHasResult] = useState(demoMode)

  const result = showFallback
    ? { ...MOCK_RESULT, probability: 0.30, ci_lower: 0.20, ci_upper: 0.42, is_fallback: true }
    : MOCK_RESULT

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">TP</span>
        <h1 className="text-[20px] font-bold text-textPrimary">TaxPredict</h1>
        <HeuristicBadge status="heuristica" />
        <label className="ml-auto flex items-center gap-1.5 text-[12px] text-textMuted cursor-pointer">
          <input type="checkbox" checked={showFallback} onChange={(e) => setShowFallback(e.target.checked)} className="w-3.5 h-3.5 rounded" />
          simular fallback
        </label>
      </div>

      {role === 'viewer' && <ViewerBanner />}

      <Card padding="md" className="flex flex-col gap-4">
        <Textarea
          label="Descrição da disputa tributária"
          placeholder="Descreva os fatos e fundamentos (20–2.000 caracteres)…"
          rows={4}
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          charCount={{ current: descricao.length, max: 2000 }}
        />
        <div className="flex items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-textSecondary">Matéria tributária</label>
            <select
              value={materia}
              onChange={(e) => setMateria(e.target.value)}
              className="rounded-[8px] border border-borderStrong bg-surface px-3 py-2 text-[13px] text-textPrimary focus:outline-none focus:ring-2 focus:ring-accentTintBorder"
            >
              {MATERIAS.map((m) => <option key={m}>{m}</option>)}
            </select>
          </div>
          <RbacGate role={role} requires="analyst">
            <Button onClick={() => setHasResult(true)}>Prever desfecho</Button>
          </RbacGate>
        </div>
      </Card>

      {!hasResult && <EmptyState icon="⚖️" title="Preencha o formulário e clique em Prever desfecho" />}

      {hasResult && (
        <div className="flex flex-col gap-4">
          {result.is_fallback && (
            <DegradationBanner
              message="Fallback ativo — estimativa nacional"
              detail="Modelo em recalibração. Prior nacional: 30%. Precisão reduzida."
            />
          )}

          <div className="grid grid-cols-3 gap-4">
            {/* Donut */}
            <Card padding="md" className="flex flex-col items-center gap-3">
              <ProbabilityDonut
                probability={result.probability}
                ciLow={result.ci_lower}
                ciHigh={result.ci_upper}
                size={160}
              />
              <HeuristicBadge status={result.model_status} />
            </Card>

            {/* SHAP */}
            <Card padding="md" className="col-span-2">
              <SectionLabel className="mb-3">Fatores (SHAP) — base: {Math.round(0.30 * 100)}%</SectionLabel>
              <div className="flex flex-col gap-2">
                {result.shap.map((f) => (
                  <div key={f.name} className="flex flex-col gap-1">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-textSecondary">{f.label}</span>
                      <span className={cn('font-mono font-semibold', f.impact >= 0 ? 'text-riskLowText' : 'text-riskCriticalText')}>
                        {f.impact >= 0 ? '+' : ''}{Math.round(f.impact * 100)}%
                      </span>
                    </div>
                    <div className="relative h-1.5 rounded-full bg-surfaceMuted">
                      <div
                        className="absolute top-0 h-1.5 rounded-full"
                        style={{
                          left: f.impact >= 0 ? '50%' : `calc(50% + ${f.impact * 100}%)`,
                          width: `${Math.abs(f.impact) * 100}%`,
                          background: f.impact >= 0 ? '#1f8a5b' : '#c4382f',
                        }}
                      />
                      <div className="absolute top-0 left-1/2 w-px h-1.5 bg-borderStrong" />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Jurisprudências */}
          <Card padding="none">
            <CardHeader className="px-5 pt-4 pb-3 border-b border-[#f0f2f5] mb-0">
              <SectionLabel>Jurisprudências similares</SectionLabel>
            </CardHeader>
            <div className="divide-y divide-[#f0f2f5]">
              {result.jurisprudencias.map((j) => (
                <div key={j.doc_id} className="px-5 py-3 flex items-start gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <VerifiableCitationChip
                        docId={j.doc_id}
                        href={j.source_url ?? `https://www.cnj.jus.br/pesquisa-jurisprudencia/resultado/?corpo=${j.doc_id}`}
                        label={`${j.tribunal} · ${j.ano}`}
                        similarity={j.similarity}
                      />
                      <DecisaoChip decisao={j.decisao} />
                    </div>
                    <p className="text-[12px] text-textSecondary line-clamp-2">{j.ementa}</p>
                  </div>
                  <div className="flex-shrink-0 text-right">
                    <span className="font-mono text-[13px] font-semibold text-accent">
                      {Math.round(j.similarity * 100)}%
                    </span>
                    <p className="text-[10px] text-textFaint">similaridade</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}

function cn(...args: string[]) {
  return args.filter(Boolean).join(' ')
}

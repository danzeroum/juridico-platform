'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Card, CardHeader, SectionLabel, Badge, SettlementRangeBar, DegradationBanner,
  EmptyState, Input, Textarea, Button, ViewerBanner, RbacGate, Skeleton, ProblemJsonError,
} from '@juridico/ui'
import type { ProblemJson } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { conciliaApi } from '@/lib/api/concilia'
import { ApiError } from '@/lib/api/client'

function riskBand(score: number | null | undefined): string {
  if (score == null) return 'MODERADO'
  if (score >= 700) return 'LOW'
  if (score >= 500) return 'MODERADO'
  if (score >= 350) return 'ALTO'
  return 'CRITICO'
}

const MOCK_RESULT = {
  valor_minimo: 75000,
  valor_sugerido: 110000,
  valor_maximo: 155000,
  percentual_causa: 22,
  risco_reu: 'MODERADO',
  probabilidade_procedencia: 0.62,
  fatores: [
    { nome: 'Prior histórico', impacto: 0.0, descricao: 'Base: média de acordos similares (R$108k)' },
    { nome: 'Ajuste TaxPredict', impacto: +0.018, descricao: 'Prob. favorável 62% → +1.8%' },
    { nome: 'Ajuste LegalScore', impacto: -0.022, descricao: 'LegalScore=648/1000 → −2.2%' },
    { nome: 'Valor presente', impacto: -0.012, descricao: 'Desconto de 12 meses → −1.2%' },
  ],
}

export default function ConciliaIAPage() {
  const { role, demoMode } = useShell()
  const [tipo, setTipo] = useState('TRABALHISTA')
  const [valor, setValor] = useState('')
  const [cnpjReu, setCnpjReu] = useState('')
  const [descricao, setDescricao] = useState('')

  const recommendMutation = useMutation({
    mutationFn: () =>
      conciliaApi.recommend({
        descricao: descricao || 'Análise de viabilidade de acordo para a ação informada.',
        valor_causa: Number(valor.replace(/[^\d.]/g, '')) || 0,
        tipo_acao: tipo,
        cnpj_reu: cnpjReu.replace(/\D/g, '') || undefined,
      }),
  })

  const hasResult = demoMode || recommendMutation.isSuccess
  const apiData = recommendMutation.data

  const result = demoMode
    ? {
        valor_minimo: MOCK_RESULT.valor_minimo,
        valor_sugerido: MOCK_RESULT.valor_sugerido,
        valor_maximo: MOCK_RESULT.valor_maximo,
        pct: MOCK_RESULT.percentual_causa,
        risco_reu: MOCK_RESULT.risco_reu,
        prob: MOCK_RESULT.probabilidade_procedencia as number | null,
        fatores: MOCK_RESULT.fatores,
      }
    : apiData
      ? {
          valor_minimo: apiData.valor_minimo,
          valor_sugerido: apiData.valor_sugerido,
          valor_maximo: apiData.valor_maximo,
          pct: Math.round(apiData.percentual_causa * 100),
          risco_reu: riskBand(apiData.risco_reu),
          prob: apiData.probabilidade_procedencia ?? null,
          fatores: apiData.fatores,
        }
      : null

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">CC</span>
        <h1 className="text-[20px] font-bold text-textPrimary">ConciliaIA</h1>
        <Badge variant="accent" className="ml-auto text-[10px]">ML</Badge>
      </div>

      {role === 'viewer' && <ViewerBanner />}

      <Card padding="md" className="flex flex-col gap-4">
        <Textarea
          label="Descrição da disputa"
          placeholder="Descreva os fatos e o objeto da ação (20–2.000 caracteres)…"
          rows={3}
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          charCount={{ current: descricao.length, max: 2000 }}
        />
        <div className="grid grid-cols-3 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-textSecondary">Tipo de ação</label>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="rounded-[8px] border border-borderStrong bg-surface px-3 py-2 text-[13px] text-textPrimary focus:outline-none focus:ring-2 focus:ring-accentTintBorder"
            >
              {['TRABALHISTA', 'CIVEL', 'TRIBUTARIO', 'CONSUMERISTA'].map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <Input label="Valor da causa (R$)" placeholder="500000" mono value={valor} onChange={(e) => setValor(e.target.value)} />
          <Input label="CNPJ do réu" placeholder="00.000.000/0000-00" mono value={cnpjReu} onChange={(e) => setCnpjReu(e.target.value)} />
        </div>
        <RbacGate role={role} requires="analyst">
          <Button onClick={() => recommendMutation.mutate()} loading={recommendMutation.isPending} className="self-start">
            Recomendar acordo
          </Button>
        </RbacGate>
      </Card>

      {!demoMode && recommendMutation.isError && recommendMutation.error instanceof ApiError && (
        <ProblemJsonError error={recommendMutation.error.problem as ProblemJson} />
      )}

      {recommendMutation.isPending && !demoMode && (
        <div className="grid grid-cols-2 gap-4">
          <Skeleton height={220} className="rounded-card" />
          <Skeleton height={220} className="rounded-card" />
        </div>
      )}

      {!hasResult && !recommendMutation.isPending && <EmptyState icon="🤝" title="Preencha o formulário e clique em Recomendar acordo" />}

      {hasResult && result && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4">
            <Card padding="md">
              <SectionLabel className="mb-4">Faixa de acordo recomendada</SectionLabel>
              <SettlementRangeBar
                min={result.valor_minimo}
                suggested={result.valor_sugerido}
                max={result.valor_maximo}
                pctOfCase={result.pct}
              />
              <div className="mt-4 flex gap-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-[10px] text-textSectionLabel uppercase tracking-[0.04em]">Risco do réu</span>
                  <Badge variant={result.risco_reu as any} dot>{result.risco_reu}</Badge>
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className="text-[10px] text-textSectionLabel uppercase tracking-[0.04em]">Prob. procedência</span>
                  <span className="font-mono text-[18px] font-bold text-textPrimary">
                    {result.prob != null ? `${Math.round(result.prob * 100)}%` : '—'}
                  </span>
                </div>
              </div>
            </Card>

            {/* Waterfall */}
            <Card padding="md">
              <SectionLabel className="mb-4">Fatores de ajuste</SectionLabel>
              <div className="flex flex-col gap-3">
                {result.fatores.map((f) => (
                  <div key={f.nome} className="flex flex-col gap-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[12px] text-textPrimary font-medium">{f.nome}</span>
                      <span className={`font-mono text-[12px] font-semibold ${f.impacto > 0 ? 'text-riskLowText' : f.impacto < 0 ? 'text-riskCriticalText' : 'text-textMuted'}`}>
                        {f.impacto === 0 ? 'base' : `${f.impacto > 0 ? '+' : ''}${(f.impacto * 100).toFixed(1)}%`}
                      </span>
                    </div>
                    <p className="text-[11px] text-textMuted">{f.descricao}</p>
                    {f.impacto !== 0 && (
                      <div className="relative h-1 rounded-full bg-surfaceMuted">
                        <div
                          className="absolute top-0 h-1 rounded-full"
                          style={{
                            left: f.impacto >= 0 ? '50%' : `calc(50% - ${Math.abs(f.impacto) * 100}%)`,
                            width: `${Math.abs(f.impacto) * 100}%`,
                            background: f.impacto >= 0 ? '#1f8a5b' : '#c4382f',
                          }}
                        />
                        <div className="absolute top-0 left-1/2 w-px h-1 bg-borderStrong" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

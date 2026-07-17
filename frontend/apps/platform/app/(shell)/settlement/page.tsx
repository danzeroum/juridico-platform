'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Card, SectionLabel, HeuristicBadge, Input, Button, SettlementRangeBar, FaixaBadge, RbacGate, EmptyState } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { settlementOptimizerApi, type SettlementResponse } from '@/lib/api/settlementOptimizer'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'

const MOCK: SettlementResponse = {
  request_id: 'req_demo_st_001',
  prob_procedencia: 0.55,
  valor_esperado_autor: 47000,
  valor_esperado_reu: 67000,
  tem_zopa: true,
  faixa_acordo: [47000, 67000],
  acordo_sugerido: 57000,
  recomendacao: 'ACORDAR',
  disclaimer: 'heurística de análise de decisão — não validada contra desfechos reais',
}

function formatBRL(v: number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v)
}

export default function SettlementOptimizerPage() {
  const { role, demoMode } = useShell()
  const [valorCausa, setValorCausa] = useState('100000')
  const [probFavoravel, setProbFavoravel] = useState('0.6')
  const [pctProvimento, setPctProvimento] = useState('0.5')
  const [custoAutor, setCustoAutor] = useState('8000')
  const [custoReu, setCustoReu] = useState('12000')

  const mutation = useMutation({
    mutationFn: () => settlementOptimizerApi.optimize({
      valor_causa: Number(valorCausa),
      prob_favorable: probFavoravel ? Number(probFavoravel) : undefined,
      pct_provimento: pctProvimento ? Number(pctProvimento) : undefined,
      custo_autor: custoAutor ? Number(custoAutor) : 0,
      custo_reu: custoReu ? Number(custoReu) : 0,
    }),
  })

  const hasResult = demoMode || mutation.isSuccess
  const result = demoMode ? MOCK : mutation.data

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">ST</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Settlement Optimizer</h1>
        <HeuristicBadge status="heuristica" />
      </div>
      <p className="text-[13px] text-textMuted -mt-3">Zona de acordo (ZOPA) por análise de decisão — não é aconselhamento jurídico.</p>

      <div className="grid grid-cols-3 gap-4 items-start">
        <Card padding="md" className="flex flex-col gap-4">
          <SectionLabel>Inputs</SectionLabel>
          <Input mono label="Valor da causa (R$)" value={valorCausa} onChange={(e) => setValorCausa(e.target.value)} />
          <Input mono label="Prob. favorável (0–1)" value={probFavoravel} onChange={(e) => setProbFavoravel(e.target.value)} />
          <Input mono label="% provimento (0–1)" value={pctProvimento} onChange={(e) => setPctProvimento(e.target.value)} />
          <Input mono label="Custo autor (R$)" value={custoAutor} onChange={(e) => setCustoAutor(e.target.value)} />
          <Input mono label="Custo réu (R$)" value={custoReu} onChange={(e) => setCustoReu(e.target.value)} />
          <RbacGate role={role} requires="analyst">
            <Button onClick={() => mutation.mutate()} loading={mutation.isPending}>Recomendar acordo</Button>
          </RbacGate>
        </Card>

        <div className="col-span-2 flex flex-col gap-4">
          <ApiErrorBanner error={mutation.error} demoMode={demoMode} />

          {!hasResult && !mutation.isPending && (
            <EmptyState icon="🤝" title="Informe os dados do caso e clique em Recomendar acordo" demoMode={demoMode} />
          )}

          {result && (
            <Card padding="lg">
              <div className="flex items-center justify-between mb-4">
                <SectionLabel>Recomendação</SectionLabel>
                <FaixaBadge value={result.recomendacao} tone={result.recomendacao === 'ACORDAR' ? 'BAIXO' : 'ALTO'} />
              </div>

              {result.tem_zopa && result.faixa_acordo && result.acordo_sugerido !== null ? (
                <SettlementRangeBar
                  min={result.faixa_acordo[0]}
                  suggested={result.acordo_sugerido}
                  max={result.faixa_acordo[1]}
                  pctOfCase={Number(valorCausa) > 0 ? (result.acordo_sugerido / Number(valorCausa)) * 100 : undefined}
                />
              ) : (
                <p className="text-[13px] text-textMuted py-6 text-center">
                  Sem sobreposição de interesses — nenhuma faixa de acordo racional. Recomendação: litigar.
                </p>
              )}

              <div className="grid grid-cols-2 gap-4 mt-6">
                <div className="bg-surfaceMuted rounded-[8px] p-4">
                  <p className="text-[11px] text-textMuted mb-1">Valor esperado — autor</p>
                  <p className="font-mono text-[20px] font-bold text-textPrimary">{formatBRL(result.valor_esperado_autor)}</p>
                </div>
                <div className="bg-surfaceMuted rounded-[8px] p-4">
                  <p className="text-[11px] text-textMuted mb-1">Valor esperado — réu</p>
                  <p className="font-mono text-[20px] font-bold text-textPrimary">{formatBRL(result.valor_esperado_reu)}</p>
                </div>
              </div>

              <p className="text-[11px] text-textFaint mt-4">{result.disclaimer}</p>
              <p className="font-mono text-[11px] text-textFaint mt-1">🔒 {result.request_id} · Ledger sem PII</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

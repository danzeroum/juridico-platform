'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, SectionLabel, Badge, HeuristicBadge, Input, FaixaBadge, EmptyState, Skeleton } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { forecastingApi, type ForecastResponse } from '@/lib/api/forecasting'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'

const MOCK: ForecastResponse = {
  status: 'ok',
  tribunal: 'TJSP',
  classe_tpu: 'Procedimento Comum Cível',
  assunto_tpu: null,
  periodos_historicos: ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06'],
  tendencia: 'CRESCENTE',
  inclinacao: 214.3,
  ultimo_valor: 18420,
  projecoes: [
    { passo: 1, valor: 18634, intervalo: [17200, 20068] },
    { passo: 2, valor: 18848, intervalo: [17040, 20656] },
    { passo: 3, valor: 19063, intervalo: [16890, 21236] },
  ],
  disclaimer: 'heurística (tendência linear) — não validada contra desfechos reais',
}

const MOCK_HISTORICO_VALORES = [15800, 16400, 17100, 17650, 18020, 18420]

export default function ForecastingPage() {
  const { demoMode } = useShell()
  const [tribunal, setTribunal] = useState('TJSP')
  const [classe, setClasse] = useState('')
  const [assunto, setAssunto] = useState('')
  const [horizonte, setHorizonte] = useState(3)

  const query = useQuery({
    queryKey: ['forecasting', tribunal, classe, assunto, horizonte],
    queryFn: () => forecastingApi.demand({ tribunal, classe: classe || undefined, assunto: assunto || undefined, horizonte }),
    enabled: !demoMode && !!tribunal,
  })

  const result = demoMode ? MOCK : query.data

  const historico = demoMode ? MOCK_HISTORICO_VALORES : []
  const maxY = result?.status === 'ok'
    ? Math.max(...historico, ...result.projecoes.map((p) => p.intervalo[1]))
    : 1

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">FC</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Forecasting</h1>
        <HeuristicBadge status="heuristica" />
      </div>
      <p className="text-[13px] text-textMuted -mt-3">Projeção de volume futuro de ações — não é aconselhamento jurídico.</p>

      <Card padding="md">
        <div className="grid grid-cols-4 gap-3">
          <Input label="Tribunal" value={tribunal} onChange={(e) => setTribunal(e.target.value)} />
          <Input label="Classe" value={classe} onChange={(e) => setClasse(e.target.value)} />
          <Input label="Assunto" value={assunto} onChange={(e) => setAssunto(e.target.value)} />
          <Input label="Horizonte" type="number" min={1} max={12} mono value={horizonte} onChange={(e) => setHorizonte(Number(e.target.value))} />
        </div>
      </Card>

      <ApiErrorBanner error={query.error} demoMode={demoMode} />

      {!demoMode && query.isLoading && <Skeleton height={280} className="rounded-card" />}

      {result?.status === 'insuficiente' && (
        <EmptyState icon="📉" title="Dados insuficientes" description={`Requer ao menos ${result.min_periodos} períodos históricos — há apenas ${result.n}.`} />
      )}

      {result?.status === 'ok' && (
        <Card padding="md">
          <div className="flex items-center justify-between gap-3 mb-4">
            <SectionLabel>Projeção — {result.tribunal}{result.classe_tpu ? ` · ${result.classe_tpu}` : ''}</SectionLabel>
            <div className="flex items-center gap-2">
              <FaixaBadge value={result.tendencia} tone={result.tendencia === 'CRESCENTE' ? 'BAIXO' : result.tendencia === 'DECRESCENTE' ? 'ALTO' : 'MODERADO'} />
              <span className="font-mono text-[11px] text-textMuted">inclinação {result.inclinacao.toFixed(2)}</span>
            </div>
          </div>

          {/* Gráfico SVG leve: linha sólida (histórico) + tracejada (projeção) + banda de incerteza */}
          <svg viewBox="0 0 600 200" className="w-full h-56" role="img" aria-label={`Série histórica e projeção de ${result.tribunal}, tendência ${result.tendencia}`}>
            <title>Histórico e projeção de volume de ações</title>
            {(() => {
              const allX = historico.length + result.projecoes.length
              const stepX = 560 / Math.max(1, allX - 1)
              const yFor = (v: number) => 190 - (v / maxY) * 170
              const histPts = historico.map((v, i) => [20 + i * stepX, yFor(v)])
              const lastHistX = histPts.length ? histPts[histPts.length - 1][0] : 20
              const lastHistY = histPts.length ? histPts[histPts.length - 1][1] : 190
              const projPts = result.projecoes.map((p, i) => [lastHistX + (i + 1) * stepX, yFor(p.valor)])
              const bandTop = result.projecoes.map((p, i) => [lastHistX + (i + 1) * stepX, yFor(p.intervalo[1])])
              const bandBottom = result.projecoes.map((p, i) => [lastHistX + (i + 1) * stepX, yFor(p.intervalo[0])]).reverse()
              const bandPath = [[lastHistX, lastHistY], ...bandTop, ...bandBottom, [lastHistX, lastHistY]]
                .map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt[0]},${pt[1]}`).join(' ')
              return (
                <>
                  <path d={bandPath} fill="rgba(47,111,237,0.12)" stroke="none" />
                  <polyline points={histPts.map((p) => p.join(',')).join(' ')} fill="none" stroke="#2f6fed" strokeWidth={2} />
                  <polyline
                    points={[[lastHistX, lastHistY], ...projPts].map((p) => p.join(',')).join(' ')}
                    fill="none" stroke="#2f6fed" strokeWidth={2} strokeDasharray="5,4"
                  />
                  {histPts.map((p, i) => <circle key={`h${i}`} cx={p[0]} cy={p[1]} r={2.5} fill="#2f6fed" />)}
                  {projPts.map((p, i) => <circle key={`p${i}`} cx={p[0]} cy={p[1]} r={3} fill="#fff" stroke="#2f6fed" strokeWidth={2} />)}
                </>
              )
            })()}
          </svg>

          <div className="mt-4 flex flex-col gap-2">
            <SectionLabel>Passos projetados</SectionLabel>
            {result.projecoes.map((p) => (
              <div key={p.passo} className="flex items-center justify-between text-[12px] py-1.5 border-b border-[#f0f2f5] last:border-0">
                <span className="text-textSecondary">Passo +{p.passo}</span>
                <span className="font-mono text-textPrimary">{Math.round(p.valor).toLocaleString('pt-BR')}</span>
                <span className="font-mono text-textFaint text-[11px]">[{Math.round(p.intervalo[0]).toLocaleString('pt-BR')}–{Math.round(p.intervalo[1]).toLocaleString('pt-BR')}]</span>
              </div>
            ))}
          </div>

          <p className="text-[11px] text-textFaint mt-3">{result.disclaimer}</p>
        </Card>
      )}
    </div>
  )
}

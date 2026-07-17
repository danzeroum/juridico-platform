'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, SectionLabel, HeuristicBadge, Input, Badge, EmptyState, Skeleton } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { earlyWarningApi, type EarlyWarningResponse } from '@/lib/api/earlyWarning'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'

const MOCK: EarlyWarningResponse = {
  tribunal: 'TJSP',
  classe_tpu: null,
  assunto_tpu: null,
  n_gatilhos: 2,
  tem_alerta: true,
  gatilhos: [
    { tipo: 'SURTO_VOLUME', severidade: 'HIGH', z_score: 3.4, variacao_pct: 0.58, valor_atual: 18420, media_historica: 14100 },
    { tipo: 'PICO_CONGESTIONAMENTO', severidade: 'MEDIUM', taxa_congestionamento: 0.72 },
  ],
  disclaimer: 'heurística de detecção de surto — não validada',
}

const TIPO_LABEL: Record<string, string> = {
  SURTO_VOLUME: 'Surto de volume',
  PICO_CONGESTIONAMENTO: 'Pico de congestionamento',
}

export default function EarlyWarningPage() {
  const { demoMode } = useShell()
  const [tribunal, setTribunal] = useState('TJSP')
  const [classe, setClasse] = useState('')
  const [assunto, setAssunto] = useState('')

  const query = useQuery({
    queryKey: ['early-warning', tribunal, classe, assunto],
    queryFn: () => earlyWarningApi.evaluate({ tribunal, classe: classe || undefined, assunto: assunto || undefined }),
    enabled: !demoMode && !!tribunal,
  })

  const result = demoMode ? MOCK : query.data

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">EW</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Early Warning</h1>
        <HeuristicBadge status="heuristica" />
      </div>
      <p className="text-[13px] text-textMuted -mt-3">Surtos de volume e picos de congestionamento — não é aconselhamento jurídico.</p>

      <Card padding="md">
        <div className="grid grid-cols-3 gap-3">
          <Input label="Tribunal" value={tribunal} onChange={(e) => setTribunal(e.target.value)} />
          <Input label="Classe" value={classe} onChange={(e) => setClasse(e.target.value)} placeholder="opcional" />
          <Input label="Assunto" value={assunto} onChange={(e) => setAssunto(e.target.value)} placeholder="opcional" />
        </div>
      </Card>

      <ApiErrorBanner error={query.error} demoMode={demoMode} />

      {!demoMode && query.isLoading && <Skeleton height={200} className="rounded-card" />}

      {result && (
        result.gatilhos.length === 0 ? (
          <EmptyState icon="✅" title="Nenhum gatilho ativo" description="Nenhum surto de volume ou pico de congestionamento detectado para os filtros informados." />
        ) : (
          <div className="flex flex-col gap-3">
            {result.gatilhos.map((g, i) => (
              <Card key={i} padding="md" className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <Badge variant={g.severidade} dot>{g.severidade}</Badge>
                  <div>
                    <p className="text-[13px] font-medium text-textPrimary">{TIPO_LABEL[g.tipo] ?? g.tipo}</p>
                    <p className="text-[11px] text-textMuted">{result.tribunal}{result.classe_tpu ? ` · ${result.classe_tpu}` : ''}{result.assunto_tpu ? ` · ${result.assunto_tpu}` : ''}</p>
                  </div>
                </div>
                <div className="font-mono text-[12px] text-textSecondary text-right">
                  {g.tipo === 'SURTO_VOLUME' ? (
                    <>
                      <p>z-score {g.z_score?.toFixed(2)}</p>
                      <p className="text-textFaint">{g.valor_atual?.toLocaleString('pt-BR')} vs média {g.media_historica?.toLocaleString('pt-BR')}</p>
                    </>
                  ) : (
                    <p>congestionamento {g.taxa_congestionamento !== undefined ? `${Math.round(g.taxa_congestionamento * 100)}%` : '—'}</p>
                  )}
                </div>
              </Card>
            ))}
            <p className="text-[11px] text-textFaint">{result.disclaimer}</p>
          </div>
        )
      )}
    </div>
  )
}

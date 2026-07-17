'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Card, SectionLabel, HeuristicBadge, Input, Button, GaugeDonut, FaixaBadge, RbacGate, EmptyState } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { secondOpinionApi, type SecondOpinionOk } from '@/lib/api/secondOpinion'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'

const MOCK: SecondOpinionOk = {
  status: 'ok',
  request_id: 'req_demo_so_001',
  favorabilidade: 0.61,
  veredito: 'FAVORAVEL',
  concordancia: 0.86,
  nivel_concordancia: 'ALTA',
  sinais: { legalscore: 0.648, taxpredict: 0.62, jurimetria: 0.55 },
  n_sinais: 3,
  disclaimer: 'heurística de consenso — não validada contra desfechos reais',
}

const VEREDITO_TONE = { FAVORAVEL: 'BAIXO', INCERTO: 'MODERADO', DESFAVORAVEL: 'CRITICO' } as const

export default function SecondOpinionPage() {
  const { role, demoMode } = useShell()
  const [legalscore, setLegalscore] = useState('648')
  const [taxpredict, setTaxpredict] = useState('0.62')
  const [provimento, setProvimento] = useState('0.55')

  const mutation = useMutation({
    mutationFn: () => secondOpinionApi.opinion({
      legalscore: legalscore ? Number(legalscore) : undefined,
      taxpredict_prob: taxpredict ? Number(taxpredict) : undefined,
      pct_provimento: provimento ? Number(provimento) : undefined,
    }),
  })

  const hasResult = demoMode || mutation.isSuccess
  const result = demoMode ? MOCK : (mutation.data?.status === 'ok' ? mutation.data : null)
  const semSinais = !demoMode && mutation.data?.status === 'sem_sinais'

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">SO</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Second Opinion</h1>
        <HeuristicBadge status="heuristica" />
      </div>
      <p className="text-[13px] text-textMuted -mt-3">
        Parecer de consenso combinando LegalScore + TaxPredict + jurimetria — não é aconselhamento jurídico.
      </p>

      <div className="grid grid-cols-3 gap-4 items-start">
        <Card padding="md" className="flex flex-col gap-4">
          <SectionLabel>Sinais</SectionLabel>
          <Input mono label="LegalScore (0–1000)" value={legalscore} onChange={(e) => setLegalscore(e.target.value)} />
          <Input mono label="TaxPredict — P(favorável) 0–1" value={taxpredict} onChange={(e) => setTaxpredict(e.target.value)} />
          <Input mono label="Jurimetria — % provimento 0–1" value={provimento} onChange={(e) => setProvimento(e.target.value)} />
          <RbacGate role={role} requires="analyst">
            <Button onClick={() => mutation.mutate()} loading={mutation.isPending}>Gerar parecer</Button>
          </RbacGate>
        </Card>

        <div className="col-span-2 flex flex-col gap-4">
          <ApiErrorBanner error={mutation.error} demoMode={demoMode} />

          {!hasResult && !mutation.isPending && (
            <EmptyState icon="⚖️" title="Informe ao menos 1 sinal e clique em Gerar parecer" demoMode={demoMode} />
          )}

          {semSinais && (
            <EmptyState icon="⚖️" title="Nenhum sinal informado" description="Informe ao menos um dos três sinais para gerar um parecer." />
          )}

          {result && (
            <Card padding="lg">
              <div className="flex items-start gap-8">
                <GaugeDonut
                  value={result.favorabilidade}
                  label="Favorabilidade"
                  faixaLabel={result.veredito}
                  tone={VEREDITO_TONE[result.veredito]}
                  size={160}
                />
                <div className="flex-1 flex flex-col gap-3">
                  <div>
                    <SectionLabel>Veredito</SectionLabel>
                    <div className="mt-1"><FaixaBadge value={result.veredito} tone={VEREDITO_TONE[result.veredito]} /></div>
                  </div>
                  <div>
                    <SectionLabel>Concordância entre sinais</SectionLabel>
                    <p className="text-[13px] mt-1">
                      {result.concordancia !== null ? `${Math.round(result.concordancia * 100)}%` : '—'} · <span className="font-medium">{result.nivel_concordancia}</span>
                    </p>
                  </div>
                  <div>
                    <SectionLabel className="mb-2 block">Breakdown normalizado</SectionLabel>
                    <div className="flex flex-col gap-2">
                      {Object.entries(result.sinais).map(([k, v]) => (
                        <div key={k} className="flex flex-col gap-1">
                          <div className="flex justify-between text-[12px]">
                            <span className="text-textSecondary capitalize">{k}</span>
                            <span className="font-mono">{Math.round(v * 100)}%</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-surfaceMuted overflow-hidden">
                            <div className="h-1.5 rounded-full bg-accent" style={{ width: `${v * 100}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
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

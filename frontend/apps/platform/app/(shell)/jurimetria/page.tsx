'use client'
import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Card, SectionLabel, Badge, HeuristicBadge, SourceChip, Input, Button,
  Table, Thead, Tbody, Tr, Th, Td, Skeleton, EmptyState,
} from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { jurimetriaApi, type IndicadorRow } from '@/lib/api/jurimetria'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'

const MOCK_INDICADORES: IndicadorRow[] = [
  { tribunal: 'TJSP', classe_tpu: 'Procedimento Comum Cível', assunto_tpu: 'Indenização por Dano Moral', periodo: '2026-06', fonte: 'BLEND', n_processos: 18420, duracao_mediana_dias: 412, duracao_p25_dias: 210, duracao_p75_dias: 780, taxa_congestionamento: 0.68, taxa_litigiosidade: 0.31, pct_provimento: 0.42 },
  { tribunal: 'TJRJ', classe_tpu: 'Execução Fiscal', assunto_tpu: 'ICMS', periodo: '2026-06', fonte: 'DATAJUD', n_processos: 9871, duracao_mediana_dias: 980, duracao_p25_dias: 540, duracao_p75_dias: 1620, taxa_congestionamento: 0.81, taxa_litigiosidade: 0.44, pct_provimento: 0.28 },
  { tribunal: 'TRF3', classe_tpu: 'Mandado de Segurança', assunto_tpu: 'PIS/COFINS', periodo: '2026-06', fonte: 'ABJ', n_processos: 3120, duracao_mediana_dias: 265, duracao_p25_dias: 140, duracao_p75_dias: 410, taxa_congestionamento: 0.35, taxa_litigiosidade: 0.18, pct_provimento: 0.61 },
]

const MOCK_MI = {
  request_id: 'req_demo_jm_001',
  tribunal: 'TJSP',
  ramo: null,
  total_processos: 152340,
  n_segmentos: 3,
  segmentos: [
    { classe_tpu: 'Procedimento Comum Cível', assunto_tpu: 'Indenização por Dano Moral', total_processos: 74200, congestionamento_medio: 0.68, duracao_mediana_tipica: 412, provimento_medio: 0.42 },
    { classe_tpu: 'Execução Fiscal', assunto_tpu: 'ICMS', total_processos: 51900, congestionamento_medio: 0.81, duracao_mediana_tipica: 980, provimento_medio: 0.28 },
    { classe_tpu: 'Mandado de Segurança', assunto_tpu: 'PIS/COFINS', total_processos: 26240, congestionamento_medio: 0.35, duracao_mediana_tipica: 265, provimento_medio: 0.61 },
  ],
}

function congestionColor(v: number | null): string {
  if (v === null) return '#9aa3af'
  if (v >= 0.7) return '#c4382f'
  if (v >= 0.5) return '#cf6a1f'
  if (v >= 0.3) return '#caa215'
  return '#1f8a5b'
}

export default function JurimetriaPage() {
  const { role, demoMode } = useShell()
  const [tribunal, setTribunal] = useState('')
  const [classe, setClasse] = useState('')
  const [assunto, setAssunto] = useState('')
  const [fonte, setFonte] = useState('')

  const query = useQuery({
    queryKey: ['jurimetria', 'indicadores', tribunal, classe, assunto, fonte],
    queryFn: () => jurimetriaApi.indicadores({ tribunal, classe, assunto, fonte, limit: 100 }),
    enabled: !demoMode,
  })

  const miMutation = useMutation({
    mutationFn: () => jurimetriaApi.marketIntelligence(tribunal || undefined),
  })

  const rows = demoMode ? MOCK_INDICADORES : (query.data?.results ?? [])
  const mi = demoMode ? MOCK_MI : miMutation.data

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">JM</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Jurimetria</h1>
        <HeuristicBadge status="heuristica" />
      </div>
      <p className="text-[13px] text-textMuted -mt-3">
        Indicadores agregados por tribunal/classe/assunto — não é aconselhamento jurídico.
      </p>

      <Card padding="md">
        <div className="grid grid-cols-4 gap-3">
          <Input label="Tribunal" placeholder="TJSP" value={tribunal} onChange={(e) => setTribunal(e.target.value)} />
          <Input label="Classe" placeholder="Procedimento Comum Cível" value={classe} onChange={(e) => setClasse(e.target.value)} />
          <Input label="Assunto" placeholder="Indenização por Dano Moral" value={assunto} onChange={(e) => setAssunto(e.target.value)} />
          <Input label="Fonte" placeholder="DATAJUD | ABJ | BLEND" value={fonte} onChange={(e) => setFonte(e.target.value)} />
        </div>
      </Card>

      <ApiErrorBanner error={query.error} demoMode={demoMode} />

      {!demoMode && query.isLoading && <Skeleton height={220} className="rounded-card" />}

      {(demoMode || query.isSuccess) && (
        <Card padding="md">
          <SectionLabel className="mb-3">Indicadores</SectionLabel>
          {rows.length === 0 ? (
            <EmptyState icon="📊" title="0 segmentos" description="Nenhum indicador encontrado para os filtros informados." demoMode={demoMode} />
          ) : (
            <Table>
              <Thead>
                <Tr>
                  <Th>Tribunal</Th><Th>Classe</Th><Th>Assunto</Th><Th>Fonte</Th>
                  <Th mono>Nº processos</Th><Th mono>Duração mediana</Th><Th>Congestionamento</Th><Th mono>% provimento</Th>
                </Tr>
              </Thead>
              <Tbody>
                {rows.map((r, i) => (
                  <Tr key={i}>
                    <Td mono>{r.tribunal}</Td>
                    <Td>{r.classe_tpu}</Td>
                    <Td>{r.assunto_tpu}</Td>
                    <Td><SourceChip fonte={r.fonte} stale={r.fonte === 'DATAJUD'} /></Td>
                    <Td mono>{r.n_processos.toLocaleString('pt-BR')}</Td>
                    <Td mono>{r.duracao_mediana_dias ?? '—'} dias</Td>
                    <Td>
                      <div className="flex items-center gap-2 w-32">
                        <div className="flex-1 h-1.5 rounded-full bg-surfaceMuted overflow-hidden">
                          <div className="h-1.5 rounded-full" style={{ width: `${(r.taxa_congestionamento ?? 0) * 100}%`, background: congestionColor(r.taxa_congestionamento) }} />
                        </div>
                        <span className="font-mono text-[11px]" style={{ color: congestionColor(r.taxa_congestionamento) }}>
                          {r.taxa_congestionamento !== null ? `${Math.round(r.taxa_congestionamento * 100)}%` : '—'}
                        </span>
                      </div>
                    </Td>
                    <Td mono>{r.pct_provimento !== null ? `${Math.round(r.pct_provimento * 100)}%` : '—'}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </Card>
      )}

      {rows.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          <Card padding="md">
            <SectionLabel className="mb-3">Congestionamento por classe</SectionLabel>
            <div className="flex flex-col gap-3">
              {rows.map((r, i) => (
                <div key={i} className="flex flex-col gap-1">
                  <div className="flex justify-between text-[12px]">
                    <span className="text-textSecondary truncate">{r.classe_tpu}</span>
                    <span className="font-mono" style={{ color: congestionColor(r.taxa_congestionamento) }}>
                      {r.taxa_congestionamento !== null ? `${Math.round(r.taxa_congestionamento * 100)}%` : '—'}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surfaceMuted overflow-hidden">
                    <div className="h-1.5 rounded-full" style={{ width: `${(r.taxa_congestionamento ?? 0) * 100}%`, background: congestionColor(r.taxa_congestionamento) }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>
          <Card padding="md">
            <SectionLabel className="mb-3">Duração — mediana + faixa IQR p25–p75</SectionLabel>
            <div className="flex flex-col gap-3">
              {rows.map((r, i) => (
                <div key={i} className="flex flex-col gap-1">
                  <div className="flex justify-between text-[12px]">
                    <span className="text-textSecondary truncate">{r.classe_tpu}</span>
                    <span className="font-mono text-textSecondary">{r.duracao_mediana_dias ?? '—'}d</span>
                  </div>
                  {r.duracao_p25_dias !== null && r.duracao_p75_dias !== null && (
                    <p className="text-[10px] font-mono text-textFaint">IQR {r.duracao_p25_dias}–{r.duracao_p75_dias}d</p>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Market Intelligence */}
      <div className="rounded-card p-5" style={{ background: '#0c1c33' }}>
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.06em]" style={{ color: '#9fb0c5' }}>Market Intelligence</p>
            <p className="text-[13px] text-white mt-0.5">Relatório setorial agregado — sem PII</p>
          </div>
          <Button variant="secondary" onClick={() => miMutation.mutate()} loading={miMutation.isPending}>
            Gerar relatório
          </Button>
        </div>
        {mi ? (
          <>
            <div className="grid grid-cols-3 gap-3">
              {mi.segmentos.map((s, i) => (
                <div key={i} className="rounded-[8px] p-3" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <p className="text-[11px]" style={{ color: '#9fb0c5' }}>{s.classe_tpu}</p>
                  <p className="font-mono text-[18px] font-bold text-white mt-1">{s.total_processos.toLocaleString('pt-BR')}</p>
                  <p className="text-[11px] mt-1" style={{ color: '#9fb0c5' }}>
                    provimento médio {s.provimento_medio !== null ? `${Math.round(s.provimento_medio * 100)}%` : '—'}
                  </p>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2 mt-4">
              <Badge variant="accent">🔒 Ledger</Badge>
              <span className="font-mono text-[11px]" style={{ color: '#9fb0c5' }}>{mi.request_id} · sem PII</span>
            </div>
          </>
        ) : (
          <p className="text-[12px]" style={{ color: '#9fb0c5' }}>0 segmentos — gere o relatório para ver o resumo.</p>
        )}
      </div>
    </div>
  )
}

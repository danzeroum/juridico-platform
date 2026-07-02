'use client'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Card, SectionLabel, Badge, Button, RbacGate, EmptyState, Skeleton, ProblemJsonError,
  Table, Thead, Tbody, Tr, Th, Td, SourceChip, CircuitBreakerBadge, FreshnessBandChip,
} from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { adminIngestaoApi, type FonteIngestao } from '@/lib/api/adminIngestao'

const MOCK_FONTES: FonteIngestao[] = [
  { fonte: 'RECEITA', lag_dias: 2, circuit_breaker: 'CLOSED', records_in: 480210, records_out: 480102, perda_pct: 0.02, ultimo_run_iso: '2026-07-01T03:12:00Z' },
  { fonte: 'PGFN', lag_dias: 5, circuit_breaker: 'CLOSED', records_in: 210044, records_out: 209980, perda_pct: 0.03, ultimo_run_iso: '2026-06-30T03:05:00Z' },
  { fonte: 'DATAJUD', lag_dias: 4, circuit_breaker: 'HALF_OPEN', records_in: 991200, records_out: 902100, perda_pct: 8.99, ultimo_run_iso: '2026-07-01T02:40:00Z' },
  { fonte: 'PNCP', lag_dias: 1, circuit_breaker: 'CLOSED', records_in: 55210, records_out: 55210, perda_pct: 0, ultimo_run_iso: '2026-07-01T01:00:00Z' },
  { fonte: 'SNIS', lag_dias: 548, circuit_breaker: 'OPEN', records_in: 0, records_out: 0, perda_pct: 100, ultimo_run_iso: '2025-01-02T00:00:00Z' },
  { fonte: 'CONFAZ', lag_dias: 12, circuit_breaker: 'CLOSED', records_in: 3410, records_out: 3401, perda_pct: 0.26, ultimo_run_iso: '2026-06-25T04:20:00Z' },
]

export default function AdminIngestaoPage() {
  const { role, demoMode } = useShell()

  const query = useQuery({
    queryKey: ['admin', 'ingestao', 'fontes'],
    queryFn: () => adminIngestaoApi.fontes(),
    enabled: !demoMode && role === 'admin',
    retry: false,
  })

  const runMutation = useMutation({ mutationFn: (fonte: string) => adminIngestaoApi.run(fonte) })

  const fontes = demoMode ? MOCK_FONTES : (query.data?.fontes ?? [])

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">IG</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Ingestão & Saúde de Dados</h1>
        <Badge variant="blocked">admin</Badge>
      </div>
      <p className="text-[13px] text-textMuted -mt-3">Operar/observar o pipeline por fonte pública.</p>

      <RbacGate
        role={role}
        requires="admin"
        showLockChip={false}
        fallback={<EmptyState icon="🔒" title="Exige perfil Admin" description="Esta tela é restrita ao grupo Admin · Dados." />}
      >
        {!demoMode && !query.isLoading && !query.isSuccess && (
          <ProblemJsonError
            error={{
              type: 'about:blank',
              title: 'Console de ingestão indisponível',
              status: 503,
              detail: 'O backend de observabilidade da ingestão ainda não expõe um endpoint HTTP (services/ingest/ é Celery-only). Ative o modo demonstração para visualizar o layout.',
            }}
          />
        )}

        {!demoMode && query.isLoading && <Skeleton height={280} className="rounded-card" />}

        {fontes.length === 0 && (demoMode || query.isSuccess) ? (
          <EmptyState icon="📡" title="Nenhuma fonte configurada" demoMode={demoMode} />
        ) : fontes.length > 0 ? (
          <Card padding="md">
            <SectionLabel className="mb-3">Fontes</SectionLabel>
            <Table>
              <Thead>
                <Tr>
                  <Th>Fonte</Th><Th>Frescor</Th><Th>Circuit breaker</Th>
                  <Th mono>Records in</Th><Th mono>Records out</Th><Th mono>% perda</Th>
                  <Th>Último run</Th><Th>Ação</Th>
                </Tr>
              </Thead>
              <Tbody>
                {fontes.map((f) => (
                  <Tr key={f.fonte}>
                    <Td><SourceChip fonte={f.fonte} /></Td>
                    <Td><FreshnessBandChip lagDays={f.lag_dias} /></Td>
                    <Td><CircuitBreakerBadge state={f.circuit_breaker} /></Td>
                    <Td mono>{f.records_in.toLocaleString('pt-BR')}</Td>
                    <Td mono>{f.records_out.toLocaleString('pt-BR')}</Td>
                    <Td mono style={f.perda_pct >= 5 ? { color: '#c4382f', fontWeight: 600 } : undefined}>{f.perda_pct.toFixed(2)}%</Td>
                    <Td mono className="text-[11px]">{new Date(f.ultimo_run_iso).toLocaleString('pt-BR')}</Td>
                    <Td>
                      <RbacGate role={role} requires="admin">
                        <Button
                          variant="secondary" size="sm"
                          disabled={f.circuit_breaker === 'OPEN'}
                          loading={runMutation.isPending && runMutation.variables === f.fonte}
                          onClick={() => runMutation.mutate(f.fonte)}
                        >
                          disparar
                        </Button>
                      </RbacGate>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Card>
        ) : null}
      </RbacGate>
    </div>
  )
}

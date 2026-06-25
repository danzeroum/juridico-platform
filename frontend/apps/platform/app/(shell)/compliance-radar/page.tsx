'use client'
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Card, CardHeader, SectionLabel, Badge, FreshnessSeal, AlertList, EmptyState, Button, ProblemJsonError, Skeleton } from '@juridico/ui'
import type { ProblemJson } from '@juridico/ui'
import { lagToFreshnessBand } from '@juridico/tokens'
import { useShell } from '@/app/context/shell'
import { complianceApi } from '@/lib/api/compliance'
import { ApiError } from '@/lib/api/client'
import { Tabs, TabPanel } from '@juridico/ui'
import type { AlertItem } from '@juridico/ui'

const PERFIL_IBGE = '1302603' // Manaus/AM

const UF_DATA = [
  { uf: 'SP', severity: 'LOW' as const }, { uf: 'RJ', severity: 'HIGH' as const },
  { uf: 'MG', severity: 'MEDIUM' as const }, { uf: 'RS', severity: 'LOW' as const },
  { uf: 'BA', severity: 'CRITICAL' as const }, { uf: 'PR', severity: 'LOW' as const },
  { uf: 'PE', severity: 'HIGH' as const }, { uf: 'CE', severity: 'MEDIUM' as const },
  { uf: 'PA', severity: 'CRITICAL' as const }, { uf: 'MA', severity: 'HIGH' as const },
  { uf: 'AM', severity: 'CRITICAL' as const }, { uf: 'SC', severity: 'LOW' as const },
  { uf: 'GO', severity: 'MEDIUM' as const }, { uf: 'ES', severity: 'LOW' as const },
  { uf: 'MT', severity: 'MEDIUM' as const }, { uf: 'RN', severity: 'HIGH' as const },
  { uf: 'PB', severity: 'MEDIUM' as const }, { uf: 'AL', severity: 'HIGH' as const },
  { uf: 'PI', severity: 'CRITICAL' as const }, { uf: 'MS', severity: 'LOW' as const },
  { uf: 'SE', severity: 'MEDIUM' as const }, { uf: 'RO', severity: 'MEDIUM' as const },
  { uf: 'TO', severity: 'MEDIUM' as const }, { uf: 'AC', severity: 'MEDIUM' as const },
  { uf: 'AP', severity: 'MEDIUM' as const }, { uf: 'RR', severity: 'MEDIUM' as const },
  { uf: 'DF', severity: 'LOW' as const },
]

const SEVERITY_COLORS = {
  LOW: '#1f8a5b', MEDIUM: '#b07d00', HIGH: '#cf6a1f', CRITICAL: '#c4382f',
}

const MOCK_ALERTS: AlertItem[] = [
  { id: '1', severity: 'CRITICAL', title: 'Arrecadação crítica — Manaus/AM', subjectRef: 'IBGE:1302603', channels: ['email', 'webhook'], deliveryStatus: 'done', createdAt: '2h' },
  { id: '2', severity: 'HIGH', title: 'Saneamento abaixo do mínimo — Teresina/PI', subjectRef: 'IBGE:2211001', channels: ['slack'], deliveryStatus: 'pending', createdAt: '5h' },
]

const TABS = [
  { id: 'cartograma', label: 'Cartograma' },
  { id: 'municipios', label: 'Municípios' },
  { id: 'perfil', label: 'Perfil' },
  { id: 'assinaturas', label: 'Assinaturas' },
  { id: 'alertas', label: 'Alertas' },
]

const MOCK_INDICATORS = [
  { label: 'Arrecadação YoY', value: '-8.3%', lagDays: 90, severity: 'HIGH' as const },
  { label: 'Emprego YoY', value: '+1.2%', lagDays: 45, severity: 'LOW' as const },
  { label: 'Cobertura de Água', value: '71%', lagDays: 548, severity: 'CRITICAL' as const },
  { label: 'Cobertura de Esgoto', value: '38%', lagDays: 548, severity: 'CRITICAL' as const },
  { label: 'IDHM', value: '0.668', lagDays: 365, severity: 'MEDIUM' as const },
  { label: 'PIB per capita', value: 'R$ 18.4k', lagDays: 365, severity: 'MEDIUM' as const },
]

export default function ComplianceRadarPage() {
  const { demoMode } = useShell()
  const [activeTab, setActiveTab] = useState('cartograma')
  const [selectedUf, setSelectedUf] = useState<string | null>(null)

  const [selectedMun, setSelectedMun] = useState<{ cod: string; nome: string } | null>(null)

  const evalMutation = useMutation({
    mutationFn: () => complianceApi.evaluate(PERFIL_IBGE),
  })

  // Coleta ao vivo do IBGE — municípios da UF selecionada no cartograma.
  const municipiosQuery = useQuery({
    queryKey: ['ibge-municipios', selectedUf],
    queryFn: () => complianceApi.municipios(selectedUf as string),
    enabled: !!selectedUf,
  })

  const populacaoQuery = useQuery({
    queryKey: ['ibge-populacao', selectedMun?.cod],
    queryFn: () => complianceApi.populacao(selectedMun!.cod),
    enabled: !!selectedMun,
  })

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">CR</span>
        <h1 className="text-[20px] font-bold text-textPrimary">ComplianceRadar</h1>
        <Badge variant="accent" className="ml-auto text-[10px]">99% entrega</Badge>
      </div>

      <Tabs tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />

      <TabPanel id="cartograma" activeTab={activeTab}>
        <div className="grid grid-cols-4 gap-4 mt-4">
          <div className="col-span-3">
            <Card padding="md">
              <SectionLabel className="mb-3">Brasil — Severidade por UF</SectionLabel>
              {/* SNIS warning */}
              <div className="mb-4">
                <FreshnessSeal source="SNIS" lagDays={548} band="very_stale" />
              </div>
              <div
                role="group"
                aria-label="Cartograma de severidade por UF"
                className="grid gap-1.5"
                style={{ gridTemplateColumns: 'repeat(7, 1fr)' }}
              >
                {UF_DATA.map((d) => (
                  <button
                    key={d.uf}
                    role="group"
                    aria-label={`${d.uf}: ${d.severity}`}
                    onClick={() => { setSelectedUf(d.uf); setSelectedMun(null); setActiveTab('municipios') }}
                    className="h-10 rounded-[6px] flex items-center justify-center text-white text-[10px] font-bold transition-transform hover:scale-110"
                    style={{ background: SEVERITY_COLORS[d.severity] }}
                    title={`${d.uf}: ${d.severity}`}
                  >
                    {d.uf}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-4 mt-4">
                {Object.entries(SEVERITY_COLORS).map(([sev, color]) => (
                  <div key={sev} className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-sm" style={{ background: color }} aria-hidden />
                    <span className="text-[11px] text-textMuted">{sev}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
          <div>
            <Card padding="none">
              <CardHeader className="px-4 pt-4 pb-3 border-b border-[#f0f2f5] mb-0">
                <SectionLabel>Municípios em alerta</SectionLabel>
              </CardHeader>
              {[
                { name: 'Manaus/AM', sev: 'CRITICAL' as const }, { name: 'Belém/PA', sev: 'CRITICAL' as const },
                { name: 'Teresina/PI', sev: 'HIGH' as const }, { name: 'São Luís/MA', sev: 'HIGH' as const },
              ].map((m) => (
                <div key={m.name} className="flex items-center gap-2 px-4 py-2 border-b border-[#f0f2f5]">
                  <Badge variant={m.sev} dot>{m.sev}</Badge>
                  <span className="text-[12px] text-textPrimary">{m.name}</span>
                </div>
              ))}
            </Card>
          </div>
        </div>
      </TabPanel>

      <TabPanel id="perfil" activeTab={activeTab}>
        <Card padding="md" className="mt-4 flex flex-col gap-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="font-mono text-[12px] text-textMuted">IBGE: {PERFIL_IBGE}</p>
              <h2 className="text-[17px] font-bold text-textPrimary">Manaus / AM</h2>
            </div>
            <div className="flex items-center gap-3">
              {evalMutation.isSuccess && (
                <Badge variant={evalMutation.data.rules_fired > 0 ? 'ALTO' : 'LOW'}>
                  {evalMutation.data.rules_fired} regra(s) disparada(s)
                </Badge>
              )}
              <Button variant="secondary" size="sm" loading={evalMutation.isPending} onClick={() => evalMutation.mutate()}>
                Avaliar regras agora
              </Button>
            </div>
          </div>

          {evalMutation.isError && evalMutation.error instanceof ApiError && (
            <ProblemJsonError error={evalMutation.error.problem as ProblemJson} />
          )}
          <div className="grid grid-cols-3 gap-3">
            {MOCK_INDICATORS.map((ind) => (
              <div key={ind.label} className="bg-surfaceMuted rounded-card p-3">
                <p className="text-[10px] text-textSectionLabel font-semibold uppercase tracking-[0.04em] mb-1">{ind.label}</p>
                <p className="font-mono text-[20px] font-bold text-textPrimary">{ind.value}</p>
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant={ind.severity} dot>{ind.severity}</Badge>
                  <FreshnessSeal source="IBGE" lagDays={ind.lagDays} band={lagToFreshnessBand(ind.lagDays)} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </TabPanel>

      <TabPanel id="alertas" activeTab={activeTab}>
        <Card padding="none" className="mt-4">
          <AlertList alerts={MOCK_ALERTS} />
        </Card>
      </TabPanel>

      <TabPanel id="municipios" activeTab={activeTab}>
        <Card padding="md" className="mt-4">
          {!selectedUf && (
            <EmptyState icon="🏘️" title="Lista de municípios" description="Selecione uma UF no cartograma — os municípios são coletados ao vivo do IBGE." />
          )}

          {selectedUf && municipiosQuery.isLoading && <Skeleton height={240} className="rounded-card" />}

          {selectedUf && municipiosQuery.isError && municipiosQuery.error instanceof ApiError && (
            <ProblemJsonError error={municipiosQuery.error.problem as ProblemJson} />
          )}

          {selectedUf && municipiosQuery.data && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <SectionLabel>Municípios de {selectedUf} · {municipiosQuery.data.total}</SectionLabel>
                <FreshnessSeal source="IBGE" lagDays={0} band="fresh" />
              </div>
              <div className="grid grid-cols-3 gap-2 max-h-[420px] overflow-y-auto pr-1">
                {municipiosQuery.data.municipios.map((m) => (
                  <button
                    key={m.cod_ibge}
                    onClick={() => setSelectedMun({ cod: m.cod_ibge, nome: m.municipio })}
                    className={`flex flex-col items-start gap-0.5 rounded-[6px] border px-3 py-2 text-left transition-colors ${selectedMun?.cod === m.cod_ibge ? 'border-accent bg-accentTintBg' : 'border-borderStrong hover:bg-surfaceMuted'}`}
                  >
                    <span className="text-[12px] font-medium text-textPrimary">{m.municipio}</span>
                    <span className="font-mono text-[10px] text-textMuted">IBGE {m.cod_ibge}</span>
                  </button>
                ))}
              </div>

              {selectedMun && (
                <div className="mt-1 rounded-card bg-surfaceMuted p-4">
                  <p className="text-[10px] uppercase tracking-[0.04em] text-textSectionLabel font-semibold mb-1">{selectedMun.nome}</p>
                  {populacaoQuery.isLoading && <span className="text-[12px] text-textMuted">Consultando IBGE…</span>}
                  {populacaoQuery.data && (
                    <p className="font-mono text-[20px] font-bold text-textPrimary">
                      {populacaoQuery.data.populacao != null ? populacaoQuery.data.populacao.toLocaleString('pt-BR') : '—'}
                      <span className="text-[11px] font-normal text-textMuted ml-2">hab. · pop. estimada {populacaoQuery.data.ano ?? ''}</span>
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </Card>
      </TabPanel>

      <TabPanel id="assinaturas" activeTab={activeTab}>
        <Card padding="md" className="mt-4">
          <EmptyState icon="🔔" title="Assinaturas de alerta" description="Nenhuma assinatura ativa. Configure canais (webhook, email, slack, whatsapp) para receber alertas." />
        </Card>
      </TabPanel>
    </div>
  )
}

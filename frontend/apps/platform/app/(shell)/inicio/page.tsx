'use client'
import { useRouter } from 'next/navigation'
import { Card, CardHeader, SectionLabel, Badge, EmptyState, FreshnessSeal } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { ArrowRight, AlertTriangle, Activity, ClipboardList, Zap } from 'lucide-react'
import { cn } from '@juridico/ui'
import { lagToFreshnessBand } from '@juridico/tokens'

const PRODUCTS = [
  { code: 'LS', name: 'LegalScore', desc: 'Rating de risco jurídico-financeiro de PJ', href: '/legalscore', sla: 'p95 < 1,5s' },
  { code: 'CT', name: 'ContabilIA', desc: 'Auditoria contábil automatizada (8 cross-checks)', href: '/contabilia', sla: 'p95 < 60s' },
  { code: 'CR', name: 'ComplianceRadar', desc: 'Monitoramento municipal com alertas', href: '/compliance-radar', sla: '99% entrega' },
  { code: 'TP', name: 'TaxPredict', desc: 'Previsão bayesiana de desfecho tributário', href: '/taxpredict', sla: 'p95 < 3s' },
  { code: 'LW', name: 'LicitaWatch', desc: 'Anomalias em licitações e contratos públicos', href: '/licita-watch', sla: 'PNCP' },
  { code: 'DB', name: 'DanoBot', desc: 'Quantificação de danos em saúde pública', href: '/danobot', blocked: true, sla: 'bloqueado' },
  { code: 'PB', name: 'PetiBot', desc: 'Geração de peças com precedentes verificáveis', href: '/petibot', sla: 'RAG' },
  { code: 'CC', name: 'ConciliaIA', desc: 'Recomendação de acordo com faixa de valores', href: '/concilia', sla: 'ML' },
]

const SOURCES = [
  { name: 'Receita', lagDays: 2 },
  { name: 'PGFN', lagDays: 31 },
  { name: 'DATAJUD', lagDays: 4 },
  { name: 'PNCP', lagDays: 1 },
  { name: 'CAGED', lagDays: 45 },
  { name: 'SICONFI', lagDays: 90 },
  { name: 'SNIS', lagDays: 548 },
]

const RECENT_ALERTS = [
  { severity: 'CRITICAL' as const, title: 'Arrecadação crítica — Manaus/AM', ref: 'IBGE:1302603', time: '2h' },
  { severity: 'HIGH' as const, title: 'Único proponente — Órgão 0001', ref: 'CNPJ:00.394.460/0007-94', time: '5h' },
  { severity: 'MEDIUM' as const, title: 'DATAJUD defasado >30d', ref: 'sistema', time: '1d' },
]

export default function InicioPage() {
  const { demoMode, setDemoMode } = useShell()
  const router = useRouter()

  if (!demoMode) {
    return (
      <EmptyState
        icon="📊"
        title="Nenhum dado ingerido"
        description="Conecte as APIs e ingira dados para ver o dashboard."
        demoMode
        action={{ label: 'Ativar dados de demonstração', onClick: () => setDemoMode(true) }}
      />
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { icon: Activity, label: 'Consultas hoje', value: '1.247', color: 'text-accent' },
          { icon: ClipboardList, label: 'Auditorias na fila', value: '3', color: 'text-riskMedium' },
          { icon: AlertTriangle, label: 'Alertas críticos', value: '2', color: 'text-riskCritical' },
          { icon: Zap, label: 'Uso da API', value: '42/100', color: 'text-riskLow' },
        ].map((kpi) => (
          <Card key={kpi.label} padding="md">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-textSectionLabel mb-1">
                  {kpi.label}
                </p>
                <p className={cn('font-mono text-[28px] font-semibold leading-none', kpi.color)}>
                  {kpi.value}
                </p>
              </div>
              <kpi.icon className={cn('w-5 h-5 flex-shrink-0 mt-0.5', kpi.color)} aria-hidden />
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Products grid */}
        <div className="col-span-2 flex flex-col gap-4">
          <SectionLabel>Produtos · Lentes</SectionLabel>
          <div className="grid grid-cols-2 gap-3">
            {PRODUCTS.map((p) => (
              <button
                key={p.code}
                onClick={() => !p.blocked && router.push(p.href)}
                disabled={p.blocked}
                className={cn(
                  'text-left rounded-card border border-border bg-surface p-4 transition-colors duration-[120ms]',
                  p.blocked
                    ? 'opacity-50 cursor-not-allowed'
                    : 'hover:border-accentTintBorder',
                )}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="font-mono text-[11px] font-bold px-1.5 py-0.5 rounded-[4px] bg-surfaceMuted text-textSecondary">
                    {p.code}
                  </span>
                  {p.blocked ? (
                    <Badge variant="CRITICO">BLOQUEADO</Badge>
                  ) : (
                    <span className="font-mono text-[10px] text-textFaint">{p.sla}</span>
                  )}
                </div>
                <p className="text-[13px] font-semibold text-textPrimary">{p.name}</p>
                <p className="text-[11px] text-textMuted mt-0.5">{p.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-4">
          {/* Recent alerts */}
          <Card padding="none">
            <CardHeader className="px-4 pt-4 pb-3 border-b border-[#f0f2f5] mb-0">
              <SectionLabel>Alertas recentes</SectionLabel>
              <button
                onClick={() => router.push('/alertas')}
                className="text-[11px] text-accent hover:underline flex items-center gap-1"
              >
                ver todos <ArrowRight className="w-3 h-3" aria-hidden />
              </button>
            </CardHeader>
            <div className="divide-y divide-[#f0f2f5]">
              {RECENT_ALERTS.map((a) => (
                <div key={a.title} className="flex items-center gap-2 px-4 py-2.5">
                  <Badge variant={a.severity} dot className="flex-shrink-0">{a.severity}</Badge>
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] font-medium text-textPrimary truncate">{a.title}</p>
                    <p className="text-[10px] font-mono text-textFaint">{a.ref}</p>
                  </div>
                  <span className="text-[10px] text-textFaint flex-shrink-0">{a.time}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Data freshness */}
          <Card padding="md">
            <SectionLabel className="mb-3">Frescor das fontes</SectionLabel>
            <div className="flex flex-col gap-2">
              {SOURCES.map((s) => (
                <div key={s.name} className="flex items-center justify-between gap-2">
                  <FreshnessSeal
                    source={s.name}
                    lagDays={s.lagDays}
                    band={lagToFreshnessBand(s.lagDays)}
                  />
                </div>
              ))}
            </div>
          </Card>

          {/* Open entity CTA */}
          <button
            onClick={() => router.push('/entidade')}
            className="w-full rounded-card border border-accentTintBorder bg-accentTintBg py-3 text-[13px] font-semibold text-accent hover:bg-accentTintBgAlt transition-colors"
          >
            Abrir entidade (CNPJ) →
          </button>
        </div>
      </div>
    </div>
  )
}

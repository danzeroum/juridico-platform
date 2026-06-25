'use client'
import { useParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import {
  Card, CardHeader, SectionLabel, Badge, TrustHeader, FreshnessSeal,
  EmptyState, DegradationBanner, SkeletonCard,
} from '@juridico/ui'
import { lagToFreshnessBand } from '@juridico/tokens'
import { useShell } from '@/app/context/shell'
import { entidadeApi } from '@/lib/api/entidade'
import { ArrowRight, Shield } from 'lucide-react'
import { cn } from '@juridico/ui'

function fmtDate(v?: string | null): string | null {
  if (!v || v.length !== 10) return v ?? null
  const [y, m, d] = v.split('-')
  return `${d}/${m}/${y}`
}

// Mock entity data (real: GET /api/v1/entities/{cnpj})
const MOCK_ENTITY = {
  cnpj: '00.000.000/0001-91',
  razaoSocial: 'Empresa Demonstração S.A.',
  situacao: 'ATIVA',
  cnae: '6201-5/00 — Desenvolvimento de programas de computador',
  porte: 'Médio',
  capital: 'R$ 500.000,00',
  abertura: '15/03/2010',
}

const MOCK_LENSES = [
  {
    code: 'LS', name: 'LegalScore', href: 'legalscore',
    summary: '648', label: 'MODERADO', variant: 'MODERADO' as const,
    detail: 'Score de risco jurídico-financeiro',
  },
  {
    code: 'CT', name: 'ContabilIA', href: 'contabilia',
    summary: '5 achados', label: '1 crítico', variant: 'ALTO' as const,
    detail: 'Auditoria contábil — último relatório',
  },
  {
    code: 'TP', name: 'TaxPredict', href: 'taxpredict',
    summary: '62%', label: 'desfecho favorável', variant: 'MODERADO' as const,
    detail: 'Predição bayesiana tributária',
  },
  {
    code: 'CC', name: 'ConciliaIA', href: 'concilia',
    summary: 'R$ 110k', label: 'acordo sugerido', variant: 'LOW' as const,
    detail: 'Faixa de acordo recomendada',
  },
  {
    code: 'PB', name: 'PetiBot', href: 'petibot',
    summary: '3 peças', label: 'geradas', variant: 'LOW' as const,
    detail: 'Peças jurídicas com precedentes',
  },
  {
    code: 'LW', name: 'LicitaWatch', href: 'licita-watch',
    summary: 'N/A', label: 'não aplicável (PJ)', variant: 'muted' as const,
    detail: 'Monitoramento de contratos públicos',
  },
]

export default function EntidadePage() {
  const params = useParams()
  const router = useRouter()
  const { demoMode } = useShell()
  const cnpj = typeof params.cnpj === 'string' ? decodeURIComponent(params.cnpj) : ''
  const cnpjDigits = cnpj.replace(/\D/g, '')

  const entidadeQuery = useQuery({
    queryKey: ['entidade', cnpjDigits],
    queryFn: () => entidadeApi.get(cnpjDigits),
    enabled: !demoMode && cnpjDigits.length === 14,
  })

  // Loading / vazio no modo real (dados ao vivo da Receita)
  if (!demoMode) {
    if (entidadeQuery.isLoading) return <SkeletonCard />
    if (!entidadeQuery.data?.encontrado) {
      return (
        <div className="flex flex-col gap-4">
          <DegradationBanner
            message="Cadastro da Receita indisponível"
            detail="Fonte CNPJ fora da allowlist de rede ou CNPJ não encontrado. Veja docs/NETWORK-ALLOWLIST.md."
          />
          <EmptyState icon="🏢" title="Nenhuma entidade carregada" description="Pesquise um CNPJ válido na barra de busca acima." />
        </div>
      )
    }
  }

  const cad = entidadeQuery.data?.cadastro
  const entity = demoMode
    ? { ...MOCK_ENTITY, cnpj: cnpj || MOCK_ENTITY.cnpj }
    : {
        cnpj: cnpjDigits,
        razaoSocial: cad?.razao_social || '—',
        situacao: cad?.situacao_cadastral || '—',
        cnae: [cad?.cnae_fiscal, cad?.cnae_descricao].filter(Boolean).join(' — ') || '—',
        porte: cad?.porte || '—',
        capital: cad?.capital_social != null
          ? cad.capital_social.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
          : '—',
        abertura: fmtDate(cad?.data_abertura) || '—',
      }
  const ativa = entity.situacao === 'ATIVA'

  return (
    <div className="flex flex-col gap-5">
      {/* Label */}
      <div className="flex items-center gap-2 px-1">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-textSectionLabel">
          A entidade é o hub · os produtos são lentes
        </span>
      </div>

      {/* Entity header */}
      <Card padding="md">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <h1 className="text-[20px] font-bold text-textPrimary">{entity.razaoSocial}</h1>
              <Badge variant={ativa ? 'LOW' : 'ALTO'} dot>{entity.situacao}</Badge>
            </div>
            <p className="font-mono text-[13px] text-textSecondary">{entity.cnpj}</p>
            <p className="text-[12px] text-textMuted">{entity.cnae}</p>
          </div>
          <div className="flex flex-col gap-1 text-right text-[11px] text-textMuted flex-shrink-0">
            <span>Porte: <strong className="text-textSecondary">{entity.porte}</strong></span>
            <span>Capital: <strong className="text-textSecondary font-mono">{entity.capital}</strong></span>
            <span>Abertura: <strong className="text-textSecondary font-mono">{entity.abertura}</strong></span>
          </div>
        </div>
      </Card>

      {/* Trust Header */}
      <TrustHeader
        sources={[
          { name: 'Receita', lagDays: 2, band: lagToFreshnessBand(2) },
          { name: 'PGFN', lagDays: 31, band: lagToFreshnessBand(31) },
          { name: 'DATAJUD', lagDays: 4, band: lagToFreshnessBand(4) },
        ]}
        score={648}
        ciLow={610}
        ciHigh={689}
        modelStatus="heuristica"
        sourceNames={['DATAJUD', 'PGFN', 'Receita', 'CAGED', 'Neo4j']}
        extraSourceCount={2}
        onVerify={() => router.push('/auditoria')}
      />

      <div className="grid grid-cols-3 gap-5">
        {/* Lens grid */}
        <div className="col-span-2">
          <SectionLabel className="mb-3">Lentes disponíveis</SectionLabel>
          <div className="grid grid-cols-2 gap-3">
            {MOCK_LENSES.map((lens) => (
              <button
                key={lens.code}
                onClick={() => router.push(`/${lens.href}?cnpj=${encodeURIComponent(entity.cnpj)}`)}
                className="text-left rounded-card border border-border bg-surface p-4 hover:border-accentTintBorder transition-colors"
              >
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-[4px] bg-surfaceMuted text-textSecondary">
                    {lens.code}
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-textFaint" aria-hidden />
                </div>
                {demoMode && (
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="font-mono text-[20px] font-bold text-textPrimary">{lens.summary}</span>
                    <Badge variant={lens.variant}>{lens.label}</Badge>
                  </div>
                )}
                <p className="text-[11px] text-textMuted">{lens.detail}</p>
                <p className="text-[12px] font-semibold text-textSecondary mt-1">{lens.name}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Right rail */}
        <div className="flex flex-col gap-4">
          {/* Entity alerts */}
          <Card padding="none">
            <CardHeader className="px-4 pt-4 pb-3 border-b border-[#f0f2f5] mb-0">
              <SectionLabel>Alertas desta entidade</SectionLabel>
            </CardHeader>
            <div className="p-4 text-[12px] text-textFaint text-center py-6">
              Nenhum alerta ativo
            </div>
          </Card>

          {/* Decision Ledger CTA */}
          <div
            className="rounded-card p-4 text-white flex flex-col gap-2"
            style={{ background: '#0c1c33' }}
          >
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-accent" aria-hidden />
              <span className="text-[11px] font-semibold uppercase tracking-[0.06em]">Decision Ledger</span>
            </div>
            <p className="text-[11px] text-[#9fb0c5]">
              Prova criptográfica de integridade (Merkle) para todas as decisões desta entidade.
            </p>
            <button
              onClick={() => router.push('/auditoria')}
              className="self-start text-[11px] font-medium text-accent hover:underline flex items-center gap-1 mt-1"
            >
              Ver trilha de auditoria <ArrowRight className="w-3 h-3" aria-hidden />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

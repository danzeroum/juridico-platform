'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, SectionLabel, HeuristicBadge, Input, GaugeDonut, Skeleton, DegradationBanner } from '@juridico/ui'
import { RISK_COLORS } from '@juridico/tokens'
import { useShell } from '@/app/context/shell'
import { chamberProfilerApi, type ChamberProfile } from '@/lib/api/chamberProfiler'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'

const MOCK: ChamberProfile = {
  tribunal: 'TJSP',
  grao: 'tribunal+classe',
  n_processos: 18420,
  n_segmentos: 6,
  perfil: {
    provimento: { valor: 0.42, faixa: 'MODERADO_PROVIMENTO' },
    congestionamento: { valor: 0.81, faixa: 'MUITO_CONGESTIONADO' },
    duracao_mediana_dias: { valor: 412, faixa: 'MEDIANO' },
  },
  disclaimer: 'perfil AGREGADO por órgão (não por juiz individual) — heurística, não validada; ver governança LGPD em pendencias.md',
}

function toneFor(faixa: string): keyof typeof RISK_COLORS {
  if (/ALTO|MUITO_CONGESTIONADO|LENTO/.test(faixa)) return 'CRITICO'
  if (/MODERADO|CONGESTIONADO|MEDIANO/.test(faixa)) return 'MODERADO'
  return 'BAIXO'
}

export default function ChamberProfilerPage() {
  const { demoMode } = useShell()
  const [tribunal, setTribunal] = useState('TJSP')
  const [classe, setClasse] = useState('')

  const query = useQuery({
    queryKey: ['chamber-profiler', tribunal, classe],
    queryFn: () => chamberProfilerApi.profile(tribunal, classe || undefined),
    enabled: !demoMode && !!tribunal,
  })

  const profile = demoMode ? MOCK : query.data

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">CP</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Chamber Profiler</h1>
        <HeuristicBadge status="heuristica" />
      </div>
      <p className="text-[13px] text-textMuted -mt-3">Perfil agregado do órgão julgador — não é aconselhamento jurídico.</p>

      <DegradationBanner
        message="⚖ Vedado perfilar juiz individual (LGPD)"
        detail="O grão mínimo é órgão julgador (tribunal+classe) — o request não aceita identificador de magistrado."
      />

      <Card padding="md">
        <div className="grid grid-cols-2 gap-3">
          <Input label="Tribunal" value={tribunal} onChange={(e) => setTribunal(e.target.value)} />
          <Input label="Classe" value={classe} onChange={(e) => setClasse(e.target.value)} placeholder="opcional" />
        </div>
      </Card>

      <ApiErrorBanner error={query.error} demoMode={demoMode} />

      {!demoMode && query.isLoading && <Skeleton height={260} className="rounded-card" />}

      {profile && (
        <Card padding="lg">
          <SectionLabel className="mb-1">{profile.tribunal} · grão {profile.grao}</SectionLabel>
          <p className="text-[12px] text-textMuted mb-6">{profile.n_processos.toLocaleString('pt-BR')} processos · {profile.n_segmentos} segmentos</p>

          <div className="grid grid-cols-3 gap-6 justify-items-center">
            <GaugeDonut
              value={profile.perfil.provimento.valor ?? 0}
              label="Provimento"
              faixaLabel={profile.perfil.provimento.faixa}
              tone={toneFor(profile.perfil.provimento.faixa)}
            />
            <GaugeDonut
              value={profile.perfil.congestionamento.valor ?? 0}
              label="Congestionamento"
              faixaLabel={profile.perfil.congestionamento.faixa}
              tone={toneFor(profile.perfil.congestionamento.faixa)}
            />
            <GaugeDonut
              value={Math.min(1, (profile.perfil.duracao_mediana_dias.valor ?? 0) / 1000)}
              valueLabel={`${profile.perfil.duracao_mediana_dias.valor ?? '—'}d`}
              label="Duração mediana"
              faixaLabel={profile.perfil.duracao_mediana_dias.faixa}
              tone={toneFor(profile.perfil.duracao_mediana_dias.faixa)}
            />
          </div>

          <p className="text-[11px] text-textFaint mt-6 text-center">{profile.disclaimer}</p>
        </Card>
      )}
    </div>
  )
}

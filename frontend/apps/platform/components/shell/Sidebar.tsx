'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { LogOut, ChevronDown } from 'lucide-react'

interface NavItem {
  code: string
  label: string
  href: string
  locked?: boolean
  tip?: string
}

const PLATAFORMA_NAV: NavItem[] = [
  { code: 'IN', label: 'Início', href: '/inicio' },
  { code: 'EN', label: 'Entidade', href: '/entidade' },
  { code: 'AL', label: 'Alertas', href: '/alertas' },
  { code: 'AU', label: 'Auditoria', href: '/auditoria' },
  { code: 'CF', label: 'Conformidade', href: '/conformidade' },
]

const INTELIGENCIA_NAV: NavItem[] = [
  { code: 'JM', label: 'Jurimetria', href: '/jurimetria', tip: 'Indicadores agregados por tribunal/classe/assunto' },
  { code: 'KG', label: 'Knowledge Graph', href: '/knowledge-graph', tip: 'Processos de uma empresa + rede de co-litigância' },
  { code: 'FC', label: 'Forecasting', href: '/forecasting', tip: 'Projeção de volume futuro de ações' },
  { code: 'CP', label: 'Chamber Profiler', href: '/chamber-profiler', tip: 'Perfil agregado do órgão julgador — nunca por juiz' },
  { code: 'SO', label: 'Second Opinion', href: '/second-opinion', tip: 'Parecer de consenso entre LegalScore/TaxPredict/jurimetria' },
  { code: 'ST', label: 'Settlement Optimizer', href: '/settlement', tip: 'Zona de acordo (ZOPA) por análise de decisão' },
  { code: 'EW', label: 'Early Warning', href: '/early-warning', tip: 'Surtos de volume e picos de congestionamento' },
]

const PRODUTOS_NAV: NavItem[] = [
  { code: 'LS', label: 'LegalScore', href: '/legalscore' },
  { code: 'CT', label: 'ContabilIA', href: '/contabilia' },
  { code: 'CR', label: 'ComplianceRadar', href: '/compliance-radar' },
  { code: 'TP', label: 'TaxPredict', href: '/taxpredict' },
  { code: 'FI', label: 'Fiscal', href: '/fiscal', tip: 'Triagem NCM/ICMS + enriquecimento em lote' },
  { code: 'LW', label: 'LicitaWatch', href: '/licita-watch' },
  { code: 'DB', label: 'DanoBot', href: '/danobot', locked: true },
  { code: 'PB', label: 'PetiBot', href: '/petibot' },
  { code: 'DF', label: 'Defensor', href: '/defensor' },
  { code: 'CC', label: 'ConciliaIA', href: '/concilia' },
  { code: 'TC', label: 'TribunaConnect', href: '/tribuna' },
]

const ADMIN_NAV: NavItem[] = [
  { code: 'IG', label: 'Ingestão & Saúde de Dados', href: '/admin/ingestao', tip: 'Operar/observar o pipeline por fonte (admin)' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { tenant, role } = useShell()

  const configItem: NavItem = { code: 'CG', label: 'Configurações', href: '/configuracoes' }

  return (
    <nav
      className="flex flex-col h-full flex-shrink-0 overflow-y-auto"
      style={{ width: 238, background: '#0c1c33' }}
      aria-label="Navegação principal"
    >
      {/* Logo + tenant */}
      <div className="px-5 pt-5 pb-4 border-b" style={{ borderColor: '#1a2d4e' }}>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-7 h-7 rounded-[6px] bg-accent flex items-center justify-center">
            <span className="font-mono text-[10px] font-bold text-white">JC</span>
          </div>
          <span className="text-[13px] font-semibold text-white">Jurídico-Contábil</span>
        </div>
        <button className="w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-[6px] hover:bg-white/5 transition-colors">
          <span className="text-[12px] font-medium text-[#9fb0c5] truncate">{tenant?.name ?? '—'}</span>
          <ChevronDown className="w-3.5 h-3.5 text-[#9fb0c5] flex-shrink-0" aria-hidden />
        </button>
      </div>

      {/* PLATAFORMA */}
      <div className="flex-1 px-3 py-3">
        <p className="px-2 mb-1 text-[10px] font-semibold uppercase tracking-[0.08em]" style={{ color: '#4a6080' }}>
          Plataforma
        </p>
        <div className="flex flex-col gap-0.5">
          {PLATAFORMA_NAV.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}
          {role === 'admin' && <NavLink item={configItem} pathname={pathname} />}
        </div>

        <div className="my-3 border-t" style={{ borderColor: '#1a2d4e' }} />

        <p className="px-2 mb-1 text-[10px] font-semibold uppercase tracking-[0.08em]" style={{ color: '#4a6080' }}>
          Produtos · Lentes
        </p>
        <div className="flex flex-col gap-0.5">
          {PRODUTOS_NAV.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}
        </div>

        <div className="my-3 border-t" style={{ borderColor: '#1a2d4e' }} />

        <p className="px-2 mb-1 text-[10px] font-semibold uppercase tracking-[0.08em]" style={{ color: '#4a6080' }}>
          Inteligência · Jurimetria
        </p>
        <div className="flex flex-col gap-0.5">
          {INTELIGENCIA_NAV.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}
        </div>

        {role === 'admin' && (
          <>
            <div className="my-3 border-t" style={{ borderColor: '#1a2d4e' }} />
            <p className="px-2 mb-1 text-[10px] font-semibold uppercase tracking-[0.08em]" style={{ color: '#4a6080' }}>
              Admin · Dados
            </p>
            <div className="flex flex-col gap-0.5">
              {ADMIN_NAV.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Footer: user */}
      <div className="px-3 pb-4 border-t" style={{ borderColor: '#1a2d4e' }}>
        <div className="flex items-center gap-2 px-2 py-2 mt-3">
          <div className="w-7 h-7 rounded-full bg-accentTintBg flex items-center justify-center text-[10px] font-bold text-accent flex-shrink-0">
            U
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-medium text-white truncate">Usuário</p>
            <p className="text-[10px] font-mono capitalize" style={{ color: '#9fb0c5' }}>{role}</p>
          </div>
          <a
            href="/api/auth/logout"
            aria-label="Sair"
            className="text-[#9fb0c5] hover:text-white transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </a>
        </div>
      </div>
    </nav>
  )
}

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const isActive = pathname === item.href || pathname.startsWith(item.href + '/')

  return (
    <Link
      href={item.locked ? '#' : item.href}
      aria-current={isActive ? 'page' : undefined}
      aria-disabled={item.locked}
      title={item.tip}
      data-tip={item.tip}
      className={cn(
        'flex items-center gap-2.5 px-2.5 py-1.5 rounded-[6px] transition-colors duration-[120ms]',
        isActive
          ? 'text-white'
          : 'text-[#9fb0c5] hover:text-white hover:bg-white/5',
        item.locked && 'opacity-50 pointer-events-none',
      )}
      style={isActive ? {
        background: 'rgba(47,111,237,0.16)',
        boxShadow: 'inset 3px 0 0 #2f6fed',
      } : {}}
    >
      <span className="font-mono text-[10px] font-medium w-5 flex-shrink-0 text-center opacity-60">
        {item.code}
      </span>
      <span className="text-[12px] font-medium">{item.label}</span>
      {item.locked && (
        <span className="ml-auto text-[9px] font-mono uppercase px-1 py-0.5 rounded bg-riskCriticalBg text-riskCriticalText">
          bloq.
        </span>
      )}
    </Link>
  )
}

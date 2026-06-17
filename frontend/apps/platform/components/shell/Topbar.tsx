'use client'
import { usePathname, useRouter } from 'next/navigation'
import { Bell, Search } from 'lucide-react'
import { cn } from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import type { RbacRole } from '@juridico/tokens'

const ROLE_LABELS: Record<RbacRole, string> = {
  admin: 'Admin',
  analyst: 'Analista',
  viewer: 'Leitor',
}

const ROLE_ORDER: RbacRole[] = ['admin', 'analyst', 'viewer']

export function Topbar() {
  const pathname = usePathname()
  const router = useRouter()
  const { role, setRole, demoMode, setDemoMode } = useShell()

  const breadcrumb = pathToBreadcrumb(pathname)

  function handleSearch(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      const val = (e.target as HTMLInputElement).value.trim()
      if (val) router.push(`/entidade/${encodeURIComponent(val)}`)
    }
  }

  return (
    <header
      className="flex items-center gap-4 px-6 border-b border-border bg-surface flex-shrink-0"
      style={{ height: 58 }}
    >
      {/* Breadcrumb */}
      <div className="flex-1 min-w-0">
        <h1 className="text-[14px] font-semibold text-textPrimary truncate">{breadcrumb}</h1>
      </div>

      {/* Global search */}
      <div className="relative w-64">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-textFaint" aria-hidden />
        <input
          type="search"
          placeholder="CNPJ, empresa, município…"
          className={cn(
            'w-full rounded-[8px] border border-borderStrong bg-surfaceMuted pl-8 pr-3 py-1.5 text-[12px] text-textPrimary',
            'placeholder:text-textFaint',
            'focus:outline-none focus:ring-2 focus:ring-accentTintBorder focus:border-accent',
          )}
          onKeyDown={handleSearch}
          aria-label="Busca global — pressione Enter para abrir entidade"
        />
      </div>

      {/* Demo toggle */}
      <button
        onClick={() => setDemoMode(!demoMode)}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1 rounded-pill text-[11px] font-medium border transition-colors',
          demoMode
            ? 'bg-accentTintBg text-accent border-accentTintBorder'
            : 'bg-surfaceMuted text-textMuted border-border',
        )}
        aria-pressed={demoMode}
        title="Toggle de dados de demonstração"
      >
        <span
          className={cn('w-1.5 h-1.5 rounded-full', demoMode ? 'bg-accent' : 'bg-textMuted')}
          aria-hidden
        />
        {demoMode ? 'Demo' : 'Limpo'}
      </button>

      {/* RBAC switcher */}
      <div className="flex items-center gap-0.5 bg-surfaceMuted rounded-[8px] p-0.5 border border-border">
        {ROLE_ORDER.map((r) => (
          <button
            key={r}
            onClick={() => setRole(r)}
            className={cn(
              'px-2.5 py-1 rounded-[6px] text-[11px] font-medium transition-colors',
              role === r
                ? 'bg-surface text-textPrimary shadow-sm'
                : 'text-textMuted hover:text-textSecondary',
            )}
            aria-pressed={role === r}
          >
            {ROLE_LABELS[r]}
          </button>
        ))}
      </div>

      {/* Rate limit */}
      <div className="flex flex-col gap-0.5 min-w-[60px]" title="Uso da API: 42/100 req/min">
        <div className="flex justify-between">
          <span className="text-[10px] font-mono text-textFaint">42/100</span>
        </div>
        <div className="h-1 rounded-full bg-surfaceMuted overflow-hidden">
          <div className="h-1 rounded-full bg-accent" style={{ width: '42%' }} />
        </div>
      </div>

      {/* Notifications */}
      <button className="relative text-textMuted hover:text-textPrimary transition-colors" aria-label="Notificações (3 não lidas)">
        <Bell className="w-4.5 h-4.5" />
        <span
          className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-riskCritical text-white text-[9px] font-bold flex items-center justify-center"
          aria-hidden
        >
          3
        </span>
      </button>
    </header>
  )
}

function pathToBreadcrumb(pathname: string): string {
  const map: Record<string, string> = {
    '/inicio': 'Início',
    '/entidade': 'Entidade',
    '/alertas': 'Alertas',
    '/auditoria': 'Auditoria',
    '/conformidade': 'Conformidade',
    '/configuracoes': 'Configurações',
    '/legalscore': 'LegalScore',
    '/contabilia': 'ContabilIA',
    '/compliance-radar': 'ComplianceRadar',
    '/taxpredict': 'TaxPredict',
    '/licita-watch': 'LicitaWatch',
    '/danobot': 'DanoBot',
    '/petibot': 'PetiBot',
    '/concilia': 'ConciliaIA',
    '/tribuna': 'TribunaConnect',
  }
  for (const [prefix, label] of Object.entries(map)) {
    if (pathname === prefix || pathname.startsWith(prefix + '/')) return label
  }
  return 'Plataforma'
}

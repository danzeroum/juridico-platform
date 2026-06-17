import type { Metadata } from 'next'

export const metadata: Metadata = { title: 'Entrar — Plataforma Jurídico-Contábil' }

export default function LoginPage() {
  return (
    <div className="min-h-screen flex">
      {/* Left: Navy hero */}
      <div
        className="flex flex-col justify-between p-10 text-white"
        style={{
          flex: '1.1',
          background: '#0c1c33',
          backgroundImage: 'radial-gradient(circle at 30% 40%, rgba(47,111,237,0.08) 0%, transparent 60%)',
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-[8px] bg-accent flex items-center justify-center">
            <span className="font-mono text-[13px] font-bold text-white">JC</span>
          </div>
          <span className="text-[16px] font-semibold">Jurídico-Contábil</span>
        </div>

        {/* Headline */}
        <div className="flex flex-col gap-6">
          <div>
            <h1 className="text-[32px] font-bold leading-tight tracking-[-0.02em] mb-3">
              Decisões de risco com<br />prova de origem.
            </h1>
            <p className="text-[14px] text-[#9fb0c5] max-w-md leading-relaxed">
              IA aplicada ao direito e à contabilidade brasileira. Cada número carrega fonte,
              defasagem, intervalo de incerteza e prova de integridade verificável.
            </p>
          </div>

          {/* Feature chips */}
          <div className="flex flex-wrap gap-2">
            {[
              'Decision Ledger · Merkle',
              'LGPD · multi-tenant',
              '14 fontes públicas',
            ].map((chip) => (
              <span
                key={chip}
                className="px-3 py-1 rounded-pill text-[12px] font-mono font-medium border"
                style={{ borderColor: '#21385f', color: '#9fb0c5' }}
              >
                {chip}
              </span>
            ))}
          </div>
        </div>

        {/* Honest SLA footer */}
        <p className="text-[11px] font-mono" style={{ color: '#4a6080' }}>
          ~99% · nó único · janela de manutenção dom 02:00–04:00
        </p>
      </div>

      {/* Right: Form */}
      <div
        className="flex flex-col items-center justify-center p-10"
        style={{ flex: '0.9', background: '#f5f6f8' }}
      >
        <div className="w-full max-w-[360px]">
          <h2 className="text-[22px] font-semibold text-textPrimary mb-1">Entrar</h2>
          <p className="text-[13px] text-textMuted mb-7">Acesse sua conta da plataforma</p>

          <form className="flex flex-col gap-4" action="/api/auth/login" method="POST">
            <div className="flex flex-col gap-1">
              <label htmlFor="email" className="text-[12px] font-medium text-textSecondary">E-mail</label>
              <input
                id="email"
                type="email"
                name="email"
                required
                autoComplete="email"
                placeholder="voce@escritorio.com.br"
                className="w-full rounded-[8px] border border-borderStrong bg-surface px-3 py-2.5 text-[13px] text-textPrimary placeholder:text-textFaint focus:outline-none focus:ring-2 focus:ring-accentTintBorder focus:border-accent"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="password" className="text-[12px] font-medium text-textSecondary">Senha</label>
              <input
                id="password"
                type="password"
                name="password"
                required
                autoComplete="current-password"
                placeholder="••••••••"
                className="w-full rounded-[8px] border border-borderStrong bg-surface px-3 py-2.5 text-[13px] text-textPrimary placeholder:text-textFaint focus:outline-none focus:ring-2 focus:ring-accentTintBorder focus:border-accent"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="tenant" className="text-[12px] font-medium text-textSecondary">Tenant / Escritório</label>
              <select
                id="tenant"
                name="tenant"
                className="w-full rounded-[8px] border border-borderStrong bg-surface px-3 py-2.5 text-[13px] text-textPrimary focus:outline-none focus:ring-2 focus:ring-accentTintBorder focus:border-accent"
              >
                <option value="">Selecionar…</option>
                <option value="demo">Demo</option>
              </select>
            </div>

            <button
              type="submit"
              className="w-full rounded-[8px] bg-accent text-white py-2.5 text-[13px] font-semibold hover:bg-accentHover transition-colors mt-1"
            >
              Entrar
            </button>
          </form>

          <p className="mt-6 text-center text-[11px] text-textFaint">
            conexão isolada por tenant · TLS · auditada
          </p>
        </div>
      </div>
    </div>
  )
}

'use client'
import { Card, CardHeader, SectionLabel, Badge, Avatar, AvatarStack } from '@juridico/ui'

const PRESENCE = [
  { name: 'Ana Souza', status: 'online' as const, action: 'editando' },
  { name: 'Carlos Lima', status: 'online' as const, action: 'online' },
  { name: 'Maria Gomes', status: 'away' as const, action: 'ausente' },
  { name: 'João Santos', status: 'offline' as const, action: 'offline' },
]

const TIMELINE = [
  { author: 'Ana Souza', time: '14:32', content: 'Adicionou cláusula de rescisão antecipada' },
  { author: 'Carlos Lima', time: '14:28', content: 'Revisou seção DOS FATOS' },
  { author: 'Maria Gomes', time: '14:15', content: 'Importou modelo de ação coletiva' },
]

export default function TribunaConnectPage() {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">TC</span>
        <h1 className="text-[20px] font-bold text-textPrimary">TribunaConnect</h1>
        <Badge variant="beta">BETA · TEMPO REAL</Badge>
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-pill bg-riskLowBg border border-[#bfe3d0]">
          <span
            className="w-1.5 h-1.5 rounded-full bg-riskLow"
            style={{ animation: 'pulse 1.6s cubic-bezier(0.4,0,0.6,1) infinite' }}
            aria-hidden
          />
          <span className="text-[11px] font-medium text-riskLowText">AO VIVO · 3 de 4 on-line</span>
        </div>
      </div>

      {/* Case banner */}
      <div className="rounded-card px-5 py-4 text-white flex items-center justify-between gap-4" style={{ background: '#0c1c33' }}>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[#9fb0c5] mb-1">Ação Coletiva</p>
          <p className="text-[14px] font-semibold">Processo nº 0001234-56.2026.8.26.0001</p>
          <p className="text-[11px] text-[#9fb0c5] mt-0.5">Alerta vinculado: CRITICAL — Arrecadação Manaus/AM</p>
        </div>
        <AvatarStack names={PRESENCE.map((p) => p.name)} max={4} size="sm" />
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Shared draft */}
        <div className="col-span-2 flex flex-col gap-3">
          <Card padding="md">
            <SectionLabel className="mb-3">Minuta compartilhada</SectionLabel>
            <div
              contentEditable
              suppressContentEditableWarning
              className="min-h-[300px] text-[13px] text-textPrimary leading-relaxed outline-none focus:ring-2 focus:ring-accentTintBorder rounded-[6px] p-2 -m-2"
            >
              EXMO. SR. JUIZ DA {'{'}VARA{'}'} DA FAZENDA PÚBLICA DA COMARCA DE MANAUS/AM...{'\n\n'}
              Os autores, por seus advogados, vêm respeitosamente perante V. Exa. propor a presente{'\n'}
              AÇÃO CIVIL PÚBLICA COM PEDIDO DE TUTELA DE URGÊNCIA...
            </div>
            <p className="text-[11px] text-textMuted mt-3 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-riskLow animate-pulse" aria-hidden />
              Ana Souza está digitando…
            </p>
          </Card>

          {/* Timeline */}
          <Card padding="md">
            <SectionLabel className="mb-3">
              Timeline compartilhada
              <span className="ml-2 text-[10px] font-mono text-accent normal-case tracking-normal">ao vivo</span>
            </SectionLabel>
            <div className="flex flex-col gap-3">
              {TIMELINE.map((event, i) => (
                <div key={i} className="flex items-start gap-3">
                  <Avatar name={event.author} size="xs" />
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[12px] font-semibold text-textPrimary">{event.author}</span>
                      <span className="text-[11px] font-mono text-textFaint">{event.time}</span>
                    </div>
                    <p className="text-[12px] text-textSecondary">{event.content}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Presence rail */}
        <div className="flex flex-col gap-4">
          <Card padding="md">
            <SectionLabel className="mb-3">Presença</SectionLabel>
            <div className="flex flex-col gap-2">
              {PRESENCE.map((p) => (
                <div key={p.name} className="flex items-center gap-2.5">
                  <Avatar name={p.name} size="sm" status={p.status} />
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] font-medium text-textPrimary truncate">{p.name}</p>
                    <p className="text-[10px] text-textMuted">{p.action}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card padding="none">
            <CardHeader className="px-4 pt-4 pb-3 border-b border-[#f0f2f5] mb-0">
              <SectionLabel>Canais</SectionLabel>
            </CardHeader>
            {[{ name: '#geral', unread: 3 }, { name: '#jurisprudências', unread: 0 }, { name: '#notas', unread: 1 }].map((ch) => (
              <div key={ch.name} className="flex items-center justify-between px-4 py-2 hover:bg-surfaceMuted/50 cursor-pointer">
                <span className="text-[12px] font-mono text-textSecondary">{ch.name}</span>
                {ch.unread > 0 && (
                  <span className="w-4 h-4 rounded-full bg-accent text-white text-[9px] font-bold flex items-center justify-center">
                    {ch.unread}
                  </span>
                )}
              </div>
            ))}
          </Card>
        </div>
      </div>
    </div>
  )
}

import { Card } from '@juridico/ui'
import { Lock } from 'lucide-react'

export default function DanoBotPage() {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">DB</span>
        <h1 className="text-[20px] font-bold text-textPrimary">DanoBot</h1>
        <span className="px-2 py-0.5 rounded-chip text-[11px] font-semibold bg-riskCriticalBg text-riskCriticalText border border-[#f0c2bd]">
          BLOQUEADO
        </span>
      </div>

      <Card padding="lg" className="flex flex-col items-center gap-5 py-12">
        <div className="w-14 h-14 rounded-full bg-surfaceMuted flex items-center justify-center">
          <Lock className="w-7 h-7 text-textMuted" aria-hidden />
        </div>

        <div className="flex flex-col items-center gap-2 text-center max-w-md">
          <p className="text-[17px] font-bold text-textPrimary">Indisponível — em conformidade legal</p>
          <p className="text-[13px] text-textSecondary">
            O produto DanoBot está aguardando liberação formal do DPO conforme exigência do
            DATASUS (art. 11, Lei 14.510/2022) e da decisão interna PD-06. Qualquer consulta
            retorna <span className="font-mono">HTTP 501</span> intencionalmente.
          </p>
          <span className="mt-1 px-3 py-1 rounded-pill text-[11px] font-mono bg-surfaceMuted text-textMuted border border-border">
            aguardando liberação do DPO
          </span>
        </div>

        {/* Preview layout (disabled) */}
        <div className="w-full mt-4 opacity-30 pointer-events-none select-none">
          <div className="grid grid-cols-3 gap-3">
            {['Indicador A', 'Indicador B', 'Indicador C'].map((label) => (
              <div key={label} className="bg-surfaceMuted rounded-card p-4 h-24 flex items-center justify-center">
                <span className="text-[12px] text-textFaint">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  )
}

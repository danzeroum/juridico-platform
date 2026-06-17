import * as React from 'react'
import { cn } from '../lib/cn'

interface DegradationBannerProps {
  message?: string
  detail?: string
  className?: string
}

export function DegradationBanner({
  message = 'Score parcial — circuit breaker ativo',
  detail,
  className,
}: DegradationBannerProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex items-start gap-3 rounded-[8px] border border-[#ecdcae] bg-[#fbf6e9] px-4 py-3',
        className,
      )}
    >
      <span
        className="w-2 h-2 mt-1.5 rounded-full bg-[#b07d00] flex-shrink-0"
        style={{ animation: 'pulse 1.6s cubic-bezier(0.4,0,0.6,1) infinite' }}
        aria-hidden
      />
      <div className="flex flex-col gap-0.5">
        <p className="text-[13px] font-medium text-[#7a5800]">{message}</p>
        {detail && <p className="text-[12px] text-[#7a5800] opacity-80">{detail}</p>}
      </div>
    </div>
  )
}

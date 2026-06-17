import * as React from 'react'
import { cn } from '../lib/cn'

export function Table({ className, children, ...props }: React.HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn('w-full border-collapse text-[13px]', className)} {...props}>
        {children}
      </table>
    </div>
  )
}

export function Thead({ className, children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={cn('border-b border-border', className)} {...props}>
      {children}
    </thead>
  )
}

export function Tbody({ className, children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody {...props} className={className}>{children}</tbody>
}

export function Tr({ className, children, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn('border-b border-[#f0f2f5] hover:bg-surfaceMuted transition-colors', className)}
      {...props}
    >
      {children}
    </tr>
  )
}

export function Th({ className, children, mono, ...props }: React.ThHTMLAttributes<HTMLTableCellElement> & { mono?: boolean }) {
  return (
    <th
      className={cn(
        'px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-[0.06em] text-textSectionLabel',
        mono && 'font-mono',
        className,
      )}
      {...props}
    >
      {children}
    </th>
  )
}

export function Td({ className, children, mono, ...props }: React.TdHTMLAttributes<HTMLTableCellElement> & { mono?: boolean }) {
  return (
    <td
      className={cn(
        'px-3 py-2.5 text-[13px] text-textPrimary',
        mono && 'font-mono text-[12px]',
        className,
      )}
      {...props}
    >
      {children}
    </td>
  )
}

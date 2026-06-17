import * as React from 'react'
import { cn } from '../lib/cn'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean
  label?: string
  error?: string
  hint?: string
  startIcon?: React.ReactNode
  endIcon?: React.ReactNode
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ mono, label, error, hint, startIcon, endIcon, className, id: idProp, ...props }, ref) => {
    const id = idProp ?? React.useId()
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={id} className="text-[12px] font-medium text-textSecondary">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {startIcon && (
            <span className="absolute left-3 text-textMuted pointer-events-none">{startIcon}</span>
          )}
          <input
            ref={ref}
            id={id}
            className={cn(
              'w-full rounded-[8px] border border-borderStrong bg-surface px-3 py-2 text-[13px] text-textPrimary',
              'placeholder:text-textFaint',
              'transition-shadow duration-[120ms]',
              'focus:outline-none focus:shadow-focusRing focus:border-accent',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              mono && 'font-mono',
              startIcon && 'pl-9',
              endIcon && 'pr-9',
              error && 'border-riskCritical',
              className,
            )}
            aria-invalid={error ? 'true' : undefined}
            aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
            {...props}
          />
          {endIcon && (
            <span className="absolute right-3 text-textMuted">{endIcon}</span>
          )}
        </div>
        {error && (
          <span id={`${id}-error`} role="alert" className="text-[11px] text-riskCriticalText">
            {error}
          </span>
        )}
        {hint && !error && (
          <span id={`${id}-hint`} className="text-[11px] text-textFaint">
            {hint}
          </span>
        )}
      </div>
    )
  },
)
Input.displayName = 'Input'

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
  hint?: string
  charCount?: { current: number; max: number }
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, hint, charCount, className, id: idProp, ...props }, ref) => {
    const id = idProp ?? React.useId()
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <div className="flex justify-between items-center">
            <label htmlFor={id} className="text-[12px] font-medium text-textSecondary">
              {label}
            </label>
            {charCount && (
              <span className="text-[11px] text-textFaint font-mono">
                {charCount.current}/{charCount.max}
              </span>
            )}
          </div>
        )}
        <textarea
          ref={ref}
          id={id}
          className={cn(
            'w-full rounded-[8px] border border-borderStrong bg-surface px-3 py-2 text-[13px] text-textPrimary',
            'placeholder:text-textFaint resize-none',
            'transition-shadow duration-[120ms]',
            'focus:outline-none focus:shadow-focusRing focus:border-accent',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            error && 'border-riskCritical',
            className,
          )}
          aria-invalid={error ? 'true' : undefined}
          {...props}
        />
        {error && <span role="alert" className="text-[11px] text-riskCriticalText">{error}</span>}
        {hint && !error && <span className="text-[11px] text-textFaint">{hint}</span>}
      </div>
    )
  },
)
Textarea.displayName = 'Textarea'

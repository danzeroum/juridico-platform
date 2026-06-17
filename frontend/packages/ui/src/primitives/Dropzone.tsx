'use client'
import * as React from 'react'
import { cn } from '../lib/cn'
import { Upload } from 'lucide-react'

interface DropzoneProps {
  accept?: string
  maxSize?: number
  hint?: string
  onFiles: (files: FileList) => void
  className?: string
  disabled?: boolean
}

export function Dropzone({ accept, maxSize, hint, onFiles, className, disabled }: DropzoneProps) {
  const [dragOver, setDragOver] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    if (disabled) return
    if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files)
  }

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label="Área de upload — clique ou arraste arquivos"
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => e.key === 'Enter' && !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-[10px] border-2 border-dashed p-8 cursor-pointer transition-colors',
        dragOver ? 'border-accent bg-accentTintBg' : 'border-border bg-surfaceMuted hover:border-accentTintBorder',
        disabled && 'opacity-50 cursor-not-allowed',
        className,
      )}
    >
      <Upload className="w-8 h-8 text-textMuted" aria-hidden />
      <div className="text-center">
        <p className="text-[13px] font-medium text-textPrimary">Arraste ou clique para enviar</p>
        {hint && <p className="text-[12px] text-textMuted mt-1">{hint}</p>}
        {maxSize && (
          <p className="text-[11px] text-textFaint mt-0.5">
            Máx. {(maxSize / 1024 / 1024).toFixed(0)} MB
          </p>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => e.target.files && onFiles(e.target.files)}
      />
    </div>
  )
}

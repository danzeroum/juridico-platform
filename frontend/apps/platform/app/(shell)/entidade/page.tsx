'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Input, Button, EmptyState } from '@juridico/ui'
import { Search } from 'lucide-react'

export default function EntidadeIndexPage() {
  const router = useRouter()
  const [cnpj, setCnpj] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const clean = cnpj.replace(/\D/g, '')
    if (clean.length === 14) {
      router.push(`/entidade/${encodeURIComponent(cnpj)}`)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-6">
      <EmptyState
        icon="🏢"
        title="Buscar entidade"
        description="Digite um CNPJ para abrir o hub de análise com todas as lentes disponíveis."
      />
      <form onSubmit={handleSubmit} className="flex gap-2 w-full max-w-md">
        <div className="flex-1">
          <Input
            mono
            placeholder="00.000.000/0000-00"
            value={cnpj}
            onChange={(e) => setCnpj(e.target.value)}
            aria-label="CNPJ da entidade"
          />
        </div>
        <Button type="submit" variant="primary">
          <Search className="w-4 h-4" aria-hidden />
          Abrir
        </Button>
      </form>
    </div>
  )
}

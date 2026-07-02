'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Card, SectionLabel, Badge, Input, Button, RelationBadge, EmptyState, Skeleton, DegradationBanner,
} from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { knowledgeGraphApi, type NetworkSummary, type ProcessoRow } from '@/lib/api/knowledgeGraph'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'

const MOCK_NETWORK: NetworkSummary = {
  cnpj: '12.345.678/0001-90',
  n_vizinhos: 4,
  distribuicao: { ISOLADO: 1, OCASIONAL: 1, RECORRENTE: 1, PREDATORIO: 1 },
  tem_litigancia_predatoria: true,
  vizinhos: [
    { cnpj: '98.765.432/0001-10', nome: 'Telecom Brasil Conecta S.A.', ramos: ['Telecom'], processos_em_comum: 34, relacao: 'PREDATORIO' },
    { cnpj: '11.222.333/0001-44', nome: 'Construtora Alfa Ltda.', ramos: ['Construção Civil'], processos_em_comum: 7, relacao: 'RECORRENTE' },
    { cnpj: '55.666.777/0001-88', nome: 'Logística Beta S.A.', ramos: ['Logística'], processos_em_comum: 3, relacao: 'OCASIONAL' },
    { cnpj: '22.333.444/0001-99', nome: 'Varejo Gama Ltda.', ramos: ['Varejo'], processos_em_comum: 1, relacao: 'ISOLADO' },
  ],
}

const MOCK_PROCESSOS: ProcessoRow[] = [
  { id_cnj: '1023456-45.2025.8.26.0100', tribunal: 'TJSP', classe: 'Procedimento Comum Cível', assunto: 'Indenização', ramo: 'Cível', data: '2025-11-02' },
  { id_cnj: '0451209-88.2024.8.19.0001', tribunal: 'TJRJ', classe: 'Execução Fiscal', assunto: 'ICMS', ramo: 'Tributário', data: '2024-06-18' },
]

const MOCK_STATS = { empresas: 128430, processos: 891204, arestas: 214887 }

export default function KnowledgeGraphPage() {
  const { demoMode } = useShell()
  const [cnpj, setCnpj] = useState('')

  const networkMutation = useMutation({ mutationFn: (c: string) => knowledgeGraphApi.companyNetwork(c) })
  const processesMutation = useMutation({ mutationFn: (c: string) => knowledgeGraphApi.companyProcesses(c) })

  function buscar() {
    if (!cnpj) return
    networkMutation.mutate(cnpj)
    processesMutation.mutate(cnpj)
  }

  const hasResult = demoMode || networkMutation.isSuccess
  const network = demoMode ? MOCK_NETWORK : networkMutation.data
  const processos = demoMode ? MOCK_PROCESSOS : (processesMutation.data?.results ?? [])
  const stats = demoMode ? MOCK_STATS : MOCK_STATS // /stats é global — não depende do CNPJ buscado

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">KG</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Knowledge Graph</h1>
        <Badge variant="accent">rede CNPJ↔CNPJ</Badge>
      </div>
      <p className="text-[13px] text-textMuted -mt-3">
        Processos de uma empresa e rede de co-litigância — apenas dados públicos, pessoas naturais não são expostas.
      </p>

      <Card padding="md">
        <form onSubmit={(e) => { e.preventDefault(); buscar() }} className="flex items-end gap-3">
          <div className="flex-1">
            <Input mono label="CNPJ" placeholder="00.000.000/0000-00" value={cnpj} onChange={(e) => setCnpj(e.target.value)} />
          </div>
          <Button type="submit" loading={networkMutation.isPending || processesMutation.isPending}>Buscar rede</Button>
        </form>
      </Card>

      <ApiErrorBanner error={networkMutation.error} demoMode={demoMode} />

      <div className="grid grid-cols-3 gap-4">
        <Card padding="md"><SectionLabel>Empresas</SectionLabel><p className="font-mono text-[25px] font-semibold mt-1">{stats.empresas.toLocaleString('pt-BR')}</p></Card>
        <Card padding="md"><SectionLabel>Processos</SectionLabel><p className="font-mono text-[25px] font-semibold mt-1">{stats.processos.toLocaleString('pt-BR')}</p></Card>
        <Card padding="md"><SectionLabel>Arestas</SectionLabel><p className="font-mono text-[25px] font-semibold mt-1">{stats.arestas.toLocaleString('pt-BR')}</p></Card>
      </div>

      {!hasResult && !networkMutation.isPending && (
        <EmptyState icon="🕸️" title="Informe um CNPJ e clique em Buscar rede" demoMode={demoMode} />
      )}

      {networkMutation.isPending && <Skeleton height={220} className="rounded-card" />}

      {hasResult && network && (
        <>
          {network.tem_litigancia_predatoria && (
            <DegradationBanner
              message="⚠ Litigância predatória detectada"
              detail="Uma ou mais empresas da rede compartilham volume anormal de processos com esta entidade."
            />
          )}

          <div className="grid grid-cols-2 gap-4 items-start">
            <Card padding="md">
              <SectionLabel className="mb-3">Rede de vizinhos ({network.n_vizinhos})</SectionLabel>
              {network.vizinhos.length === 0 ? (
                <p className="text-[13px] text-textFaint text-center py-8">Nenhum vizinho — empresa sem co-litigância detectada.</p>
              ) : (
                <div className="flex flex-col divide-y divide-[#f0f2f5]">
                  {network.vizinhos.map((v) => (
                    <div key={v.cnpj} className="flex items-center justify-between gap-3 py-2.5">
                      <div className="min-w-0">
                        <p className="text-[13px] font-medium text-textPrimary truncate">{v.nome ?? '—'}</p>
                        <p className="font-mono text-[11px] text-textMuted">{v.cnpj} · {(v.ramos ?? []).join(', ')}</p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className="font-mono text-[11px] text-textMuted">{v.processos_em_comum} em comum</span>
                        <RelationBadge relacao={v.relacao} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card padding="md">
              <SectionLabel className="mb-3">Processos ligados</SectionLabel>
              {processos.length === 0 ? (
                <p className="text-[13px] text-textFaint text-center py-8">Nenhum processo encontrado.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {processos.map((p, i) => (
                    <a
                      key={i}
                      href={`https://www.cnj.jus.br/datajud/${p.id_cnj}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex flex-col gap-0.5 p-2.5 rounded-[6px] hover:bg-surfaceMuted transition-colors"
                    >
                      <span className="font-mono text-[12px] text-accent">{p.id_cnj}</span>
                      <span className="text-[11px] text-textMuted">{p.tribunal} · {p.classe} · {p.assunto}</span>
                    </a>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

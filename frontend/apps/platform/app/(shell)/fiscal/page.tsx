'use client'
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Card, SectionLabel, Badge, Input, Button, RbacGate, EmptyState, Skeleton, Dropzone,
  JobProgress, Table, Thead, Tbody, Tr, Th, Td, SourceChip,
} from '@juridico/ui'
import { useShell } from '@/app/context/shell'
import { fiscalApi, type NcmTriageResult, type UF } from '@/lib/api/fiscal'
import { ApiErrorBanner } from '@/components/ApiErrorBanner'

const UFS: UF[] = ['SP', 'RJ', 'MG', 'PR', 'SC', 'RS', 'ES', 'GO', 'MT', 'MS', 'BA', 'PE', 'CE', 'DF']

const MOCK_TRIAGE: NcmTriageResult = {
  sku_descricao: 'Notebook 14" 16GB RAM 512GB SSD',
  suggested_ncm: { ncm_codigo: '84713012', descricao: 'Máquinas automáticas de processamento de dados, portáteis', confidence: 0.91, fonte_regra: 'TIPI' },
  icms: { interna_pct: 18, fcp_pct: 2, interna_efetiva_pct: 20, interestadual_pct: 12, difal_pct: 8, fundamento_legal: 'Resolução SF 22/1989 (art. 1º)' },
  categoria: 'Informática',
  conflito_detectado: false,
  observacoes: [],
  decision_proof: 'fiscal_demo_0001',
  contract_version: 'fiscal/v1',
}

export default function FiscalPage() {
  const { role, demoMode } = useShell()
  const [descricao, setDescricao] = useState('')
  const [ufOrigem, setUfOrigem] = useState<UF>('SP')
  const [ufDestino, setUfDestino] = useState<UF>('RJ')

  const triageMutation = useMutation({
    mutationFn: () => fiscalApi.triage({ descricao, uf_origem: ufOrigem, uf_destino: ufDestino }),
  })

  const [jobId, setJobId] = useState<string | null>(null)
  const enrichMutation = useMutation({
    mutationFn: (file: File) => fiscalApi.enrichSpreadsheet(file, ufOrigem),
    onSuccess: (res) => setJobId(res.job_id),
  })
  const jobQuery = useQuery({
    queryKey: ['fiscal', 'job', jobId],
    queryFn: () => fiscalApi.jobStatus(jobId as string),
    enabled: !demoMode && !!jobId,
    refetchInterval: (q) => (q.state.data?.status === 'running' || q.state.data?.status === 'queued' ? 1500 : false),
  })

  const hasResult = demoMode || triageMutation.isSuccess
  const result = demoMode ? MOCK_TRIAGE : triageMutation.data

  const MOCK_JOB = {
    status: 'done' as const, progress: 100, total: 340,
    rows: [
      { item: 'Notebook 14"', ncm: '84713012', confianca: 0.91, status: 'ok' as const },
      { item: 'Mouse óptico USB', ncm: '84716053', confianca: 0.62, status: 'rever' as const },
    ],
    download_url: '#',
  }
  const job = demoMode ? MOCK_JOB : jobQuery.data

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[11px] font-bold px-2 py-1 rounded-[5px] bg-surfaceMuted text-textSecondary">FI</span>
        <h1 className="text-[20px] font-bold text-textPrimary">Fiscal</h1>
        <Badge variant="accent">NCM · ICMS</Badge>
      </div>
      <p className="text-[13px] text-textMuted -mt-3">Triagem NCM/ICMS de um item, com fundamento legal e proveniência TIPI.</p>

      <div className="grid grid-cols-3 gap-4 items-start">
        <Card padding="md" className="flex flex-col gap-4">
          <SectionLabel>Triagem</SectionLabel>
          <Input label="Descrição do item" value={descricao} onChange={(e) => setDescricao(e.target.value)} placeholder="Notebook 14 polegadas 16GB RAM" />
          <div className="grid grid-cols-2 gap-3">
            <SelectUf label="UF origem" value={ufOrigem} onChange={setUfOrigem} />
            <SelectUf label="UF destino" value={ufDestino} onChange={setUfDestino} />
          </div>
          <RbacGate role={role} requires="analyst">
            <Button onClick={() => triageMutation.mutate()} loading={triageMutation.isPending}>Triar item</Button>
          </RbacGate>
        </Card>

        <div className="col-span-2 flex flex-col gap-4">
          <ApiErrorBanner error={triageMutation.error} demoMode={demoMode} />

          {!hasResult && !triageMutation.isPending && (
            <EmptyState icon="🧾" title="Descreva um item e clique em Triar item" demoMode={demoMode} />
          )}

          {triageMutation.isPending && <Skeleton height={200} className="rounded-card" />}

          {result && (
            <Card padding="lg">
              {result.conflito_detectado && <Badge variant="MODERADO" className="mb-3">⚠ conflito de alíquota — rever</Badge>}
              <div className="flex items-start justify-between gap-4 mb-4">
                <div>
                  <SectionLabel>NCM sugerido</SectionLabel>
                  <p className="font-mono text-[22px] font-bold text-textPrimary mt-1">{result.suggested_ncm?.ncm_codigo ?? '—'}</p>
                  <p className="text-[12px] text-textMuted mt-0.5">{result.suggested_ncm?.descricao}</p>
                </div>
                <div className="flex flex-col items-end gap-1.5">
                  <SourceChip fonte={result.suggested_ncm?.fonte_regra ?? 'TIPI'} />
                  <Badge variant={((result.suggested_ncm?.confidence ?? 0) < 0.7) ? 'MODERADO' : 'BAIXO'}>
                    {Math.round((result.suggested_ncm?.confidence ?? 0) * 100)}% confiança
                  </Badge>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 bg-surfaceMuted rounded-[8px] p-4">
                <IcmsCell label="Interna" value={result.icms.interna_pct} />
                <IcmsCell label="FCP" value={result.icms.fcp_pct} />
                <IcmsCell label="Efetiva" value={result.icms.interna_efetiva_pct} />
                <IcmsCell label="Interestadual" value={result.icms.interestadual_pct} />
                <IcmsCell label="DIFAL" value={result.icms.difal_pct} />
              </div>

              <p className="text-[12px] text-textMuted mt-3">{result.icms.fundamento_legal}</p>
              {result.decision_proof && (
                <p className="font-mono text-[11px] text-textFaint mt-2">🔒 {result.decision_proof}</p>
              )}
            </Card>
          )}
        </div>
      </div>

      <Card padding="md" className="flex flex-col gap-4">
        <SectionLabel>Enriquecimento em lote (.xlsx)</SectionLabel>
        <RbacGate role={role} requires="analyst">
          <Dropzone
            accept=".xlsx"
            hint="Planilha com colunas Descrição/NCM/UF"
            onFiles={(files) => { if (files[0]) enrichMutation.mutate(files[0]) }}
          />
        </RbacGate>
        <ApiErrorBanner error={enrichMutation.error} demoMode={demoMode} />

        {job && (
          <>
            <JobProgress
              status={job.status === 'queued' ? 'queued' : job.status}
              progress={job.progress}
              steps={[
                { id: 'upload', label: 'Upload recebido', status: 'done' },
                { id: 'enrich', label: 'Enriquecendo itens', status: job.status === 'running' ? 'active' : job.status === 'done' ? 'done' : 'pending' },
                { id: 'xlsx', label: 'Planilha gerada', status: job.status === 'done' ? 'done' : 'pending' },
              ]}
              onDownload={job.download_url ? () => window.open(job.download_url, '_blank') : undefined}
            />
            {job.rows && job.rows.length > 0 && (
              <Table>
                <Thead>
                  <Tr><Th>Item</Th><Th mono>NCM</Th><Th mono>Confiança</Th><Th>Status</Th></Tr>
                </Thead>
                <Tbody>
                  {job.rows.map((r, i) => (
                    <Tr key={i}>
                      <Td>{r.item}</Td>
                      <Td mono>{r.ncm ?? '—'}</Td>
                      <Td mono>{r.confianca !== undefined ? `${Math.round(r.confianca * 100)}%` : '—'}</Td>
                      <Td><Badge variant={r.status === 'ok' ? 'BAIXO' : 'MODERADO'}>{r.status === 'ok' ? 'ok' : 'rever'}</Badge></Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            )}
          </>
        )}
      </Card>
    </div>
  )
}

function IcmsCell({ label, value }: { label: string; value: number | null }) {
  return (
    <div>
      <p className="text-[10px] text-textMuted">{label}</p>
      <p className="font-mono text-[15px] font-semibold text-textPrimary">{value !== null ? `${value}%` : '—'}</p>
    </div>
  )
}

function SelectUf({ label, value, onChange }: { label: string; value: UF; onChange: (v: UF) => void }) {
  return (
    <label className="flex flex-col gap-1.5 text-[12px] font-medium text-textSecondary">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as UF)}
        className="h-10 rounded-[8px] border border-borderStrong bg-surface px-3 text-[13px] text-textPrimary focus:outline-none focus:shadow-focusRing focus:border-accent"
      >
        {UFS.map((uf) => <option key={uf} value={uf}>{uf}</option>)}
      </select>
    </label>
  )
}

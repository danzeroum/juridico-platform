import { api } from './client'

// Espelha services/gateway/routers/knowledge_graph.py (prefix /api/v1/knowledge-graph).
export interface GraphStats {
  empresas: number
  processos: number
  arestas: number
}

export interface ProcessoRow {
  id_cnj?: string
  tribunal?: string
  classe?: string
  assunto?: string
  ramo?: string
  data?: string
  [key: string]: unknown
}

export type Relacao = 'ISOLADO' | 'OCASIONAL' | 'RECORRENTE' | 'PREDATORIO'

export interface VizinhoRow {
  cnpj: string
  nome?: string
  ramos?: string[]
  processos_em_comum: number
  relacao: Relacao
  [key: string]: unknown
}

export interface NetworkSummary {
  cnpj: string
  n_vizinhos: number
  distribuicao: Record<Relacao, number>
  tem_litigancia_predatoria: boolean
  vizinhos: VizinhoRow[]
}

export const knowledgeGraphApi = {
  stats: () => api.get<GraphStats>('/api/v1/knowledge-graph/stats'),

  companyProcesses: (cnpj: string, limit = 100) =>
    api.get<{ cnpj: string; count: number; results: ProcessoRow[] }>(
      `/api/v1/knowledge-graph/company/${cnpj}/processes?limit=${limit}`,
    ),

  companyNetwork: (cnpj: string, limit = 50) =>
    api.get<NetworkSummary>(`/api/v1/knowledge-graph/company/${cnpj}/network?limit=${limit}`),
}

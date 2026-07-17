import { api } from './client'

// Espelha services/gateway/routers/chamber_profiler.py (prefix /api/v1/chamber-profiler).
// Grão mínimo tribunal+classe — NUNCA aceita identificador de magistrado (LGPD).
export interface FaixaMetrica {
  valor: number | null
  faixa: string
}

export interface ChamberProfile {
  tribunal: string
  grao: string
  n_processos: number
  n_segmentos: number
  perfil: {
    provimento: FaixaMetrica
    congestionamento: FaixaMetrica
    duracao_mediana_dias: { valor: number | null; faixa: string }
  }
  disclaimer: string
}

export const chamberProfilerApi = {
  profile: (tribunal: string, classe?: string) => {
    const q = classe ? `?classe=${encodeURIComponent(classe)}` : ''
    return api.get<ChamberProfile>(`/api/v1/chamber-profiler/tribunal/${encodeURIComponent(tribunal)}${q}`)
  },
}

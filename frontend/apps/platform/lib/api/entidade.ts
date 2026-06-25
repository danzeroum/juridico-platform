import { api } from './client'

export interface CnpjCadastro {
  razao_social?: string
  situacao_cadastral?: string
  data_situacao_cadastral?: string | null
  porte?: string | null
  natureza_juridica?: string | null
  capital_social?: number | null
  data_abertura?: string | null
  municipio?: string | null
  uf?: string | null
  cnae_fiscal?: string | null
  cnae_descricao?: string | null
}

export interface EntidadeResponse {
  cnpj: string
  encontrado: boolean
  cadastro: CnpjCadastro
  source: string
  contract_version: string
}

export const entidadeApi = {
  get: (cnpj: string) =>
    api.get<EntidadeResponse>(`/api/v1/entidade/${cnpj.replace(/\D/g, '')}`),
}

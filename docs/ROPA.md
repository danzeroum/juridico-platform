# ROPA — Registro de Operações de Tratamento de Dados Pessoais

> **Registro de Atividades de Processamento (LGPD art. 37).**
> Atualizado em: 2026-06-16
>
> **Status de validação:** Rascunho — pendente de revisão por DPO/advogado antes do go-live.
> Ver Pendencia.md PD-06.

---

## 1. Identificação do Controlador

| Campo | Valor |
|---|---|
| Razão social | [RAZÃO SOCIAL DO CLIENTE — preencher] |
| CNPJ | [CNPJ — preencher] |
| DPO | [NOME E E-MAIL DO DPO — preencher] |
| Plataforma | juridico-platform |
| Versão deste documento | 1.0 |

---

## 2. Classificação das 14 Fontes de Dados

### Legenda de classificação

| Símbolo | Significado |
|---|---|
| 🟢 Público | Dado tornado público pelo titular ou por lei; não é dado pessoal nos termos da LGPD |
| 🟡 Pessoal | Dado pessoal identificável (CPF, nome, e-mail) — LGPD art. 5º, I |
| 🔴 Sensível | Dado pessoal sensível (saúde, biometria, etc.) — LGPD art. 5º, II e art. 11 |

### Tabela de fontes

| # | Fonte | Tipo de Dado | Classificação | Base Legal | Finalidade | Produtos |
|---|---|---|---|---|---|---|
| 1 | **Receita Federal (CNPJ)** | Cadastro PJ, sócios PF (nome, CPF), capital, CNAE | 🟡 Pessoal (sócios) | Art. 7º, §3º — dado tornado público pelo titular ao registrar PJ | Enriquecimento cadastral, identificação de sócios, score | LegalScore, ContabilIA |
| 2 | **DATAJUD (CNJ)** | Processos judiciais: partes (PF/PJ), advogados, valores | 🟡 Pessoal (partes PF) | Art. 7º, §3º — processos são públicos; **validar com DPO se sustenta para profiling** | Score jurídico, previsão de desfecho | LegalScore, TaxPredict, PetiBot |
| 3 | **PGFN** | Dívida ativa, inscrições de PJ e PF | 🟢 Público (PJ) / 🟡 Pessoal (PF devedora) | Art. 7º, §3º para PJ; para PF verificar base legal | Risco financeiro, score | LegalScore, ComplianceRadar |
| 4 | **CAGED (MTE)** | Emprego/desemprego por município, CNAE, faixa salarial (agregado) | 🟢 Público (agregado) | Art. 7º, VI — interesse legítimo; dado agregado, sem identificação individual | Indicadores de emprego regional | LegalScore, ComplianceRadar |
| 5 | **SICONFI (STN)** | Execução orçamentária municipal/estadual (agregado) | 🟢 Público | Obrigação legal (LRF) — dado obrigatoriamente público | Saúde fiscal municipal | ComplianceRadar, ContabilIA |
| 6 | **PNCP** | Licitações públicas: editais, vencedores, valores (PJ e PF) | 🟢 Público (PJ) / 🟡 Pessoal (PF licitante) | Art. 7º, §3º — dado tornado público no ato licitatório | Monitoramento de contratos públicos | LicitaWatch, ComplianceRadar |
| 7 | **DATASUS/SIH** | Internações hospitalares, procedimentos, CID (dado de saúde) | **🔴 SENSÍVEL** | **⚠️ BLOQUEIO:** art. 11 — lista fechada sem "interesse legítimo". Base defensável: art. 12 (dado anonimizado/agregado) + DPO opinion antes da Fase 3. Ver Pendencia.md PD-06 | Indicadores de saúde municipal (agregado, k-anonymity ≥ 5) | ComplianceRadar, DanoBot |
| 8 | **SNIS (MDR)** | Indicadores de saneamento por município (agregado) | 🟢 Público | Obrigação de transparência pública | Qualidade de vida municipal | ComplianceRadar |
| 9 | **INEP** | Indicadores de educação por escola/município (IDEB, matrículas) | 🟢 Público | Obrigação legal — INEP publica oficialmente | Qualidade de educação municipal | ComplianceRadar |
| 10 | **ComexStat** | Exportações/importações por empresa (CNPJ), NCM, valor | 🟢 Público (PJ) | Art. 7º, §3º — dado de comércio exterior é público (Siscomex) | Análise de setor externo | ContabilIA |
| 11 | **Portal Transparência Federal** | Contratos, convênios, pagamentos a PF/PJ | 🟡 Pessoal (PF beneficiária) | Art. 7º, §3º — dado tornado público por obrigação legal (LAI) | Conformidade, detecção de irregularidades | ComplianceRadar, LicitaWatch |
| 12 | **Câmara dos Deputados (Legisweb)** | Legislação, normas, ementas (sem dado pessoal) | 🟢 Público | Dado de domínio público | Base normativa para RAG (TaxPredict, PetiBot) | TaxPredict, PetiBot |
| 13 | **BCB/ESTBAN** | Indicadores bancários por município (agregado) | 🟢 Público | BCB publica por obrigação regulatória | Saúde financeira regional | ContabilIA, ComplianceRadar |
| 14 | **IBGE** | Dados demográficos e econômicos municipais (agregado) | 🟢 Público | Produção estatística pública (Lei 5.534/68) | Contexto econômico-demográfico | Todos os produtos |

---

## 3. Medidas Técnicas por Tipo de Dado

### 3.1 Dado pessoal (🟡)

| Medida | Implementação |
|---|---|
| Pseudonimização | HMAC-SHA256 com chave em KMS/Docker Secret antes de qualquer persistência |
| Minimização | Somente campos necessários para a finalidade declarada |
| Retenção | Conforme prazo legal aplicável; ledger: 7 anos (art. 16) |
| Right-to-erasure | Crypto-shredding: chave AES-256-GCM por titular no KMS; destruir chave = dado irrelegível |
| k-anonymity | k ≥ 5 em qualquer agregação que combine quasi-identificadores |

### 3.2 Dado sensível — saúde (🔴 DATASUS)

| Medida | Status |
|---|---|
| DPO opinion (obrigatória) | **PENDENTE** — ver Pendencia.md PD-06 |
| Base legal (art. 11) | **PENDENTE** — uso somente de dado agregado/anonimizado (art. 12) |
| k-anonymity reforçada | k ≥ 5 com supressão de células < 5 (implementado em `k_anonymize()`) |
| RIPD | **PENDENTE** — Relatório de Impacto à Proteção de Dados |
| Armazenamento | Bronze privado; sem acesso anônimo; sem dado de saúde identificável |

---

## 4. Direitos dos Titulares (LGPD arts. 17–22)

| Direito | Como é atendido |
|---|---|
| Acesso (art. 18, I) | API `/api/v1/legalscore/audit/{request_id}` expõe entradas do Ledger |
| Correção (art. 18, III) | Dado público de fontes externas — orientar o titular a corrigir na fonte |
| Eliminação (art. 18, IV) | Crypto-shredding (destruição da chave AES por titular no KMS) |
| Portabilidade (art. 18, V) | Export JSON de dados do titular via endpoint autenticado |
| Revogação de consentimento (art. 18, IX) | Remoção do cadastro; crypto-shredding das entradas do Ledger |

---

## 5. Tensão Right-to-Erasure × Decision Ledger (Solucionada)

O ledger é append-only (7 anos de retenção) e usa Merkle tree. Apagar entradas
quebraria a prova de integridade. Solução: **crypto-shredding**.

- `subject_token` no Ledger = pseudônimo cifrado com AES-256-GCM por titular.
- Chave armazenada no KMS por `titular_id`.
- Solicitação de erasure → destruição da chave no KMS.
- Resultado: `subject_token` torna-se criptograficamente irrelegível.
- Merkle root e hashes de inputs/outputs permanecem intactos → integridade preservada.
- A retenção de 7 anos aplica-se à estrutura do ledger; o vínculo com o titular
  torna-se irreversivelmente rompido.

---

## 6. Resposta a Incidentes (LGPD art. 48)

| Cenário | Ação imediata | Notificação ANPD/Titulares |
|---|---|---|
| Vazamento de bucket MinIO | Revogar credenciais MinIO, auditar logs de acesso, identificar registros expostos | Dentro de 72h se dado pessoal exposto |
| Acesso indevido ao banco (Postgres/Neo4j) | Revogar token/senha, audit log completo | Dentro de 72h se dado pessoal exposto |
| Comprometimento da chave HMAC | Rotação imediata da chave; re-pseudonimização de todos os registros via `rotate_key_reprocess()` | Avaliar se dado era acessível |
| Comprometimento da chave AES/KMS | Destruir chave comprometida; emitir nova chave; re-cifrar `subject_token` | Dentro de 72h |
| Comprometimento da chave JWT privada | Invalidar todos os tokens; gerar novo par RSA; republicar JWKS | Comunicar usuários |

**Cadeia de evidências:** Decision Ledger + logs imutáveis (Loki) para auditoria.
Audit trail exportável em formato PDF para notificação à ANPD.

---

## 7. Transferências Internacionais

Por padrão, nenhum dado pessoal é transferido internacionalmente. Serviços de nuvem
(se utilizados) devem ser em regiões brasileiras ou com cláusulas contratuais padrão.

---

## 8. Histórico de Revisões

| Data | Versão | Alteração |
|---|---|---|
| 2026-06-16 | 1.0 | Criação do documento — rascunho inicial |

---

*Pendente de validação por DPO/advogado antes do go-live de qualquer produto.*

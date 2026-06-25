# Allowlist de rede — fontes de dados externas

Este documento lista os **hosts de saída (egress)** que precisam ser liberados na
política de rede do ambiente para que cada módulo colete **dados reais** das fontes
públicas. Para cada host: o que destrava, o estado do coletor no repositório, o tipo
de autenticação e a cadência.

> **Contexto.** O ambiente aplica uma política de egress com allowlist. Hoje apenas
> `servicodados.ibge.gov.br` (IBGE) responde — todas as integrações com dados reais
> entregues até aqui (perfil socioeconômico do município no ComplianceRadar e o IPCA
> do TaxPredict) usam essa fonte. As demais fontes estão **bloqueadas** (403 no CONNECT
> do proxy, ou timeout). Liberar os hosts abaixo destrava os módulos correspondentes
> sem mudança de código — os coletores já existem (salvo onde indicado).

## Como liberar e verificar

1. Adicionar o host à allowlist de egress do ambiente (porta 443/TCP, HTTPS).
2. Confirmar a liberação a partir do container:
   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" --max-time 10 "https://<host>/..."
   # 200/302 = liberado · 403 (CONNECT) = ainda bloqueado pela política
   curl -sS "$HTTPS_PROXY/__agentproxy/status"   # registra a razão de bloqueios recentes
   ```
3. Rodar o ingest do módulo (ex.: `make ingest-ibge UF=AM`) e validar o endpoint.

## Hosts a liberar (prioridade)

| # | Host | Porta | Módulo destravado | Coletor | Auth | Cadência | Status atual |
|---|------|-------|-------------------|---------|------|----------|--------------|
| 1 | `pncp.gov.br` | 443 | **LicitaWatch** (contratos públicos PNCP) | `services/ingest/tasks/pncp.py` ✅ pronto | nenhuma | diária | ⛔ timeout |
| 2 | `api-publica.datajud.cnj.jus.br` | 443 | **PetiBot / TaxPredict** (jurisprudência → RAG), **LegalScore** (processos) | `services/ingest/tasks/datajud.py` ✅ pronto | API key pública (`DATAJUD_TOKEN`) | diária | ⛔ 403 |
| 3 | `apidatalake.tesouro.gov.br` | 443 | **ContabilIA / ComplianceRadar** (SICONFI — contas públicas) | `services/ingest/tasks/siconfi.py` ✅ pronto | nenhuma | mensal | ⛔ não testado |
| 4 | `api.dados.gov.br` | 443 | **ContabilIA / ComplianceRadar** (CAGED — emprego) | `services/ingest/tasks/caged.py` ✅ pronto | chave dados.gov | mensal | ⛔ 403 |
| 5 | `minhareceita.org` *(ou `brasilapi.com.br`)* | 443 | **LegalScore / Entidade** (cadastro CNPJ) | `services/ingest/tasks/receita.py` ⚠️ ajustar host | nenhuma | semanal | ⛔ 403 (brasilapi) |
| 6 | `consumidor.gov.br` | 443 | **Defensor** (dados abertos de reclamações; referência) | ❌ a criar | nenhuma (CSV bulk) | semanal | ⛔ 403 |
| 7 | `api.bcb.gov.br` | 443 | **TaxPredict** (SELIC/câmbio — macro além do IPCA) | ❌ a criar (`fetch_*` no padrão IBGE) | nenhuma | diária | ⛔ 403 |
| — | `servicodados.ibge.gov.br` | 443 | **ComplianceRadar / TaxPredict** (já em uso) | `services/ingest/tasks/ibge.py` ✅ | nenhuma | anual | ✅ liberado |
| — | `hooks.slack.com` *(opcional)* | 443 | Entrega de alertas (outbox → Slack) | `compliance/licitawatch` | webhook URL | evento | ⛔ não testado |

✅ pronto = coletor existe e só depende da liberação · ⚠️ = pequeno ajuste · ❌ = coletor a criar.

## O que cada liberação entrega (de ponta a ponta)

- **PNCP** → `GET /api/v1/licitawatch/orgao/{cnpj}/evaluate` passa a calcular os indicadores
  LL01–LL04 sobre contratos reais; a aba de Contratos sai do modo demo.
- **DataJud** → popula as coleções ChromaDB (`*_jurisprudencia`); PetiBot e TaxPredict passam a
  retornar precedentes reais (`precedentes_encontrados` > 0) em vez de degradação graciosa.
- **SICONFI + CAGED** → habilitam os cross-checks CC01/CC02 do ContabilIA (hoje marcados como
  "dados públicos não consultados") e as regras de alerta do ComplianceRadar (queda de
  arrecadação/emprego).
- **Receita/CNPJ** → enriquece LegalScore e a página Entidade com razão social, CNAE, porte e
  situação cadastral reais.
- **Consumidor.gov** → base de referência para classificação de casos no Defensor.
- **BCB** → complementa o contexto macro do TaxPredict (SELIC, câmbio) — o IPCA já vem do IBGE.

## Base legal (LGPD)

Todas as fontes acima são **dados públicos** (LGPD art. 7º, IV / obrigação legal) — ver
`docs/ROPA.md` para a classificação por fonte. **Exceção bloqueada por decisão:** DATASUS
(dados de saúde, art. 11) permanece fora até parecer do DPO (PD-06 em `Pendencia.md`); por isso
o DanoBot segue retornando 501 e **não** está nesta lista.

## Observação

Liberar 1–4 já destrava os módulos de maior valor (LicitaWatch, PetiBot/TaxPredict jurisprudência,
ContabilIA, ComplianceRadar de alertas) reutilizando coletores que já existem e já têm testes.
Nenhuma dessas integrações exige credenciais privadas — apenas a chave **pública** do DataJud.

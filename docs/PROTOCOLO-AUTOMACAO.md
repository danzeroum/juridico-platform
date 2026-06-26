# Automação de protocolo (Defensor → Procon / Consumidor.gov)

Camada que protocola a defesa montada pelo Defensor nos órgãos de defesa do
consumidor. Projetada com **simulação como padrão** e submissão real **opt-in,
gated por credenciais e rede**.

## Por que simulação por padrão

Protocolar em nome do consumidor é uma **ação externa com efeito legal**. Errar
(caso errado, dados errados, duplicidade) tem consequências reais. Além disso, os
portais reais exigem **login gov.br** e normalmente **CAPTCHA**, e estão hoje
**bloqueados pela política de rede** deste ambiente (ver `NETWORK-ALLOWLIST.md`).
Por isso, nada é submetido de verdade sem ação explícita.

## Arquitetura

```
POST /api/v1/defensor/protocolar
        │
        ▼
services/defensor/protocolar.py  → escolhe o driver por (PROTOCOLO_MODO, canal)
        │
        ├─ SimulacaoDriver            (padrão) → status SIMULADO, número estável, 0 rede
        └─ _PlaywrightPortalDriver    (modo real)
             ├─ ConsumidorGovDriver
             └─ ProconSPDriver
```

- **`ProtocoloDriver`** (`protocolo/base.py`): interface; `submit()` nunca levanta —
  sempre devolve um `ProtocoloResultado`.
- **`SimulacaoDriver`** (`protocolo/simulacao.py`): gera um número determinístico
  (`SIM-<CANAL>-<hash>`), sem qualquer chamada externa.
- **Drivers reais** (`protocolo/real.py`): Playwright (Chromium já vem no ambiente),
  importado de forma tardia. `submit()`:
  1. sem credenciais → `AGUARDA_CREDENCIAIS` (não toca a rede);
  2. com credenciais → tenta o fluxo real; qualquer falha vira `FALHA` controlada.
- **`factory.get_driver(canal, modo)`**: `modo != "real"` → simulação; `modo == "real"`
  → driver do canal, ou simulação se o canal não tiver automação (OUVIDORIA, CONTENCIOSO).

### Estados (`ProtocoloStatus`)

| Status | Quando |
|---|---|
| `SIMULADO` | modo simulação (padrão) — nada submetido |
| `AGUARDA_CREDENCIAIS` | modo real, sem credenciais do portal |
| `ENVIADO` | submissão real concluída (número do portal) |
| `FALHA` | tentativa real falhou (rede/seletor/captcha) |
| `CANAL_NAO_SUPORTADO` | sem driver real para o canal |

## Habilitar submissão real (produção)

1. Liberar o host na allowlist de rede (`consumidor.gov.br` / `procon.sp.gov.br`).
2. Configurar credenciais (Docker Secrets ou env):
   - `CONSUMIDOR_GOV_USER` / `CONSUMIDOR_GOV_PASSWORD`
   - `PROCON_SP_USER` / `PROCON_SP_PASSWORD`
3. `PROTOCOLO_MODO=real`.
4. Completar o fluxo Playwright em `protocolo/real.py::_submit_real`: mapear os
   seletores do portal, o **login gov.br** e o **tratamento de CAPTCHA** (exige
   serviço externo ou intervenção humana). Hoje esse método é um scaffold que
   sinaliza `FALHA` controlada em vez de submeter algo incorreto.

## O que ainda falta para submissão real de fato

- Mapeamento de seletores/etapas contra o portal real (inacessível aqui).
- Estratégia de **CAPTCHA** (humano-no-loop ou serviço de resolução).
- Persistência do protocolo no **decision ledger** (auditoria/idempotência) para
  evitar duplicidade de submissão.
- Autorização explícita do titular para protocolar em seu nome.

## Conformidade

A submissão age em nome do consumidor: requer base legal/consentimento e trilha
de auditoria. Mantenha `PROTOCOLO_MODO=simulacao` até que login, captcha,
idempotência e autorização estejam resolvidos.

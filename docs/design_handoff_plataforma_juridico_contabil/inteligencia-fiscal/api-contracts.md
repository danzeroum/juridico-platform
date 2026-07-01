# Contratos de API — Inteligência + Fiscal + Ingestão

> Assinaturas request/response por tela. Convenções da plataforma: respostas de lista
> trazem `{ items, count, limit, offset }`; erros seguem **problem+json**
> (`{ type, title, status, detail, instance, contract_version }`); toda saída registrável
> traz `decision_proof` (Ledger). Enum de fonte: `DATAJUD | ABJ | BLEND | TIPI | CONFAZ | PNCP | SICONFI | RECEITA | PGFN`.
> Base: `/api/v1`. Cada rota respeita RBAC e rate-limit do tenant.

---

## JM · Jurimetria
```
GET /jurimetria/indicadores?tribunal&classe&assunto&fonte&limit&offset
→ 200 {
  items: [{
    tribunal, classe, assunto, fonte: Fonte,
    n_processos: int, duracao_mediana_dias: int,
    congestionamento: float(0..1), pct_provimento: float(0..1),
    duracao_iqr: { p25:int, p75:int }
  }],
  count, limit, offset,
  decision_proof: { req_id, ledger_hash }
}

GET /jurimetria/market-intelligence?segmento
→ 200 { segmentos: [{ seg, n_processos, ticket_medio, soma }], decision_proof }
```
Estados: `fonte` defasada → item mantém `fonte` mas front pinta chip em âmbar; lista vazia → `items: []`.

## KG · Knowledge Graph
```
GET /knowledge-graph/rede?cnpj
→ 200 {
  entidade: { cnpj, nome },
  stats: { empresas:int, processos:int, arestas:int },
  vizinhos: [{ cnpj, nome, ramos:[str], processos_comum:int,
               relacao: 'ISOLADO'|'OCASIONAL'|'RECORRENTE'|'PREDATORIO' }],
  processos: [{ id_cnj, tribunal, classe, assunto, ramo, data }],
  predatorio_detectado: bool
}
```
Estado vazio: `vizinhos: []`, `predatorio_detectado:false`.

## FC · Forecasting
```
GET /forecasting?tribunal&classe&assunto&horizonte
→ 200 {
  historico: [{ periodo, valor:int }],           // ≥3 exigidos
  projecao:  [{ passo:int, valor:int, lo:int, hi:int }],
  tendencia: 'CRESCENTE'|'ESTAVEL'|'DECRESCENTE', inclinacao: float,
  heuristico: true
}
→ 422 problem+json quando historico < 3 períodos (title: "dados insuficientes")
```

## CP · Chamber Profiler
```
GET /chamber-profiler?tribunal&classe          // NÃO aceita juiz/magistrado
→ 200 {
  grao: { tribunal, classe, n_processos, segmentos:int },
  metricas: {
    provimento:        { valor:float, faixa },   // PROVIMENTO_BAIXO|MODERADO|ALTO
    congestionamento:  { valor:float, faixa },   // POUCO|CONGESTIONADO|MUITO_CONGESTIONADO
    duracao_mediana:   { dias:int,   faixa }     // RAPIDO|MODERADO|LENTO
  },
  heuristico: true
}
→ 400 se o request contiver identificador de magistrado (vedado por LGPD)
```

## SO · Second Opinion
```
POST /second-opinion { legalscore:int(0..1000), taxpredict:float(0..1), jurimetria_provimento:float(0..1) }
→ 200 {
  favorabilidade: float(0..1),
  veredito: 'FAVORAVEL'|'INCERTO'|'DESFAVORAVEL',
  concordancia: float(0..1), nivel_concordancia: 'BAIXA'|'MEDIA'|'ALTA',
  sinais: [{ label, raw, normalizado:float }],
  decision_proof: { req_id, ledger_hash, pii:false }
}
```

## ST · Settlement Optimizer
```
POST /settlement { valor_causa:num, prob_favoravel:float, pct_provimento:float, custo_autor:num, custo_reu:num }
→ 200 {
  tem_zopa: bool,
  faixa: { lo:num, hi:num }, sugerido:num,
  valor_esperado_autor:num, valor_esperado_reu:num,
  recomendacao: 'ACORDAR'|'LITIGAR',
  decision_proof
}
```
Sem ZOPA: `tem_zopa:false`, `faixa:null`, `recomendacao:'LITIGAR'`.

## EW · Early Warning
```
GET /early-warning?tribunal&classe&assunto
→ 200 {
  gatilhos: [{
    tipo: 'SURTO_VOLUME'|'PICO_CONGESTIONAMENTO',
    severidade: 'CRITICAL'|'HIGH'|'MEDIUM'|'LOW',
    descricao, metrica: { nome, valor, media?, z?:float }
  }]
}
```
Vazio: `gatilhos: []` → estado verde "nenhum gatilho ativo".

## FI · Fiscal
```
POST /fiscal/triagem { descricao, uf_origem, uf_destino }
→ 200 {
  ncm, confianca:float(0..1), fonte:'TIPI',
  icms: { interna:float, fcp:float, efetiva:float, interestadual:float, difal:float },
  fundamento, conflito: bool,
  decision_proof
}

POST /fiscal/lote  (multipart .xlsx)  → { job_id }
GET  /fiscal/lote/{job_id}
→ 200 {
  status: 'RUNNING'|'DONE'|'FAILED', total:int, done:int, failed:int,
  rows: [{ item, ncm, confianca:float, status:'ok'|'rever' }],
  download_url?, expires_at?      // .xlsx, expira em 24h
}
```

## IG · Ingestão & Saúde de Dados  (ADMIN)
```
GET /admin/ingestao/fontes
→ 200 { fontes: [{
    fonte: Fonte, lag_dias:int,
    circuit_breaker: 'CLOSED'|'HALF_OPEN'|'OPEN',
    records_in:int, records_out:int, perda_pct:float,
    ultimo_run_iso
  }] }

POST /admin/ingestao/fontes/{fonte}/run   → 202 { job_id }   // exige role=admin
```
Frescor (front): lag ≤2d `fresco` (verde) · ≤7d `recente` (âmbar) · >7d `defasado` (vermelho).
CB `OPEN` = fonte pausada após falhas consecutivas.

---

### Notas de implementação
- **RBAC:** IG e todas as mutations (`/run`, `/lote`) exigem `admin`/`analyst` conforme a lente;
  gate no front (`RbacGate`) **e** no gateway.
- **demoMode:** quando ligado, o front serve as fixtures do protótipo (mesmos números) sem tocar a rede.
- **problem+json:** 429 (rate limit), 501 (fonte não liberada), 503 (circuit breaker) →
  `ApiErrorBanner` acima do conteúdo.
- **Ledger:** `decision_proof.req_id` no formato `<PREFIXO>-AAAA-NNNN` (MI, SO, ST, FI…).

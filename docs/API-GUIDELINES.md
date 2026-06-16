# API Guidelines — Plataforma Jurídico-Contábil

> **Norma obrigatória.** Todo endpoint de todo produto deve satisfazer estas
> convenções antes de ir a produção. O CI verifica automaticamente os
> anti-patterns proibidos. Violação = PR bloqueado.

---

## 1. Versionamento

```
/api/v1/{produto}/{recurso}
```

| Exemplos corretos | Exemplos incorretos |
|---|---|
| `/api/v1/legalscore/score` | `/score/company` |
| `/api/v1/taxpredict/predict` | `/legalscore/v1/score` |
| `/api/v1/compliance/alerts` | `/api/legalscore/score` |

**Regra:** versão somente no prefixo da rota. Mudança incompatível cria `/api/v2/...`.
Mudança compatível (adicionar campo opcional, novo endpoint) mantém `v1`.

---

## 2. Métodos HTTP

| Operação | Método | Justificativa |
|---|---|---|
| Calcular score (gera entrada no Ledger) | `POST` | Cria estado (idempotente via `Idempotency-Key`) |
| Buscar perfil/perfil de empresa | `GET` | Leitura pura; cacheável |
| Atualizar configuração de alerta | `PATCH` | Atualização parcial |
| Cancelar assinatura | `DELETE` | Remoção de recurso |
| Batch submit | `POST` | Cria job assíncrono |

**Proibido:** usar `GET` para operações com efeitos colaterais; usar `POST` para
leitura pura quando os parâmetros cabem na URL.

---

## 3. Contrato de Erro (`application/problem+json` — RFC 9457)

**Todo erro** retorna `Content-Type: application/problem+json` com este schema:

```json
{
  "type": "https://juridico-platform/errors/400",
  "title": "Requisição inválida",
  "status": 400,
  "detail": "CNPJ deve ter 14 dígitos numéricos. Recebido: '1234'.",
  "instance": "/api/v1/legalscore/score",
  "contract_version": "1.0"
}
```

| Campo | Obrigatório | Descrição |
|---|---|---|
| `type` | ✅ | URI identificador do tipo de erro |
| `title` | ✅ | Título humano para o tipo (invariante) |
| `status` | ✅ | HTTP status code (número) |
| `detail` | ✅ | Descrição específica desta ocorrência |
| `instance` | ✅ | Path da request que gerou o erro |
| `contract_version` | ✅ | Versão do contrato de erro |

**Nunca retornar:** stack trace, mensagem de exceção Python cru, JSON sem o schema acima.

---

## 4. Paginação e Filtros (coleções)

Todo endpoint que retorna lista deve suportar:

```
GET /api/v1/legalscore/company/{cnpj}/processes?page=1&per_page=20&tipo=trabalhista
```

Resposta:
```json
{
  "items": [...],
  "total": 142,
  "page": 1,
  "per_page": 20,
  "pages": 8
}
```

**Proibido:** retornar lista sem paginação.

---

## 5. Idempotência (`Idempotency-Key`)

Endpoints que criam estado (`POST` score, `POST` alerta) devem suportar:

```http
POST /api/v1/legalscore/score
Idempotency-Key: meu-cliente-12345-tentativa-1
```

**Comportamento:**
- Primeira request com a chave: executa normalmente, armazena resultado (24h).
- Request repetida com a mesma chave (dentro de 24h): retorna o resultado da
  requisição original com HTTP 200 (segurança de retry em falhas de rede).
- Após 24h: nova execução (a chave expirou).
- **Não é cache de resultado:** o score muda quando os dados-fonte mudam. A
  idempotência serve exclusivamente para evitar duplo processamento em retentativas.

---

## 6. Rate Limiting

```
HTTP/1.1 429 Too Many Requests
Content-Type: application/problem+json
Retry-After: 60

{
  "type": "https://juridico-platform/errors/429",
  "title": "Rate limit excedido",
  "status": 429,
  "detail": "Máximo de 100 requisições por minuto por tenant.",
  "instance": "/api/v1/legalscore/score",
  "contract_version": "1.0"
}
```

- Limite padrão: **100 req/min por tenant** (configurável por plano).
- Contagem por `tenant_id` (claim JWT), não por IP.
- Header `Retry-After` obrigatório em 429.

---

## 7. OpenAPI 3.1 com Exemplos Reais

Todo endpoint deve ter:
- `summary`: ação em português, concisa.
- `description`: contexto de uso e limitações (heurística, SLA, etc.).
- `responses`: exemplo de resposta de sucesso **e** dos principais erros.
- `response_model` com Pydantic (FastAPI gera o schema automaticamente).

**Proibido:** endpoint sem documentação na OpenAPI; campo sem descrição.

---

## 8. Substantivos Autoexplicativos

| Correto | Incorreto |
|---|---|
| `/api/v1/legalscore/company/{cnpj}` | `/api/v1/getCompany` |
| `/api/v1/taxpredict/predict` | `/api/v1/doPredict` |
| `/api/v1/compliance/alerts` | `/api/v1/getAlerts` |

Recursos são **substantivos**. Ações são os **métodos HTTP**.

---

## 9. Observabilidade

Todo endpoint deve emitir:

1. **Log JSON estruturado** (via `logging` com `JsonFormatter`):
   - `request_id`, `tenant_id`, `method`, `path`, `status`, `duration_ms`
2. **OTel span** com atributos `tenant.id` e operação principal.
3. **Métricas Prometheus** via `prometheus-fastapi-instrumentator` (automático).

---

## 10. Anti-patterns Proibidos (gate no CI)

O CI verifica automaticamente a ausência destes anti-patterns:

| Anti-pattern | Verificação |
|---|---|
| SHA-256 truncado em `lgpd.py` | `grep hexdigest()\[` |
| Merkle tree com janela limitada | `grep entries\[-` |
| `--api.insecure=true` no Traefik | `grep api.insecure=true` |
| Portas de banco no host | Parse YAML do compose |
| Endpoint sem paginação em coleção | Review manual no PR |
| Erro sem `problem+json` | Review manual no PR |

---

## 11. Dados de Contexto no Payload

Todo payload de score deve incluir:
```json
{
  "source_date": "2026-06-15",
  "lag_days": 1
}
```

O consumidor deve saber **quando** os dados foram coletados, não apenas o resultado.
Fontes com lag > SLA declarado exigem o campo `data_freshness: "stale"`.

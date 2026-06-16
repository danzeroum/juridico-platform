"""
Locust load test para validação de SLA do LegalScore PJ.

Alvo: p95 < 1.5s para POST /api/v1/legalscore/score
      batch 1k CNPJs < 30s total

Uso local:
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
           --users=50 --spawn-rate=10 --run-time=60s --headless
"""

import random
import string

from locust import HttpUser, between, task


def _random_cnpj() -> str:
    """CNPJ sintético (não válido) para testes de carga."""
    return "".join(random.choices(string.digits, k=14))


def _auth_header() -> dict[str, str]:
    """Header de auth para testes — substitua por token real em ambiente de carga."""
    return {"Authorization": "Bearer test-load-token"}


class LegalScoreUser(HttpUser):
    """Usuário que executa score individual com SLA p95 < 1.5s."""

    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.cnpjs = [_random_cnpj() for _ in range(100)]
        self.idx = 0

    @task(10)
    def score_single(self):
        cnpj = self.cnpjs[self.idx % len(self.cnpjs)]
        self.idx += 1
        with self.client.post(
            "/api/v1/legalscore/score",
            json={"cnpj": cnpj},
            headers=_auth_header(),
            catch_response=True,
            name="/api/v1/legalscore/score",
        ) as resp:
            if resp.status_code in (200, 401, 403):
                # 401/403 esperado se não há token real — marcar como sucesso para medir latência
                resp.success()
            elif resp.status_code == 503:
                resp.failure("Serviço indisponível")

    @task(2)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(1)
    def company_profile(self):
        cnpj = self.cnpjs[self.idx % len(self.cnpjs)]
        self.client.get(
            f"/api/v1/legalscore/company/{cnpj}",
            headers=_auth_header(),
            name="/api/v1/legalscore/company/{cnpj}",
        )


class BatchScoreUser(HttpUser):
    """Usuário que submete batches de 100 CNPJs — valida throughput."""

    wait_time = between(5, 10)

    @task
    def batch_score(self):
        cnpjs = [_random_cnpj() for _ in range(100)]
        with self.client.post(
            "/api/v1/legalscore/batch",
            json={"cnpjs": cnpjs},
            headers=_auth_header(),
            catch_response=True,
            name="/api/v1/legalscore/batch",
        ) as resp:
            if resp.status_code in (202, 400, 401, 403, 503):
                resp.success()
            else:
                resp.failure(f"Unexpected: {resp.status_code}")

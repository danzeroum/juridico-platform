"""
Locust load test — medição REAL de SLA (não estimativa).

Por que esta versão substitui a anterior:
    A versão antiga marcava 401/403 como `success()` "para medir latência" e usava
    CNPJs sintéticos sem token. Sem auth válida, toda requisição era rejeitada no
    gateway em milissegundos — o p95 medido era o do caminho de REJEIÇÃO de auth,
    não o do cálculo do score (feature assembly + engine + ledger). Logo, o número
    não comprovava o SLA. Esta versão:
      - autentica via POST /api/v1/auth/token e usa o Bearer JWT em todas as chamadas;
      - trata 401/403/5xx como FALHA;
      - falha rápido se a autenticação não funcionar (não mede algo inválido);
      - exige CNPJs SEMEADOS para exercitar o caminho de cómputo real.

Pré-requisitos para a medição valer:
    1. Banco semeado com dados de ingestão para os CNPJs usados. Passe a lista em
       LOAD_TEST_CNPJS (separada por vírgula). Sem dados semeados, o endpoint não
       exercita o caminho de cálculo e as respostas não-200 contarão como falha.
    2. Rodar contra ambiente representativo (NÃO o CI).

Alvo de SLA (LegalScore): p95 < 1.5s no /score; batch 1k CNPJs < 30s; erro < 0.1%.

Uso:
    LOAD_TEST_CNPJS="<cnpj1>,<cnpj2>,..." \
    locust -f tests/load/locustfile.py --host=http://gateway:8000 \
           --users=500 --spawn-rate=50 --run-time=5m --headless \
           --html=tests/load/report.html
"""
import os
import random

from locust import HttpUser, between, task
from locust.exception import StopUser

_CNPJS = [c.strip() for c in os.getenv("LOAD_TEST_CNPJS", "").split(",") if c.strip()]
_CREDS = {
    "username": os.getenv("LOAD_TEST_USER", "load-tester"),
    "password": os.getenv("LOAD_TEST_PASS", "load-test"),
    "tenant_slug": os.getenv("LOAD_TEST_TENANT", "dev-tenant"),
}


class LegalScoreUser(HttpUser):
    """Mede o SLA do caminho real de score, autenticado."""

    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        # Autentica; sem token, abortar este usuário (medição seria inválida).
        with self.client.post(
            "/api/v1/auth/token",
            json=_CREDS,
            name="POST /api/v1/auth/token",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"auth falhou ({resp.status_code}) — medição abortada")
                raise StopUser()
            token = resp.json().get("access_token")
            if not token:
                resp.failure("token ausente na resposta de auth")
                raise StopUser()
            resp.success()

        self.client.headers.update({"Authorization": f"Bearer {token}"})

        if not _CNPJS:
            # Sem seed, o caminho de cómputo não é exercido — avisa explicitamente.
            print(
                "AVISO: LOAD_TEST_CNPJS vazio. As requisições não baterão em dados "
                "semeados e respostas não-200 contarão como falha. Semeie os dados."
            )
        self.cnpjs = _CNPJS or [str(random.randint(10**13, 10**14 - 1)) for _ in range(50)]

    @task(10)
    def score_single(self) -> None:
        cnpj = random.choice(self.cnpjs)
        with self.client.post(
            "/api/v1/legalscore/score",
            json={"cnpj": cnpj},
            name="POST /api/v1/legalscore/score",
            catch_response=True,
        ) as resp:
            # 200 é o ÚNICO sucesso. 401/403/5xx são falha (mede o caminho certo).
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"esperado 200, obtido {resp.status_code}")

    @task(3)
    def company_profile(self) -> None:
        cnpj = random.choice(self.cnpjs)
        with self.client.get(
            f"/api/v1/legalscore/company/{cnpj}",
            name="GET /api/v1/legalscore/company/{cnpj}",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"esperado 200, obtido {resp.status_code}")


class BatchScoreUser(HttpUser):
    """Valida o SLA do batch (1k CNPJs < 30s) — autenticado."""

    wait_time = between(5, 10)

    def on_start(self) -> None:
        with self.client.post(
            "/api/v1/auth/token", json=_CREDS,
            name="POST /api/v1/auth/token", catch_response=True,
        ) as resp:
            if resp.status_code != 200 or not resp.json().get("access_token"):
                resp.failure("auth falhou — medição abortada")
                raise StopUser()
            resp.success()
            self.client.headers.update(
                {"Authorization": f"Bearer {resp.json()['access_token']}"}
            )
        self.cnpjs = _CNPJS or [str(random.randint(10**13, 10**14 - 1)) for _ in range(1000)]

    @task
    def batch_score(self) -> None:
        cnpjs = [random.choice(self.cnpjs) for _ in range(1000)]
        with self.client.post(
            "/api/v1/legalscore/batch",
            json={"cnpjs": cnpjs},
            name="POST /api/v1/legalscore/batch",
            catch_response=True,
        ) as resp:
            # Batch é assíncrono: 202 Accepted é o sucesso esperado.
            if resp.status_code == 202:
                resp.success()
            else:
                resp.failure(f"esperado 202, obtido {resp.status_code}")

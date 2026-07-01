#!/usr/bin/env python3
"""
Gerador de scaffold de produto (SEAMS).

Estampa os arquivos §1-§3 do docs/new-product-checklist.md a partir de templates:
- services/shared/contracts/<foo>.py   (contrato + Protocol)
- services/<foo>/engine/factory.py     (factory SEAMS)
- services/gateway/routers/<foo>.py    (router P2)

Não toca no gateway main.py nem em migrações — imprime os passos manuais (§4-§8).
Idempotente-seguro: recusa sobrescrever arquivos existentes.

Uso:
    python scripts/scaffold_product.py <nome> "<descrição>"
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _contract(name: str, cap: str, desc: str) -> str:
    return f'''"""Contrato SEAMS de {cap} — {desc}."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

CONTRACT_VERSION = "{name}/v1"


class {cap}Request(BaseModel):
    model_config = {{"extra": "forbid"}}


class {cap}Result(BaseModel):
    model_config = {{"extra": "forbid"}}


class {cap}Error(Exception):
    ...


class {cap}Unavailable({cap}Error):
    ...


@runtime_checkable
class {cap}Engine(Protocol):
    name: str

    def healthy(self) -> bool: ...

    def evaluate(self, req: {cap}Request) -> {cap}Result: ...
'''


def _factory(name: str, cap: str) -> str:
    return f'''"""Factory SEAMS de {cap}."""
from __future__ import annotations

from services.shared.contracts.{name} import {cap}Request, {cap}Result, {cap}Unavailable


class _Python{cap}Engine:
    name = "python"

    def healthy(self) -> bool:
        return True

    def evaluate(self, req: {cap}Request) -> {cap}Result:
        return {cap}Result()


def get_{name}_engine() -> _Python{cap}Engine:
    """Retorna a implementação default. Levanta {cap}Unavailable se indisponível."""
    engine = _Python{cap}Engine()
    if not engine.healthy():
        raise {cap}Unavailable("{cap} engine indisponível")
    return engine
'''


def _router(name: str, cap: str, desc: str) -> str:
    return f'''"""
{cap} — {desc}

Segue o template P2 do router LegalScore (JWT via _get_tenant, problem+json
global, OTel opcional, exemplos OpenAPI, Decision Ledger). Endpoints 501 até
implementação.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

router = APIRouter(tags=["{name}"])


def _get_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token JWT não contém tenant_id.")
    return tenant_id


@router.get("/health", summary="Status do produto {cap}")
async def health(request: Request) -> Any:
    _get_tenant(request)
    return {{"product": "{name}", "status": "ok", "contract_version": "{name}/v1"}}
'''


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    name = sys.argv[1].lower()
    desc = sys.argv[2]
    cap = name.capitalize()

    targets = {
        ROOT / "services" / "shared" / "contracts" / f"{name}.py": _contract(name, cap, desc),
        ROOT / "services" / name / "engine" / "factory.py": _factory(name, cap),
        ROOT / "services" / "gateway" / "routers" / f"{name}.py": _router(name, cap, desc),
    }

    for path, content in targets.items():
        if path.exists():
            print(f"· pulado (já existe): {path.relative_to(ROOT)}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.name == name and path.name == "factory.py":
            (path.parent / "__init__.py").touch(exist_ok=True)
            (path.parent.parent / "__init__.py").touch(exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"✓ criado: {path.relative_to(ROOT)}")

    print("\nPassos manuais restantes (ver docs/new-product-checklist.md):")
    print(f"  4. Registrar em services/gateway/main.py: import {name} + "
          f'include_router({name}.router, prefix="/api/v1/{name}")')
    print("  5. Adicionar bloco Decision Ledger nos endpoints que decidem.")
    print(f"  6. Migração scripts/migrations/00N_{name}_schema.sql (se persistir).")
    print("  7. Registrar tasks Celery (se async).")
    print(f"  8. Frontend frontend/apps/{name}/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

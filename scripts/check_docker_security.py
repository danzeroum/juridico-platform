"""
Verifica que nenhum banco de dados tem porta exposta no host em
docker/compose/base.yml. Apenas Traefik (80/443) e acesso local
(127.0.0.1:XXXX) são permitidos.
"""
import sys
from pathlib import Path

import yaml

BASE_YML = Path(__file__).resolve().parents[1] / "docker" / "compose" / "base.yml"

DB_SERVICES = {
    "postgres",
    "pgbouncer",
    "neo4j",
    "opensearch",
    "redis",
    "minio",
    "chromadb",
}

ALLOWED_HOSTS = {"127.0.0.1", "traefik"}


def _is_db_port_exposed(service_name: str, ports: list) -> list[str]:
    violations = []
    for entry in ports:
        port_str = str(entry)
        # "HOST:CONTAINER" or just "CONTAINER" or dict with target/published
        if isinstance(entry, dict):
            published = str(entry.get("published", ""))
            host_ip = entry.get("host_ip", "0.0.0.0")
            if published and host_ip not in ("127.0.0.1",):
                violations.append(f"{service_name}: porta publicada {published} (host_ip={host_ip})")
        else:
            # String form: "127.0.0.1:8080:8080" or "8080:8080" or "8080"
            parts = port_str.split(":")
            if len(parts) == 3:
                host_ip = parts[0]
                if host_ip not in ("127.0.0.1",):
                    violations.append(f"{service_name}: porta exposta no host com IP {host_ip}")
            elif len(parts) == 2:
                # "HOST_PORT:CONTAINER_PORT" — no IP → binds 0.0.0.0 → violation
                violations.append(f"{service_name}: porta exposta no host sem restrição de IP: {port_str}")
            # single port number = expose only (not published) → OK
    return violations


PROTECTED_BUCKETS = {"bronze", "silver", "gold", "documents", "backups"}


def _check_minio_anonymous(compose_text: str) -> list[str]:
    """Verifica que nenhum bucket MinIO tem acesso anônimo de download/public."""
    violations = []
    for line in compose_text.splitlines():
        stripped = line.strip()
        # Proibido: mc anonymous set download|public|upload
        if "mc anonymous set" in stripped and "set none" not in stripped:
            violations.append(f"minio: acesso anônimo proibido detectado: {stripped!r}")
    # Verificar que todos os buckets protegidos têm 'set none'
    for bucket in PROTECTED_BUCKETS:
        expected = f"anonymous set none local/{bucket}"
        if expected not in compose_text:
            violations.append(f"minio: bucket '{bucket}' sem 'anonymous set none' no minio-init")
    return violations


def main() -> None:
    if not BASE_YML.exists():
        print(f"FALHA: {BASE_YML} não encontrado", file=sys.stderr)
        sys.exit(1)

    with BASE_YML.open(encoding="utf-8") as fh:
        compose_text = fh.read()

    compose = yaml.safe_load(compose_text)
    services = compose.get("services", {})
    all_violations: list[str] = []

    for svc_name, svc_def in services.items():
        if svc_name not in DB_SERVICES:
            continue
        ports = svc_def.get("ports", [])
        if ports:
            violations = _is_db_port_exposed(svc_name, ports)
            all_violations.extend(violations)

    # Verificar MinIO anonymous access
    all_violations.extend(_check_minio_anonymous(compose_text))

    if all_violations:
        for v in all_violations:
            print(f"FALHA: {v}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: nenhuma porta de banco exposta no host em {BASE_YML.name}")
    print("OK: MinIO sem acesso anônimo — todos os buckets com 'anonymous set none'")


if __name__ == "__main__":
    main()

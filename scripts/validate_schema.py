"""Validates schemas/alert.v1.json against the JSON Schema meta-schema."""
import json
import sys
from pathlib import Path

import jsonschema

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "alert.v1.json"


def main() -> None:
    if not SCHEMA_PATH.exists():
        print(f"FALHA: {SCHEMA_PATH} não encontrado", file=sys.stderr)
        sys.exit(1)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        print(f"OK: {SCHEMA_PATH.name} é um JSON Schema válido")
    except jsonschema.SchemaError as exc:
        print(f"FALHA: schema inválido — {exc.message}", file=sys.stderr)
        sys.exit(1)

    required_fields = {"alert_id", "dedup_key", "rule_id", "severity", "channels", "occurred_at"}
    schema_props = set(schema.get("properties", {}).keys())
    missing = required_fields - schema_props
    if missing:
        print(f"FALHA: campos obrigatórios ausentes no schema: {missing}", file=sys.stderr)
        sys.exit(1)

    if schema.get("additionalProperties") is not False:
        print("FALHA: additionalProperties deve ser false", file=sys.stderr)
        sys.exit(1)

    print("OK: todos os campos obrigatórios presentes e additionalProperties=false")


if __name__ == "__main__":
    main()

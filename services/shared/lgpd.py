"""
Utilitarios LGPD - Pseudonimizacao e protecao de dados pessoais
TODO os registros ingeridos passam por este modulo antes de qualquer persistencia.
"""

import hashlib
import re
from typing import Dict, Any


def hash_cpf(cpf: str) -> str:
    """Pseudonimiza CPF com hash SHA-256 truncado (12 chars)."""
    cpf_clean = re.sub(r'\D', '', cpf)
    return hashlib.sha256(cpf_clean.encode()).hexdigest()[:12]


def hash_name(name: str) -> str:
    """Pseudonimiza nome com hash SHA-256 truncado (10 chars)."""
    return hashlib.sha256(name.strip().lower().encode()).hexdigest()[:10]


def hash_user_id(user_id: str) -> str:
    """Pseudonimiza identificador de usuario para o Ledger."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


def pseudonymize_process_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pseudonimiza registro de processo judicial.
    CPF -> hash | Nome -> hash | Endereco/CEP -> removidos | CNPJ -> mantido (dado publico)
    """
    safe = record.copy()

    # CPF -> hash
    for field in ["parte_cpf", "cpf_autor", "cpf_reu", "cpf_advogado"]:
        if field in safe and safe[field]:
            safe[f"{field}_hash"] = hash_cpf(safe.pop(field))

    # Nome -> hash
    for field in ["parte_nome", "nome_autor", "nome_reu"]:
        if field in safe and safe[field]:
            safe[f"{field}_hash"] = hash_name(safe.pop(field))

    # Endereco e CEP -> removidos completamente
    for field in ["endereco", "cep", "logradouro", "bairro", "complemento"]:
        safe.pop(field, None)

    # CNPJ -> mantido (dado publico da Receita Federal)
    # Numero do processo -> mantido (dado publico do DATAJUD)

    return safe


def k_anonymize(records: list, quasi_identifiers: list, k: int = 5) -> list:
    """
    Suprime registros de grupos com menos de k entidades.
    Implementa padrao DadoSabedoria de k-anonymity.
    """
    from collections import Counter

    # Contar ocorrencias de cada combinacao de quasi-identificadores
    counts = Counter(
        tuple(r.get(qi) for qi in quasi_identifiers)
        for r in records
    )

    # Filtrar grupos com menos de k
    return [
        r for r in records
        if counts[tuple(r.get(qi) for qi in quasi_identifiers)] >= k
    ]

"""Testes de crypto-shredding (P0-3 da DoD)."""
from __future__ import annotations

import base64

import pytest

from services.shared.lgpd_crypto import (
    decrypt_from_ledger,
    encrypt_for_ledger,
    erase_titular,
    is_erased,
)

PSEUDONYM = "uid:12345678000195"
TENANT = "tenant-abc"


def _clean(pseudonym: str = PSEUDONYM, tenant: str = TENANT) -> None:
    """Remove chave do store para garantir estado limpo entre testes."""
    erase_titular(pseudonym, tenant)


class TestEncrypt:
    def test_retorna_string_nao_vazia(self):
        _clean()
        token = encrypt_for_ledger(PSEUDONYM, TENANT)
        assert isinstance(token, str) and len(token) > 0

    def test_token_e_base64url_valido(self):
        _clean()
        token = encrypt_for_ledger(PSEUDONYM, TENANT)
        raw = base64.urlsafe_b64decode(token.encode())
        # IV (12) + ciphertext (len(pseudonym)) + GCM tag (16)
        assert len(raw) == 12 + len(PSEUDONYM.encode()) + 16

    def test_mesmo_pseudonimo_gera_tokens_diferentes(self):
        """IV aleatório garante que cada cifra é distinta."""
        _clean()
        t1 = encrypt_for_ledger(PSEUDONYM, TENANT)
        t2 = encrypt_for_ledger(PSEUDONYM, TENANT)
        assert t1 != t2

    def test_tenants_diferentes_geram_tokens_diferentes(self):
        _clean(PSEUDONYM, "tenant-a")
        _clean(PSEUDONYM, "tenant-b")
        t1 = encrypt_for_ledger(PSEUDONYM, "tenant-a")
        t2 = encrypt_for_ledger(PSEUDONYM, "tenant-b")
        assert t1 != t2

    def test_token_nao_contem_pseudonimo_em_claro(self):
        _clean()
        token = encrypt_for_ledger(PSEUDONYM, TENANT)
        assert PSEUDONYM not in token


class TestDecrypt:
    def test_decrypt_retorna_pseudonimo_original(self):
        _clean()
        token = encrypt_for_ledger(PSEUDONYM, TENANT)
        recovered = decrypt_from_ledger(token, PSEUDONYM, TENANT)
        assert recovered == PSEUDONYM

    def test_token_adulterado_levanta_excecao(self):
        from cryptography.exceptions import InvalidTag
        _clean()
        token = encrypt_for_ledger(PSEUDONYM, TENANT)
        raw = base64.urlsafe_b64decode(token.encode())
        # Flip de um byte no ciphertext
        corrupted = bytearray(raw)
        corrupted[12] ^= 0xFF
        bad_token = base64.urlsafe_b64encode(bytes(corrupted)).decode()
        with pytest.raises((InvalidTag, Exception)):
            decrypt_from_ledger(bad_token, PSEUDONYM, TENANT)


class TestErasure:
    def test_erase_retorna_true_quando_chave_existia(self):
        _clean()
        encrypt_for_ledger(PSEUDONYM, TENANT)  # cria a chave
        assert erase_titular(PSEUDONYM, TENANT) is True

    def test_erase_retorna_false_quando_ja_apagada(self):
        _clean()
        assert erase_titular(PSEUDONYM, TENANT) is False

    def test_apos_erase_decrypt_levanta_keyerror(self):
        _clean()
        token = encrypt_for_ledger(PSEUDONYM, TENANT)
        erase_titular(PSEUDONYM, TENANT)
        with pytest.raises(KeyError):
            decrypt_from_ledger(token, PSEUDONYM, TENANT)

    def test_is_erased_true_apos_erase(self):
        _clean()
        encrypt_for_ledger(PSEUDONYM, TENANT)
        erase_titular(PSEUDONYM, TENANT)
        assert is_erased(PSEUDONYM, TENANT) is True

    def test_is_erased_false_antes_de_erase(self):
        _clean()
        encrypt_for_ledger(PSEUDONYM, TENANT)
        assert is_erased(PSEUDONYM, TENANT) is False

    def test_merkle_intacta_apos_erase(self):
        """
        Critério central do crypto-shredding: apagar a chave NÃO quebra a
        prova de integridade do Ledger (verify_integrity continua True).
        A integridade é sobre o hash de inputs/outputs, não sobre o token.
        """
        from services.shared.ledger.merkle import DecisionLedger

        ledger = DecisionLedger()
        _clean()
        token = encrypt_for_ledger(PSEUDONYM, TENANT)

        ledger.add_entry(
            request_id="req-erasure-001",
            product="legalscore",
            inputs={"cnpj_partial": "12345678****"},
            outputs={"score": 750, "risk_level": "BAIXO"},
            subject_token=token,
        )
        proof = ledger.get_proof("req-erasure-001")

        # Apagar a chave do titular
        erase_titular(PSEUDONYM, TENANT)

        # Integridade do Ledger continua verificável
        assert ledger.verify_integrity("req-erasure-001", proof) is True

    def test_erase_nao_afeta_outros_titulares(self):
        """Apagar o titular A não apaga o titular B."""
        p_a = "uid:aaaaaaaa"
        p_b = "uid:bbbbbbbb"
        _clean(p_a, TENANT)
        _clean(p_b, TENANT)

        token_b = encrypt_for_ledger(p_b, TENANT)
        encrypt_for_ledger(p_a, TENANT)

        erase_titular(p_a, TENANT)

        # Titular B ainda pode ser decifrado
        recovered = decrypt_from_ledger(token_b, p_b, TENANT)
        assert recovered == p_b

    def test_erase_isolado_por_tenant(self):
        """Apagar no tenant A não afeta o mesmo pseudônimo no tenant B."""
        _clean(PSEUDONYM, "tenant-x")
        _clean(PSEUDONYM, "tenant-y")

        token_y = encrypt_for_ledger(PSEUDONYM, "tenant-y")
        encrypt_for_ledger(PSEUDONYM, "tenant-x")

        erase_titular(PSEUDONYM, "tenant-x")

        # tenant-y intacto
        recovered = decrypt_from_ledger(token_y, PSEUDONYM, "tenant-y")
        assert recovered == PSEUDONYM

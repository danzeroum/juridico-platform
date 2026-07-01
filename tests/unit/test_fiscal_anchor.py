"""Testes da ancoragem Merkle de lote: raiz + prova de inclusão verificável."""
from __future__ import annotations

from services.fiscal.batch.anchor import (
    batch_manifest_hash,
    build_batch_anchor,
    inclusion_proof,
    serialize_result,
    verify_inclusion,
)
from services.shared.contracts.fiscal import (
    FonteRegra,
    IcmsResolution,
    NcmCandidate,
    NcmTriageResult,
)


def _result(desc: str, ncm: str) -> NcmTriageResult:
    return NcmTriageResult(
        sku_descricao=desc,
        suggested_ncm=NcmCandidate(
            ncm_codigo=ncm, descricao=desc, confidence=1.0, fonte_regra=FonteRegra.TIPI
        ),
        icms=IcmsResolution(interna_efetiva_pct=18.0, interestadual_pct=12.0, difal_pct=6.0),
    )


RESULTS = [_result(f"item {i}", f"8471{i:04d}") for i in range(7)]  # nº ímpar → testa padding


class TestBatchAnchor:
    def test_raiz_e_folhas(self):
        anchor = build_batch_anchor(RESULTS)
        assert anchor["count"] == 7
        assert len(anchor["leaf_hashes"]) == 7
        assert len(anchor["root"]) == 64

    def test_prova_de_inclusao_verifica(self):
        anchor = build_batch_anchor(RESULTS)
        for i in range(len(RESULTS)):
            proof = inclusion_proof(anchor["leaf_hashes"], i, anchor["root"])
            assert verify_inclusion(proof) is True

    def test_prova_adulterada_falha(self):
        anchor = build_batch_anchor(RESULTS)
        proof = inclusion_proof(anchor["leaf_hashes"], 3, anchor["root"])
        proof["leaf_hash"] = "0" * 64  # adultera a folha
        assert verify_inclusion(proof) is False

    def test_lote_de_um_item(self):
        anchor = build_batch_anchor([_result("único", "84710001")])
        proof = inclusion_proof(anchor["leaf_hashes"], 0, anchor["root"])
        assert verify_inclusion(proof) is True

    def test_raiz_muda_com_conteudo(self):
        a1 = build_batch_anchor(RESULTS)
        a2 = build_batch_anchor(RESULTS[:-1])
        assert a1["root"] != a2["root"]

    def test_manifest_hash_deterministico(self):
        h1 = batch_manifest_hash("job1", "tenant1", 7)
        h2 = batch_manifest_hash("job1", "tenant1", 7)
        assert h1 == h2 and len(h1) == 64


class TestChordSerialization:
    """A prova de inclusão deve sobreviver ao round-trip de serialização do chord."""

    def test_serialize_result(self):
        item = serialize_result(3, RESULTS[0])
        assert item["leaf_index"] == 3
        assert item["ncm_sugerido"] == RESULTS[0].suggested_ncm.ncm_codigo
        assert item["fonte_regra"] == "TIPI"
        assert item["difal_pct"] == 6.0

    def test_roundtrip_model_dump_preserva_ancora(self):
        from services.shared.contracts.fiscal import NcmTriageResult

        # Simula o transporte do chord: model_dump(json) → dict → NcmTriageResult.
        transported = [NcmTriageResult(**r.model_dump(mode="json")) for r in RESULTS]
        anchor_orig = build_batch_anchor(RESULTS)
        anchor_rt = build_batch_anchor(transported)
        # Mesma raiz após round-trip → folhas idênticas.
        assert anchor_rt["root"] == anchor_orig["root"]
        proof = inclusion_proof(anchor_rt["leaf_hashes"], 2, anchor_rt["root"])
        assert verify_inclusion(proof) is True

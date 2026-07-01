"""Testes do sink de persistência DRY (services/ingest/pipeline/base.py::persist_silver)."""
from services.ingest.pipeline import base


def _patch_stores(monkeypatch, *, minio=None, opensearch=None):
    """Substitui os clientes lazimport por fakes."""
    import services.shared.storage.minio_client as mc
    import services.shared.storage.opensearch_client as oc

    monkeypatch.setattr(mc, "put_jsonl", minio or (lambda s, d, r: f"bronze-{s}/dt={d}/x.jsonl"))
    monkeypatch.setattr(oc, "bulk_index", opensearch or (lambda idx, docs, id_field="id": len(docs)))


def test_persist_silver_grava_bronze_opensearch_e_grafo(monkeypatch):
    _patch_stores(monkeypatch)
    bronze = [{"id_processo": "1"}, {"id_processo": "2"}]
    silver = [{"id_processo": "1"}, {"id_processo": "2"}]
    calls: list[int] = []

    def graph_writer(records):
        calls.append(len(records))
        return len(records)

    counts = base.persist_silver(
        "DATAJUD", "2024-01-01", bronze, silver,
        opensearch_index="datajud-silver-2024-01", graph_writer=graph_writer,
    )
    assert counts["bronze"] == 2
    assert counts["opensearch"] == 2
    assert counts["graph"] == 2
    assert counts["errors"] == []
    assert calls == [2]


def test_persist_silver_sem_index_nem_grafo(monkeypatch):
    _patch_stores(monkeypatch)
    counts = base.persist_silver("PGFN", "2024-01-01", [{"a": 1}], [{"a": 1}])
    assert counts["bronze"] == 1
    assert counts["opensearch"] == 0
    assert counts["graph"] == 0


def test_persist_silver_degrada_graciosamente_em_falha_de_store(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("minio down")

    _patch_stores(monkeypatch, minio=boom)
    counts = base.persist_silver(
        "DATAJUD", "2024-01-01", [{"id_processo": "1"}], [{"id_processo": "1"}],
        opensearch_index="datajud-silver-2024-01",
    )
    # MinIO falhou mas OpenSearch seguiu; erro registrado, não propagado.
    assert counts["bronze"] == 0
    assert counts["opensearch"] == 1
    assert any("minio" in e for e in counts["errors"])

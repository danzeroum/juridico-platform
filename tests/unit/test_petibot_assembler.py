"""Testes do PetiBot assembler."""
from __future__ import annotations

from services.petibot.assembler import assemble_petition
from services.shared.contracts.petibot import PetiRequest, PetiResponse, TipoAcao


def _make_req(tipo: str = "TRABALHISTA", descricao: str | None = None) -> PetiRequest:
    return PetiRequest(
        descricao=descricao or "Reclamação trabalhista por horas extras não pagas durante o período contratual.",
        tipo_acao=TipoAcao(tipo),
        polo_ativo="João Silva",
        polo_passivo="Empresa XYZ Ltda",
        valor_causa=50_000.0,
    )


class TestAssemblePetition:
    def test_retorna_petirresponse(self):
        req = _make_req()
        resp = assemble_petition(req)
        assert isinstance(resp, PetiResponse)

    def test_trabalhista_tem_secao_pedidos(self):
        resp = assemble_petition(_make_req("TRABALHISTA"))
        titulos = [s.titulo for s in resp.secoes]
        assert "DOS PEDIDOS" in titulos

    def test_trabalhista_tem_verbas_rescisorias(self):
        resp = assemble_petition(_make_req("TRABALHISTA"))
        titulos = [s.titulo for s in resp.secoes]
        assert "DAS VERBAS RESCISÓRIAS" in titulos

    def test_tributario_tem_direito_tributario(self):
        req = _make_req(
            tipo="TRIBUTARIO",
            descricao="Ação anulatória de lançamento tributário de IRPJ por suposta omissão de receitas não tributáveis.",
        )
        resp = assemble_petition(req)
        titulos = [s.titulo for s in resp.secoes]
        assert "DO DIREITO TRIBUTÁRIO" in titulos

    def test_civel_tem_danos(self):
        req = _make_req(
            tipo="CIVEL",
            descricao="Ação de indenização por danos morais e materiais decorrentes de acidente de trânsito causado por terceiro.",
        )
        resp = assemble_petition(req)
        titulos = [s.titulo for s in resp.secoes]
        assert "DOS DANOS" in titulos

    def test_polo_ativo_passivo_preservados(self):
        req = _make_req()
        resp = assemble_petition(req)
        assert resp.polo_ativo == "João Silva"
        assert resp.polo_passivo == "Empresa XYZ Ltda"

    def test_tipo_acao_preservado(self):
        req = _make_req("TRIBUTARIO", "Descrição longa suficiente para a petição tributária em questão.")
        resp = assemble_petition(req)
        assert resp.tipo_acao == "TRIBUTARIO"

    def test_sem_rag_gracioso(self):
        """Sem ChromaDB em CI → precedentes_encontrados == 0, sem crash."""
        resp = assemble_petition(_make_req())
        assert resp.precedentes_encontrados == 0
        for s in resp.secoes:
            assert isinstance(s.precedentes, list)

    def test_secoes_tem_conteudo(self):
        resp = assemble_petition(_make_req())
        for s in resp.secoes:
            assert s.conteudo != ""

    def test_todos_os_tipos_funcionam(self):
        base = "Descrição longa o suficiente para servir de base à petição judicial em questão."
        for tipo in TipoAcao:
            req = PetiRequest(
                descricao=base,
                tipo_acao=tipo,
                polo_ativo="Autor",
                polo_passivo="Réu",
            )
            resp = assemble_petition(req)
            assert len(resp.secoes) >= 3

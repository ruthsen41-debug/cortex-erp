"""Testes da Escrita Fiscal (Acumuladores, Livros, Retenções, Apuração e Guias)."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app
from backend.database import get_conn
from backend.services.fiscal_book_engine import calculate_fiscal_entry
from backend.services.tax_calculator import get_icms_rate

client = TestClient(app)


def _headers():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_icms_rate_senado_e_calculo_acumulador():
    assert get_icms_rate("SP", "MT") == 7.0
    assert get_icms_rate("MT", "SP") == 12.0
    assert get_icms_rate("SP", "SP") == 18.0
    assert get_icms_rate("MT", "MT") == 17.0

    # Serviço tomado com retenções IRRF 1,5%, CSRF 4,65%, INSS 11%, ISS retido 3%
    acc_serv = {
        "tipo": "servico_tomado",
        "cfop_padrao": "1933",
        "aliquota_iss": 3.0,
        "retencao_iss": 1,
        "retencao_irrf_pct": 1.5,
        "retencao_csrf_pct": 4.65,
        "retencao_inss_pct": 11.0,
        "gera_credito_pis_cofins": 1,
    }
    res = calculate_fiscal_entry(
        {"valor_contabil": 10000.0},
        acc_serv,
        {"regime_tributario": "lucro_real", "uf": "MT"},
    )
    assert res["valor_iss"] == 300.0 and res["iss_retido"] == 300.0
    assert res["irrf_retido"] == 150.0
    assert res["csrf_retido"] == 465.0
    assert res["inss_retido"] == 1100.0
    assert res["valor_pis"] == 165.0 and res["valor_cofins"] == 760.0
    assert res["ibs_valor"] == 10.0 and res["cbs_valor"] == 90.0

    # Dispensa legal IRRF < R$ 10,00 e CSRF <= R$ 10,00
    peq = calculate_fiscal_entry(
        {"valor_contabil": 200.0},
        acc_serv,
        {"regime_tributario": "lucro_real", "uf": "MT"},
    )
    assert peq["irrf_retido"] == 0.0 and peq["csrf_retido"] == 0.0


def test_api_escrita_fiscal_livros_apuracao_transporte_e_guias():
    h = _headers()
    comp_1 = "2017-04"
    comp_2 = "2017-05"
    orig_company = client.get("/api/company", headers=h).json()
    orig_regime = orig_company.get("regime_tributario", "simples_nacional")

    created_entries = []
    created_acc_id = None
    created_fin_ids = []
    try:
        # Ajusta empresa para Lucro Real durante o teste
        assert client.put("/api/company", headers=h, json={"regime_tributario": "lucro_real"}).status_code == 200

        accs = client.get("/api/fiscal-books/accumulators", headers=h).json()
        assert len(accs) >= 7
        by_cod = {a["codigo"]: a for a in accs}

        # Criar acumulador customizado
        new_acc = client.post("/api/fiscal-books/accumulators", headers=h, json={
            "codigo": "999T", "descricao": "Teste ST", "tipo": "saida",
            "cfop_padrao": "5405", "cst_icms": "60", "aliquota_icms": 17.0,
            "tem_icms_st": 1, "mva_pct": 40.0,
        })
        assert new_acc.status_code == 201, new_acc.text
        created_acc_id = new_acc.json()["id"]

        # Mês 1 (2017-04): Entrada R$ 20.000 (crédito ICMS 3.400) e Saída R$ 10.000 (débito ICMS 1.700) -> saldo credor 1.700
        e1 = client.post("/api/fiscal-books/entries", headers=h, json={
            "accumulator_id": by_cod["101"]["id"], "numero": "1001", "data_emissao": f"{comp_1}-10",
            "competencia": comp_1, "participante_nome": "Fornecedor Teste", "valor_contabil": 20000.0,
            "gerar_contabil": True, "gerar_financeiro": False,
        })
        assert e1.status_code == 201, e1.text
        created_entries.append(e1.json()["id"])
        assert e1.json()["valor_icms"] == 3400.0
        assert e1.json()["accounting_entry_id"] is not None

        s1 = client.post("/api/fiscal-books/entries", headers=h, json={
            "accumulator_id": by_cod["201"]["id"], "numero": "2001", "data_emissao": f"{comp_1}-15",
            "competencia": comp_1, "participante_nome": "Cliente Teste", "valor_contabil": 10000.0,
            "gerar_contabil": True, "gerar_financeiro": False,
        })
        assert s1.status_code == 201, s1.text
        created_entries.append(s1.json()["id"])
        assert s1.json()["valor_icms"] == 1700.0

        # Serviço tomado com retenções + financeiro líquido
        st1 = client.post("/api/fiscal-books/entries", headers=h, json={
            "accumulator_id": by_cod["401"]["id"], "numero": "3001", "data_emissao": f"{comp_1}-20",
            "competencia": comp_1, "participante_nome": "Consultoria PJ", "valor_contabil": 10000.0,
            "gerar_contabil": True, "gerar_financeiro": True,
        })
        assert st1.status_code == 201, st1.text
        created_entries.append(st1.json()["id"])
        if st1.json().get("financial_entry_id"):
            created_fin_ids.append(st1.json()["financial_entry_id"])
        assert st1.json()["irrf_retido"] == 150.0
        assert st1.json()["csrf_retido"] == 465.0
        assert st1.json()["inss_retido"] == 1100.0

        # Saída com ST (acumulador customizado) no mês 2 (2017-05): R$ 30.000 -> débito ICMS 5.100 - saldo anterior 1.700 = 3.400
        s2 = client.post("/api/fiscal-books/entries", headers=h, json={
            "accumulator_id": created_acc_id, "numero": "2002", "data_emissao": f"{comp_2}-10",
            "competencia": comp_2, "participante_nome": "Cliente ST", "valor_contabil": 30000.0,
            "gerar_contabil": False, "gerar_financeiro": False,
        })
        assert s2.status_code == 201, s2.text
        created_entries.append(s2.json()["id"])
        assert s2.json()["valor_icms_st"] > 0

        # Livros Fiscais
        books = client.get(f"/api/fiscal-books/books?competencia={comp_1}", headers=h)
        assert books.status_code == 200
        b = books.json()
        assert b["livro_entradas"]["count"] >= 1
        assert b["livro_saidas"]["count"] >= 1
        assert b["livro_servicos_tomados"]["count"] >= 1
        assert len(b["resumo_cfop"]) >= 3

        # Sync ERP
        sync = client.post(f"/api/fiscal-books/sync?competencia={comp_1}", headers=h)
        assert sync.status_code == 200 and "total_escriturado" in sync.json()

        # Apuração mês 1 -> saldo credor ICMS transportado = 1.700
        ap1 = client.post(f"/api/fiscal-books/apurations/run?competencia={comp_1}", headers=h)
        assert ap1.status_code == 200, ap1.text
        ap1_map = {a["imposto"]: a for a in ap1.json()["apurations"]}
        assert ap1_map["ICMS"]["saldo_credor_transportar"] == 1700.0
        assert ap1_map["ICMS"]["valor_a_recolher"] == 0.0
        assert ap1_map["IRRF_RET"]["valor_a_recolher"] == 150.0
        assert ap1_map["CSRF_RET"]["valor_a_recolher"] == 465.0
        assert ap1_map["INSS_RET"]["valor_a_recolher"] == 1100.0

        # Apuração mês 2 -> usa saldo credor anterior (1.700)
        ap2 = client.post(f"/api/fiscal-books/apurations/run?competencia={comp_2}", headers=h)
        assert ap2.status_code == 200
        ap2_map = {a["imposto"]: a for a in ap2.json()["apurations"]}
        assert ap2_map["ICMS"]["saldo_credor_anterior"] == 1700.0
        assert ap2_map["ICMS"]["valor_a_recolher"] == 3400.0

        # Guia HTML + Lançamento financeiro da guia
        guia = client.get(f"/api/fiscal-books/apurations/{ap2_map['ICMS']['id']}/guia", headers=h)
        assert guia.status_code == 200 and "3.400,00" in guia.text

        fin_g = client.post(f"/api/fiscal-books/apurations/{ap2_map['ICMS']['id']}/gerar-financeiro", headers=h)
        assert fin_g.status_code == 200 and fin_g.json()["financial_entry"]["amount"] == 3400.0
        created_fin_ids.append(fin_g.json()["financial_entry"]["id"])
    finally:
        client.put("/api/company", headers=h, json={"regime_tributario": orig_regime})
        for eid in created_entries:
            client.delete(f"/api/fiscal-books/entries/{eid}", headers=h)
        if created_acc_id:
            client.delete(f"/api/fiscal-books/accumulators/{created_acc_id}", headers=h)
        conn = get_conn()
        for fid in created_fin_ids:
            conn.execute("DELETE FROM financial_entries WHERE id = ?", (fid,))
        conn.execute("DELETE FROM fiscal_apurations WHERE competencia IN (?, ?)", (comp_1, comp_2))
        conn.commit()
        conn.close()

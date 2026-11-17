"""Testes da Etapa 3: SPED PVA (Fiscal, ECD, Contribuições, ECF), LALUR e Contabilidade Completa."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app
from backend.database import get_conn

client = TestClient(app)


def _headers():
    res = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_sped_fiscal_ecd_contribuicoes_ecf_e_lalur():
    h = _headers()
    comp = "2018-06"
    s_date, e_date = f"{comp}-01", f"{comp}-30"

    conn = get_conn()
    orig_comp = dict(conn.execute("SELECT * FROM companies WHERE id = 1").fetchone())
    conn.close()

    created_fiscal = []
    created_asset_id = None
    try:
        # Atualiza dados do contador e regime Lucro Real diretamente para validar 0100 / ECF
        conn = get_conn()
        conn.execute("""
            UPDATE companies
            SET regime_tributario = 'lucro_real',
                contador_nome = 'MARIA CONTADORA CRC',
                contador_cpf = '12345678901',
                contador_crc = 'CRC-MT-009988/O'
            WHERE id = 1
        """)
        conn.commit()
        conn.close()

        # Cria um bem imobilizado para Bloco G (CIAP) e F120
        asset_res = client.post("/api/patrimony", headers=h, json={
            "name": "Servidor Dell PowerEdge SPED",
            "category": "informatica",
            "acquisition_date": f"{comp}-05",
            "acquisition_value": 12000.0,
            "useful_life_months": 60,
        })
        assert asset_res.status_code == 200, asset_res.text
        created_asset_id = asset_res.json()["id"]

        accs = {a["codigo"]: a for a in client.get("/api/fiscal-books/accumulators", headers=h).json()}
        fe_in = client.post("/api/fiscal-books/entries", headers=h, json={
            "accumulator_id": accs["101"]["id"], "numero": "8801", "data_emissao": f"{comp}-10",
            "competencia": comp, "participante_nome": "Fornecedor SPED", "participante_doc": "11222333000181",
            "valor_contabil": 10000.0, "gerar_contabil": False, "gerar_financeiro": False,
        })
        assert fe_in.status_code == 201, fe_in.text
        created_fiscal.append(fe_in.json()["id"])

        fe_out = client.post("/api/fiscal-books/entries", headers=h, json={
            "accumulator_id": accs["201"]["id"], "numero": "8802", "data_emissao": f"{comp}-15",
            "competencia": comp, "participante_nome": "Cliente SPED", "participante_doc": "99888777000166",
            "valor_contabil": 15000.0, "gerar_contabil": False, "gerar_financeiro": False,
        })
        assert fe_out.status_code == 201, fe_out.text
        created_fiscal.append(fe_out.json()["id"])

        ap_run = client.post(f"/api/fiscal-books/apurations/run?competencia={comp}", headers=h)
        assert ap_run.status_code == 200

        # 1) SPED Fiscal (0100 dinâmico, C100, C190, E110, Bloco G e Bloco 9 exato)
        sped = client.get(f"/api/reports/sped-fiscal?start_date={s_date}&end_date={e_date}", headers=h)
        assert sped.status_code == 200, sped.text
        txt = sped.text
        assert "|0100|MARIA CONTADORA CRC|" in txt
        assert "|C100|" in txt
        assert "|C190|" in txt
        assert "|E110|" in txt
        assert "|G001|0|" in txt
        assert "|G125|" in txt
        lines = [ln for ln in txt.strip().splitlines() if ln.strip()]
        assert lines[-1].startswith(f"|9999|{len(lines)}|")

        # 2) Mapeamento Referencial + SPED ECD
        map_res = client.post("/api/accounting/mapeamento-referencial/auto", headers=h)
        assert map_res.status_code == 200 and map_res.json()["mapped_count"] > 10

        ecd = client.get(f"/api/accounting/ecd?year=2018&start_date={s_date}&end_date={e_date}", headers=h)
        assert ecd.status_code == 200, ecd.text
        ecd_txt = ecd.text
        assert "|I010|G|" in ecd_txt
        assert "|I030|" in ecd_txt
        assert "|I050|" in ecd_txt
        assert "|I051|" in ecd_txt
        assert "|I150|" in ecd_txt
        assert "|I155|" in ecd_txt
        assert "|J100|" in ecd_txt
        assert "|J150|" in ecd_txt
        assert "|J900|" in ecd_txt
        assert "|J930|" in ecd_txt
        assert "|L020|" not in ecd_txt
        assert "|L022|" not in ecd_txt

        # 3) EFD-Contribuições (Bloco C, F120, M200/M600) e SPED ECF
        efd_c = client.get(f"/api/reports/efd-contribuicoes?start_date={s_date}&end_date={e_date}", headers=h)
        assert efd_c.status_code == 200, efd_c.text
        assert "|M200|" in efd_c.text and "|M600|" in efd_c.text
        assert "|F120|" in efd_c.text

        ecf = client.get("/api/reports/ecf?year=2018", headers=h)
        assert ecf.status_code == 200, ecf.text
        ecf_txt = ecf.text
        assert "|0000|LECF|" in ecf_txt
        assert "|J050|" in ecf_txt and "|J051|" in ecf_txt
        assert "|L001|0|" in ecf_txt
        assert "|M001|0|" in ecf_txt
        assert "|N620|" in ecf_txt and "|N660|" in ecf_txt

        # 4) LALUR Balancetes Mensais de Suspensão/Redução
        bal_susp = client.get("/api/lalur/balancetes-suspensao?ano=2018", headers=h)
        assert bal_susp.status_code == 200
        bs_data = bal_susp.json()
        assert len(bs_data["meses"]) == 12
        assert "estimativa_mes" in bs_data["meses"][0]
        assert "balancete_suspensao_mes" in bs_data["meses"][0]
    finally:
        for fid in created_fiscal:
            client.delete(f"/api/fiscal-books/entries/{fid}", headers=h)
        if created_asset_id:
            client.delete(f"/api/patrimony/{created_asset_id}", headers=h)
        conn = get_conn()
        conn.execute("DELETE FROM fiscal_apurations WHERE competencia = ?", (comp,))
        conn.execute("""
            UPDATE companies
            SET regime_tributario = ?, contador_nome = ?, contador_cpf = ?, contador_crc = ?
            WHERE id = 1
        """, (
            orig_comp.get("regime_tributario", "simples_nacional"),
            orig_comp.get("contador_nome") or "",
            orig_comp.get("contador_cpf") or "",
            orig_comp.get("contador_crc") or "",
        ))
        conn.commit()
        conn.close()


def test_accounting_are_lock_dfc_dmpl_notas_e_historicos():
    h = _headers()
    yr = 2016
    s_date, e_date = f"{yr}-01-01", f"{yr}-12-31"
    created_entry_ids = []
    period_id = None
    try:
        # 1) Históricos Padrão + lançamento automático a partir do histórico
        hists = client.get("/api/accounting/historicos-padrao", headers=h)
        assert hists.status_code == 200 and len(hists.json()) >= 5

        e_std = client.post("/api/accounting/entries/from-standard", headers=h, json={
            "history_code": "H002",
            "entry_date": f"{yr}-05-10",
            "amount": 5000.0,
            "complement": "Cliente Teste",
            "document_number": "REC-2016",
        })
        assert e_std.status_code == 201, e_std.text
        created_entry_ids.append(e_std.json()["id"])

        # Lançamento de Receita (3.1.01) e Despesa (5.2.01) para testar ARE, DFC e DMPL
        accs = {a["code"]: a["id"] for a in client.get("/api/accounting/accounts", headers=h).json()}
        e_rec = client.post("/api/accounting/entries", headers=h, json={
            "entry_date": f"{yr}-06-15",
            "description": "Venda exercício 2016",
            "lines": [
                {"account_id": accs["1.1.02"], "debit": 12000.0, "credit": 0.0},
                {"account_id": accs["3.1.01"], "debit": 0.0, "credit": 12000.0},
            ],
        })
        assert e_rec.status_code == 201, e_rec.text
        created_entry_ids.append(e_rec.json()["id"])

        e_desp = client.post("/api/accounting/entries", headers=h, json={
            "entry_date": f"{yr}-07-20",
            "description": "Aluguel exercício 2016",
            "lines": [
                {"account_id": accs["5.2.01"], "debit": 4000.0, "credit": 0.0},
                {"account_id": accs["1.1.02"], "debit": 0.0, "credit": 4000.0},
            ],
        })
        assert e_desp.status_code == 201, e_desp.text
        created_entry_ids.append(e_desp.json()["id"])

        # 2) DFC, DMPL, Notas Explicativas e Caderno HTML
        dfc = client.get(f"/api/accounting/dfc?start_date={s_date}&end_date={e_date}", headers=h)
        assert dfc.status_code == 200
        dfc_d = dfc.json()
        assert dfc_d["metodo_direto"]["recebimentos_clientes"] >= 12000.0
        assert dfc_d["metodo_indireto"]["lucro_liquido_exercicio"] == 8000.0

        dmpl = client.get(f"/api/accounting/dmpl?year={yr}", headers=h)
        assert dmpl.status_code == 200
        assert dmpl.json()["dlpa"]["lucro_prejuizo_exercicio"] == 8000.0

        notas = client.get(f"/api/accounting/notas-explicativas?year={yr}", headers=h)
        assert notas.status_code == 200 and len(notas.json()) >= 5

        caderno = client.get(f"/api/accounting/relatorio-demonstracoes-html?year={yr}", headers=h)
        assert caderno.status_code == 200
        assert "Carta de Responsabilidade" in caderno.text

        # 3) Encerramento ARE + Trava de período fechado + Reabertura
        close_res = client.post("/api/accounting/close-period", headers=h, json={
            "start_date": s_date, "end_date": e_date, "lock_period": True,
        })
        assert close_res.status_code == 200, close_res.text
        cd = close_res.json()
        period_id = cd["period_id"]
        assert cd["lucro_prejuizo"] == 8000.0
        assert cd["are_entry_id"] is not None
        assert cd["status_periodo"] == "fechado"

        # ECD contendo o lançamento ARE (|I200|...|E|) e |I250|
        ecd_2016 = client.get(f"/api/accounting/ecd?year={yr}&start_date={s_date}&end_date={e_date}", headers=h)
        assert ecd_2016.status_code == 200
        assert "|I200|" in ecd_2016.text and "|I250|" in ecd_2016.text

        # Tentativa de lançar em período bloqueado deve retornar 400
        blocked = client.post("/api/accounting/entries", headers=h, json={
            "entry_date": f"{yr}-08-01",
            "description": "Tentativa bloqueada",
            "lines": [
                {"account_id": accs["1.1.01"], "debit": 100.0, "credit": 0.0},
                {"account_id": accs["3.1.01"], "debit": 0.0, "credit": 100.0},
            ],
        })
        assert blocked.status_code == 400

        # Reabertura libera lançamentos novamente
        reopen = client.post(f"/api/accounting/reopen-period/{period_id}", headers=h)
        assert reopen.status_code == 200 and reopen.json()["status_periodo"] == "aberto"

        # Exclusão do lançamento manual agora permitida
        del_res = client.delete(f"/api/accounting/entries/{created_entry_ids[-1]}", headers=h)
        assert del_res.status_code == 200
        created_entry_ids.pop()
    finally:
        conn = get_conn()
        if period_id:
            p_row = conn.execute("SELECT are_entry_id FROM accounting_periods WHERE id = ?", (period_id,)).fetchone()
            if p_row and p_row["are_entry_id"]:
                conn.execute("DELETE FROM accounting_entry_lines WHERE entry_id = ?", (p_row["are_entry_id"],))
                conn.execute("DELETE FROM accounting_entries WHERE id = ?", (p_row["are_entry_id"],))
            conn.execute("DELETE FROM accounting_periods WHERE id = ?", (period_id,))
        for eid in created_entry_ids:
            conn.execute("DELETE FROM accounting_entry_lines WHERE entry_id = ?", (eid,))
            conn.execute("DELETE FROM accounting_entries WHERE id = ?", (eid,))
        conn.execute("DELETE FROM accounting_notes WHERE year = ?", (yr,))
        conn.commit()
        conn.close()

"""Testes da Etapa 4: Multiempresa Escritório, Processos, CNDs, Auditoria Cruzada, Patrimônio e Honorários."""
import sys
from datetime import date, timedelta
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


def test_multiempresa_processos_cnds_e_auditoria_cruzada():
    h = _headers()
    new_company_id = None
    comp = "2019-07"
    cnd_ids = []

    try:
        # 1) Multiempresa: cria empresa cliente e verifica seeds automáticos
        create_res = client.post("/api/company/create", headers=h, json={
            "razao_social": "CLIENTE ESCRITORIO TESTE LTDA",
            "nome_fantasia": "Cliente Teste",
            "cnpj": "77.111.222/0001-33",
            "regime_tributario": "lucro_presumido",
            "uf": "MT",
            "cidade": "Cuiabá",
        })
        assert create_res.status_code == 201, create_res.text
        new_company_id = create_res.json()["id"]

        lst = client.get("/api/company/list", headers=h)
        assert lst.status_code == 200
        ids = [c["id"] for c in lst.json()["companies"]]
        assert 1 in ids and new_company_id in ids

        # Troca de empresa sem relogar
        sw = client.post("/api/company/switch", headers=h, json={"company_id": new_company_id})
        assert sw.status_code == 200 and sw.json()["company_id"] == new_company_id
        h2 = {"Authorization": f"Bearer {sw.json()['access_token']}"}

        # Verifica que a nova empresa recebeu Plano de Contas e Acumuladores
        accts = client.get("/api/accounting/accounts", headers=h2)
        assert accts.status_code == 200 and len(accts.json()) >= 20
        accs_fisc = client.get("/api/fiscal-books/accumulators", headers=h2)
        assert accs_fisc.status_code == 200 and len(accs_fisc.json()) >= 7

        # 2) Domínio Processos & Protocolo Digital
        gen = client.post(f"/api/office/processes/generate?competencia={comp}", headers=h2)
        assert gen.status_code == 200, gen.text
        procs = gen.json()["processes"]
        assert len(procs) >= 6  # Lucro Presumido inclui SPED Fiscal, EFD-Contribuições, Reinf etc.
        proc_id = procs[0]["id"]

        upd = client.put(f"/api/office/processes/{proc_id}", headers=h2, json={
            "status": "em_andamento", "observacoes": "Em conferência",
        })
        assert upd.status_code == 200 and upd.json()["status"] == "em_andamento"

        prot = client.post(f"/api/office/processes/{proc_id}/protocolar", headers=h2)
        assert prot.status_code == 200
        assert prot.json()["status"] == "protocolado" and len(prot.json()["protocolo_hash"]) == 16

        conf = client.post(f"/api/office/processes/{proc_id}/confirmar-leitura", headers=h2)
        assert conf.status_code == 200
        assert conf.json()["status"] == "confirmado_cliente" and conf.json()["confirmado_cliente_em"] != ""

        # 3) Monitoramento de CNDs
        dt_hoje = date.today()
        cnd_vencida = client.post("/api/office/cnds", headers=h2, json={
            "tipo": "RFB_PGFN",
            "numero_certidao": "2026-VENC-01",
            "data_emissao": (dt_hoje - timedelta(days=190)).isoformat(),
            "data_validade": (dt_hoje - timedelta(days=5)).isoformat(),
        })
        assert cnd_vencida.status_code == 201 and cnd_vencida.json()["status_alerta"] == "vencida"
        cnd_ids.append(cnd_vencida.json()["id"])

        cnd_ok = client.post("/api/office/cnds", headers=h2, json={
            "tipo": "FGTS_CRF",
            "numero_certidao": "2026-OK-02",
            "data_emissao": dt_hoje.isoformat(),
            "data_validade": (dt_hoje + timedelta(days=30)).isoformat(),
        })
        assert cnd_ok.status_code == 201 and cnd_ok.json()["status_alerta"] == "regular"
        cnd_ids.append(cnd_ok.json()["id"])

        cnds_list = client.get("/api/office/cnds", headers=h2)
        assert cnds_list.status_code == 200 and len(cnds_list.json()) >= 2

        for cid in cnd_ids:
            assert client.delete(f"/api/office/cnds/{cid}", headers=h2).status_code == 200

        # 4) Auditoria Fiscal Cruzada
        cruz = client.get(f"/api/audit/cruzamento-fiscal?competencia={comp}", headers=h2)
        assert cruz.status_code == 200, cruz.text
        cruz_d = cruz.json()
        assert "score_conformidade" in cruz_d and len(cruz_d["cruzamentos"]) == 5
    finally:
        # Restaura empresa 1 para o usuário admin
        client.post("/api/company/switch", headers=h, json={"company_id": 1})
        if new_company_id:
            conn = get_conn()
            conn.execute("DELETE FROM office_processes WHERE company_id = ?", (new_company_id,))
            conn.execute("DELETE FROM company_cnds WHERE company_id = ?", (new_company_id,))
            conn.execute("DELETE FROM accounting_accounts WHERE company_id = ?", (new_company_id,))
            conn.execute("DELETE FROM payroll_rubrics WHERE company_id = ?", (new_company_id,))
            conn.execute("DELETE FROM fiscal_accumulators WHERE company_id = ?", (new_company_id,))
            conn.execute("DELETE FROM bank_accounts WHERE company_id = ?", (new_company_id,))
            conn.execute("DELETE FROM user_companies WHERE company_id = ?", (new_company_id,))
            conn.execute("DELETE FROM companies WHERE id = ?", (new_company_id,))
            conn.commit()
            conn.close()


def test_patrimonio_avancado_e_honorarios_reajuste():
    h = _headers()
    asset_id = None
    baixa_entry_id = None
    lalur_id = None
    contrato_id = None
    comp = "2015-03"

    try:
        # 1) Patrimônio: criação com vida útil societária (120m) != fiscal IN 1.700 (60m)
        cr_asset = client.post("/api/patrimony", headers=h, json={
            "name": "Empilhadeira Elétrica Parity",
            "category": "maquinas_equipamentos",
            "acquisition_date": "2015-01-10",
            "acquisition_value": 60000.0,
            "useful_life_months": 120,
            "tax_useful_life_months": 60,
            "icms_credit_total": 10200.0,
        })
        assert cr_asset.status_code == 200, cr_asset.text
        asset_id = cr_asset.json()["id"]

        # Depreciação paralela CPC 27 vs IN 1.700 + geração LALUR
        par = client.get(f"/api/patrimony/depreciacao-paralela?competencia={comp}&gerar_lalur=true", headers=h)
        assert par.status_code == 200, par.text
        pd = par.json()
        item = next(i for i in pd["items"] if i["asset_id"] == asset_id)
        assert item["depreciacao_societaria"] == 500.0
        assert item["depreciacao_fiscal"] == 1000.0
        assert item["diferenca_mensal"] == -500.0
        assert item["efeito_lalur"] == "exclusao"
        lalur_id = pd.get("lalur_lancamento_id")
        assert lalur_id is not None

        # Baixa patrimonial com ganho de capital (vendido por 65.000 vs líquido 60.000 = +5.000)
        baixa = client.post(f"/api/patrimony/{asset_id}/baixa", headers=h, json={
            "disposal_date": "2015-04-01",
            "disposal_value": 65000.0,
            "disposal_reason": "venda",
            "gerar_contabil": True,
        })
        assert baixa.status_code == 200, baixa.text
        bd = baixa.json()
        assert bd["status"] == "baixado"
        assert bd["capital_gain_loss"] == 5000.0
        assert bd["tipo_resultado"] == "ganho_capital"
        baixa_entry_id = bd.get("accounting_entry_id")
        assert baixa_entry_id is not None

        # 2) Honorários: contrato + reajuste anual em lote + faturamento com valor por funcionário
        hc = client.post("/api/honorarios/contratos", headers=h, json={
            "client_name": "Empresa Honorários Teste",
            "cnpj_cpf": "12.345.678/0001-99",
            "regime": "lucro_presumido",
            "valor_mensal": 2000.0,
            "dia_vencimento": 10,
        })
        assert hc.status_code == 200, hc.text
        contrato_id = hc.json()["id"]

        reaj = client.post("/api/honorarios/reajustar-anual", headers=h, json={
            "indice": "IPCA",
            "percentual": 10.0,
            "contrato_ids": [contrato_id],
        })
        assert reaj.status_code == 200, reaj.text
        assert reaj.json()["contratos_reajustados"] == 1
        assert reaj.json()["mrr_novo"] == 2200.0

        fat = client.post(
            f"/api/honorarios/faturar-mes?competencia={comp}&valor_por_funcionario=50",
            headers=h,
        )
        assert fat.status_code == 200, fat.text
        assert fat.json()["faturas_geradas"] >= 1
        faturas = client.get(f"/api/honorarios/faturas?competencia={comp}", headers=h).json()
        fat_c = next(f for f in faturas if f["contrato_id"] == contrato_id)
        assert fat_c["valor"] >= 2200.0
    finally:
        if asset_id:
            client.delete(f"/api/patrimony/{asset_id}", headers=h)
        if contrato_id:
            client.delete(f"/api/honorarios/contratos/{contrato_id}", headers=h)
        conn = get_conn()
        if baixa_entry_id:
            conn.execute("DELETE FROM accounting_entry_lines WHERE entry_id = ?", (baixa_entry_id,))
            conn.execute("DELETE FROM accounting_entries WHERE id = ?", (baixa_entry_id,))
        if lalur_id:
            conn.execute("DELETE FROM lalur_lancamentos WHERE id = ?", (lalur_id,))
        conn.execute("DELETE FROM lalur_parte_b WHERE descricao = 'Controle Depreciação Societária vs Fiscal'")
        conn.execute("DELETE FROM honorarios_faturas WHERE competencia = ?", (comp,))
        conn.commit()
        conn.close()

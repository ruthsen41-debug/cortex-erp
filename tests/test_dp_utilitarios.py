"""Bloco 5 — automação e utilitários do DP: vencimentos legais, folha no contas a pagar, alteração e
exclusão em grupo, acerto da data de pagamento e rotinas automáticas."""
from datetime import date, datetime

from backend.database import get_conn
from backend.routers import dp_utilitarios as du
from backend.services import dp_rotinas as rt
from tests.test_complementar_escalas import EMP, _cpf, _empresa_nova, client

U = "/api/dp/utilitarios"
ANTIGO = {**EMP, "admission_date": "2024-01-10"}


def _func(h, **extra):
    r = client.post("/api/dp/employees", headers=h, json={**ANTIGO, "cpf": _cpf(), **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _folha(h, comp):
    r = client.post("/api/dp/payroll/run", headers=h, json={"competence": comp})
    assert r.status_code == 201, r.text
    return r.json()["run"]["id"]


# ── regras puras ─────────────────────────────────────────────────────────────
def test_quinto_dia_util_conta_sabado_e_pula_domingo_e_feriado():
    # competência 10/2026 → novembro/2026 começa num domingo: 2(seg),3,4,5,6 → 5º dia útil = 06/11
    assert rt.quinto_dia_util("2026-10") == date(2026, 11, 6)
    # feriado em 02/11 (Finados): 3,4,5,6,7(sáb) → 07/11
    assert rt.quinto_dia_util("2026-10", [date(2026, 11, 2)]) == date(2026, 11, 7)
    # dezembro → janeiro do ano seguinte
    assert rt.quinto_dia_util("2026-12", [date(2027, 1, 1)]) == date(2027, 1, 7)


def test_dia20_antecipa_para_dia_util_anterior():
    assert rt.dia20_antecipado("2026-10") == date(2026, 11, 20)          # sexta
    assert rt.dia20_antecipado("2026-11") == date(2026, 12, 18)          # 20/12 é domingo → sexta 18
    assert rt.dia20_antecipado("2026-10", [date(2026, 11, 20)]) == date(2026, 11, 19)


def test_agenda_das_rotinas():
    assert rt.competencia_alvo(date(2026, 1, 5), "anterior") == "2025-12"
    assert rt.competencia_alvo(date(2026, 1, 5), "atual") == "2026-01"
    assert rt.proxima_execucao(31, "08:00", datetime(2026, 2, 1)) == datetime(2026, 2, 28, 8, 0)
    assert rt.proxima_execucao(5, "08:00", datetime(2026, 3, 5, 8, 0)) == datetime(2026, 4, 5, 8, 0)
    assert rt.proxima_execucao(5, "09:30", datetime(2026, 3, 5, 8, 0)) == datetime(2026, 3, 5, 9, 30)
    assert rt.validar_rotina({"tipo": "enviar_holerites", "dia": 6})["competencia"] == "anterior"
    for ruim in ({"tipo": "x", "dia": 1}, {"tipo": "calcular_folha", "dia": 32},
                 {"tipo": "calcular_folha", "dia": 1, "hora": "25:00"}):
        try:
            rt.validar_rotina(ruim)
            assert False, f"deveria rejeitar {ruim}"
        except ValueError:
            pass


# ── folha no contas a pagar ──────────────────────────────────────────────────
def test_financeiro_da_folha_gera_titulos_sem_duplicar_e_baixa_em_lote():
    cid, h = _empresa_nova()
    _func(h, name="Ana Caixa", salary=4000)
    _func(h, name="Beto Caixa", salary=2500)
    run = _folha(h, "2026-10")

    prev = client.get(f"{U}/financeiro/{run}", headers=h)
    assert prev.status_code == 200, prev.text
    tit = {t["chave"].split("-", 1)[1]: t for t in prev.json()["titulos"]}
    assert {"LIQ", "FGTS", "INSS"} <= set(tit) and all(t["status"] == "nao_lancado" for t in tit.values())
    assert tit["LIQ"]["vencimento"] == "2026-11-06" and tit["FGTS"]["vencimento"] == "2026-11-20"

    g = client.post(f"{U}/financeiro/{run}/gerar", headers=h, json={})
    assert g.status_code == 201, g.text
    n = len(g.json()["criados"])
    again = client.post(f"{U}/financeiro/{run}/gerar", headers=h, json={}).json()
    assert again["criados"] == [] and again["ja_existiam"] == n

    situ = client.get(f"{U}/financeiro/{run}", headers=h).json()["titulos"]
    assert all(t["status"] == "pendente" and t["lancamento_id"] for t in situ)

    assert client.post(f"{U}/financeiro/{run}/baixar", headers=h, json={}).status_code == 422
    conn = get_conn()
    try:
        ba = conn.execute("SELECT id FROM bank_accounts WHERE company_id=? ORDER BY id LIMIT 1", (cid,)).fetchone()
        if not ba:
            ba_id = conn.execute("INSERT INTO bank_accounts (company_id, name, bank_name, active) VALUES (?, 'Conta Folha', 'Banco', 1)",
                                 (cid,)).lastrowid
            conn.commit()
        else:
            ba_id = ba["id"]
    finally:
        conn.close()
    pago = client.post(f"{U}/financeiro/{run}/baixar", headers=h,
                       json={"bank_account_id": ba_id, "payment_date": "2026-11-06"})
    assert pago.status_code == 200, pago.text
    assert all(t["status"] == "pago" for t in client.get(f"{U}/financeiro/{run}", headers=h).json()["titulos"])
    assert client.post(f"{U}/financeiro/{run}/baixar", headers=h, json={"bank_account_id": ba_id}).status_code == 400


def test_financeiro_por_funcionario_e_isolamento_entre_empresas():
    _, h = _empresa_nova()
    a = _func(h, name="Caio Lista", salary=3000)
    b = _func(h, name="Duda Lista", salary=3200)
    run = _folha(h, "2026-09")
    out = client.post(f"{U}/financeiro/{run}/gerar", headers=h, json={"por_funcionario": True}).json()
    chaves = {t["chave"] for t in out["criados"]}
    assert {f"DP{run}-LIQ-{a}", f"DP{run}-LIQ-{b}"} <= chaves and f"DP{run}-LIQ" not in chaves
    _, h2 = _empresa_nova()
    assert client.get(f"{U}/financeiro/{run}", headers=h2).status_code == 404
    assert client.post(f"{U}/financeiro/{run}/gerar", headers=h2, json={}).status_code == 404


# ── alteração em grupo ───────────────────────────────────────────────────────
def test_alteracao_em_grupo_de_salario_com_historico_e_piso():
    cid, h = _empresa_nova()
    a = _func(h, name="Eva Reajuste", salary=2000)
    b = _func(h, name="Fabio Reajuste", salary=5000)
    dados = {"campo": "salario", "modo": "percentual", "valor": 10, "employee_ids": [a, b]}
    prev = client.post(f"{U}/alteracao-grupo/previa", headers=h, json=dados).json()
    assert {l["nome"]: l["depois"] for l in prev["linhas"]} == {"Eva Reajuste": 2200.0, "Fabio Reajuste": 5500.0}
    assert any("S-2206" in av for av in prev["avisos"])
    # piso: novo salário de 3000 só para quem ganha menos
    r = client.post(f"{U}/alteracao-grupo/aplicar", headers=h,
                    json={"campo": "salario", "modo": "novo", "valor": 3000, "somente_abaixo": True,
                          "employee_ids": [a, b], "data_vigencia": "2026-11-01", "motivo": "Piso CCT"})
    assert r.status_code == 200, r.text
    assert r.json()["alterados"] == 1
    conn = get_conn()
    try:
        sal = {x["id"]: x["salary"] for x in conn.execute("SELECT id, salary FROM employees WHERE id IN (?,?)", (a, b))}
        hist = conn.execute("SELECT * FROM salary_history WHERE employee_id=? ORDER BY id DESC", (a,)).fetchone()
        assert conn.execute("SELECT COUNT(*) FROM salary_history WHERE employee_id=?", (b,)).fetchone()[0] == 0
    finally:
        conn.close()
    assert sal == {a: 3000.0, b: 5000.0}
    assert hist["salario_anterior"] == 2000 and hist["salario_novo"] == 3000 and hist["percentual"] == 50.0
    assert hist["motivo"] == "Piso CCT" and hist["data_vigencia"] == "2026-11-01"


def test_alteracao_em_grupo_validacoes_e_outros_campos():
    _, h = _empresa_nova()
    a = _func(h, name="Gil Setor")
    r = client.post(f"{U}/alteracao-grupo/aplicar", headers=h,
                    json={"campo": "department", "valor": "Expedição", "employee_ids": [a]})
    assert r.status_code == 200 and r.json()["alterados"] == 1
    emp = client.get(f"/api/dp/employees/{a}", headers=h).json()
    assert emp["department"] == "Expedição"
    for ruim, cod in (({"campo": "senha", "valor": 1, "employee_ids": [a]}, 422),
                      ({"campo": "role", "valor": "X", "employee_ids": []}, 422),
                      ({"campo": "horas_semana", "valor": 50, "employee_ids": [a]}, 422),
                      ({"campo": "salario", "modo": "novo", "valor": -1, "employee_ids": [a]}, 422),
                      ({"campo": "work_schedule_id", "valor": 999999, "employee_ids": [a]}, 404)):
        assert client.post(f"{U}/alteracao-grupo/previa", headers=h, json=ruim).status_code == cod, ruim
    _, h2 = _empresa_nova()          # funcionário de outra empresa
    assert client.post(f"{U}/alteracao-grupo/aplicar", headers=h2,
                       json={"campo": "role", "valor": "Invasor", "employee_ids": [a]}).status_code == 404


# ── exclusão em grupo ────────────────────────────────────────────────────────
def test_exclusao_em_grupo_de_ferias_respeita_competencia_fechada():
    cid, h = _empresa_nova()
    ids = []
    for nome in ("Hugo Férias", "Iara Férias"):
        eid = _func(h, name=nome)
        r = client.post("/api/dp/ferias", headers=h, json={"employee_id": eid, "data_inicio": "2025-03-02",
                                                         "dias_gozo": 30, "periodo_inicio": "2024-01-10"})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    lista = client.get(f"{U}/exclusao-grupo?tipo=ferias&inicio=2025-03-01&fim=2025-03-31", headers=h).json()
    assert {x["id"] for x in lista} == set(ids)
    conn = get_conn()
    try:
        comp = conn.execute("SELECT COALESCE(NULLIF(competencia,''), substr(data_inicio,1,7)) FROM payroll_special WHERE id=?",
                            (ids[1],)).fetchone()[0][:7]
        conn.execute("UPDATE payroll_special SET competencia='2024-12' WHERE id=?", (ids[1],))
        conn.execute("INSERT INTO payroll_competencias (company_id, competencia, status) VALUES (?, '2024-12', 'fechada')", (cid,))
        conn.commit()
    finally:
        conn.close()
    assert comp
    out = client.post(f"{U}/exclusao-grupo", headers=h, json={"tipo": "ferias", "ids": ids}).json()
    res = {r["id"]: r for r in out["resultado"]}
    assert out["excluidos"] == 1 and res[ids[0]]["ok"] and not res[ids[1]]["ok"] and "fechada" in res[ids[1]]["erro"]
    assert client.post(f"{U}/exclusao-grupo", headers=h, json={"tipo": "decimo_1", "ids": [ids[1]]}).json()["excluidos"] == 0
    assert client.get(f"{U}/exclusao-grupo?tipo=xx&inicio=2025-01-01&fim=2025-12-31", headers=h).status_code == 422


# ── acerto da data de pagamento ──────────────────────────────────────────────
def test_data_pagamento_muda_folha_e_vencimento_e_trava_s1210_aceito():
    cid, h = _empresa_nova()
    eid = _func(h, name="Joel Pagamento", salary=3000)
    run = _folha(h, "2026-08")
    client.post(f"{U}/financeiro/{run}/gerar", headers=h, json={})
    lista = client.get(f"{U}/data-pagamento?competencia=2026-08", headers=h).json()
    assert any(x["tipo"] == "folha" and x["id"] == run for x in lista)

    r = client.post(f"{U}/data-pagamento", headers=h, json={"nova_data": "2026-09-04", "itens": [{"tipo": "folha", "id": run}]})
    assert r.status_code == 200, r.text
    conn = get_conn()
    try:
        venc = conn.execute("""SELECT due_date FROM financial_entries WHERE origin_type='folha_dp' AND origin_id=?
                               AND document_number=?""", (run, f"DP{run}-LIQ")).fetchone()[0]
        fgts = conn.execute("""SELECT due_date FROM financial_entries WHERE origin_type='folha_dp' AND origin_id=?
                               AND document_number=?""", (run, f"DP{run}-FGTS")).fetchone()[0]
        # S-1210 aceito no mês do pagamento atual (setembro)
        conn.execute("""INSERT INTO esocial_eventos (company_id, tipo, grupo, referencia_tipo, referencia_id, per_apur, status)
                        VALUES (?, 'S-1210', 3, 'pagamento', ?, '2026-09', 'aceito')""", (cid, eid))
        conn.commit()
    finally:
        conn.close()
    assert str(venc)[:10] == "2026-09-04" and str(fgts)[:10] == "2026-09-18"     # guia não muda

    mover = {"nova_data": "2026-10-02", "itens": [{"tipo": "folha", "id": run}]}
    bloq = client.post(f"{U}/data-pagamento", headers=h, json=mover)
    assert bloq.status_code == 409 and "S-1210" in str(bloq.json())
    ok = client.post(f"{U}/data-pagamento", headers=h, json={**mover, "confirmar": True})
    assert ok.status_code == 200 and any("regime de caixa" in a for a in ok.json()["avisos"])
    # dentro do mesmo mês não pede confirmação
    assert client.post(f"{U}/data-pagamento", headers=h,
                       json={"nova_data": "2026-10-05", "itens": [{"tipo": "folha", "id": run}]}).status_code == 200
    assert client.post(f"{U}/data-pagamento", headers=h, json={"nova_data": "2026-10-05", "itens": []}).status_code == 422


# ── rotinas automáticas ──────────────────────────────────────────────────────
def test_rotinas_crud_execucao_e_cron(monkeypatch):
    cid, h = _empresa_nova()
    _func(h, name="Lia Rotina", salary=2800)
    r = client.post(f"{U}/rotinas", headers=h, json={"tipo": "calcular_folha", "dia": 25, "hora": "07:30"})
    assert r.status_code == 201, r.text
    rot = r.json()
    assert rot["competencia"] == "atual" and rot["proxima_execucao"]
    assert client.post(f"{U}/rotinas", headers=h, json={"tipo": "nada", "dia": 1}).status_code == 422

    # executa agora: calcula a folha do mês corrente; na 2ª vez é ignorada
    out = client.post(f"{U}/rotinas/{rot['id']}/executar", headers=h).json()
    assert out["status"] == "ok", out
    assert client.post(f"{U}/rotinas/{rot['id']}/executar", headers=h).json()["status"] == "ignorada"

    fin = client.post(f"{U}/rotinas", headers=h, json={"tipo": "gerar_financeiro", "dia": 1, "competencia": "atual"}).json()
    res = client.post(f"{U}/rotinas/{fin['id']}/executar", headers=h).json()
    assert res["status"] == "ok" and "título" in res["mensagem"]

    lista = client.get(f"{U}/rotinas", headers=h).json()
    assert len(lista["rotinas"]) == 2 and len(lista["execucoes"]) == 3
    assert client.put(f"{U}/rotinas/{fin['id']}", headers=h, json={"tipo": "gerar_financeiro", "dia": 3, "ativo": False}).json()["proxima_execucao"] == ""

    # executar-pendentes: só uma rodada ganha a rotina vencida
    conn = get_conn()
    try:
        conn.execute("UPDATE dp_rotinas SET proxima_execucao='2000-01-01T00:00' WHERE id=?", (rot["id"],))
        conn.commit()
    finally:
        conn.close()
    feitas = du.executar_pendentes(datetime(2001, 1, 10, 9, 0))
    assert [f["rotina_id"] for f in feitas if f["rotina_id"] == rot["id"]] == [rot["id"]]
    assert all(f["rotina_id"] != rot["id"] for f in du.executar_pendentes(datetime(2001, 1, 10, 9, 0)))

    monkeypatch.delenv("CORTEX_CRON_TOKEN", raising=False)
    assert client.post(f"{U}/rotinas/executar-pendentes").status_code == 403
    monkeypatch.setenv("CORTEX_CRON_TOKEN", "segredo")
    assert client.post(f"{U}/rotinas/executar-pendentes", headers={"X-Cron-Token": "errado"}).status_code == 403
    assert client.post(f"{U}/rotinas/executar-pendentes", headers={"X-Cron-Token": "segredo"}).status_code == 200

    _, h2 = _empresa_nova()
    assert client.delete(f"{U}/rotinas/{rot['id']}", headers=h2).status_code == 404
    assert client.delete(f"{U}/rotinas/{rot['id']}", headers=h).json() == {"ok": True}

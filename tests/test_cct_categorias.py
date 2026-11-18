"""Bloco 3 da paridade DP: regras da convenção coletiva (ATS, HE, data-base, médias) e categorias
especiais (horista, diarista, comissionado, professor)."""
from datetime import date

from backend.services import cct_regras as cr
from backend.services import payroll_engine as pe
from backend.services.payroll_tables import builtin_tables
from tests.test_complementar_escalas import EMP, _cpf, _empresa_nova, client

T2026 = builtin_tables("2026-03")

CCT = {"categoria": "Comércio", "sindicato_empregados": "Sindicato A", "sindicato_empregadores": "Sindicato B",
       "uf": "MT", "data_inicio": "2026-01-01", "data_fim": "2026-12-31", "piso_salarial": 2000.0,
       "adicional_hora_extra_pct": 60.0, "he_100_pct": 120.0, "adicional_noturno_pct": 25.0,
       "ats_tipo": "trienio", "ats_pct": 5.0, "ats_base": "salario", "ats_max_periodos": 0,
       "data_base_mes": 1, "media_meses": 6}


def _valor(res, codigo):
    return sum(l["valor"] for l in res["lines"] if l["codigo"] == codigo)


# ── Regras puras ─────────────────────────────────────────────────────────────
def test_percentuais_nunca_abaixo_da_lei():
    assert cr.percentuais(None) == (50.0, 100.0, 20.0)
    assert cr.percentuais({"adicional_hora_extra_pct": 40, "he_100_pct": 0, "adicional_noturno_pct": 10}) == (50.0, 100.0, 20.0)
    assert cr.percentuais(CCT) == (60.0, 120.0, 25.0)


def test_cct_do_funcionario_escolhida_ou_unica_vigente():
    a = {"id": 1, "data_inicio": "2026-01-01", "data_fim": "2026-12-31"}
    b = {"id": 2, "data_inicio": "2025-01-01", "data_fim": "2025-12-31"}
    em = date(2026, 6, 1)
    assert cr.cct_do_funcionario([a, b], {}, em) is a
    assert cr.cct_do_funcionario([a, b], {"cct_id": 2}, em) is b          # escolhida, mesmo vencida
    assert cr.cct_do_funcionario([a, {**a, "id": 3}], {}, em) is None      # duas vigentes: não adivinha


def test_salario_mensal_por_unidade_e_professor():
    assert cr.salario_mensal({"salary": 10, "tipo_salario": "1", "horas_semana": 44})[0] == 2200.0
    assert cr.salario_mensal({"salary": 100, "tipo_salario": "2"})[0] == 3000.0
    assert cr.salario_mensal({"salary": 700, "tipo_salario": "3"})[0] == 3000.0
    assert cr.salario_mensal({"salary": 1500, "tipo_salario": "4"})[0] == 3000.0
    assert cr.salario_mensal({"salary": 0, "tipo_salario": "7"})[0] == 0.0
    # 20 aulas × R$ 30 × 4,5 semanas = 2.700 + 1/6 de DSR = 3.150
    assert round(cr.salario_mensal({"salary": 30, "categoria_especial": "professor", "aulas_semanais": 20})[0], 2) == 3150.0


def test_adicional_tempo_servico():
    adm = date(2020, 3, 10)
    v, ref = cr.adicional_tempo_servico(CCT, adm, date(2026, 3, 9), 3000, 1518)
    assert v == 150.0 and ref.startswith("1 triênio")                    # 5 anos completos → 1 triênio
    v, _ = cr.adicional_tempo_servico(CCT, adm, date(2026, 3, 10), 3000, 1518)
    assert v == 300.0                                                     # 6 anos → 2 triênios
    assert cr.adicional_tempo_servico({**CCT, "ats_max_periodos": 1}, adm, date(2026, 3, 10), 3000, 1518)[0] == 150.0
    assert cr.adicional_tempo_servico({**CCT, "ats_base": "piso"}, adm, date(2026, 3, 10), 3000, 1518)[0] == 200.0
    assert cr.adicional_tempo_servico({**CCT, "ats_tipo": ""}, adm, date(2026, 3, 10), 3000, 1518)[0] == 0.0
    assert cr.adicional_tempo_servico(CCT, date(2025, 1, 1), date(2026, 6, 1), 3000, 1518)[0] == 0.0


def test_indenizacao_data_base_lei_7238_sumulas_182_e_314():
    assert cr.indenizacao_data_base(1, date(2026, 12, 15)) == date(2027, 1, 1)   # nos 30 dias anteriores
    assert cr.indenizacao_data_base(1, date(2027, 1, 1)) is None                 # alcançou a data-base (Súm. 314)
    assert cr.indenizacao_data_base(1, date(2026, 11, 20)) is None               # antes da janela
    assert cr.indenizacao_data_base(0, date(2026, 12, 15)) is None


def test_janela_de_media_da_convencao():
    assert cr.janela_media(None, "2026-01", "2026-12", 12) == ("2026-01", 12)
    assert cr.janela_media({"media_meses": 6}, "2026-01", "2026-12", 12) == ("2026-07", 6)
    assert cr.janela_media({"media_meses": 6}, "2026-01", "2026-03", 12) == ("2026-01", 6)


# ── Motor ────────────────────────────────────────────────────────────────────
def test_motor_ats_entra_no_valor_hora_e_percentuais_da_cct():
    base = dict(employee_id=1, nome="T", salario=2200.0, he50=10, he50_pct=60.0)
    res = pe.calculate_employee(pe.EmployeeInput(**base, ats_valor=220.0, ats_ref="1 triênio(s) × 10%"), T2026)
    assert _valor(res, "0015") == 220.0
    assert _valor(res, "0002") == round((2200 + 220) / 220 * 1.6 * 10, 2)   # 176,00


def test_motor_professor_separa_dsr():
    res = pe.calculate_employee(pe.EmployeeInput(employee_id=1, nome="P", salario=3150.0, categoria="professor"), T2026)
    assert _valor(res, "0001") == 2700.0 and _valor(res, "0019") == 450.0


def test_motor_comissoes_dsr_e_garantia_minima():
    lanc = [{"codigo": "0016", "quantidade": 0, "valor": 1000.0}]
    res = pe.calculate_employee(pe.EmployeeInput(employee_id=1, nome="C", salario=0.0, categoria="variavel",
                                                 lancamentos=lanc, dias_uteis=25, dias_dsr=5, piso=2000.0), T2026)
    assert _valor(res, "0016") == 1000.0
    assert _valor(res, "0017") == 200.0                                   # 1.000 / 25 × 5
    assert _valor(res, "0018") == 800.0                                   # completa até o piso de 2.000
    assert any("garantia mínima" in a for a in res["avisos"])


# ── API ──────────────────────────────────────────────────────────────────────
def test_api_cct_regras_gravadas_e_validacao():
    _, h = _empresa_nova()
    r = client.post("/api/conventions", headers=h, json=CCT)
    assert r.status_code == 200, r.text
    cct = next(c for c in client.get("/api/conventions/list", headers=h).json() if c["id"] == r.json()["id"])
    assert (cct["ats_tipo"], cct["ats_pct"], cct["he_100_pct"], cct["data_base_mes"], cct["media_meses"]) == \
        ("trienio", 5.0, 120.0, 1, 6)
    assert client.put(f"/api/conventions/{cct['id']}", headers=h, json={**CCT, "ats_pct": 3}).status_code == 200
    assert client.put("/api/conventions/999999", headers=h, json=CCT).status_code == 404
    assert client.post("/api/conventions", headers=h, json={**CCT, "ats_tipo": "decenio"}).status_code == 422

    # Convenção de outra empresa não pode ser vinculada
    _, h2 = _empresa_nova()
    r2 = client.post("/api/dp/employees", headers=h2, json={**EMP, "cpf": _cpf(), "cct_id": cct["id"]})
    assert r2.status_code == 422 and "Convenção" in r2.json()["detail"]


def test_api_salario_zero_e_professor_validados():
    _, h = _empresa_nova()
    assert client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf(), "salary": 0}).status_code == 422
    ok = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf(), "salary": 0, "tipo_salario": "7"})
    assert ok.status_code == 201, ok.text
    prof = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf(), "salary": 30,
                                                           "categoria_especial": "professor"})
    assert prof.status_code == 422 and "aulas" in prof.json()["detail"]


def test_api_folha_aplica_ats_e_professor():
    _, h = _empresa_nova()
    client.post("/api/conventions", headers=h, json=CCT)
    antigo = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf(), "admission_date": "2020-03-10"})
    prof = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf(), "salary": 30,
                                                           "categoria_especial": "professor", "aulas_semanais": 20})
    assert antigo.status_code == prof.status_code == 201
    calc = client.post("/api/dp/payroll/preview", headers=h, json={"competence": "2026-08"}).json()
    por_id = {r["employee_id"]: r for r in calc["results"]}
    r_antigo, r_prof = por_id[antigo.json()["id"]], por_id[prof.json()["id"]]
    assert _valor(r_antigo, "0015") == 300.0                              # 6 anos → 2 triênios × 5% de 3.000
    assert _valor(r_prof, "0001") == 2700.0 and _valor(r_prof, "0019") == 450.0


def test_api_rescisao_paga_indenizacao_da_data_base():
    _, h = _empresa_nova()
    client.post("/api/conventions", headers=h, json=CCT)                   # data-base em janeiro
    eid = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf(), "admission_date": "2025-06-02"}).json()["id"]
    # Dispensa em 25/11 com aviso indenizado de 33 dias → projeção 28/12: nos 30 dias antes de 01/01
    resc = client.post("/api/dp/rescisao", headers=h, json={
        "employee_id": eid, "data_desligamento": "2026-11-25", "tipo": "sem_justa_causa",
        "aviso_modo": "indenizado", "saldo_fgts": 0})
    assert resc.status_code in (200, 201), resc.text
    assert any(l["codigo"] == "0049" for l in resc.json()["lines"])

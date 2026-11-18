"""Bloco 4 — benefícios: VT por dias de uso, compra e recibo; plano de saúde por faixa etária com
dependentes e coparticipação; empréstimo consignado com margem, na folha e na rescisão."""
from datetime import date

from backend.database import get_conn
from backend.services import beneficios as bf
from backend.services import payroll_engine as pe
from backend.services.payroll_tables import builtin_tables
from tests.test_complementar_escalas import EMP, _cpf, _empresa_nova, client

B = "/api/dp/beneficios"


def _func(h, **extra):
    r = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf(), **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _linhas(h, emp_id, comp):
    hol = client.get(f"/api/dp/employees/{emp_id}/holerite-preview?competencia={comp}", headers=h)
    assert hol.status_code == 200, hol.text
    hol = hol.json()["holerite"]
    return {l["codigo"]: l for l in hol["lines"]}, hol


# ── regras puras ─────────────────────────────────────────────────────────────
def test_dias_uso_vt_exclui_ferias_afastamento_e_faltas():
    ini, fim = date(2026, 3, 1), date(2026, 3, 31)          # março/2026: 22 dias úteis
    assert bf.dias_uso_vt(ini, fim, set()) == 22
    assert bf.dias_uso_vt(ini, fim, {date(2026, 3, 2)}) == 21                                  # feriado numa segunda
    assert bf.dias_uso_vt(ini, fim, set(), periodos_fora=[(date(2026, 3, 16), date(2026, 3, 31))]) == 10
    assert bf.dias_uso_vt(ini, fim, set(), faltas={date(2026, 3, 3), date(2026, 3, 7)}) == 21  # sábado não conta
    assert bf.dias_uso_vt(ini, fim, set(), admissao=date(2026, 3, 23)) == 7
    assert bf.desconto_vt(3000, 400) == 180.0 and bf.desconto_vt(3000, 100) == 100.0


def test_mensalidade_por_faixa_etaria_e_rateio():
    faixas = [{"idade_min": a, "idade_max": b, "valor": v} for (a, b), v in
              zip(bf.FAIXAS_ANS, (100, 150, 180, 200, 220, 250, 300, 400, 500, 700))]
    plano = {"nome": "Ouro", "modalidade_valor": "faixa", "pct_empresa_titular": 80, "pct_empresa_dependente": 0}
    deps = [{"nome": "Filho", "data_nascimento": "2020-05-01"}, {"nome": "Sem data", "data_nascimento": ""}]
    m = bf.mensalidade_plano(plano, faixas, "1986-11-30", deps, date(2026, 11, 30))
    titular, filho, sem = m["vidas"]
    assert titular["idade"] == 40 and titular["valor"] == 250 and titular["empregado"] == 50.0
    assert filho["idade"] == 6 and filho["valor"] == 100 and filho["empregado"] == 100
    assert sem["valor"] == 0 and any("Sem data" in a for a in m["avisos"])
    assert m["empregado"] == 150.0 and m["empresa"] == 200.0
    # aniversário de 59 anos muda a faixa no mês em que acontece
    assert bf.mensalidade_plano(plano, faixas, "1967-11-15", [], date(2026, 11, 30))["vidas"][0]["valor"] == 700
    try:
        bf.validar_faixas([{"idade_min": 0, "idade_max": 20, "valor": 1}, {"idade_min": 18, "idade_max": 30, "valor": 1}])
        assert False, "faixas sobrepostas deveriam falhar"
    except ValueError as e:
        assert "sobrepõem" in str(e)


def test_consignado_parcelas_margem_e_saldo():
    c = {"competencia_inicio": "2026-09", "parcelas_total": 3, "valor_parcela": 200, "ativo": 1}
    assert bf.parcela_do_mes(c, "2026-08") == (0, 0.0)
    assert bf.parcela_do_mes(c, "2026-10") == (2, 200.0)
    assert bf.parcela_do_mes(c, "2026-12") == (0, 0.0)                   # passou da última
    assert bf.saldo_rescisao(c, "2026-10") == 400.0                      # parcelas 2 e 3
    assert bf.saldo_rescisao({**c, "saldo_devedor": 350}, "2026-10") == 350.0
    assert bf.margem(3000, 500, 35) == 875.0
    out, avisos = bf.aplicar_margem([{"nome": "A", "valor": 600}, {"nome": "B", "valor": 400}], 875)
    assert [p["valor"] for p in out] == [600, 275] and len(avisos) == 1


def test_motor_desconta_plano_copart_e_consignado_sem_mexer_nas_bases():
    t = builtin_tables("2026-10")
    base = pe.EmployeeInput(employee_id=1, nome="X", salario=3000, dependentes=0)
    sem = pe.calculate_employee(base, t)
    com = pe.calculate_employee(pe.EmployeeInput(
        employee_id=1, nome="X", salario=3000, dependentes=0,
        planos_saude=[{"nome": "Plano Ouro", "valor": 150, "ref": "2 vida(s)"}],
        copart=[{"nome": "Coparticipação — Ouro", "valor": 45.5}],
        consignados=[{"nome": "Consignado Banco", "valor": 5000, "origem": "credito_trabalhador", "ref": "1/24"}],
        consignado_pct=35), t)
    lin = {l["codigo"]: l for l in com["lines"]}
    assert lin["0111"]["valor"] == 150 and lin["0112"]["valor"] == 45.5
    assert com["inss"] == sem["inss"] and com["irrf"] == sem["irrf"] and com["fgts"] == sem["fgts"]
    margem = round((3000 - sem["inss"] - sem["irrf"]) * 0.35, 2)
    assert lin["0113"]["valor"] == margem                                # parcela limitada à margem
    assert any("margem" in a for a in com["avisos"])
    conv = pe.calculate_employee(pe.EmployeeInput(employee_id=1, nome="X", salario=3000, consignados=[
        {"nome": "Convênio", "valor": 100, "origem": "convenio"}]), t)
    assert {l["codigo"] for l in conv["lines"]} >= {"0114"}
    assert pe.SYSTEM_RUBRICS["PLANO_SAUDE"][6] == "9219" and pe.SYSTEM_RUBRICS["CONSIGNADO"][6] == "9253"
    assert pe.SYSTEM_RUBRICS["VA"][6] == "9299"


# ── API ──────────────────────────────────────────────────────────────────────
def test_api_vt_linhas_previa_compra_e_recibo():
    _, h = _empresa_nova()
    emp = _func(h, name="Vera Ônibus", admission_date="2025-01-10", salary=2000)
    _func(h, name="Sem Vale")
    r = client.post(f"{B}/vt/linhas", headers=h, json={"employee_id": emp, "descricao": "Linha 101", "tarifa": 5, "vales_dia": 2})
    assert r.status_code == 201, r.text
    assert client.post(f"{B}/vt/linhas", headers=h, json={"employee_id": emp, "tarifa": 0}).status_code == 422
    conn = get_conn()
    try:     # afastamento de 16 a 31/03 → só 10 dias úteis (2 a 13/03) de uso em março/2026
        conn.execute("""INSERT INTO employee_absences (company_id, employee_id, tipo, data_inicio, data_fim)
                        SELECT company_id, id, 'doenca', '2026-03-16', '2026-03-31' FROM employees WHERE id=?""", (emp,))
        conn.commit()
    finally:
        conn.close()
    prev = client.get(f"{B}/vt/linhas?competencia=2026-03", headers=h).json()["previa"]
    assert len(prev) == 1 and prev[0]["dias_uso"] == 10 and prev[0]["custo"] == 100.0
    assert prev[0]["desconto"] == 100.0                                  # 6% de 2000 = 120 > custo

    lin, _ = _linhas(h, emp, "2026-03")
    assert lin["0102"]["valor"] == 100.0                                 # a folha usa os mesmos dias

    html = client.get(f"{B}/vt/compra?competencia=2026-03", headers=h).text
    assert "Compra de vale-transporte" in html and "Linha 101" in html and "Sem Vale" not in html
    csv = client.get(f"{B}/vt/compra?competencia=2026-03&formato=csv", headers=h)
    assert csv.headers["content-type"].startswith("text/csv") and "20 vales" in csv.content.decode("utf-8-sig")
    rec = client.get(f"{B}/vt/recibo?competencia=2026-03&employee_id={emp}", headers=h).text
    assert "Recibo de entrega de vale-transporte" in rec and "Vera Ônibus" in rec and "03/2026" in rec


def test_api_plano_de_saude_adesao_dependentes_copart_e_folha():
    _, h = _empresa_nova()
    emp = _func(h, name="Paula Plano", birth_date="1986-04-20")
    dep = client.post(f"/api/dp/employees/{emp}/dependents", headers=h,
                      json={"nome": "Davi", "data_nascimento": "2018-02-01", "parentesco": "03", "plano_saude": 1})
    assert dep.status_code == 201, dep.text

    faixas = [{"idade_min": a, "idade_max": b, "valor": v} for (a, b), v in
              zip(bf.FAIXAS_ANS, (90, 120, 150, 180, 210, 260, 320, 420, 520, 750))]
    p = client.post(f"{B}/planos", headers=h, json={"nome": "Saúde Total", "operadora": "Operadora X", "registro_ans": "123456",
                                                     "pct_empresa_titular": 50, "pct_empresa_dependente": 0, "faixas": faixas})
    assert p.status_code == 201, p.text
    pid = p.json()["id"]
    padrao = client.post(f"{B}/planos", headers=h, json={"nome": "Sem faixas"}).json()
    assert len(padrao["faixas"]) == 10                                   # cria as 10 faixas da ANS zeradas
    assert client.post(f"{B}/planos", headers=h, json={"nome": "Ruim", "faixas": [
        {"idade_min": 0, "idade_max": 30, "valor": 1}, {"idade_min": 20, "idade_max": 40, "valor": 1}]}).status_code == 422

    ad = client.post(f"{B}/adesoes", headers=h, json={"employee_id": emp, "plano_id": pid, "data_inicio": "2026-01-01"})
    assert ad.status_code == 201, ad.text
    assert client.post(f"{B}/adesoes", headers=h, json={"employee_id": emp, "plano_id": pid,
                                                         "data_inicio": "2026-02-01"}).status_code == 400
    lista = client.get(f"{B}/adesoes?employee_id={emp}&competencia=2026-10", headers=h).json()
    assert lista[0]["total"] == 260 + 90 and lista[0]["empregado"] == 130 + 90      # titular 40 anos (39–43)

    cpf = client.get(f"/api/dp/employees/{emp}", headers=h).json()["cpf"]
    imp = client.post(f"{B}/copart/importar", headers=h, json={
        "plano_id": pid, "competencia": "2026-10",
        "texto": f"cpf;beneficiario;descricao;valor\n{cpf};Davi;Consulta pediatra;35,00\n00000000000;X;Y;10\n{cpf};Paula;Exame;sem"})
    assert imp.json()["importadas"] == 1 and len(imp.json()["erros"]) == 2

    lin, hol = _linhas(h, emp, "2026-10")
    assert lin["0111"]["valor"] == 220.0 and lin["0111"]["referencia"] == "2 vida(s)"
    assert lin["0112"]["valor"] == 35.0

    conf = client.get(f"{B}/planos/conferencia?competencia=2026-10&plano_id={pid}", headers=h).text
    assert "Conferência do plano de saúde" in conf and "Davi" in conf and "2 vida(s)" in conf
    assert client.delete(f"{B}/planos/{pid}", headers=h).status_code == 400   # tem adesão ativa


def test_api_consignado_folha_margem_rescisao_e_isolamento():
    _, h = _empresa_nova()
    emp = _func(h, name="Rui Crédito", admission_date="2025-01-06", salary=3000)
    c = client.post(f"{B}/consignados", headers=h, json={
        "employee_id": emp, "origem": "credito_trabalhador", "instituicao": "Banco Y", "contrato": "CT-1",
        "valor_parcela": 300, "parcelas_total": 10, "competencia_inicio": "2026-09"})
    assert c.status_code == 201, c.text
    assert client.post(f"{B}/consignados", headers=h, json={"employee_id": emp, "origem": "agiota", "valor_parcela": 1,
                                                             "parcelas_total": 1, "competencia_inicio": "2026-09"}).status_code == 422
    lista = client.get(f"{B}/consignados?employee_id={emp}&competencia=2026-10", headers=h).json()
    assert lista[0]["parcela_atual"] == 2 and lista[0]["valor_mes"] == 300

    lin, _ = _linhas(h, emp, "2026-10")
    assert lin["0113"]["valor"] == 300 and lin["0113"]["referencia"] == "2/10"

    assert client.get(f"{B}/consignados/margem/{emp}", headers=h).status_code == 400   # sem folha ainda
    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-10"}).status_code in (200, 201)
    m = client.get(f"{B}/consignados/margem/{emp}", headers=h).json()
    assert m["margem_utilizada"] == 300 and m["percentual"] == 35
    assert m["margem_disponivel"] == round(m["margem_total"] - 300, 2)

    resc = client.post("/api/dp/rescisao/preview", headers=h, json={
        "employee_id": emp, "data_desligamento": "2026-11-20", "tipo": "sem_justa_causa", "saldo_fgts": 3000})
    assert resc.status_code == 200, resc.text
    r = resc.json()
    cons = [l for l in r["lines"] if l["codigo"] == "0113"]
    assert cons and cons[0]["valor"] <= 300 * 9                         # parcelas 3 a 10 + a de novembro
    assert any("consignado" in a.lower() for a in r["avisos"])

    _, h2 = _empresa_nova()                                              # outra empresa não enxerga
    assert client.get(f"{B}/consignados", headers=h2).json() == []
    assert client.put(f"{B}/consignados/{c.json()['id']}", headers=h2, json={"valor_parcela": 1}).status_code == 404


def test_parametro_margem_consignavel():
    _, h = _empresa_nova()
    assert client.put("/api/dp/parametros", headers=h, json={"consignado_margem_pct": 150}).status_code in (400, 422)
    r = client.put("/api/dp/parametros", headers=h, json={"consignado_margem_pct": 30})
    assert r.status_code == 200 and r.json()["parametros"]["consignado_margem_pct"] == 30

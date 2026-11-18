"""Conferência folha × eSocial (totalizadores S-5001, S-5002 e S-5003) por trabalhador."""
from backend.database import get_conn
from backend.services.esocial import conferencia as cf
from tests.test_complementar_escalas import EMP, _cpf, _empresa_nova, client

NS = {"S-5001": "evtBasesTrab", "S-5002": "evtIrrfBenef", "S-5003": "evtBasesFGTS"}


def _xml(tipo, corpo):
    ev = NS[tipo]
    return (f'<eSocial xmlns="http://www.esocial.gov.br/schema/evt/{ev}/v_S_01_03_00"><{ev} Id="ID1">'
            f'{corpo}</{ev}></eSocial>')


def s5001(cpf, per, base, inss, base13=0.0, desc=None):
    b13 = f"<infoBaseCS><ind13>1</ind13><tpValor>11</tpValor><valor>{base13:.2f}</valor></infoBaseCS>" if base13 else ""
    return _xml("S-5001", f"""<ideEvento><nrRecArqBase>1.1.1</nrRecArqBase><indApuracao>1</indApuracao><perApur>{per}</perApur></ideEvento>
      <ideTrabalhador><cpfTrab>{cpf}</cpfTrab></ideTrabalhador>
      <infoCpCalc><tpCR>108201</tpCR><vrCpSeg>{inss:.2f}</vrCpSeg><vrDescSeg>{(desc if desc is not None else inss):.2f}</vrDescSeg></infoCpCalc>
      <infoCpCalc><tpCR>160601</tpCR><vrCpSeg>99.00</vrCpSeg><vrDescSeg>99.00</vrDescSeg></infoCpCalc>
      <infoCp><classTrib>99</classTrib><ideEstabLot><infoCategIncid><codCateg>101</codCateg>
        <infoBaseCS><ind13>0</ind13><tpValor>11</tpValor><valor>{base:.2f}</valor></infoBaseCS>
        <infoBaseCS><ind13>0</ind13><tpValor>15</tpValor><valor>777.00</valor></infoBaseCS>{b13}
        <infoBaseCS><ind13>0</ind13><tpValor>31</tpValor><valor>50.00</valor></infoBaseCS>
      </infoCategIncid></ideEstabLot></infoCp>""")


def s5002(cpf, per, irrf):
    return _xml("S-5002", f"""<ideEvento><nrRecArqBase>1.1.2</nrRecArqBase><perApur>{per}</perApur></ideEvento>
      <ideTrabalhador><cpfBenef>{cpf}</cpfBenef><dmDev><perRef>{per}</perRef><ideDmDev>X</ideDmDev><tpPgto>1</tpPgto>
        <dtPgto>{per}-05</dtPgto><codCateg>101</codCateg>
        <totApurMen><CRMen>056107</CRMen><vlrRendTrib>3000.00</vlrRendTrib><vlrRendTrib13>0</vlrRendTrib13>
          <vlrPrevOficial>0</vlrPrevOficial><vlrPrevOficial13>0</vlrPrevOficial13><vlrCRMen>{irrf:.2f}</vlrCRMen>
          <vlrCR13Men>0</vlrCR13Men></totApurMen></dmDev>
        <totInfoIR><consolidApurMen><CRMen>056107</CRMen><vlrCRMen>{irrf:.2f}</vlrCRMen></consolidApurMen></totInfoIR>
      </ideTrabalhador>""")


def s5003(cpf, per, base, fgts):
    return _xml("S-5003", f"""<ideEvento><nrRecArqBase>1.1.3</nrRecArqBase><indApuracao>1</indApuracao><perApur>{per}</perApur></ideEvento>
      <ideTrabalhador><cpfTrab>{cpf}</cpfTrab></ideTrabalhador>
      <infoFGTS><ideEstab><ideLotacao><infoTrabFGTS><codCateg>101</codCateg><infoBaseFGTS>
        <basePerApur><tpValor>11</tpValor><indIncid>1</indIncid><remFGTS>{base:.2f}</remFGTS><dpsFGTS>{fgts:.2f}</dpsFGTS></basePerApur>
        <basePerApur><tpValor>11</tpValor><indIncid>9</indIncid><remFGTS>500.00</remFGTS><dpsFGTS>40.00</dpsFGTS></basePerApur>
      </infoBaseFGTS></infoTrabFGTS></ideLotacao></ideEstab></infoFGTS>""")


def _tot(conn, cid, tipo, per, xml, status_origem="aceito"):
    ev = conn.execute("""INSERT INTO esocial_eventos (company_id, tipo, grupo, per_apur, status)
                         VALUES (?, 'S-1200', 3, ?, ?)""", (cid, per, status_origem)).lastrowid
    conn.execute("INSERT INTO esocial_totalizadores (company_id, evento_origem_id, tipo, per_apur, xml) VALUES (?,?,?,?,?)",
                 (cid, ev, tipo, per, xml))


def test_leitura_dos_totalizadores_ignora_consignado_exclusivas_do_empregador_e_suspensos():
    a = cf.ler_s5001(s5001("12345678909", "2026-08", 3000, 253.41, base13=1500))
    assert a == {"cpf": "12345678909", "per_apur": "2026-08", "base_inss": 3000.0, "base_inss_13": 1500.0,
                 "inss_calculado": 253.41, "inss_descontado": 253.41, "sal_familia": 50.0, "sal_maternidade": 0.0}
    b = cf.ler_s5002(s5002("123.456.789-09", "2026-09", 87.5))
    assert b["cpf"] == "12345678909" and b["irrf"] == 87.5            # sem somar o consolidApurMen de novo
    c = cf.ler_s5003(s5003("12345678909", "2026-08", 3000, 240))
    assert c["base_fgts"] == 3000.0 and c["fgts"] == 240.0           # indIncid 9 (suspenso) fora
    assert cf.ler_s5001("<lixo") is None


def test_conferencia_aponta_divergencia_falta_e_ignora_retificados():
    cid, h = _empresa_nova()
    ids = {}
    for nome, sal in (("Ana Confere", 3000), ("Bia Diverge", 4500), ("Caio Falta", 2500)):
        cpf = _cpf()
        r = client.post("/api/dp/employees", headers=h, json={**EMP, "name": nome, "cpf": cpf, "salary": sal})
        assert r.status_code in (200, 201), r.text
        ids[nome] = cpf
    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-08"}).status_code == 201
    conn = get_conn()
    try:
        conn.execute("UPDATE payroll_runs SET data_pagamento='2026-08-31' WHERE company_id=? AND competence='2026-08'", (cid,))
        conn.commit()
        folha = cf.folha_por_cpf(conn, cid, "2026-08")
        a, b = folha[ids["Ana Confere"]], folha[ids["Bia Diverge"]]
        assert a["base_inss"] == 3000 and a["base_fgts"] == 3000 and a["fgts"] == 240 and a["inss"] > 0
        _tot(conn, cid, "S-5001", "2026-08", s5001(ids["Ana Confere"], "2026-08", a["base_inss"], a["inss"]))
        _tot(conn, cid, "S-5002", "2026-08", s5002(ids["Ana Confere"], "2026-08", a["irrf"]))
        _tot(conn, cid, "S-5003", "2026-08", s5003(ids["Ana Confere"], "2026-08", a["base_fgts"], a["fgts"]))
        # Bia: o totalizador antigo (retificado) estava certo; o válido tem base de INSS maior
        _tot(conn, cid, "S-5001", "2026-08", s5001(ids["Bia Diverge"], "2026-08", b["base_inss"], b["inss"]), "substituido")
        _tot(conn, cid, "S-5001", "2026-08", s5001(ids["Bia Diverge"], "2026-08", b["base_inss"] + 200, b["inss"] + 15))
        _tot(conn, cid, "S-5002", "2026-08", s5002(ids["Bia Diverge"], "2026-08", b["irrf"]))
        _tot(conn, cid, "S-5003", "2026-08", s5003(ids["Bia Diverge"], "2026-08", b["base_fgts"], b["fgts"]))
        # alguém que só está no eSocial
        _tot(conn, cid, "S-5003", "2026-08", s5003("52998224725", "2026-08", 1000, 80))
        conn.commit()
    finally:
        conn.close()

    r = client.get("/api/esocial/conferencia/2026-08", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    por_cpf = {l["cpf"]: l for l in d["linhas"]}
    assert por_cpf[ids["Ana Confere"]]["situacao"] == "ok"
    bia = por_cpf[ids["Bia Diverge"]]
    assert bia["situacao"] == "divergente"
    assert {x["item"] for x in bia["divergencias"]} == {"base_inss", "inss"}
    assert next(x for x in bia["divergencias"] if x["item"] == "base_inss")["diferenca"] == 200.0
    caio = por_cpf[ids["Caio Falta"]]
    assert caio["situacao"] == "sem_totalizador" and set(caio["faltando"]) >= {"S-5001", "S-5003"}
    assert por_cpf["52998224725"]["situacao"] == "so_esocial"
    assert d["linhas"][0]["situacao"] == "divergente" and d["pode_fechar"] is False
    assert d["contagem"] == {"divergente": 1, "so_esocial": 1, "sem_totalizador": 1, "ok": 1}
    assert d["consolidados"] == {"S-5011": False, "S-5012": False, "S-5013": False}

    csv = client.get("/api/esocial/conferencia/2026-08?formato=csv", headers=h)
    texto = csv.content.decode("utf-8-sig")
    assert csv.headers["content-type"].startswith("text/csv") and "Bia Diverge" in texto and "Divergente" in texto

    assert client.get("/api/esocial/conferencia/2026-13", headers=h).status_code == 400
    _, h2 = _empresa_nova()                      # outra empresa não vê nada
    assert client.get("/api/esocial/conferencia/2026-08", headers=h2).json()["linhas"] == []


def test_conferencia_inclui_rescisao_e_irrf_pelo_mes_do_pagamento():
    cid, h = _empresa_nova()
    cpf = _cpf()
    r = client.post("/api/dp/employees", headers=h, json={**EMP, "name": "Davi Pago Depois", "cpf": cpf, "salary": 8000})
    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-07"}).status_code == 201
    conn = get_conn()
    try:
        conn.execute("UPDATE payroll_runs SET data_pagamento='2026-08-05' WHERE company_id=?", (cid,))
        conn.commit()
        julho, agosto = cf.folha_por_cpf(conn, cid, "2026-07"), cf.folha_por_cpf(conn, cid, "2026-08")
    finally:
        conn.close()
    assert julho[cpf]["irrf"] == 0 and julho[cpf]["base_inss"] == 8000     # INSS/FGTS na competência
    assert agosto[cpf]["irrf"] > 0 and agosto[cpf]["base_inss"] == 0       # IRRF no mês do pagamento
    d = client.get("/api/esocial/conferencia/2026-08", headers=h).json()
    lin = d["linhas"][0]
    assert set(lin["valores"]) == {"irrf"} and lin["faltando"] == ["S-5002"]
    anual = client.get("/api/esocial/conferencia/2026", headers=h).json()
    assert all(i["totalizador"] != "S-5002" for i in anual["itens"])

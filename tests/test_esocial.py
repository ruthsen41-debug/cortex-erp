"""Central do eSocial (S-1.3): eventos válidos no XSD oficial, assinatura, lote e fluxo de transmissão
com o webservice simulado (sem certificado real)."""
import random
import sys
import uuid
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.database import get_conn  # noqa: E402
from backend.main import app  # noqa: E402
from backend.services.esocial import assinatura as asg  # noqa: E402
from backend.services.esocial import comunicacao as com  # noqa: E402
from backend.services.esocial import eventos as ev  # noqa: E402
from backend.services.esocial import servico, tabelas  # noqa: E402
from backend.services.esocial import validacao as val  # noqa: E402

client = TestClient(app)

CO = {"cnpj": "45.123.789/0001-90", "cnae_principal": "6201501"}
CFG = {"class_trib": "01", "fpas": "515", "ini_valid": "2026-11"}
EMP = {"cpf": "52998224725", "name": "Joana Teste", "sexo": "F", "birth_date": "1995-08-20", "raca_cor": "3",
       "estado_civil": "1", "grau_instrucao": "07", "logradouro": "Rua Teste", "numero": "10", "bairro": "Centro",
       "cep": "78200-000", "cod_municipio": "5102504", "uf": "MT", "admission_date": "2026-11-03",
       "sindicato_cnpj": "12.345.678/0001-95", "matricula": "MAT-001", "role": "Assistente", "cbo": "411010",
       "salary": 2800, "tipo_salario": "5", "tipo_contrato": "experiencia", "experiencia_dias": 45,
       "experiencia_prorrogacao": 45, "horas_semana": 44, "horario_entrada": "08:00", "horario_saida": "18:00",
       "intervalo_inicio": "12:00", "intervalo_fim": "14:00", "celular": "65999990000", "email": "j@x.com"}
DEPS = [{"nome": "Lucas", "data_nascimento": "2019-03-10", "parentesco": "03", "irrf": 1, "salario_familia": 1}]
LINHAS = [{"codigo": "0001", "tipo": "provento", "referencia": "30d", "valor": 2800},
          {"codigo": "0100", "tipo": "desconto", "referencia": "tabela", "valor": 227.69},
          {"codigo": "0201", "tipo": "informativo", "valor": 2800}]

CASOS = {
    "S-1000": lambda: ev.s1000(CO, CFG, 2),
    "S-1005": lambda: ev.s1005(CO, CFG, 2),
    "S-1010": lambda: ev.s1010(CO, CFG, 2, {"codigo": "0001", "nome": "Salário Base", "tipo": "provento"}),
    "S-1020": lambda: ev.s1020(CO, CFG, 2),
    "S-2200": lambda: ev.s2200(CO, CFG, 2, EMP, DEPS),
    "S-2205": lambda: ev.s2205(CO, CFG, 2, EMP, DEPS, "2026-11-10"),
    "S-2206": lambda: ev.s2206(CO, CFG, 2, EMP, "2026-11-10"),
    "S-2230": lambda: ev.s2230(CO, CFG, 2, EMP, "03", "2026-11-05", "2026-11-30"),
    "S-2299": lambda: ev.s2299(CO, CFG, 2, EMP, "02", "2026-11-28", LINHAS),
    "S-1200": lambda: ev.s1200(CO, CFG, 2, {"cpf": EMP["cpf"]}, "2026-11", [
        {"ide_dm_dev": "FOL202611R1", "cod_categ": "101", "matricula": "MAT-001", "linhas": LINHAS},
        {"ide_dm_dev": "FER12", "cod_categ": "101", "matricula": "MAT-001",
         "linhas": [{"codigo": "0008", "tipo": "provento", "valor": 1000}]}]),
    "S-1200-13": lambda: ev.s1200(CO, CFG, 2, {"cpf": EMP["cpf"]}, "2026", [
        {"ide_dm_dev": "D13X7", "cod_categ": "101", "matricula": "MAT-001",
         "linhas": [{"codigo": "0010", "tipo": "provento", "valor": 2800}, {"codigo": "0120", "tipo": "desconto", "valor": 1400}]}],
        ind_apuracao="2"),
    "S-1200-RPA": lambda: ev.s1200(CO, CFG, 2, {"cpf": "11144477735", "nome": "Autônomo Teste", "dt_nasc": "1980-01-01",
                                                "cbo": "317110", "sem_cadastro": True}, "2026-11", [
        {"ide_dm_dev": "RPA3", "cod_categ": "701", "linhas": [{"codigo": "0060", "tipo": "provento", "valor": 1500},
                                                              {"codigo": "0100", "tipo": "desconto", "valor": 165}]}]),
    "S-2210": lambda: ev.s2210(CO, CFG, 2, EMP, {
        "data_acidente": "2026-11-10", "hora_acidente": "09:30", "hrs_trab_antes": "0130", "tp_acid": "1",
        "cod_sit_geradora": "200004300", "cod_parte_ating": "753030000", "lateralidade": "0",
        "cod_agnt_causador": "302010200", "cod_natureza_lesao": "702000000", "dt_atendimento": "2026-11-10",
        "hr_atendimento": "10:15", "cod_cid": "S06.0", "nm_emit": "Dr. Fulano", "nr_oc": "12345", "uf_oc": "MT",
        "houve_afastamento": 1, "dias_afastamento": 3, "tp_local": "4", "local_logradouro": "Av. Brasil",
        "local_numero": "100", "local_cep": "78200-000", "local_cod_municipio": "5102504", "local_uf": "MT"}),
    "S-2220": lambda: ev.s2220(CO, CFG, 2, EMP, {"tipo": "admissional", "data_exame": "2026-11-01", "resultado": "apto",
                                                "medico": "Dra. Beltrana", "crm_medico": "9876", "crm_uf": "MT",
                                                "procedimentos": [{"cod": "0295"}, {"cod": "0281", "ord": "1"}]},
                               {"nome": "Dr. Coordenador", "crm": "5555", "uf": "MT"}),
    "S-2240": lambda: ev.s2240(CO, CFG, 2, EMP, {"dt_inicio": "2026-11-03", "dsc_setor": "Administrativo",
                                                "dsc_ativ": "Atividades de escritório", "resp_cpf": "52998224725",
                                                "agentes": [{"cod": "09.01.001"}]}),
    "S-2240-ruido": lambda: ev.s2240(CO, CFG, 2, EMP, {
        "dt_inicio": "2026-11-03", "dsc_setor": "Produção", "dsc_ativ": "Operação de prensa", "resp_cpf": "52998224725",
        "resp_ide_oc": "4", "resp_nr_oc": "123456", "resp_uf_oc": "MT",
        "agentes": [{"cod": "02.01.001", "tp_aval": "1", "int_conc": "88", "lim_tol": "85", "un_med": "11",
                     "tec_medicao": "NHO 01", "utiliz_epc": "1", "utiliz_epi": "2", "ca_epi": "CA 12345"}]}),
    "S-2298": lambda: ev.s2298(CO, CFG, 2, EMP, {"data_reintegracao": "2026-11-10", "nr_processo": "00012345620265230001"}),
    "S-2300": lambda: ev.s2300(CO, CFG, 2, {
        "id": 4, "cpf": "11144477735", "nome": "Estagiária Teste", "sexo": "F", "raca_cor": "1", "grau_instrucao": "08",
        "data_nascimento": "2004-05-05", "data_inicio": "2026-11-03", "data_fim": "2027-11-02", "logradouro": "Rua A",
        "numero": "1", "cep": "78200-000", "cod_municipio": "5102504", "uf": "MT", "nivel_esocial": "4",
        "cnpj_inst_ensino": "33.683.111/0001-07", "curso": "Administração", "bolsa_auxilio": 1200,
        "cpf_supervisor": "52998224725", "email": "e@x.com"}),
    "S-2399": lambda: ev.s2399(CO, CFG, 2, {"id": 4, "cpf": "11144477735"}, "2026-12-20"),
    "S-1210": lambda: ev.s1210(CO, CFG, 2, EMP, "2026-11", [{"dt_pgto": "2026-11-30", "tp_pgto": "1",
                                                            "per_ref": "2026-11", "ide_dm_dev": "FOL202611R1",
                                                            "vr_liq": 2572.31}]),
    "S-1298": lambda: ev.s1298(CO, CFG, 2, "2026-11"),
    "S-1299": lambda: ev.s1299(CO, CFG, 2, "2026-11", True, True),
    "S-3000": lambda: ev.s3000(CO, CFG, 2, "S-1200", "1.1.0000000000000000001", per_apur="2026-11"),
}


@pytest.mark.parametrize("hoje", ["2026-11-17", "2026-11-25"])
@pytest.mark.parametrize("tipo", sorted(CASOS))
def test_evento_valido_no_xsd_oficial(tipo, hoje):
    key, cert = asg.certificado_teste()
    vigente = lambda h=hoje: tabelas.pacote_vigente(h)  # noqa: E731
    with mock.patch.object(ev, "pacote_vigente", vigente), mock.patch.object(val, "pacote_vigente", vigente):
        ev_id, xml = CASOS[tipo]()
        evento = tipo[:6]
        assinado = asg.assinar(xml, key, cert)
        assert val.validar_evento(assinado, evento) == []
    assert len(ev_id) == 36 and ev_id.startswith("ID145123789000000")
    assert f"/{tabelas.EVENTOS[evento][0]}/v_S_01_03_00" in xml


def test_assinatura_confere_e_detecta_alteracao():
    key, cert = asg.certificado_teste()
    _id, xml = CASOS["S-2200"]()
    assinado = asg.assinar(xml, key, cert)
    assert asg.verificar(assinado)[0]
    adulterado = assinado.replace("2800.00", "9800.00")
    ok, msg = asg.verificar(adulterado)
    assert not ok and "digest" in msg


def test_dados_incompletos_listam_o_que_falta():
    with pytest.raises(ev.DadosIncompletos) as exc:
        ev.s2200(CO, CFG, 2, {**EMP, "sindicato_cnpj": "", "cod_municipio": "", "raca_cor": "6"}, [])
    texto = " ".join(exc.value.problemas)
    assert "sindicato" in texto and "IBGE" in texto and "Raça/cor" in texto


def test_rubrica_padrao_tem_natureza_e_incidencias_oficiais():
    assert tabelas.rubrica_esocial("0100", "desconto", 0, 0, 0) == ("9201", "2", "31", "41", "00")
    assert tabelas.rubrica_esocial("0001", "provento", 1, 1, 1)[0] == "1000"
    assert tabelas.rubrica_esocial("9999", "provento", 1, 0, 1) == ("1299", "1", "11", "79", "11")


def test_lote_valido_e_retornos_lidos():
    key, cert = asg.certificado_teste()
    eventos = []
    for t in ("S-2200", "S-2230"):
        i, x = CASOS[t]()
        eventos.append({"id": i, "xml": asg.assinar(x, key, cert)})
    lote = com.montar_lote(2, "45123789", {"tp_insc": "1", "nr_insc": "45123789000190"}, eventos)
    assert val.validar_lote(lote) == []
    env = com.envelope(com.WS_ENVIO, "EnviarLoteEventos", "loteEventos", lote).decode()
    assert "EnviarLoteEventos" in env and "envioLoteEventos" in env

    r = com.ler_retorno_envio(_soap_envio("201", "1.2.202611.0000000000123"))
    assert r["cd_resposta"] == "201" and r["protocolo"] == "1.2.202611.0000000000123"
    p = com.ler_retorno_processamento(_soap_proc([(eventos[0]["id"], "201", "1.1.0000000000000000077", [])]))
    assert p["eventos"][0]["nr_recibo"] == "1.1.0000000000000000077"


# ─── webservice simulado ──────────────────────────────────────────────────────

def _soap(resultado: str, conteudo: str) -> bytes:
    return (f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
            f'<{resultado}Response xmlns="urn:x"><{resultado}Result>{conteudo}</{resultado}Result>'
            f'</{resultado}Response></s:Body></s:Envelope>').encode()


def _soap_envio(cd: str, protocolo: str) -> bytes:
    return _soap("EnviarLoteEventos", f"""
<eSocial xmlns="http://www.esocial.gov.br/schema/lote/eventos/envio/retornoEnvio/v1_1_0">
 <retornoEnvioLoteEventos><ideEmpregador><tpInsc>1</tpInsc><nrInsc>45123789</nrInsc></ideEmpregador>
  <ideTransmissor><tpInsc>1</tpInsc><nrInsc>45123789000190</nrInsc></ideTransmissor>
  <status><cdResposta>{cd}</cdResposta><descResposta>Lote recebido</descResposta></status>
  <dadosRecepcaoLote><dhRecepcao>2026-11-17T10:00:00</dhRecepcao><versaoAplicativoRecepcao>1</versaoAplicativoRecepcao>
  <protocoloEnvio>{protocolo}</protocoloEnvio></dadosRecepcaoLote></retornoEnvioLoteEventos></eSocial>""")


def _soap_proc(itens) -> bytes:
    evs = ""
    for ev_id, cd, recibo, ocorr in itens:
        oc = "".join(f"<ocorrencia><tipo>1</tipo><codigo>{c}</codigo><descricao>{d}</descricao>"
                     f"<localizacao>x</localizacao></ocorrencia>" for c, d in ocorr)
        rec = f"<recibo><nrRecibo>{recibo}</nrRecibo><hash>h</hash></recibo>" if recibo else ""
        evs += f"""<evento Id="{ev_id}"><retornoEvento>
 <eSocial xmlns="http://www.esocial.gov.br/schema/evt/retornoEvento/v1_3_0"><retornoEvento Id="{ev_id}">
  <processamento><cdResposta>{cd}</cdResposta><descResposta>ok</descResposta>
   <ocorrencias>{oc}</ocorrencias></processamento>{rec}</retornoEvento></eSocial></retornoEvento>
 <tot tipo="S5001"><eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtBasesTrab/v_S_01_03_00"/></tot></evento>"""
    return _soap("ConsultarLoteEventos", f"""
<eSocial xmlns="http://www.esocial.gov.br/schema/lote/eventos/envio/retornoProcessamento/v1_3_0">
 <retornoProcessamentoLoteEventos><status><cdResposta>201</cdResposta><descResposta>Processado</descResposta></status>
  <retornoEventos>{evs}</retornoEventos></retornoProcessamentoLoteEventos></eSocial>""")


def _cpf():
    n = [random.randint(0, 9) for _ in range(9)]
    for t in (9, 10):
        n.append((sum(n[i] * (t + 1 - i) for i in range(t)) * 10 % 11) % 10)
    return "".join(map(str, n))


def _empresa_nova():
    admin = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"}).json()
    h_admin = {"Authorization": f"Bearer {admin['access_token']}"}
    email = f"esoc_{uuid.uuid4().hex[:8]}@teste.com.br"
    cid = client.post("/api/auth/register-company", json={
        "company_name": "Empresa eSocial", "admin_name": "Dono", "email": email,
        "password": "senha123"}).json()["company"]["id"]
    client.post(f"/api/superadmin/companies/{cid}/approve", headers=h_admin)
    conn = get_conn()
    conn.execute("UPDATE companies SET cnpj = ?, cnae_principal = ?, regime_tributario = 'simples_nacional' WHERE id = ?",
                 ("45.123.789/0001-90", "6201501", cid))
    conn.commit()
    conn.close()
    tok = client.post("/api/auth/login", json={"email": email, "password": "senha123"}).json()["access_token"]
    return cid, {"Authorization": f"Bearer {tok}"}


def test_fluxo_completo_gerar_transmitir_consultar_excluir():
    cid, h = _empresa_nova()
    cfg = client.get("/api/esocial/config", headers=h).json()
    assert cfg["config"]["class_trib"] == "01" and cfg["config"]["ambiente"] == 2
    assert not cfg["certificado"]["ok"]

    tabs = client.post("/api/esocial/gerar/tabelas", headers=h).json()["eventos"]
    assert {e["tipo"] for e in tabs} >= {"S-1000", "S-1005", "S-1020", "S-1010"}
    assert all(e["status"] == "pendente" for e in tabs), [e for e in tabs if e["status"] != "pendente"]

    dados = {k: v for k, v in EMP.items() if k not in ("matricula",)}
    emp = client.post("/api/dp/employees", headers=h, json={**dados, "cpf": _cpf()}).json()
    incompleto = client.post("/api/dp/employees", headers=h, json={
        "name": "Sem Dados", "cpf": _cpf(), "admission_date": "2026-11-03", "role": "Aux", "salary": 2000}).json()
    adm = client.post(f"/api/esocial/gerar/admissao/{emp['id']}", headers=h).json()["eventos"][0]
    assert adm["status"] == "pendente", adm["erros"]
    ruim = client.post(f"/api/esocial/gerar/admissao/{incompleto['id']}", headers=h).json()["eventos"][0]
    assert ruim["status"] == "erro_validacao" and any("sindicato" in e for e in ruim["erros"])

    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-11"}).status_code == 201
    run_id = client.get("/api/dp/payroll", headers=h).json()[0]["id"]
    folha = client.post(f"/api/esocial/gerar/folha/{run_id}", headers=h,
                        json={"data_pagamento": "2026-11-30"}).json()["eventos"]
    assert {"S-1200", "S-1210"} <= {e["tipo"] for e in folha}

    # Sem certificado A1 a transmissão é recusada com orientação
    r = client.post("/api/esocial/transmitir", headers=h, json={})
    assert r.status_code == 412 and "certificado" in r.json()["detail"].lower()

    # Com certificado (de teste) e webservice simulado
    chamadas, rejeitou = [], []

    def transporte(url, action, corpo, ctx, timeout):
        chamadas.append(url)
        if action == com.ACTION_ENVIO:
            return _soap_envio("201", f"1.2.202611.{len(chamadas):013d}")
        protocolo = corpo.decode().split("<protocoloEnvio>")[1].split("<")[0]
        conn2 = get_conn()
        ids = [dict(x)["evento_id"] for x in conn2.execute(
            """SELECT e.evento_id FROM esocial_eventos e JOIN esocial_lotes lo ON lo.id = e.lote_id
               WHERE e.company_id = ? AND e.status = 'enviado' AND lo.protocolo = ?""", (cid, protocolo)).fetchall()]
        conn2.close()
        itens = [(i, "201", f"1.1.{abs(hash(i)) % 10**19:019d}", []) for i in ids]
        if itens and not rejeitou:  # um evento rejeitado (só na 1ª consulta) para conferir as ocorrências
            rejeitou.append(True)
            itens[-1] = (itens[-1][0], "401", "", [("1234", "Matrícula já cadastrada")])
        return _soap_proc(itens)

    conn = get_conn()
    try:
        with mock.patch.object(servico, "carregar_certificado", return_value=asg.certificado_teste()):
            env = servico.transmitir(conn, cid, transporte=transporte)
            assert env["enviados"] >= 6 and all(lote["ok"] for lote in env["lotes"])
            assert [lote["grupo"] for lote in env["lotes"]] == sorted(lote["grupo"] for lote in env["lotes"])
            assert "producaorestrita" in chamadas[0]
            cons = servico.consultar(conn, cid, transporte=transporte)
            assert any(x["status"] == "processado" for x in cons["lotes"])
            pn = servico.painel(conn, cid, {})
            assert pn["contagem"]["aceito"] >= 5 and pn["contagem"]["rejeitado"] >= 1
            rej = next(e for e in pn["eventos"] if e["status"] == "rejeitado")
            assert rej["ocorrencias"][0]["codigo"] == "1234"
            assert conn.execute("SELECT COUNT(*) AS n FROM esocial_totalizadores WHERE company_id = ? AND tipo = 'S-5001'",
                                (cid,)).fetchone()["n"] >= 1

            # Exclusão (S-3000) de um S-1200 aceito
            s1200 = next(e for e in pn["eventos"] if e["tipo"] == "S-1200" and e["status"] == "aceito")
            exc = servico.gerar_exclusao(conn, cid, s1200["id"])
            assert exc["status"] == "pendente", exc["erros"]
            servico.transmitir(conn, cid, ids=[exc["id"]], transporte=transporte)
            servico.consultar(conn, cid, transporte=transporte)
            st = conn.execute("SELECT status FROM esocial_eventos WHERE id = ?", (s1200["id"],)).fetchone()["status"]
            assert st == "excluido"
    finally:
        conn.close()

    fg = client.get("/api/esocial/fgts/2026-11", headers=h).json()
    assert fg["funcionarios"] and fg["total_mensal"] > 0
    xml = client.get(f"/api/esocial/eventos/{adm['id']}/xml", headers=h)
    assert xml.status_code == 200 and "assinatura-de-teste" in xml.headers["content-disposition"]

    # Isolamento entre empresas
    admin = client.post("/api/auth/login", json={"email": "admin@cortex.com.br", "password": "admin123"}).json()
    h_admin = {"Authorization": f"Bearer {admin['access_token']}"}
    assert client.get(f"/api/esocial/eventos/{adm['id']}/xml", headers=h_admin).status_code == 404



def _ins(conn, tabela, dados):
    cols = ", ".join(dados)
    cur = conn.execute(f"INSERT INTO {tabela} ({cols}) VALUES ({', '.join('?' for _ in dados)})", list(dados.values()))
    conn.commit()
    return cur.lastrowid


def test_eventos_sst_estagio_rpa_13_e_agrupamento():
    cid, h = _empresa_nova()
    dados = {k: v for k, v in EMP.items() if k not in ("matricula",)}
    emp = client.post("/api/dp/employees", headers=h, json={**dados, "cpf": _cpf()}).json()
    eid = emp["id"]
    conn = get_conn()
    try:
        cat = _ins(conn, "work_accidents", {"company_id": cid, "employee_id": eid, "data_acidente": "2026-11-10",
                                             "hora_acidente": "09:30", "descricao": "Queda", "houve_afastamento": 1,
                                             "dias_afastamento": 3})
        aso = _ins(conn, "medical_exams", {"company_id": cid, "employee_id": eid, "tipo": "admissional",
                                            "data_exame": "2026-11-01", "resultado": "apto", "medico": "Dra. Beltrana",
                                            "crm_medico": "9876"})
        rein = _ins(conn, "reintegracoes", {"company_id": cid, "employee_id": eid, "data_demissao": "2026-10-01",
                                             "data_reintegracao": "2026-11-10", "nr_processo": "00012345620265230001"})
        est = _ins(conn, "interns", {"company_id": cid, "nome": "Estagiária Teste", "cpf": _cpf(),
                                      "data_nascimento": "2004-05-05", "curso": "Administração", "instituicao": "UNEMAT", "bolsa_auxilio": 1200,
                                      "data_inicio": "2026-11-03", "data_fim": "2027-11-02", "status": "ativo"})
        aut = _ins(conn, "autonomous_workers", {"company_id": cid, "nome": "Autônomo Teste", "cpf": _cpf(), "cbo": "317110"})
        _ins(conn, "rpa_payments", {"company_id": cid, "autonomous_id": aut, "competencia": "2026-11",
                                    "data_pagamento": "2026-11-20", "descricao_servico": "Manutenção", "valor_bruto": 1500, "inss_retido": 165,
                                    "irrf_retido": 0, "valor_liquido": 1335})
        fer = _ins(conn, "payroll_special", {"company_id": cid, "employee_id": eid, "tipo": "ferias",
                                             "competencia": "2026-11", "data_inicio": "2026-11-16",
                                             "data_pagamento": "2026-11-14", "liquido": 900})
        _ins(conn, "payroll_special_lines", {"special_id": fer, "codigo": "0008", "nome": "Férias", "tipo": "provento",
                                             "valor": 933.33})
        d13 = _ins(conn, "payroll_special", {"company_id": cid, "employee_id": eid, "tipo": "decimo_2",
                                             "competencia": "2026-12", "data_pagamento": "2026-12-18", "liquido": 1300})
        _ins(conn, "payroll_special_lines", {"special_id": d13, "codigo": "0010", "nome": "13º", "tipo": "provento",
                                             "valor": 2800})
    finally:
        conn.close()

    # Sem os códigos do eSocial a CAT fica com erro e lista o que falta
    r = client.post(f"/api/esocial/gerar/cat/{cat}", headers=h).json()["eventos"][0]
    assert r["status"] == "erro_validacao" and any("Parte do corpo" in e for e in r["erros"])
    client.put(f"/api/esocial/complementos/cat/{cat}", headers=h, json={
        "cod_sit_geradora": "200004300", "cod_parte_ating": "753030000", "cod_agnt_causador": "302010200",
        "cod_natureza_lesao": "702000000", "dt_atendimento": "2026-11-10", "hr_atendimento": "10:15",
        "cod_cid": "S06.0", "nm_emit": "Dr. Fulano", "nr_oc": "12345", "uf_oc": "MT", "hrs_trab_antes": "0130"})
    r = client.post(f"/api/esocial/gerar/cat/{cat}", headers=h).json()["eventos"][0]
    assert r["status"] == "pendente", r["erros"]

    client.put(f"/api/esocial/complementos/aso/{aso}", headers=h, json={
        "crm_uf": "MT", "procedimentos": [{"cod": "0295"}, {"cod": "0281", "ord": "1"}]})
    assert client.post(f"/api/esocial/gerar/aso/{aso}", headers=h).json()["eventos"][0]["status"] == "pendente"

    expo = client.post("/api/esocial/exposicoes", headers=h, json={"employee_id": eid}).json()["id"]
    client.put(f"/api/esocial/complementos/exposicao/{expo}", headers=h, json={"dsc_setor": "Administrativo",
                                                                               "resp_cpf": "52998224725"})
    assert client.post(f"/api/esocial/gerar/exposicao/{expo}", headers=h).json()["eventos"][0]["status"] == "pendente"

    assert client.post(f"/api/esocial/gerar/reintegracao/{rein}", headers=h).json()["eventos"][0]["status"] == "pendente"

    client.put(f"/api/esocial/complementos/estagiario/{est}", headers=h, json={
        "sexo": "F", "raca_cor": "1", "grau_instrucao": "08", "logradouro": "Rua A", "numero": "1", "cep": "78200-000",
        "cod_municipio": "5102504", "uf": "MT", "nivel_esocial": "4", "cnpj_inst_ensino": "33.683.111/0001-07"})
    ini = client.post(f"/api/esocial/gerar/estagio-inicio/{est}", headers=h).json()["eventos"][0]
    assert ini["status"] == "pendente", ini["erros"]
    fim = client.post(f"/api/esocial/gerar/estagio-termino/{est}", headers=h, json={"data": "2026-12-20"}).json()["eventos"][0]
    assert fim["status"] == "pendente", fim["erros"]

    # RPA sem data de nascimento: erro claro; depois de completar, o S-1200 sai com infoComplem
    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-11"}).status_code == 201
    rem = client.post("/api/esocial/gerar/remuneracoes", headers=h, json={"per_apur": "2026-11"}).json()["eventos"]
    rpa = next(e for e in rem if "Autônomo" in e["descricao"])
    assert rpa["status"] == "erro_validacao" and any("nascimento" in e for e in rpa["erros"])
    client.put(f"/api/esocial/complementos/autonomo/{aut}", headers=h, json={"data_nascimento": "1980-01-01"})
    rem = client.post("/api/esocial/gerar/remuneracoes", headers=h, json={"per_apur": "2026-11"}).json()["eventos"]
    assert all(e["status"] == "pendente" for e in rem), [e for e in rem if e["status"] != "pendente"]
    assert len(rem) == 3  # funcionário, estagiária e autônomo: um S-1200 por CPF

    conn = get_conn()
    try:
        xml = conn.execute("""SELECT xml FROM esocial_eventos WHERE company_id = ? AND tipo = 'S-1200'
                              AND referencia_tipo = 'remuneracao' AND per_apur = '2026-11'""", (cid,)).fetchone()["xml"]
    finally:
        conn.close()
    assert xml.count("<dmDev>") == 2 and "FER" in xml  # folha + férias no mesmo S-1200

    pg = client.post("/api/esocial/gerar/pagamentos", headers=h, json={"per_apur": "2026-11"}).json()["eventos"]
    assert {e["status"] for e in pg} == {"pendente"} and len(pg) == 2  # férias (funcionário) e RPA

    d13 = client.post("/api/esocial/gerar/remuneracoes", headers=h, json={"per_apur": "2026"}).json()["eventos"]
    assert len(d13) == 1 and d13[0]["status"] == "pendente" and "13º" in d13[0]["descricao"]

    tab = client.get("/api/esocial/tabelas/13?q=cranio", headers=h).json()
    assert tab and tab[0]["codigo"] == "753030000"

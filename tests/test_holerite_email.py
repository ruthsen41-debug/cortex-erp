"""Envio de holerites por e-mail (SMTP da empresa, senha cifrada, registro dos envios)."""
import email

import pytest

from backend.database import get_conn
from backend.services import holerite_email as he
from tests.test_complementar_escalas import EMP, _cpf, _empresa_nova, client


class FakeSMTP:
    enviados = []
    falhar_para = set()
    logins = []

    def __init__(self, host, port, timeout=None, **kw):
        self.host, self.port = host, port

    def ehlo(self):
        pass

    def starttls(self, context=None):
        pass

    def login(self, user, pwd):
        FakeSMTP.logins.append((user, pwd))

    def sendmail(self, de, para, dados):
        if para[0] in FakeSMTP.falhar_para:
            raise he.smtplib.SMTPRecipientsRefused({para[0]: (550, b"caixa inexistente")})
        FakeSMTP.enviados.append((de, para[0], dados))

    def quit(self):
        pass


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.enviados, FakeSMTP.falhar_para, FakeSMTP.logins = [], set(), []
    monkeypatch.setattr(he.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(he.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    return FakeSMTP


def _folha(h):
    ids = []
    for nome, mail in (("Ana Souza", "ana@exemplo.com"), ("Bruno Lima", "bruno@exemplo.com"), ("Caio Sem Email", "")):
        r = client.post("/api/dp/employees", headers=h, json={**EMP, "name": nome, "cpf": _cpf(), "email": mail})
        assert r.status_code in (200, 201), r.text
        ids.append(r.json()["id"])
    assert client.post("/api/dp/payroll/run", headers=h, json={"competence": "2026-10"}).status_code in (200, 201)
    return client.get("/api/dp/payroll", headers=h).json()[0]["id"], ids


def test_config_guarda_senha_cifrada_e_nao_devolve(smtp):
    cid, h = _empresa_nova()
    assert client.get("/api/dp/email-config", headers=h).json()["origem"] == "nenhuma"
    r = client.put("/api/dp/email-config", headers=h, json={
        "host": "smtp.exemplo.com", "porta": 587, "seguranca": "starttls", "usuario": "rh@exemplo.com",
        "senha": "segredo123", "remetente": "rh@exemplo.com", "nome_remetente": "RH Exemplo"})
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert cfg["origem"] == "empresa" and cfg["tem_senha"] and "senha" not in cfg
    conn = get_conn()
    gravada = conn.execute("SELECT senha_cifrada FROM smtp_config WHERE company_id=?", (cid,)).fetchone()[0]
    conn.close()
    assert gravada and "segredo123" not in gravada
    # salvar de novo sem senha mantém a anterior
    client.put("/api/dp/email-config", headers=h, json={**cfg, "senha": ""})
    assert client.post("/api/dp/email-config/teste", headers=h, json={"para": "eu@exemplo.com"}).status_code == 200
    assert smtp.logins[-1] == ("rh@exemplo.com", "segredo123")
    assert client.put("/api/dp/email-config", headers=h, json={"host": "x", "remetente": "invalido"}).status_code == 400
    assert client.put("/api/dp/email-config", headers=h,
                      json={**cfg, "assunto": "Holerite {mes}"}).status_code == 400   # campo desconhecido


def test_envio_dos_holerites_e_reenvio_das_falhas(smtp):
    _, h = _empresa_nova()
    run_id, ids = _folha(h)
    # sem servidor configurado: erro claro
    r = client.post(f"/api/dp/payroll/{run_id}/holerites/email", headers=h, json={})
    assert r.status_code == 400 and "não configurado" in r.json()["detail"]

    client.put("/api/dp/email-config", headers=h, json={"host": "smtp.exemplo.com", "usuario": "rh@exemplo.com",
                                                         "senha": "x", "remetente": "rh@exemplo.com"})
    smtp.falhar_para = {"bruno@exemplo.com"}
    r = client.post(f"/api/dp/payroll/{run_id}/holerites/email", headers=h, json={})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["enviados"] == 1 and d["falhas"] == 2
    st = {x["employee_id"]: x["status"] for x in d["resultado"]}
    assert st == {ids[0]: "enviado", ids[1]: "erro", ids[2]: "sem_email"}

    de, para, bruto = smtp.enviados[0]
    msg = email.message_from_bytes(bruto)
    assert para == "ana@exemplo.com" and "Holerite" in msg["Subject"]
    anexos = [p for p in msg.walk() if p.get_filename()]
    assert anexos[0].get_filename().startswith("holerite_2026-10_Ana_Souza")
    html = anexos[0].get_payload(decode=True).decode()
    assert "Ana Souza" in html and "Bruno Lima" not in html          # só o holerite dela

    envios = {x["employee_id"]: x for x in client.get(f"/api/dp/payroll/{run_id}/holerites/envios", headers=h).json()["funcionarios"]}
    assert envios[ids[0]]["status"] == "enviado" and not envios[ids[2]]["email_valido"]

    smtp.falhar_para = set()
    r = client.post(f"/api/dp/payroll/{run_id}/holerites/email", headers=h, json={"somente_pendentes": True}).json()
    assert {x["employee_id"] for x in r["resultado"]} == {ids[1], ids[2]}    # Ana não recebe de novo
    assert len(smtp.enviados) == 2


def test_envio_exige_permissao_e_folha_da_empresa(smtp):
    _, h = _empresa_nova()
    run_id, _ = _folha(h)
    _, h2 = _empresa_nova()
    assert client.post(f"/api/dp/payroll/{run_id}/holerites/email", headers=h2, json={}).status_code == 404
    assert client.get(f"/api/dp/payroll/{run_id}/holerites/envios", headers=h2).status_code == 404

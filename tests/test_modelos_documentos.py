"""Pacote de modelos de documentos do DP: geração, validações legais e personalização por empresa."""
from datetime import date

from tests.test_complementar_escalas import EMP, _cpf, _empresa_nova, client

from backend.services.modelos_documentos import MODELOS, valor_extenso, validar_texto, ModeloErro, renderizar

BASE = "/api/dp/modelos-documentos"


def _func(h, **extra):
    r = client.post("/api/dp/employees", headers=h, json={**EMP, "cpf": _cpf(), **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_valor_extenso():
    assert valor_extenso(3000) == "três mil reais"
    assert valor_extenso(1518.5) == "mil quinhentos e dezoito reais e cinquenta centavos"
    assert valor_extenso(2030) == "dois mil e trinta reais"
    assert valor_extenso(1_000_000) == "um milhão de reais"
    assert valor_extenso(0.01) == "um centavo"


def test_todos_os_modelos_padrao_sao_validos_e_geram():
    _, h = _empresa_nova()
    eid = _func(h, name="Paula Modelos", admission_date="2026-01-05", experiencia_dias=45, experiencia_prorrogacao=45)
    lista = client.get(BASE, headers=h).json()["modelos"]
    assert {m["codigo"] for m in lista} >= set(MODELOS)
    campos = {"data_termino": "2026-12-31", "valor_hora": "15", "data_inicio": "2026-12-01",
              "valor": "300", "parcelas": "3", "ultimo_dia": "2026-11-10"}
    for cod in MODELOS:
        validar_texto(MODELOS[cod]["texto"], cod)
        r = client.get(f"/api/dp/employees/{eid}/modelo/{cod}", headers=h, params=campos)
        assert r.status_code == 200, (cod, r.text)
        assert "Paula Modelos" in r.text and "{{" not in r.text and "[[" not in r.text, cod


def test_regras_legais_dos_campos():
    _, h = _empresa_nova()
    eid = _func(h, name="Rui Regras", admission_date="2026-01-05", salary=3000)
    url = f"/api/dp/employees/{eid}/modelo"
    exp = client.get(f"{url}/contrato_experiencia", headers=h, params={"dias": 30, "prorrogacao": 60}).text
    assert "03/02/2026" in exp and "04/04/2026" in exp and "três mil reais" in exp
    assert client.get(f"{url}/contrato_experiencia", headers=h, params={"dias": 45, "prorrogacao": 50}).status_code == 422
    assert client.get(f"{url}/contrato_determinado", headers=h, params={"data_termino": "2028-01-05"}).status_code == 422
    assert client.get(f"{url}/contrato_determinado", headers=h, params={"data_termino": "2028-01-04"}).status_code == 200
    assert client.get(f"{url}/acordo_prorrogacao", headers=h, params={"adicional": 40}).status_code == 422
    assert client.get(f"{url}/abono_pecuniario", headers=h, params={"dias_abono": 11}).status_code == 422

    fer = client.get(f"{url}/aviso_ferias", headers=h,
                     params={"periodo_inicio": "2026-01-05", "data_inicio": "2027-02-01", "dias": 20, "dias_abono": 10}).text
    assert "05/01/2026 a 04/01/2027" in fer and "01/02/2027 a 20/02/2027" in fer
    assert "21/02/2027" in fer and "30/01/2027" in fer and "10 dias" in fer
    assert client.get(f"{url}/aviso_ferias", headers=h,
                      params={"data_inicio": "2027-02-01", "dias": 25, "dias_abono": 10}).status_code == 422

    abono = client.get(f"{url}/abono_pecuniario", headers=h, params={"periodo_inicio": "2026-01-05"}).text
    assert "20/12/2026" in abono                                       # 15 dias antes do fim do aquisitivo

    desc = client.get(f"{url}/autorizacao_desconto", headers=h, params={"valor": "300", "parcelas": "3",
                                                                        "descricao": "<script>x</script>"}).text
    assert "R$ 100,00" in desc and "<script>" not in desc and "&lt;script&gt;" in desc


def test_aviso_ferias_usa_programacao():
    _, h = _empresa_nova()
    eid = _func(h, name="Dora Programada", admission_date="2025-03-10")
    r = client.post("/api/dp/ferias/programacao", headers=h, json={
        "employee_id": eid, "periodo_inicio": "2025-03-10", "data_inicio": "2027-03-01", "dias_gozo": 30})
    assert r.status_code in (200, 201), r.text
    fer = client.get(f"/api/dp/employees/{eid}/modelo/aviso_ferias", headers=h).text
    assert "01/03/2027 a 30/03/2027" in fer and "10/03/2025 a 09/03/2026" in fer


def test_dependentes_salario_familia_e_ir():
    _, h = _empresa_nova()
    eid = _func(h, name="Ivo Pai")
    for dep in ({"nome": "Bia Pequena", "data_nascimento": "2020-05-01", "parentesco": "03", "salario_familia": 1, "irrf": 1},
                {"nome": "Caio Grande", "data_nascimento": "2005-05-01", "parentesco": "03", "salario_familia": 1, "irrf": 0}):
        r = client.post(f"/api/dp/employees/{eid}/dependents", headers=h, json=dep)
        assert r.status_code in (200, 201), r.text
    sf = client.get(f"/api/dp/employees/{eid}/modelo/salario_familia", headers=h).text
    assert "Bia Pequena" in sf and "30/04/2034" in sf and "Caio Grande" not in sf      # maior de 14 fica fora
    ir = client.get(f"/api/dp/employees/{eid}/modelo/dependentes_ir", headers=h).text
    assert "Bia Pequena" in ir and "Caio Grande" not in ir


def test_personalizar_restaurar_e_modelo_proprio():
    _, h = _empresa_nova()
    eid = _func(h, name="Lia Custom")
    texto = "# Termo da Casa\n\nEu, **{{empregado.nome}}**, CPF {{empregado.cpf}}.\n\n[[assinaturas: empregado]]"
    r = client.put(f"{BASE}/carta_recomendacao", headers=h, json={"titulo": "Recomendação", "texto": texto})
    assert r.status_code == 200 and r.json()["personalizado"]
    doc = client.get(f"/api/dp/employees/{eid}/modelo/carta_recomendacao", headers=h).text
    assert "Termo da Casa" in doc and "<b>Lia Custom</b>" in doc
    assert client.get(f"{BASE}/aviso_ferias", headers=h).json()["rotulos_calculadas"]["retorno"] == "Retorno ao trabalho"

    ruim = client.put(f"{BASE}/carta_recomendacao", headers=h, json={"titulo": "x", "texto": "{{empregado.salario_mensal}}"})
    assert ruim.status_code == 422 and "salario_mensal" in ruim.json()["detail"]
    assert client.put(f"{BASE}/carta_recomendacao", headers=h,
                      json={"titulo": "x", "texto": "oi\n[[assinaturas: chefe]]"}).status_code == 422

    _, h2 = _empresa_nova()                                            # outra empresa continua com o padrão
    assert not client.get(f"{BASE}/carta_recomendacao", headers=h2).json()["personalizado"]

    assert client.delete(f"{BASE}/carta_recomendacao", headers=h).json()["restaurado"] is True
    carta = client.get(f"/api/dp/employees/{eid}/modelo/carta_recomendacao", headers=h).text
    assert "Carta de Recomendação" in carta and "vazio" not in carta.split("<body>")[1]   # complemento em branco some

    novo = client.post(BASE, headers=h, json={"titulo": "Termo de uniforme",
                                              "texto": "# Uniforme\n\nRecebi, {{empregado.nome}}, em {{data.hoje}}."})
    assert novo.status_code == 201, novo.text
    cod = novo.json()["codigo"]
    assert cod.startswith("pers_")
    assert any(m["codigo"] == cod and m["proprio"] for m in client.get(BASE, headers=h).json()["modelos"])
    assert "Recebi, Lia Custom" in client.get(f"/api/dp/employees/{eid}/modelo/{cod}", headers=h).text
    previa = client.post(f"{BASE}/_novo/previa", headers=h, json={"employee_id": eid, "texto": "Olá {{empregado.nome}}"})
    assert previa.status_code == 200 and "Olá Lia Custom" in previa.text
    assert client.delete(f"{BASE}/{cod}", headers=h).json()["restaurado"] is False
    assert client.get(f"/api/dp/employees/{eid}/modelo/{cod}", headers=h).status_code == 404
    assert client.get(f"/api/dp/employees/{eid}/modelo/aviso_ferias", headers=h2).status_code == 404


def test_renderizar_escapa_valores():
    html = renderizar("Nome: {{empregado.nome}}", {"empregado.nome": "<b>x</b>"}, hoje=date(2026, 11, 18))
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    try:
        validar_texto("")
        assert False
    except ModeloErro:
        pass

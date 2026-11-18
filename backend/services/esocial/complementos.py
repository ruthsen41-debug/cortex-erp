"""Campos complementares do eSocial nos cadastros do DP (CAT, ASO, PCMSO, reintegração, estágio, autônomo,
condições ambientais) e busca nas tabelas oficiais (13, 14, 15, 17, 24, 27)."""
import json
import os
import unicodedata
from functools import lru_cache
from typing import Any, Dict, List

UFS = ["", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
       "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
SN = [["N", "Não"], ["S", "Sim"]]


def _uf(k, rot):
    return {"k": k, "rot": rot, "tipo": "select", "opcoes": [[u, u or "—"] for u in UFS]}


ESPECS: Dict[str, Dict[str, Any]] = {
    "cat": {"tabela": "work_accidents", "titulo": "CAT — dados do eSocial (S-2210)", "campos": [
        {"k": "tp_acid", "rot": "Tipo de acidente", "tipo": "select", "opcoes": [["1", "Típico"], ["2", "Doença"], ["3", "Trajeto"]]},
        {"k": "tp_cat", "rot": "Tipo de CAT", "tipo": "select", "opcoes": [["1", "Inicial"], ["2", "Reabertura"], ["3", "Comunicação de óbito"]]},
        {"k": "iniciat_cat", "rot": "Iniciativa", "tipo": "select", "opcoes": [["1", "Empregador"], ["2", "Ordem judicial"], ["3", "Órgão fiscalizador"]]},
        {"k": "hora_acidente", "rot": "Hora do acidente", "tipo": "time"},
        {"k": "hrs_trab_antes", "rot": "Horas trabalhadas antes (HHMM)", "tipo": "text", "dica": "Ex.: 0230 = 2h30"},
        {"k": "ult_dia_trab", "rot": "Último dia trabalhado", "tipo": "date"},
        {"k": "ind_comun_policia", "rot": "Houve registro policial?", "tipo": "select", "opcoes": SN},
        {"k": "cod_sit_geradora", "rot": "Situação geradora", "tipo": "tabela", "tabela": "15", "largo": True},
        {"k": "cod_parte_ating", "rot": "Parte do corpo atingida", "tipo": "tabela", "tabela": "13", "largo": True},
        {"k": "lateralidade", "rot": "Lateralidade", "tipo": "select", "opcoes": [["0", "Não aplicável"], ["1", "Esquerda"], ["2", "Direita"], ["3", "Ambas"]]},
        {"k": "cod_agnt_causador", "rot": "Agente causador", "tipo": "tabela", "tabela": "14,15", "largo": True},
        {"k": "cod_natureza_lesao", "rot": "Natureza da lesão", "tipo": "tabela", "tabela": "17", "largo": True},
        {"k": "tp_local", "rot": "Local do acidente", "tipo": "select", "opcoes": [
            ["1", "Estabelecimento do empregador"], ["3", "Estabelecimento de terceiros"], ["4", "Via pública"],
            ["5", "Área rural"], ["6", "Embarcação"], ["9", "Outros"], ["2", "Estabelecimento no exterior"]]},
        {"k": "local_logradouro", "rot": "Logradouro do local (se fora da empresa)", "tipo": "text", "largo": True},
        {"k": "local_numero", "rot": "Número", "tipo": "text"}, {"k": "local_bairro", "rot": "Bairro", "tipo": "text"},
        {"k": "local_cep", "rot": "CEP", "tipo": "text"}, {"k": "local_cod_municipio", "rot": "Cód. IBGE do município", "tipo": "text"},
        _uf("local_uf", "UF"),
        {"k": "dt_atendimento", "rot": "Data do atendimento", "tipo": "date"},
        {"k": "hr_atendimento", "rot": "Hora do atendimento", "tipo": "time"},
        {"k": "ind_internacao", "rot": "Houve internação?", "tipo": "select", "opcoes": SN},
        {"k": "dur_trat", "rot": "Duração do tratamento (dias)", "tipo": "number"},
        {"k": "cod_cid", "rot": "CID", "tipo": "text", "dica": "Ex.: S62.5"},
        {"k": "diag_provavel", "rot": "Diagnóstico provável", "tipo": "text", "largo": True},
        {"k": "nm_emit", "rot": "Médico emitente do atestado", "tipo": "text", "largo": True},
        {"k": "ide_oc", "rot": "Conselho", "tipo": "select", "opcoes": [["1", "CRM"], ["2", "CRO"], ["3", "RMS"]]},
        {"k": "nr_oc", "rot": "Nº no conselho", "tipo": "text"}, _uf("uf_oc", "UF do conselho"),
        {"k": "dt_obito", "rot": "Data do óbito (se houver)", "tipo": "date"},
        {"k": "nr_rec_cat_orig", "rot": "Recibo da CAT de origem (reabertura/óbito)", "tipo": "text", "largo": True},
    ]},
    "aso": {"tabela": "medical_exams", "titulo": "ASO — dados do eSocial (S-2220)", "campos": [
        {"k": "crm_uf", "rot": "UF do CRM do médico", "tipo": "select", "opcoes": [[u, u or "—"] for u in UFS]},
        {"k": "procedimentos", "rot": "Exames realizados (Tabela 27)", "tipo": "procedimentos", "largo": True,
         "dica": "Se vazio, envia só a avaliação clínica ocupacional (0295)."},
    ]},
    "pcmso": {"tabela": "pcmso_programas", "titulo": "Médico responsável pelo PCMSO (S-2220)", "campos": [
        {"k": "responsavel_nome", "rot": "Nome do médico responsável", "tipo": "text", "largo": True},
        {"k": "responsavel_crm", "rot": "CRM", "tipo": "text"}, _uf("responsavel_uf", "UF do CRM"),
        {"k": "responsavel_cpf", "rot": "CPF (opcional)", "tipo": "text"},
    ]},
    "reintegracao": {"tabela": "reintegracoes", "titulo": "Reintegração — dados do eSocial (S-2298)", "campos": [
        {"k": "tp_reint", "rot": "Tipo", "tipo": "select", "opcoes": [["1", "Decisão judicial"], ["2", "Anistia legal"], ["9", "Outros"]]},
        {"k": "nr_processo", "rot": "Nº do processo judicial (20 dígitos)", "tipo": "text", "largo": True},
        {"k": "data_reintegracao", "rot": "Data do efetivo retorno", "tipo": "date"},
        {"k": "dt_efeito", "rot": "Data dos efeitos (se diferente)", "tipo": "date"},
    ]},
    "estagiario": {"tabela": "interns", "titulo": "Estagiário — dados do eSocial (S-2300)", "campos": [
        {"k": "sexo", "rot": "Sexo", "tipo": "select", "opcoes": [["", "—"], ["F", "Feminino"], ["M", "Masculino"]]},
        {"k": "raca_cor", "rot": "Raça/cor", "tipo": "select", "opcoes": [["", "—"], ["1", "Branca"], ["2", "Preta"], ["3", "Parda"], ["4", "Amarela"], ["5", "Indígena"]]},
        {"k": "grau_instrucao", "rot": "Grau de instrução", "tipo": "select", "opcoes": [
            ["", "—"], ["05", "Fundamental completo"], ["06", "Médio incompleto"], ["07", "Médio completo"],
            ["08", "Superior incompleto"], ["09", "Superior completo"], ["10", "Pós-graduação"]]},
        {"k": "data_nascimento", "rot": "Nascimento", "tipo": "date"},
        {"k": "logradouro", "rot": "Logradouro", "tipo": "text", "largo": True}, {"k": "numero", "rot": "Número", "tipo": "text"},
        {"k": "bairro", "rot": "Bairro", "tipo": "text"}, {"k": "cep", "rot": "CEP", "tipo": "text"},
        {"k": "cod_municipio", "rot": "Cód. IBGE do município", "tipo": "text"}, _uf("uf", "UF"),
        {"k": "nivel_esocial", "rot": "Nível do estágio", "tipo": "select", "opcoes": [
            ["", "—"], ["1", "Fundamental"], ["2", "Médio"], ["3", "Formação profissional"], ["4", "Superior"], ["8", "Especial"]]},
        {"k": "nat_estagio", "rot": "Estágio obrigatório?", "tipo": "select", "opcoes": [["N", "Não obrigatório"], ["O", "Obrigatório"]]},
        {"k": "area_atuacao", "rot": "Área de atuação", "tipo": "text", "largo": True},
        {"k": "nr_apolice", "rot": "Nº da apólice de seguro", "tipo": "text"},
        {"k": "cnpj_inst_ensino", "rot": "CNPJ da instituição de ensino", "tipo": "text"},
        {"k": "cnpj_agente_integracao", "rot": "CNPJ do agente de integração", "tipo": "text"},
        {"k": "cpf_supervisor", "rot": "CPF do supervisor", "tipo": "text"},
        {"k": "data_termino_real", "rot": "Término efetivo (para o S-2399)", "tipo": "date"},
    ]},
    "autonomo": {"tabela": "autonomous_workers", "titulo": "Autônomo — dados do eSocial (S-1200)", "campos": [
        {"k": "data_nascimento", "rot": "Data de nascimento", "tipo": "date"},
        {"k": "cbo", "rot": "CBO", "tipo": "text"},
    ]},
    "exposicao": {"tabela": "esocial_exposicoes", "titulo": "Condições ambientais do trabalho (S-2240)", "campos": [
        {"k": "dt_inicio", "rot": "Início da condição", "tipo": "date"},
        {"k": "local_amb", "rot": "Ambiente", "tipo": "select", "opcoes": [["1", "Estabelecimento do empregador"], ["2", "Estabelecimento de terceiros"]]},
        {"k": "dsc_setor", "rot": "Setor", "tipo": "text"},
        {"k": "dsc_ativ", "rot": "Atividades desempenhadas", "tipo": "textarea", "largo": True},
        {"k": "agentes", "rot": "Agentes nocivos (Tabela 24)", "tipo": "agentes", "largo": True,
         "dica": "Sem exposição: use 09.01.001 (ausência de agente nocivo)."},
        {"k": "resp_cpf", "rot": "CPF do responsável pelos registros ambientais", "tipo": "text"},
        {"k": "resp_nome", "rot": "Nome do responsável", "tipo": "text"},
        {"k": "resp_ide_oc", "rot": "Conselho", "tipo": "select", "opcoes": [["", "—"], ["1", "CRM"], ["4", "CREA"], ["9", "Outros"]]},
        {"k": "resp_nr_oc", "rot": "Nº no conselho", "tipo": "text"}, _uf("resp_uf_oc", "UF do conselho"),
        {"k": "observacao", "rot": "Observação", "tipo": "textarea", "largo": True},
    ]},
}


def ler(conn, cid: int, tipo: str, rid: int) -> Dict[str, Any]:
    esp = ESPECS.get(tipo)
    if not esp:
        raise LookupError("Cadastro desconhecido")
    row = conn.execute(f"SELECT * FROM {esp['tabela']} WHERE id = ? AND company_id = ?", (rid, cid)).fetchone()
    if not row:
        raise LookupError("Registro não encontrado")
    row = dict(row)
    valores = {c["k"]: row.get(c["k"]) for c in esp["campos"]}
    for c in esp["campos"]:
        if c["tipo"] in ("procedimentos", "agentes"):
            try:
                valores[c["k"]] = json.loads(valores[c["k"]]) if valores[c["k"]] else []
            except ValueError:
                valores[c["k"]] = []
    return {"titulo": esp["titulo"], "campos": esp["campos"], "valores": valores}


def gravar(conn, cid: int, tipo: str, rid: int, dados: Dict[str, Any]) -> Dict[str, Any]:
    esp = ESPECS.get(tipo)
    if not esp:
        raise LookupError("Cadastro desconhecido")
    if not conn.execute(f"SELECT 1 FROM {esp['tabela']} WHERE id = ? AND company_id = ?", (rid, cid)).fetchone():
        raise LookupError("Registro não encontrado")
    sets, vals = [], []
    for c in esp["campos"]:
        if c["k"] not in dados:
            continue
        v = dados[c["k"]]
        if c["tipo"] in ("procedimentos", "agentes"):
            v = json.dumps(v or [], ensure_ascii=False)
        elif c["tipo"] == "number":
            v = int(float(v or 0))
        else:
            v = "" if v is None else str(v).strip()
        sets.append(f"{c['k']} = ?")
        vals.append(v)
    if sets:
        conn.execute(f"UPDATE {esp['tabela']} SET {', '.join(sets)} WHERE id = ? AND company_id = ?", [*vals, rid, cid])
        conn.commit()
    return ler(conn, cid, tipo, rid)


def criar_exposicao(conn, cid: int, employee_id: int) -> int:
    if not conn.execute("SELECT 1 FROM employees WHERE id = ? AND company_id = ?", (employee_id, cid)).fetchone():
        raise LookupError("Funcionário não encontrado")
    emp = dict(conn.execute("SELECT admission_date, department, role FROM employees WHERE id = ?", (employee_id,)).fetchone())
    cur = conn.execute("""INSERT INTO esocial_exposicoes (company_id, employee_id, dt_inicio, dsc_setor, dsc_ativ, agentes)
                          VALUES (?,?,?,?,?,?)""",
                       (cid, employee_id, (emp.get("admission_date") or "")[:10], emp.get("department") or "",
                        f"Atividades de {emp.get('role') or 'cargo'}",
                        json.dumps([{"cod": "09.01.001"}])))
    conn.commit()
    return cur.lastrowid


# ─── tabelas oficiais ─────────────────────────────────────────────────────────

_DIR = os.path.join(os.path.dirname(__file__), "dados")


@lru_cache(maxsize=None)
def _tabela(num: str) -> List[List[str]]:
    caminho = os.path.join(_DIR, f"tabela_{num}.json")
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def _norm(t: str) -> str:
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def buscar(nums: str, termo: str = "", limite: int = 40) -> List[Dict[str, str]]:
    termo_n = _norm(termo)
    out = []
    for num in [n.strip() for n in (nums or "").split(",") if n.strip()]:
        for cod, desc in _tabela(num):
            if not termo_n or termo_n in _norm(desc) or cod.startswith(termo.strip()):
                out.append({"codigo": cod, "descricao": desc, "tabela": num})
                if len(out) >= limite:
                    return out
    return out

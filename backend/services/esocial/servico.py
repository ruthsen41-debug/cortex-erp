"""Central do eSocial: gera eventos a partir do cadastro e da folha, mantém a fila,
valida, transmite em lotes e processa os retornos (recibos, ocorrências e totalizadores)."""
import json
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import eventos as ev
from .assinatura import assinar, certificado_info, certificado_teste
from .comunicacao import MAX_EVENTOS_LOTE, ClienteESocial, ErroComunicacao, contexto_tls, montar_lote
from .tabelas import (DIAS_MINIMOS_AFASTAMENTO, EVENTOS, MOTIVO_AFASTAMENTO, MOTIVO_DESLIGAMENTO,
                      NOMES_EVENTOS, RUBRICAS_EXTRAS, RUBRICAS_NAO_ENVIADAS, CLASS_TRIB_POR_REGIME)
from .validacao import validar_evento, validar_lote

STATUS = {
    "pendente": "Pronto para enviar",
    "erro_validacao": "Com erro (corrigir antes de enviar)",
    "enviado": "Enviado — aguardando processamento",
    "aceito": "Aceito pelo eSocial",
    "rejeitado": "Rejeitado pelo eSocial",
    "erro_envio": "Erro no envio do lote",
    "excluido": "Excluído (S-3000)",
    "substituido": "Substituído por retificação",
}
_ABERTOS = ("pendente", "erro_validacao", "erro_envio")


class SemCertificado(RuntimeError):
    pass


# ─── configuração ─────────────────────────────────────────────────────────────

def _row(r) -> Dict[str, Any]:
    return dict(r) if r else {}


def empresa(conn, cid: int) -> Dict[str, Any]:
    return _row(conn.execute("SELECT * FROM companies WHERE id = ?", (cid,)).fetchone())


def obter_config(conn, cid: int) -> Dict[str, Any]:
    cfg = _row(conn.execute("SELECT * FROM esocial_config WHERE company_id = ?", (cid,)).fetchone())
    co = empresa(conn, cid)
    if not cfg:
        cfg = {"company_id": cid, "ambiente": 2, "fpas": "515", "cod_lotacao": "LOTACAO01",
               "ide_tab_rubr": "CORTEX", "ind_des_folha": "0", "ind_opt_reg_eletron": "0",
               "transmissor_tp_insc": "1", "envio_automatico": 0}
    if not cfg.get("class_trib"):
        cfg["class_trib"] = CLASS_TRIB_POR_REGIME.get((co.get("regime_tributario") or "").lower(), "")
    if not cfg.get("cnae"):
        cfg["cnae"] = ev.digitos(co.get("cnae_principal"))
    if not cfg.get("ini_valid"):
        cfg["ini_valid"] = date.today().strftime("%Y-%m")
    if not cfg.get("transmissor_nr_insc"):
        cfg["transmissor_nr_insc"] = ev.digitos(co.get("cnpj"))
    cfg["ambiente"] = int(cfg.get("ambiente") or 2)
    return cfg


CAMPOS_CONFIG = ("ambiente", "class_trib", "ind_des_folha", "ind_opt_reg_eletron", "cnae", "fpas", "cod_tercs",
                 "aliq_rat", "fap", "cod_lotacao", "ide_tab_rubr", "ini_valid", "transmissor_tp_insc",
                 "transmissor_nr_insc", "envio_automatico")


def salvar_config(conn, cid: int, dados: Dict[str, Any]) -> Dict[str, Any]:
    atual = obter_config(conn, cid)
    novo = {k: dados.get(k, atual.get(k)) for k in CAMPOS_CONFIG}
    if int(novo.get("ambiente") or 2) not in (1, 2):
        raise ValueError("Ambiente inválido")
    existe = conn.execute("SELECT 1 FROM esocial_config WHERE company_id = ?", (cid,)).fetchone()
    if existe:
        conn.execute(f"UPDATE esocial_config SET {', '.join(f'{k} = ?' for k in CAMPOS_CONFIG)}, "
                     "updated_at = CURRENT_TIMESTAMP WHERE company_id = ?", [*novo.values(), cid])
    else:
        conn.execute(f"INSERT INTO esocial_config (company_id, {', '.join(CAMPOS_CONFIG)}) "
                     f"VALUES (?, {', '.join('?' for _ in CAMPOS_CONFIG)})", [cid, *novo.values()])
    conn.commit()
    return obter_config(conn, cid)


def carregar_certificado(co: Dict[str, Any]) -> Optional[Tuple[Any, Any]]:
    """Certificado A1 cadastrado na empresa (o mesmo da NF-e) ou None."""
    if not (co.get("certificado_b64") and co.get("certificado_senha")):
        return None
    try:
        from ..sefaz_direct_real import _load_cert
    except ImportError:  # execução fora do pacote
        from services.sefaz_direct_real import _load_cert
    key, cert, _pfx, _senha = _load_cert(co)
    return key, cert


def status_certificado(conn, cid: int) -> Dict[str, Any]:
    co = empresa(conn, cid)
    try:
        par = carregar_certificado(co)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "mensagem": f"Certificado cadastrado, mas não foi possível abrir: {exc}"}
    if not par:
        return {"ok": False, "mensagem": "Nenhum certificado A1 cadastrado (Empresa → Fiscal → Certificado A1)."}
    info = certificado_info(par[1])
    if info["vencido"]:
        return {"ok": False, "mensagem": f"Certificado de {info['titular']} vencido em {info['validade']}.", **info}
    return {"ok": True, "mensagem": f"Certificado de {info['titular']}, válido até {info['validade']}.", **info}


# ─── fila ─────────────────────────────────────────────────────────────────────

def _valida(xml: str, tipo: str, par: Optional[Tuple[Any, Any]]) -> List[str]:
    key, cert = par or certificado_teste()
    return validar_evento(assinar(xml, key, cert), tipo)


def _registrar(conn, cid: int, cfg, tipo: str, gerado: Tuple[str, str], *, descricao: str = "",
               ref_tipo: str = "", ref_id: int = 0, employee_id: int = 0, per_apur: str = "",
               retif_de: Optional[Dict[str, Any]] = None) -> int:
    ev_id, xml = gerado
    erros = _valida(xml, tipo, None)
    status = "erro_validacao" if erros else "pendente"
    grupo = EVENTOS[tipo][2]
    # Um evento ainda não enviado para a mesma referência é substituído pelo novo
    conn.execute("""DELETE FROM esocial_eventos WHERE company_id = ? AND tipo = ? AND referencia_tipo = ?
                    AND referencia_id = ? AND per_apur = ? AND status IN ('pendente','erro_validacao','erro_envio')""",
                 (cid, tipo, ref_tipo, ref_id, per_apur))
    cur = conn.execute("""
        INSERT INTO esocial_eventos (company_id, tipo, grupo, descricao, referencia_tipo, referencia_id, employee_id,
            per_apur, evento_id, xml, status, erros, ind_retif, nr_recibo_orig, ambiente)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, tipo, grupo, descricao or NOMES_EVENTOS.get(tipo, tipo), ref_tipo, ref_id, employee_id, per_apur,
         ev_id, xml, status, json.dumps(erros, ensure_ascii=False) if erros else "",
         2 if retif_de else 1, (retif_de or {}).get("nr_recibo", ""), cfg["ambiente"]))
    conn.commit()
    return cur.lastrowid if hasattr(cur, "lastrowid") else 0


def _registrar_falha(conn, cid: int, cfg, tipo: str, problemas: List[str], *, descricao: str, ref_tipo: str,
                     ref_id: int, employee_id: int = 0, per_apur: str = "") -> int:
    conn.execute("""DELETE FROM esocial_eventos WHERE company_id = ? AND tipo = ? AND referencia_tipo = ?
                    AND referencia_id = ? AND per_apur = ? AND status IN ('pendente','erro_validacao','erro_envio')""",
                 (cid, tipo, ref_tipo, ref_id, per_apur))
    cur = conn.execute("""
        INSERT INTO esocial_eventos (company_id, tipo, grupo, descricao, referencia_tipo, referencia_id, employee_id,
            per_apur, status, erros, ambiente)
        VALUES (?,?,?,?,?,?,?,?,'erro_validacao',?,?)""",
        (cid, tipo, EVENTOS[tipo][2], descricao, ref_tipo, ref_id, employee_id, per_apur,
         json.dumps(problemas, ensure_ascii=False), cfg["ambiente"]))
    conn.commit()
    return cur.lastrowid if hasattr(cur, "lastrowid") else 0


def _gera(conn, cid, cfg, tipo, fn: Callable[[], Tuple[str, str]], **meta) -> Dict[str, Any]:
    try:
        rid = _registrar(conn, cid, cfg, tipo, fn(), **meta)
    except ev.DadosIncompletos as exc:
        meta.pop("retif_de", None)
        rid = _registrar_falha(conn, cid, cfg, tipo, exc.problemas, **meta)
    row = _row(conn.execute("SELECT id, tipo, descricao, status, erros FROM esocial_eventos WHERE id = ?",
                            (rid,)).fetchone())
    row["erros"] = json.loads(row["erros"]) if row.get("erros") else []
    return row


def _ultimo_aceito(conn, cid, tipo, ref_tipo, ref_id, per_apur="") -> Optional[Dict[str, Any]]:
    return _row(conn.execute("""
        SELECT * FROM esocial_eventos WHERE company_id = ? AND tipo = ? AND referencia_tipo = ? AND referencia_id = ?
          AND per_apur = ? AND status = 'aceito' ORDER BY id DESC LIMIT 1""",
        (cid, tipo, ref_tipo, ref_id, per_apur)).fetchone()) or None


# ─── geração ──────────────────────────────────────────────────────────────────

def _funcionario(conn, cid, emp_id) -> Dict[str, Any]:
    emp = _row(conn.execute("SELECT * FROM employees WHERE id = ? AND company_id = ?", (emp_id, cid)).fetchone())
    if not emp:
        raise LookupError("Funcionário não encontrado")
    return emp


def _dependentes(conn, cid, emp_id) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM employee_dependents WHERE employee_id = ? AND company_id = ? ORDER BY id",
        (emp_id, cid)).fetchall()]


def gerar_tabelas(conn, cid: int) -> List[Dict[str, Any]]:
    """S-1000, S-1005, S-1020 e S-1010 das rubricas da empresa (envio inicial do empregador)."""
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    amb = cfg["ambiente"]
    out = [
        _gera(conn, cid, cfg, "S-1000", lambda: ev.s1000(co, cfg, amb), descricao="Informações do empregador",
              ref_tipo="empresa", ref_id=cid),
        _gera(conn, cid, cfg, "S-1005", lambda: ev.s1005(co, cfg, amb), descricao="Estabelecimento (matriz)",
              ref_tipo="estabelecimento", ref_id=cid),
        _gera(conn, cid, cfg, "S-1020", lambda: ev.s1020(co, cfg, amb),
              descricao=f"Lotação {ev.cod_lotacao(cfg)}", ref_tipo="lotacao", ref_id=cid),
    ]
    try:
        from ..payroll_engine import ensure_system_rubrics
    except ImportError:
        from services.payroll_engine import ensure_system_rubrics
    ensure_system_rubrics(conn, cid)
    conn.commit()
    rubricas = [dict(r) for r in conn.execute(
        "SELECT * FROM payroll_rubrics WHERE company_id IN (?, 0) AND COALESCE(ativo, 1) = 1 ORDER BY codigo, company_id DESC",
        (cid,)).fetchall()]
    vistos = set()
    for rb in rubricas:
        if rb["codigo"] in vistos or rb["codigo"] in RUBRICAS_NAO_ENVIADAS or rb.get("tipo") == "informativo":
            continue
        vistos.add(rb["codigo"])
        out.append(_gera(conn, cid, cfg, "S-1010", lambda rb=rb: ev.s1010(co, cfg, amb, rb),
                         descricao=f"Rubrica {rb['codigo']} — {rb['nome']}", ref_tipo="rubrica", ref_id=rb["id"]))
    for i, (cod, nome, tipo) in enumerate(RUBRICAS_EXTRAS, start=1):
        if cod in vistos:
            continue
        rb = {"codigo": cod, "nome": nome, "tipo": tipo}
        out.append(_gera(conn, cid, cfg, "S-1010", lambda rb=rb: ev.s1010(co, cfg, amb, rb),
                         descricao=f"Rubrica {cod} — {nome}", ref_tipo="rubrica_extra", ref_id=i))
    return out


def gerar_admissao(conn, cid: int, emp_id: int) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    emp = _funcionario(conn, cid, emp_id)
    ret = _ultimo_aceito(conn, cid, "S-2200", "funcionario", emp_id)
    return _gera(conn, cid, cfg, "S-2200",
                 lambda: ev.s2200(co, cfg, cfg["ambiente"], emp, _dependentes(conn, cid, emp_id), retif=ret),
                 descricao=f"Admissão — {emp.get('name')}", ref_tipo="funcionario", ref_id=emp_id,
                 employee_id=emp_id, retif_de=ret)


def gerar_alteracao_cadastral(conn, cid: int, emp_id: int, dt_alteracao: str) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    emp = _funcionario(conn, cid, emp_id)
    return _gera(conn, cid, cfg, "S-2205",
                 lambda: ev.s2205(co, cfg, cfg["ambiente"], emp, _dependentes(conn, cid, emp_id), dt_alteracao),
                 descricao=f"Alteração cadastral — {emp.get('name')} ({dt_alteracao})", ref_tipo="funcionario",
                 ref_id=emp_id, employee_id=emp_id, per_apur=dt_alteracao[:10])


def gerar_alteracao_contratual(conn, cid: int, emp_id: int, dt_alteracao: str) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    emp = _funcionario(conn, cid, emp_id)
    return _gera(conn, cid, cfg, "S-2206", lambda: ev.s2206(co, cfg, cfg["ambiente"], emp, dt_alteracao),
                 descricao=f"Alteração contratual — {emp.get('name')} ({dt_alteracao})", ref_tipo="funcionario",
                 ref_id=emp_id, employee_id=emp_id, per_apur=dt_alteracao[:10])


def gerar_afastamento(conn, cid: int, absence_id: int) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    ab = _row(conn.execute("SELECT * FROM employee_absences WHERE id = ? AND company_id = ?",
                           (absence_id, cid)).fetchone())
    if not ab:
        raise LookupError("Afastamento não encontrado")
    emp = _funcionario(conn, cid, ab["employee_id"])
    cod = MOTIVO_AFASTAMENTO.get(ab.get("tipo") or "")
    if cod is None:
        raise ValueError("Este tipo de afastamento não é informado no eSocial (faltas legais curtas ou motivo não "
                         "classificado). Use um tipo com código na Tabela 18.")
    ini, fim = ev.data_iso(ab.get("data_inicio")), ev.data_iso(ab.get("data_fim") or ab.get("retorno_efetivo"))
    minimo = DIAS_MINIMOS_AFASTAMENTO.get(cod)
    if minimo and ini and fim and (date.fromisoformat(fim) - date.fromisoformat(ini)).days + 1 < minimo:
        raise ValueError("Afastamento por doença de até 15 dias não é informado no eSocial (fica por conta da empresa).")
    ret = _ultimo_aceito(conn, cid, "S-2230", "afastamento", absence_id)
    return _gera(conn, cid, cfg, "S-2230",
                 lambda: ev.s2230(co, cfg, cfg["ambiente"], emp, cod, ini, fim, ab.get("observacoes") or "", retif=ret),
                 descricao=f"Afastamento — {emp.get('name')} desde {ini}", ref_tipo="afastamento", ref_id=absence_id,
                 employee_id=emp["id"], retif_de=ret)


def gerar_desligamento(conn, cid: int, special_id: int) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    resc = _row(conn.execute("SELECT * FROM payroll_special WHERE id = ? AND company_id = ? AND tipo = 'rescisao'",
                             (special_id, cid)).fetchone())
    if not resc:
        raise LookupError("Rescisão não encontrada")
    emp = _funcionario(conn, cid, resc["employee_id"])
    linhas = [dict(r) for r in conn.execute(
        "SELECT * FROM payroll_special_lines WHERE special_id = ? ORDER BY id", (special_id,)).fetchall()]
    mtv = MOTIVO_DESLIGAMENTO.get(resc.get("referencia") or "", "")
    dt = ev.data_iso(resc.get("data_inicio") or emp.get("termination_date"))
    try:
        params = json.loads(resc.get("params") or "{}")
    except ValueError:
        params = {}
    ret = _ultimo_aceito(conn, cid, "S-2299", "rescisao", special_id)
    return _gera(conn, cid, cfg, "S-2299",
                 lambda: ev.s2299(co, cfg, cfg["ambiente"], emp, mtv, dt, linhas, params.get("data_aviso") or "",
                                  f"RESC{special_id}", retif=ret),
                 descricao=f"Desligamento — {emp.get('name')} em {dt}", ref_tipo="rescisao", ref_id=special_id,
                 employee_id=emp["id"], retif_de=ret)


def _linhas_especial(conn, special_id: int) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM payroll_special_lines WHERE special_id = ? ORDER BY id", (special_id,)).fetchall()]


def _ultimo_dia(per: str) -> str:
    import calendar
    a, m = int(per[:4]), int(per[5:7])
    return f"{per}-{calendar.monthrange(a, m)[1]:02d}"


def ide_dm_dev_folha(tipo: str, per: str, run_id: int) -> str:
    """Identificador do demonstrativo: FOL (mensal e complementar) ou DIS (diferenças de dissídio)."""
    return f"{'DIS' if tipo == 'dissidio' else 'FOL'}{per.replace('-', '')}R{run_id}"


def remuneracoes_do_periodo(conn, cid: int, per: str, ind_apuracao: str = "1") -> Dict[str, Dict[str, Any]]:
    """Todos os valores devidos no período, agrupados por trabalhador (um S-1200 por CPF).

    Mensal (AAAA-MM): folha, férias, adiantamento do 13º, bolsa de estágio e RPA.
    Anual (AAAA): 13º salário (2ª parcela / integral).
    """
    grupos: Dict[str, Dict[str, Any]] = {}

    def add(chave, trab, ref_tipo, ref_id, employee_id, dm):
        g = grupos.setdefault(chave, {"trab": trab, "ref_tipo": ref_tipo, "ref_id": ref_id,
                                      "employee_id": employee_id, "dm_devs": []})
        g["dm_devs"].append(dm)

    def emp_trab(emp):
        return {"cpf": emp.get("cpf"), "nome": emp.get("name"), "dt_nasc": emp.get("birth_date"), "cbo": emp.get("cbo")}

    if ind_apuracao == "2":
        for sp in conn.execute("""SELECT * FROM payroll_special WHERE company_id = ? AND tipo = 'decimo_2'
                                  AND status != 'cancelado' AND (substr(competencia, 1, 4) = ?
                                  OR (COALESCE(competencia, '') = '' AND substr(data_pagamento, 1, 4) = ?))""",
                               (cid, per, per)).fetchall():
            sp = dict(sp)
            emp = _funcionario(conn, cid, sp["employee_id"])
            add(f"E{emp['id']}", emp_trab(emp), "remuneracao", emp["id"], emp["id"],
                {"ide_dm_dev": f"D13{sp['id']}", "cod_categ": emp.get("esocial_category") or "101",
                 "matricula": emp.get("matricula"), "linhas": _linhas_especial(conn, sp["id"])})
        return grupos

    for it in conn.execute("""SELECT pi.*, pr.id AS run, COALESCE(pr.tipo, 'mensal') AS run_tipo, pr.info AS run_info
                              FROM payroll_items pi JOIN payroll_runs pr ON pr.id = pi.run_id
                              WHERE pr.company_id = ? AND pr.competence = ? AND pr.status != 'cancelado'
                                AND COALESCE(pr.tipo, 'mensal') IN ('mensal', 'complementar', 'dissidio')
                              ORDER BY pr.id""",
                           (cid, per)).fetchall():
        it = dict(it)
        emp = _funcionario(conn, cid, it["employee_id"])
        linhas = [dict(r) for r in conn.execute(
            "SELECT * FROM payroll_item_lines WHERE item_id = ? ORDER BY tipo DESC, codigo, id", (it["id"],)).fetchall()]
        if not linhas:
            linhas = [{"codigo": "0001", "tipo": "provento", "referencia": "30d", "valor": it.get("gross_salary")},
                      {"codigo": "0100", "tipo": "desconto", "valor": it.get("inss")},
                      {"codigo": "0101", "tipo": "desconto", "valor": it.get("irrf")}]
        dm = {"ide_dm_dev": ide_dm_dev_folha(it["run_tipo"], per, it["run"]),
              "cod_categ": emp.get("esocial_category") or "101", "matricula": emp.get("matricula"), "linhas": linhas}
        if it["run_tipo"] == "dissidio":
            try:
                dm["per_ant"] = json.loads(it.get("run_info") or "{}")
            except ValueError:
                dm["per_ant"] = {}
        add(f"E{emp['id']}", emp_trab(emp), "remuneracao", emp["id"], emp["id"], dm)

    for sp in conn.execute("""SELECT * FROM payroll_special WHERE company_id = ? AND status != 'cancelado' AND (
                                (tipo = 'ferias' AND COALESCE(NULLIF(substr(competencia, 1, 7), ''), substr(data_inicio, 1, 7)) = ?)
                                OR (tipo = 'decimo_1' AND substr(data_pagamento, 1, 7) = ?))""", (cid, per, per)).fetchall():
        sp = dict(sp)
        emp = _funcionario(conn, cid, sp["employee_id"])
        prefixo = "FER" if sp["tipo"] == "ferias" else "D13A"
        add(f"E{emp['id']}", emp_trab(emp), "remuneracao", emp["id"], emp["id"],
            {"ide_dm_dev": f"{prefixo}{sp['id']}", "cod_categ": emp.get("esocial_category") or "101",
             "matricula": emp.get("matricula"), "linhas": _linhas_especial(conn, sp["id"])})

    ini_mes, fim_mes = f"{per}-01", _ultimo_dia(per)
    for es in conn.execute("""SELECT * FROM interns WHERE company_id = ? AND COALESCE(bolsa_auxilio, 0) > 0
                              AND data_inicio <= ? AND COALESCE(NULLIF(data_termino_real, ''), data_fim, '9999-12-31') >= ?""",
                           (cid, fim_mes, ini_mes)).fetchall():
        es = dict(es)
        add(f"T{es['id']}", {"cpf": es.get("cpf"), "nome": es.get("nome"), "dt_nasc": es.get("data_nascimento")},
            "remuneracao_est", es["id"], 0,
            {"ide_dm_dev": f"EST{per.replace('-', '')}{es['id']}", "cod_categ": "901",
             "matricula": ev.matricula_estagiario(es),
             "linhas": [{"codigo": "0050", "tipo": "provento", "referencia": "1", "valor": es["bolsa_auxilio"]}]})

    for rp in conn.execute("""SELECT r.*, a.nome, a.cpf, a.cbo, a.data_nascimento FROM rpa_payments r
                              JOIN autonomous_workers a ON a.id = r.autonomous_id
                              WHERE r.company_id = ? AND r.competencia = ?""", (cid, per)).fetchall():
        rp = dict(rp)
        linhas = [{"codigo": "0060", "tipo": "provento", "valor": rp.get("valor_bruto")},
                  {"codigo": "0100", "tipo": "desconto", "valor": rp.get("inss_retido")},
                  {"codigo": "0101", "tipo": "desconto", "valor": rp.get("irrf_retido")}]
        add(f"A{rp['autonomous_id']}", {"cpf": rp.get("cpf"), "nome": rp.get("nome"), "dt_nasc": rp.get("data_nascimento"),
                                        "cbo": rp.get("cbo"), "sem_cadastro": True},
            "remuneracao_rpa", rp["autonomous_id"], 0,
            {"ide_dm_dev": f"RPA{rp['id']}", "cod_categ": "701", "linhas": linhas})
    return grupos


def pagamentos_do_periodo(conn, cid: int, per_pg: str) -> Dict[str, Dict[str, Any]]:
    """Pagamentos feitos no mês (um S-1210 por CPF), ligados aos demonstrativos do S-1200/S-2299."""
    grupos: Dict[str, Dict[str, Any]] = {}

    def add(chave, trab, ref_tipo, ref_id, employee_id, pg):
        g = grupos.setdefault(chave, {"trab": trab, "ref_tipo": ref_tipo, "ref_id": ref_id,
                                      "employee_id": employee_id, "pagamentos": []})
        g["pagamentos"].append(pg)

    runs = [dict(r) for r in conn.execute(
        """SELECT * FROM payroll_runs WHERE company_id = ? AND substr(COALESCE(data_pagamento, ''), 1, 7) = ?
           AND status != 'cancelado' AND COALESCE(tipo, 'mensal') IN ('mensal', 'complementar', 'dissidio')""",
        (cid, per_pg)).fetchall()]
    for run in runs:
        for it in conn.execute("SELECT * FROM payroll_items WHERE run_id = ?", (run["id"],)).fetchall():
            it = dict(it)
            emp = _funcionario(conn, cid, it["employee_id"])
            add(f"E{emp['id']}", {"cpf": emp.get("cpf")}, "pagamento", emp["id"], emp["id"],
                {"dt_pgto": run["data_pagamento"], "tp_pgto": "1", "per_ref": run["competence"],
                 "ide_dm_dev": ide_dm_dev_folha(run.get("tipo") or "mensal", run["competence"], run["id"]),
                 "vr_liq": it.get("net_salary")})
        if (run.get("tipo") or "mensal") != "mensal":
            continue  # bolsa de estágio só acompanha a folha mensal
        per = run["competence"]
        for es in conn.execute("""SELECT * FROM interns WHERE company_id = ? AND COALESCE(bolsa_auxilio, 0) > 0
                                  AND data_inicio <= ? AND COALESCE(NULLIF(data_termino_real, ''), data_fim, '9999-12-31') >= ?""",
                               (cid, _ultimo_dia(per), f"{per}-01")).fetchall():
            es = dict(es)
            add(f"T{es['id']}", {"cpf": es.get("cpf")}, "pagamento_est", es["id"], 0,
                {"dt_pgto": run["data_pagamento"], "tp_pgto": "1", "per_ref": per,
                 "ide_dm_dev": f"EST{per.replace('-', '')}{es['id']}", "vr_liq": es["bolsa_auxilio"]})

    for sp in conn.execute("""SELECT * FROM payroll_special WHERE company_id = ? AND status != 'cancelado'
                              AND substr(COALESCE(data_pagamento, ''), 1, 7) = ?""", (cid, per_pg)).fetchall():
        sp = dict(sp)
        emp = _funcionario(conn, cid, sp["employee_id"])
        if sp["tipo"] == "rescisao":
            tp, per_ref, ide = "2", (sp.get("data_inicio") or "")[:7], f"RESC{sp['id']}"
        elif sp["tipo"] == "ferias":
            tp, per_ref, ide = "1", (sp.get("competencia") or sp.get("data_inicio") or "")[:7], f"FER{sp['id']}"
        elif sp["tipo"] == "decimo_1":
            tp, per_ref, ide = "1", per_pg, f"D13A{sp['id']}"
        elif sp["tipo"] == "decimo_2":
            tp, per_ref, ide = "1", (sp.get("competencia") or sp.get("data_pagamento") or "")[:4], f"D13{sp['id']}"
        else:
            continue
        add(f"E{emp['id']}", {"cpf": emp.get("cpf")}, "pagamento", emp["id"], emp["id"],
            {"dt_pgto": sp["data_pagamento"], "tp_pgto": tp, "per_ref": per_ref, "ide_dm_dev": ide,
             "vr_liq": sp.get("liquido")})

    for rp in conn.execute("""SELECT r.*, a.cpf FROM rpa_payments r JOIN autonomous_workers a ON a.id = r.autonomous_id
                              WHERE r.company_id = ? AND substr(COALESCE(r.data_pagamento, ''), 1, 7) = ?""",
                           (cid, per_pg)).fetchall():
        rp = dict(rp)
        add(f"A{rp['autonomous_id']}", {"cpf": rp.get("cpf")}, "pagamento_rpa", rp["autonomous_id"], 0,
            {"dt_pgto": rp["data_pagamento"], "tp_pgto": "1", "per_ref": rp["competencia"],
             "ide_dm_dev": f"RPA{rp['id']}", "vr_liq": rp.get("valor_liquido")})
    return grupos


def gerar_remuneracoes(conn, cid: int, per: str, ind_apuracao: str = "1") -> List[Dict[str, Any]]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    out = []
    for g in remuneracoes_do_periodo(conn, cid, per, ind_apuracao).values():
        ret = _ultimo_aceito(conn, cid, "S-1200", g["ref_tipo"], g["ref_id"], per)
        nome = g["trab"].get("nome") or ""
        rot = "13º salário" if ind_apuracao == "2" else "Remuneração"
        out.append(_gera(conn, cid, cfg, "S-1200",
                         lambda g=g, ret=ret: ev.s1200(co, cfg, cfg["ambiente"], g["trab"], per, g["dm_devs"],
                                                       ind_apuracao, retif=ret),
                         descricao=f"{rot} {per} — {nome}", ref_tipo=g["ref_tipo"], ref_id=g["ref_id"],
                         employee_id=g["employee_id"], per_apur=per, retif_de=ret))
    return out


def gerar_pagamentos(conn, cid: int, per_pg: str) -> List[Dict[str, Any]]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    out = []
    for g in pagamentos_do_periodo(conn, cid, per_pg).values():
        ret = _ultimo_aceito(conn, cid, "S-1210", g["ref_tipo"], g["ref_id"], per_pg)
        nome = ""
        if g["employee_id"]:
            nome = _funcionario(conn, cid, g["employee_id"]).get("name") or ""
        out.append(_gera(conn, cid, cfg, "S-1210",
                         lambda g=g, ret=ret: ev.s1210(co, cfg, cfg["ambiente"], g["trab"], per_pg, g["pagamentos"],
                                                       retif=ret),
                         descricao=f"Pagamentos em {per_pg} — {nome or g['trab'].get('cpf')}", ref_tipo=g["ref_tipo"],
                         ref_id=g["ref_id"], employee_id=g["employee_id"], per_apur=per_pg, retif_de=ret))
    return out


def gerar_folha(conn, cid: int, run_id: int, data_pagamento: str = "") -> List[Dict[str, Any]]:
    """Atalho da tela de folha: S-1200 da competência e, com a data de pagamento, os S-1210 do mês do pagamento."""
    run = _row(conn.execute("SELECT * FROM payroll_runs WHERE id = ? AND company_id = ?", (run_id, cid)).fetchone())
    if not run:
        raise LookupError("Folha não encontrada")
    dt = ev.data_iso(data_pagamento)
    if data_pagamento and not dt:
        raise ValueError("Data de pagamento inválida. Use AAAA-MM-DD.")
    if dt:
        conn.execute("UPDATE payroll_runs SET data_pagamento = ? WHERE id = ?", (dt, run_id))
        conn.commit()
    out = gerar_remuneracoes(conn, cid, run["competence"])
    if dt:
        out += gerar_pagamentos(conn, cid, dt[:7])
    return out


# ─── SST, reintegração e estagiários ──────────────────────────────────────────

def gerar_cat(conn, cid: int, cat_id: int) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    cat = _row(conn.execute("SELECT * FROM work_accidents WHERE id = ? AND company_id = ?", (cat_id, cid)).fetchone())
    if not cat:
        raise LookupError("CAT não encontrada")
    emp = _funcionario(conn, cid, cat["employee_id"])
    ret = _ultimo_aceito(conn, cid, "S-2210", "cat", cat_id)
    return _gera(conn, cid, cfg, "S-2210", lambda: ev.s2210(co, cfg, cfg["ambiente"], emp, cat, retif=ret),
                 descricao=f"CAT — {emp.get('name')} em {cat.get('data_acidente')}", ref_tipo="cat", ref_id=cat_id,
                 employee_id=emp["id"], retif_de=ret)


def gerar_aso(conn, cid: int, exame_id: int) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    aso = _row(conn.execute("SELECT * FROM medical_exams WHERE id = ? AND company_id = ?", (exame_id, cid)).fetchone())
    if not aso:
        raise LookupError("Exame não encontrado")
    emp = _funcionario(conn, cid, aso["employee_id"])
    pc = _row(conn.execute("""SELECT * FROM pcmso_programas WHERE company_id = ? ORDER BY vigencia_inicio DESC, id DESC
                              LIMIT 1""", (cid,)).fetchone())
    resp = {"nome": pc.get("responsavel_nome"), "crm": pc.get("responsavel_crm"), "uf": pc.get("responsavel_uf"),
            "cpf": pc.get("responsavel_cpf")} if pc else None
    ret = _ultimo_aceito(conn, cid, "S-2220", "aso", exame_id)
    return _gera(conn, cid, cfg, "S-2220", lambda: ev.s2220(co, cfg, cfg["ambiente"], emp, aso, resp, retif=ret),
                 descricao=f"ASO {aso.get('tipo')} — {emp.get('name')} em {aso.get('data_exame')}", ref_tipo="aso",
                 ref_id=exame_id, employee_id=emp["id"], retif_de=ret)


def gerar_exposicao(conn, cid: int, expo_id: int) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    expo = _row(conn.execute("SELECT * FROM esocial_exposicoes WHERE id = ? AND company_id = ?", (expo_id, cid)).fetchone())
    if not expo:
        raise LookupError("Condição ambiental não encontrada")
    emp = _funcionario(conn, cid, expo["employee_id"])
    ret = _ultimo_aceito(conn, cid, "S-2240", "exposicao", expo_id)
    return _gera(conn, cid, cfg, "S-2240", lambda: ev.s2240(co, cfg, cfg["ambiente"], emp, expo, retif=ret),
                 descricao=f"Condições ambientais — {emp.get('name')} desde {expo.get('dt_inicio')}",
                 ref_tipo="exposicao", ref_id=expo_id, employee_id=emp["id"], retif_de=ret)


def gerar_reintegracao(conn, cid: int, rein_id: int) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    rein = _row(conn.execute("SELECT * FROM reintegracoes WHERE id = ? AND company_id = ?", (rein_id, cid)).fetchone())
    if not rein:
        raise LookupError("Reintegração não encontrada")
    emp = _funcionario(conn, cid, rein["employee_id"])
    ret = _ultimo_aceito(conn, cid, "S-2298", "reintegracao", rein_id)
    return _gera(conn, cid, cfg, "S-2298", lambda: ev.s2298(co, cfg, cfg["ambiente"], emp, rein, retif=ret),
                 descricao=f"Reintegração — {emp.get('name')} em {rein.get('data_reintegracao')}",
                 ref_tipo="reintegracao", ref_id=rein_id, employee_id=emp["id"], retif_de=ret)


def _estagiario(conn, cid, intern_id) -> Dict[str, Any]:
    es = _row(conn.execute("SELECT * FROM interns WHERE id = ? AND company_id = ?", (intern_id, cid)).fetchone())
    if not es:
        raise LookupError("Estagiário não encontrado")
    if not es.get("matricula"):
        conn.execute("UPDATE interns SET matricula = ? WHERE id = ?", (ev.matricula_estagiario(es), intern_id))
        conn.commit()
        es["matricula"] = ev.matricula_estagiario(es)
    return es


def gerar_estagio_inicio(conn, cid: int, intern_id: int) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    es = _estagiario(conn, cid, intern_id)
    ret = _ultimo_aceito(conn, cid, "S-2300", "estagiario", intern_id)
    return _gera(conn, cid, cfg, "S-2300", lambda: ev.s2300(co, cfg, cfg["ambiente"], es, retif=ret),
                 descricao=f"Início de estágio — {es.get('nome')}", ref_tipo="estagiario", ref_id=intern_id,
                 retif_de=ret)


def gerar_estagio_termino(conn, cid: int, intern_id: int, dt_term: str = "") -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    es = _estagiario(conn, cid, intern_id)
    dt = ev.data_iso(dt_term) or ev.data_iso(es.get("data_termino_real")) or ev.data_iso(es.get("data_fim"))
    if dt and dt != es.get("data_termino_real"):
        conn.execute("UPDATE interns SET data_termino_real = ? WHERE id = ?", (dt, intern_id))
        conn.commit()
    ret = _ultimo_aceito(conn, cid, "S-2399", "estagiario", intern_id)
    return _gera(conn, cid, cfg, "S-2399", lambda: ev.s2399(co, cfg, cfg["ambiente"], es, dt, retif=ret),
                 descricao=f"Término de estágio — {es.get('nome')} em {dt}", ref_tipo="estagiario", ref_id=intern_id,
                 retif_de=ret)


def gerar_fechamento(conn, cid: int, per_apur: str) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    q = "SELECT COUNT(*) AS n FROM esocial_eventos WHERE company_id = ? AND tipo = ? AND per_apur = ? AND status = 'aceito'"
    tem_remun = (conn.execute(q, (cid, "S-1200", per_apur)).fetchone()["n"] > 0
                 or conn.execute("""SELECT COUNT(*) AS n FROM esocial_eventos WHERE company_id = ? AND tipo = 'S-2299'
                                    AND substr(per_apur, 1, 7) = ? AND status = 'aceito'""",
                                 (cid, per_apur)).fetchone()["n"] > 0)
    tem_pgtos = conn.execute(q, (cid, "S-1210", per_apur)).fetchone()["n"] > 0
    return _gera(conn, cid, cfg, "S-1299",
                 lambda: ev.s1299(co, cfg, cfg["ambiente"], per_apur, tem_remun, tem_pgtos),
                 descricao=f"Fechamento da competência {per_apur}", ref_tipo="competencia", ref_id=0, per_apur=per_apur)


def gerar_reabertura(conn, cid: int, per_apur: str) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    return _gera(conn, cid, cfg, "S-1298", lambda: ev.s1298(co, cfg, cfg["ambiente"], per_apur),
                 descricao=f"Reabertura da competência {per_apur}", ref_tipo="competencia_reab", ref_id=0,
                 per_apur=per_apur)


def gerar_exclusao(conn, cid: int, evento_row_id: int) -> Dict[str, Any]:
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    alvo = _row(conn.execute("SELECT * FROM esocial_eventos WHERE id = ? AND company_id = ?",
                             (evento_row_id, cid)).fetchone())
    if not alvo or alvo.get("status") != "aceito" or not alvo.get("nr_recibo"):
        raise ValueError("Só é possível excluir evento aceito pelo eSocial (com número de recibo).")
    if alvo["tipo"] in ("S-1000", "S-1005", "S-1010", "S-1020", "S-1298", "S-1299", "S-3000"):
        raise ValueError(f"O {alvo['tipo']} não é excluído pelo S-3000 (tabelas usam a operação de exclusão própria).")
    cpf = ""
    if alvo.get("employee_id"):
        cpf = _funcionario(conn, cid, alvo["employee_id"]).get("cpf") or ""
    elif alvo.get("referencia_tipo") == "estagiario":
        cpf = _estagiario(conn, cid, alvo["referencia_id"]).get("cpf") or ""
    return _gera(conn, cid, cfg, "S-3000",
                 lambda: ev.s3000(co, cfg, cfg["ambiente"], alvo["tipo"], alvo["nr_recibo"], cpf, alvo.get("per_apur") or "",
                                  "2" if len(alvo.get("per_apur") or "") == 4 else "1"),
                 descricao=f"Exclusão do {alvo['tipo']} — {alvo.get('descricao')}", ref_tipo="exclusao",
                 ref_id=alvo["id"], employee_id=alvo.get("employee_id") or 0)


REGERADORES = {
    "funcionario:S-2200": lambda conn, cid, r: gerar_admissao(conn, cid, r["referencia_id"]),
    "afastamento:S-2230": lambda conn, cid, r: gerar_afastamento(conn, cid, r["referencia_id"]),
    "rescisao:S-2299": lambda conn, cid, r: gerar_desligamento(conn, cid, r["referencia_id"]),
    "cat:S-2210": lambda conn, cid, r: gerar_cat(conn, cid, r["referencia_id"]),
    "aso:S-2220": lambda conn, cid, r: gerar_aso(conn, cid, r["referencia_id"]),
    "exposicao:S-2240": lambda conn, cid, r: gerar_exposicao(conn, cid, r["referencia_id"]),
    "reintegracao:S-2298": lambda conn, cid, r: gerar_reintegracao(conn, cid, r["referencia_id"]),
    "estagiario:S-2300": lambda conn, cid, r: gerar_estagio_inicio(conn, cid, r["referencia_id"]),
    "estagiario:S-2399": lambda conn, cid, r: gerar_estagio_termino(conn, cid, r["referencia_id"]),
}


def retificar(conn, cid: int, evento_row_id: int) -> Dict[str, Any]:
    """Gera de novo o evento com os dados atuais, como retificação do recibo aceito."""
    r = _row(conn.execute("SELECT * FROM esocial_eventos WHERE id = ? AND company_id = ?",
                          (evento_row_id, cid)).fetchone())
    if not r or r.get("status") != "aceito":
        raise ValueError("Só é possível retificar evento aceito pelo eSocial.")
    chave = f"{r['referencia_tipo']}:{r['tipo']}"
    if chave in REGERADORES:
        return REGERADORES[chave](conn, cid, r)
    if r["tipo"] in ("S-1200", "S-1210"):
        per = r.get("per_apur") or ""
        if r["tipo"] == "S-1200":
            res = gerar_remuneracoes(conn, cid, per, "2" if len(per) == 4 else "1")
        else:
            res = gerar_pagamentos(conn, cid, per)
        alvo = next((x for x in res if x.get("descricao", "").endswith(r.get("descricao", "").split(" — ")[-1])), None)
        if not res:
            raise ValueError("Nada para retificar: os valores de origem não foram encontrados.")
        return alvo or res[0]
    raise ValueError(f"Retificação do {r['tipo']} não disponível; gere o evento novamente.")


def revalidar(conn, cid: int, evento_row_id: int) -> Dict[str, Any]:
    r = _row(conn.execute("SELECT * FROM esocial_eventos WHERE id = ? AND company_id = ?",
                          (evento_row_id, cid)).fetchone())
    if not r or not r.get("xml"):
        raise ValueError("Evento sem XML para validar")
    erros = _valida(r["xml"], r["tipo"], None)
    status = "erro_validacao" if erros else ("pendente" if r["status"] in _ABERTOS else r["status"])
    conn.execute("UPDATE esocial_eventos SET erros = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                 (json.dumps(erros, ensure_ascii=False) if erros else "", status, r["id"]))
    conn.commit()
    return {"id": r["id"], "status": status, "erros": erros}


def xml_assinado(conn, cid: int, evento_row_id: int) -> Tuple[str, bool]:
    """XML para download: assinado com o A1 quando houver; senão com o certificado de teste."""
    r = _row(conn.execute("SELECT * FROM esocial_eventos WHERE id = ? AND company_id = ?",
                          (evento_row_id, cid)).fetchone())
    if not r or not r.get("xml"):
        raise LookupError("Evento sem XML")
    par = None
    try:
        par = carregar_certificado(empresa(conn, cid))
    except Exception:  # noqa: BLE001
        par = None
    key, cert = par or certificado_teste()
    return assinar(r["xml"], key, cert), bool(par)


# ─── transmissão ──────────────────────────────────────────────────────────────

def _cliente(conn, cid, cfg, transporte=None) -> Tuple[ClienteESocial, Tuple[Any, Any]]:
    co = empresa(conn, cid)
    try:
        par = carregar_certificado(co)
    except Exception as exc:  # noqa: BLE001
        raise SemCertificado(f"Não foi possível abrir o certificado A1: {exc}") from exc
    if not par:
        raise SemCertificado("Para transmitir é preciso cadastrar o certificado digital A1 da empresa "
                             "(Empresa → Fiscal → Certificado A1).")
    if certificado_info(par[1])["vencido"]:
        raise SemCertificado("O certificado A1 cadastrado está vencido.")
    ctx = None if transporte else contexto_tls(*par)
    return ClienteESocial(cfg["ambiente"], ctx, transporte=transporte), par


def transmitir(conn, cid: int, ids: Optional[List[int]] = None, transporte=None) -> Dict[str, Any]:
    """Assina e envia os eventos prontos, em lotes de até 50 por grupo (tabelas → não periódicos → periódicos)."""
    cfg, co = obter_config(conn, cid), empresa(conn, cid)
    cli, (key, cert) = _cliente(conn, cid, cfg, transporte)
    sql = "SELECT * FROM esocial_eventos WHERE company_id = ? AND status IN ('pendente','erro_envio') AND xml != ''"
    params: List[Any] = [cid]
    if ids:
        sql += f" AND id IN ({','.join('?' for _ in ids)})"
        params += list(ids)
    pendentes = [dict(r) for r in conn.execute(sql + " ORDER BY grupo, id", params).fetchall()]
    transmissor = {"tp_insc": cfg.get("transmissor_tp_insc") or "1",
                   "nr_insc": ev.digitos(cfg.get("transmissor_nr_insc")) or ev.digitos(co.get("cnpj"))}
    lotes = []
    for grupo in (1, 2, 3):
        do_grupo = [p for p in pendentes if p["grupo"] == grupo]
        for i in range(0, len(do_grupo), MAX_EVENTOS_LOTE):
            bloco = do_grupo[i:i + MAX_EVENTOS_LOTE]
            assinados = [{"id": p["evento_id"], "xml": assinar(p["xml"], key, cert)} for p in bloco]
            lote_xml = montar_lote(grupo, ev.nr_insc_empregador(co), transmissor, assinados)
            erros = validar_lote(lote_xml)
            if erros:
                raise ValueError("Lote inválido: " + "; ".join(erros[:3]))
            try:
                ret = cli.enviar_lote(lote_xml)
            except ErroComunicacao as exc:
                ret = {"cd_resposta": "", "desc_resposta": str(exc), "ocorrencias": [], "protocolo": "", "xml": ""}
            ok = ret["cd_resposta"] == "201" and ret["protocolo"]
            cur = conn.execute("""
                INSERT INTO esocial_lotes (company_id, grupo, ambiente, protocolo, status, cd_resposta, desc_resposta,
                    ocorrencias, qtd_eventos, xml_retorno_envio)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (cid, grupo, cfg["ambiente"], ret["protocolo"], "enviado" if ok else "erro", ret["cd_resposta"],
                 ret["desc_resposta"], json.dumps(ret["ocorrencias"], ensure_ascii=False), len(bloco), ret["xml"]))
            lote_id = cur.lastrowid
            for p in bloco:
                conn.execute("""UPDATE esocial_eventos SET status = ?, lote_id = ?, cd_resposta = ?, desc_resposta = ?,
                                ambiente = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                             ("enviado" if ok else "erro_envio", lote_id, ret["cd_resposta"], ret["desc_resposta"],
                              cfg["ambiente"], p["id"]))
            conn.commit()
            lotes.append({"lote_id": lote_id, "grupo": grupo, "eventos": len(bloco), "ok": bool(ok),
                          "protocolo": ret["protocolo"], "mensagem": ret["desc_resposta"],
                          "ocorrencias": ret["ocorrencias"]})
    return {"lotes": lotes, "enviados": sum(x["eventos"] for x in lotes if x["ok"])}


def consultar(conn, cid: int, lote_id: Optional[int] = None, transporte=None) -> Dict[str, Any]:
    """Consulta os lotes enviados e grava recibos, ocorrências e totalizadores devolvidos."""
    cfg = obter_config(conn, cid)
    cli, _par = _cliente(conn, cid, cfg, transporte)
    sql = "SELECT * FROM esocial_lotes WHERE company_id = ? AND status = 'enviado'"
    params: List[Any] = [cid]
    if lote_id:
        sql += " AND id = ?"
        params.append(lote_id)
    resumo = []
    for lote in [dict(r) for r in conn.execute(sql, params).fetchall()]:
        try:
            ret = cli.consultar_lote(lote["protocolo"])
        except ErroComunicacao as exc:
            resumo.append({"lote_id": lote["id"], "status": "erro", "mensagem": str(exc)})
            continue
        if ret["cd_resposta"] == "101":
            resumo.append({"lote_id": lote["id"], "status": "aguardando", "mensagem": ret["desc_resposta"],
                           "tempo_estimado": ret["tempo_estimado"]})
            continue
        aceitos = rejeitados = 0
        for item in ret["eventos"]:
            row = _row(conn.execute("SELECT * FROM esocial_eventos WHERE company_id = ? AND evento_id = ? AND lote_id = ?",
                                    (cid, item["id"], lote["id"])).fetchone())
            if not row:
                continue
            aceito = item["cd_resposta"] in ("201", "202") and item["nr_recibo"]
            aceitos += bool(aceito)
            rejeitados += not aceito
            conn.execute("""UPDATE esocial_eventos SET status = ?, nr_recibo = ?, cd_resposta = ?, desc_resposta = ?,
                            ocorrencias = ?, retorno_xml = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                         ("aceito" if aceito else "rejeitado", item["nr_recibo"], item["cd_resposta"],
                          item["desc_resposta"], json.dumps(item["ocorrencias"], ensure_ascii=False),
                          item["retorno_xml"], row["id"]))
            if aceito and row.get("nr_recibo_orig"):
                conn.execute("""UPDATE esocial_eventos SET status = 'substituido' WHERE company_id = ?
                                AND nr_recibo = ? AND status = 'aceito'""", (cid, row["nr_recibo_orig"]))
            if aceito and row["tipo"] == "S-3000" and row.get("referencia_id"):
                conn.execute("UPDATE esocial_eventos SET status = 'excluido' WHERE id = ? AND company_id = ?",
                             (row["referencia_id"], cid))
            for tot in item["totalizadores"]:
                conn.execute("""INSERT INTO esocial_totalizadores (company_id, evento_origem_id, tipo, per_apur,
                                employee_id, xml) VALUES (?,?,?,?,?,?)""",
                             (cid, row["id"], _tipo_tot(tot["tipo"]), row.get("per_apur") or "",
                              row.get("employee_id") or 0, tot["xml"]))
        conn.execute("""UPDATE esocial_lotes SET status = 'processado', cd_resposta = ?, desc_resposta = ?,
                        ocorrencias = ?, xml_retorno_proc = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                     (ret["cd_resposta"], ret["desc_resposta"], json.dumps(ret["ocorrencias"], ensure_ascii=False),
                      ret["xml"], lote["id"]))
        conn.commit()
        resumo.append({"lote_id": lote["id"], "status": "processado", "mensagem": ret["desc_resposta"],
                       "aceitos": aceitos, "rejeitados": rejeitados})
    return {"lotes": resumo}


def _tipo_tot(tipo: str) -> str:
    """Retorno traz o tipo como "S5001"; padronizamos como "S-5001"."""
    t = (tipo or "").upper()
    return f"S-{t[1:]}" if len(t) == 5 and t.startswith("S") and t[1:].isdigit() else t


# ─── consultas para a tela ────────────────────────────────────────────────────

def painel(conn, cid: int, filtros: Dict[str, Any]) -> Dict[str, Any]:
    sql = """SELECT e.id, e.tipo, e.grupo, e.descricao, e.status, e.erros, e.per_apur, e.employee_id, e.nr_recibo,
                    e.cd_resposta, e.desc_resposta, e.ocorrencias, e.ind_retif, e.lote_id, e.ambiente, e.created_at,
                    e.updated_at, CASE WHEN COALESCE(e.xml, '') != '' THEN 1 ELSE 0 END AS tem_xml, emp.name AS funcionario
             FROM esocial_eventos e LEFT JOIN employees emp ON emp.id = e.employee_id
             WHERE e.company_id = ?"""
    params: List[Any] = [cid]
    if filtros.get("status"):
        sql += " AND e.status = ?"
        params.append(filtros["status"])
    if filtros.get("tipo"):
        sql += " AND e.tipo = ?"
        params.append(filtros["tipo"])
    if filtros.get("per_apur"):
        sql += " AND e.per_apur LIKE ?"
        params.append(filtros["per_apur"] + "%")
    rows = [dict(r) for r in conn.execute(sql + " ORDER BY e.id DESC LIMIT 500", params).fetchall()]
    for r in rows:
        r["erros"] = json.loads(r["erros"]) if r.get("erros") else []
        r["ocorrencias"] = json.loads(r["ocorrencias"]) if r.get("ocorrencias") else []
        r["status_nome"] = STATUS.get(r["status"], r["status"])
    contagem = {k: 0 for k in STATUS}
    for c in conn.execute("SELECT status, COUNT(*) AS n FROM esocial_eventos WHERE company_id = ? GROUP BY status",
                          (cid,)).fetchall():
        contagem[c["status"]] = c["n"]
    return {"eventos": rows, "contagem": contagem}


def conferencia_fgts(conn, cid: int, per_apur: str) -> Dict[str, Any]:
    """FGTS esperado na guia (GFD) da competência, por funcionário, a partir da folha processada."""
    itens = [dict(r) for r in conn.execute("""
        SELECT pi.employee_id, e.name, e.cpf, e.matricula, e.esocial_category, pi.base_fgts, pi.fgts, pi.gross_salary
        FROM payroll_items pi JOIN payroll_runs pr ON pr.id = pi.run_id JOIN employees e ON e.id = pi.employee_id
        WHERE pr.company_id = ? AND pr.competence = ? ORDER BY e.name""", (cid, per_apur)).fetchall()]
    rescisoes = [dict(r) for r in conn.execute("""
        SELECT ps.employee_id, e.name, e.cpf, ps.fgts, ps.multa_fgts FROM payroll_special ps
        JOIN employees e ON e.id = ps.employee_id
        WHERE ps.company_id = ? AND ps.tipo = 'rescisao' AND substr(ps.data_inicio, 1, 7) = ? AND ps.status != 'cancelado'""",
        (cid, per_apur)).fetchall()]
    enviados = {r["employee_id"]: r["status"] for r in conn.execute("""
        SELECT employee_id, status FROM esocial_eventos WHERE company_id = ? AND tipo = 'S-1200' AND per_apur = ?
        ORDER BY id""", (cid, per_apur)).fetchall()}
    linhas = []
    for it in itens:
        base = float(it.get("base_fgts") or it.get("gross_salary") or 0)
        aliq = 0.02 if str(it.get("esocial_category") or "") == "103" else 0.08
        linhas.append({"employee_id": it["employee_id"], "nome": it["name"], "cpf": it["cpf"],
                       "matricula": it.get("matricula"), "base": round(base, 2), "aliquota": aliq,
                       "fgts_folha": round(float(it.get("fgts") or 0), 2), "fgts_calculado": round(base * aliq, 2),
                       "status_s1200": STATUS.get(enviados.get(it["employee_id"], ""), "Não gerado")})
    total_mensal = round(sum(x["fgts_folha"] for x in linhas), 2)
    total_resc = round(sum(float(r.get("fgts") or 0) + float(r.get("multa_fgts") or 0) for r in rescisoes), 2)
    totalizador = _row(conn.execute("""SELECT xml FROM esocial_totalizadores WHERE company_id = ? AND tipo = 'S-5013'
                                       AND per_apur = ? ORDER BY id DESC LIMIT 1""", (cid, per_apur)).fetchone())
    return {"competencia": per_apur, "funcionarios": linhas, "rescisoes": rescisoes,
            "total_mensal": total_mensal, "total_rescisorio": total_resc,
            "total_guia_estimado": round(total_mensal + total_resc, 2),
            "s5013_recebido": bool(totalizador),
            "todos_s1200_aceitos": bool(linhas) and all(x["status_s1200"] == STATUS["aceito"] for x in linhas)}

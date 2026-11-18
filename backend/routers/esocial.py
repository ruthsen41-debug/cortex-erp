"""Central do eSocial: configuração, geração de eventos S-1.3, fila, transmissão e retornos."""
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response

try:
    from ..auth import get_current_user
    from ..database import get_conn
    from ..services.esocial import complementos, servico
    from ..services.esocial.tabelas import AMBIENTES, CLASS_TRIB, MOTIVO_AFASTAMENTO, NOMES_EVENTOS
except ImportError:
    from auth import get_current_user
    from database import get_conn
    from services.esocial import complementos, servico
    from services.esocial.tabelas import AMBIENTES, CLASS_TRIB, MOTIVO_AFASTAMENTO, NOMES_EVENTOS

router = APIRouter(prefix="/api/esocial", tags=["eSocial"])

_RE_COMP = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _cid(user: Dict[str, Any]) -> int:
    return int(user.get("company_id", 1))


def _executa(fn, *args, **kwargs):
    """Abre conexão, executa e traduz erros de negócio em respostas HTTP claras."""
    conn = get_conn()
    try:
        return fn(conn, *args, **kwargs)
    except servico.SemCertificado as exc:
        raise HTTPException(status_code=412, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()


def _comp(valor: str) -> str:
    if not _RE_COMP.match(valor or ""):
        raise HTTPException(status_code=400, detail="Competência inválida. Use AAAA-MM.")
    return valor


# ─── configuração ─────────────────────────────────────────────────────────────

@router.get("/config")
def ler_config(user=Depends(get_current_user)):
    cid = _cid(user)
    cfg = _executa(servico.obter_config, cid)
    cert = _executa(servico.status_certificado, cid)
    return {"config": cfg, "certificado": cert, "ambientes": AMBIENTES, "class_trib": CLASS_TRIB,
            "eventos": NOMES_EVENTOS}


@router.put("/config")
def gravar_config(dados: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    return {"config": _executa(servico.salvar_config, _cid(user), dados)}


# ─── painel / fila ────────────────────────────────────────────────────────────

@router.get("/painel")
def painel(status: str = "", tipo: str = "", per_apur: str = "", user=Depends(get_current_user)):
    return _executa(servico.painel, _cid(user), {"status": status, "tipo": tipo, "per_apur": per_apur})


@router.get("/origens")
def origens(user=Depends(get_current_user)):
    """Dados para os seletores da tela: funcionários, afastamentos, rescisões e folhas."""
    cid = _cid(user)

    def carregar(conn):
        s2200 = {r["employee_id"]: r["status"] for r in conn.execute(
            "SELECT employee_id, status FROM esocial_eventos WHERE company_id = ? AND tipo = 'S-2200' ORDER BY id",
            (cid,)).fetchall()}
        funcionarios = [{**dict(r), "status_s2200": servico.STATUS.get(s2200.get(r["id"], ""), "Não gerado")}
                        for r in conn.execute("""SELECT id, name, matricula, admission_date, active FROM employees
                                                 WHERE company_id = ? ORDER BY name""", (cid,)).fetchall()]
        afast = [dict(r) for r in conn.execute("""
            SELECT a.id, a.tipo, a.data_inicio, a.data_fim, e.name FROM employee_absences a
            JOIN employees e ON e.id = a.employee_id WHERE a.company_id = ? ORDER BY a.data_inicio DESC LIMIT 200""",
            (cid,)).fetchall()]
        for a in afast:
            a["codigo_esocial"] = MOTIVO_AFASTAMENTO.get(a["tipo"] or "")
        resc = [dict(r) for r in conn.execute("""
            SELECT ps.id, ps.referencia, ps.data_inicio, e.name FROM payroll_special ps
            JOIN employees e ON e.id = ps.employee_id
            WHERE ps.company_id = ? AND ps.tipo = 'rescisao' AND ps.status != 'cancelado' ORDER BY ps.id DESC LIMIT 200""",
            (cid,)).fetchall()]
        folhas = [dict(r) for r in conn.execute("""SELECT id, competence, COALESCE(tipo, 'mensal') AS tipo,
            employee_count, status FROM payroll_runs WHERE company_id = ? ORDER BY competence DESC LIMIT 36""",
            (cid,)).fetchall()]
        def lista(sql):
            return [dict(r) for r in conn.execute(sql, (cid,)).fetchall()]
        cats = lista("""SELECT w.id, w.data_acidente, e.name FROM work_accidents w JOIN employees e ON e.id = w.employee_id
                        WHERE w.company_id = ? ORDER BY w.data_acidente DESC LIMIT 200""")
        asos = lista("""SELECT m.id, m.tipo, m.data_exame, e.name FROM medical_exams m JOIN employees e ON e.id = m.employee_id
                        WHERE m.company_id = ? ORDER BY m.data_exame DESC LIMIT 300""")
        expos = lista("""SELECT x.id, x.dt_inicio, x.dsc_setor, e.name FROM esocial_exposicoes x
                         JOIN employees e ON e.id = x.employee_id WHERE x.company_id = ? ORDER BY x.id DESC LIMIT 300""")
        reints = lista("""SELECT r.id, r.data_reintegracao, e.name FROM reintegracoes r JOIN employees e ON e.id = r.employee_id
                          WHERE r.company_id = ? ORDER BY r.id DESC LIMIT 100""")
        estags = lista("""SELECT id, nome, data_inicio, data_fim, status FROM interns WHERE company_id = ? ORDER BY nome""")
        autonomos = lista("""SELECT id, nome, cpf FROM autonomous_workers WHERE company_id = ? ORDER BY nome""")
        pcmso = lista("""SELECT id, ano, responsavel_nome FROM pcmso_programas WHERE company_id = ?
                         ORDER BY vigencia_inicio DESC, id DESC LIMIT 5""")
        return {"funcionarios": funcionarios, "afastamentos": afast, "rescisoes": resc, "folhas": folhas,
                "cats": cats, "asos": asos, "exposicoes": expos, "reintegracoes": reints, "estagiarios": estags,
                "autonomos": autonomos, "pcmso": pcmso}

    return _executa(carregar)


# ─── geração ──────────────────────────────────────────────────────────────────

@router.post("/gerar/tabelas")
def gerar_tabelas(user=Depends(get_current_user)):
    return {"eventos": _executa(servico.gerar_tabelas, _cid(user))}


@router.post("/gerar/admissao/{emp_id}")
def gerar_admissao(emp_id: int, user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_admissao, _cid(user), emp_id)]}


@router.post("/gerar/admissoes")
def gerar_admissoes(user=Depends(get_current_user)):
    """S-2200 de todos os funcionários ativos que ainda não têm admissão aceita."""
    cid = _cid(user)

    def lote(conn):
        aceitos = {r["employee_id"] for r in conn.execute(
            "SELECT employee_id FROM esocial_eventos WHERE company_id = ? AND tipo = 'S-2200' AND status IN ('aceito','enviado')",
            (cid,)).fetchall()}
        ids = [r["id"] for r in conn.execute("SELECT id FROM employees WHERE company_id = ? AND COALESCE(active, 1) = 1",
                                             (cid,)).fetchall() if r["id"] not in aceitos]
        return [servico.gerar_admissao(conn, cid, i) for i in ids]

    return {"eventos": _executa(lote)}


@router.post("/gerar/alteracao-cadastral/{emp_id}")
def gerar_alteracao_cadastral(emp_id: int, dados: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_alteracao_cadastral, _cid(user), emp_id, str(dados.get("data") or ""))]}


@router.post("/gerar/alteracao-contratual/{emp_id}")
def gerar_alteracao_contratual(emp_id: int, dados: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_alteracao_contratual, _cid(user), emp_id, str(dados.get("data") or ""))]}


@router.post("/gerar/afastamento/{absence_id}")
def gerar_afastamento(absence_id: int, user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_afastamento, _cid(user), absence_id)]}


@router.post("/gerar/desligamento/{special_id}")
def gerar_desligamento(special_id: int, user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_desligamento, _cid(user), special_id)]}


@router.post("/gerar/folha/{run_id}")
def gerar_folha(run_id: int, dados: Dict[str, Any] = Body(default={}), user=Depends(get_current_user)):
    return {"eventos": _executa(servico.gerar_folha, _cid(user), run_id, str(dados.get("data_pagamento") or ""))}


@router.post("/gerar/remuneracoes")
def gerar_remuneracoes(dados: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    """S-1200 de todos os trabalhadores do período: mensal (AAAA-MM) ou 13º salário anual (AAAA)."""
    per = str(dados.get("per_apur") or "")
    if re.fullmatch(r"\d{4}", per):
        return {"eventos": _executa(servico.gerar_remuneracoes, _cid(user), per, "2")}
    return {"eventos": _executa(servico.gerar_remuneracoes, _cid(user), _comp(per), "1")}


@router.post("/gerar/pagamentos")
def gerar_pagamentos(dados: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    """S-1210 de todos os pagamentos feitos no mês (folha, férias, 13º, rescisões, RPA)."""
    return {"eventos": _executa(servico.gerar_pagamentos, _cid(user), _comp(str(dados.get("per_apur") or "")))}


@router.post("/gerar/cat/{rid}")
def gerar_cat(rid: int, user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_cat, _cid(user), rid)]}


@router.post("/gerar/aso/{rid}")
def gerar_aso(rid: int, user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_aso, _cid(user), rid)]}


@router.post("/gerar/exposicao/{rid}")
def gerar_exposicao(rid: int, user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_exposicao, _cid(user), rid)]}


@router.post("/gerar/reintegracao/{rid}")
def gerar_reintegracao(rid: int, user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_reintegracao, _cid(user), rid)]}


@router.post("/gerar/estagio-inicio/{rid}")
def gerar_estagio_inicio(rid: int, user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_estagio_inicio, _cid(user), rid)]}


@router.post("/gerar/estagio-termino/{rid}")
def gerar_estagio_termino(rid: int, dados: Dict[str, Any] = Body(default={}), user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_estagio_termino, _cid(user), rid, str(dados.get("data") or ""))]}


# ─── complementos e tabelas oficiais ──────────────────────────────────────────

@router.get("/complementos/{tipo}/{rid}")
def ler_complementos(tipo: str, rid: int, user=Depends(get_current_user)):
    return _executa(complementos.ler, _cid(user), tipo, rid)


@router.put("/complementos/{tipo}/{rid}")
def gravar_complementos(tipo: str, rid: int, dados: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    return _executa(complementos.gravar, _cid(user), tipo, rid, dados)


@router.post("/exposicoes")
def criar_exposicao(dados: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    rid = _executa(complementos.criar_exposicao, _cid(user), int(dados.get("employee_id") or 0))
    return {"id": rid}


@router.delete("/exposicoes/{rid}")
def apagar_exposicao(rid: int, user=Depends(get_current_user)):
    cid = _cid(user)

    def apagar(conn):
        conn.execute("DELETE FROM esocial_exposicoes WHERE id = ? AND company_id = ?", (rid, cid))
        conn.commit()
        return {"ok": True}

    return _executa(apagar)


@router.get("/tabelas/{nums}")
def buscar_tabela(nums: str, q: str = "", user=Depends(get_current_user)):
    return complementos.buscar(nums, q)


@router.post("/gerar/fechamento")
def gerar_fechamento(dados: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_fechamento, _cid(user), _comp(str(dados.get("per_apur") or "")))]}


@router.post("/gerar/reabertura")
def gerar_reabertura(dados: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.gerar_reabertura, _cid(user), _comp(str(dados.get("per_apur") or "")))]}


# ─── ações sobre eventos ──────────────────────────────────────────────────────

@router.post("/eventos/{evento_id}/excluir")
def excluir_no_esocial(evento_id: int, user=Depends(get_current_user)):
    """Gera o S-3000 para excluir no eSocial um evento já aceito."""
    return {"eventos": [_executa(servico.gerar_exclusao, _cid(user), evento_id)]}


@router.post("/eventos/{evento_id}/retificar")
def retificar(evento_id: int, user=Depends(get_current_user)):
    return {"eventos": [_executa(servico.retificar, _cid(user), evento_id)]}


@router.post("/eventos/{evento_id}/validar")
def validar(evento_id: int, user=Depends(get_current_user)):
    return _executa(servico.revalidar, _cid(user), evento_id)


@router.delete("/eventos/{evento_id}")
def descartar(evento_id: int, user=Depends(get_current_user)):
    """Remove da fila um evento que ainda não foi enviado."""
    cid = _cid(user)

    def apagar(conn):
        r = conn.execute("SELECT status FROM esocial_eventos WHERE id = ? AND company_id = ?", (evento_id, cid)).fetchone()
        if not r:
            raise LookupError("Evento não encontrado")
        if dict(r)["status"] not in ("pendente", "erro_validacao", "erro_envio"):
            raise ValueError("Evento já enviado não pode ser descartado; use a exclusão (S-3000).")
        conn.execute("DELETE FROM esocial_eventos WHERE id = ? AND company_id = ?", (evento_id, cid))
        conn.commit()
        return {"ok": True}

    return _executa(apagar)


@router.get("/eventos/{evento_id}/xml")
def baixar_xml(evento_id: int, user=Depends(get_current_user)):
    xml, com_a1 = _executa(servico.xml_assinado, _cid(user), evento_id)
    nome = f"evento-{evento_id}{'' if com_a1 else '-assinatura-de-teste'}.xml"
    return Response(content='<?xml version="1.0" encoding="UTF-8"?>\n' + xml, media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/eventos/{evento_id}/retorno")
def ver_retorno(evento_id: int, user=Depends(get_current_user)):
    cid = _cid(user)

    def ler(conn):
        r = conn.execute("SELECT retorno_xml FROM esocial_eventos WHERE id = ? AND company_id = ?",
                         (evento_id, cid)).fetchone()
        if not r or not dict(r)["retorno_xml"]:
            raise LookupError("Evento sem retorno do eSocial")
        return dict(r)["retorno_xml"]

    return Response(content=_executa(ler), media_type="application/xml")


# ─── transmissão ──────────────────────────────────────────────────────────────

@router.post("/transmitir")
def transmitir(dados: Dict[str, Any] = Body(default={}), user=Depends(get_current_user)):
    ids: Optional[List[int]] = [int(i) for i in dados.get("ids") or []] or None
    return _executa(servico.transmitir, _cid(user), ids)


@router.post("/consultar")
def consultar(dados: Dict[str, Any] = Body(default={}), user=Depends(get_current_user)):
    return _executa(servico.consultar, _cid(user), dados.get("lote_id"))


@router.get("/lotes")
def lotes(user=Depends(get_current_user)):
    cid = _cid(user)
    return _executa(lambda conn: [dict(r) for r in conn.execute(
        """SELECT id, grupo, ambiente, protocolo, status, cd_resposta, desc_resposta, qtd_eventos, created_at, updated_at
           FROM esocial_lotes WHERE company_id = ? ORDER BY id DESC LIMIT 100""", (cid,)).fetchall()])


# ─── FGTS Digital ─────────────────────────────────────────────────────────────

@router.get("/fgts/{per_apur}")
def fgts(per_apur: str, user=Depends(get_current_user)):
    return _executa(servico.conferencia_fgts, _cid(user), _comp(per_apur))


@router.get("/totalizadores")
def totalizadores(per_apur: str = Query(default=""), user=Depends(get_current_user)):
    cid = _cid(user)
    return _executa(lambda conn: [dict(r) for r in conn.execute(
        """SELECT t.id, t.tipo, t.per_apur, t.employee_id, e.name AS funcionario, t.created_at
           FROM esocial_totalizadores t LEFT JOIN employees e ON e.id = t.employee_id
           WHERE t.company_id = ? AND t.per_apur LIKE ? ORDER BY t.id DESC LIMIT 300""",
        (cid, (per_apur or "") + "%")).fetchall()])

"""
Manifesto do Destinatário (NF-e recebidas)
Permite importar NF-e destinadas à empresa via upload de XML ou consulta SEFAZ.
"""
import xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel

try:
    from ..database import get_conn
    from ..auth import get_current_user
    from ..utils import rows_to_dicts
except ImportError:
    from database import get_conn
    from auth import get_current_user
    from utils import rows_to_dicts

router = APIRouter(tags=["Manifesto do Destinatário"])

NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def _parse_nfe_xml(xml_content: bytes) -> dict:
    """Extrai dados fiscais de um XML de NF-e."""
    try:
        root = ET.fromstring(xml_content)
        # Support both nfeProc and NFe root
        nfe = root.find(".//nfe:NFe", NS) or root.find(".//NFe")
        if not nfe:
            nfe = root
        inf = nfe.find(".//nfe:infNFe", NS) or nfe.find(".//infNFe")
        if not inf:
            return {"erro": "XML inválido: infNFe não encontrado"}

        def g(path):
            el = inf.find(path, NS)
            if el is None:
                el = inf.find(path.replace("nfe:", ""))
            return el.text if el is not None else ""

        chave = inf.get("Id", "").replace("NFe", "")
        emit = inf.find("nfe:emit", NS) or inf.find("emit")
        dest = inf.find("nfe:dest", NS) or inf.find("dest")
        ide  = inf.find("nfe:ide",  NS) or inf.find("ide")
        total = inf.find(".//nfe:ICMSTot", NS) or inf.find(".//ICMSTot")

        def gt(el, path):
            if el is None: return ""
            c = el.find(f"nfe:{path}", NS) or el.find(path)
            return c.text if c is not None else ""

        items = []
        for det in inf.findall("nfe:det", NS) or inf.findall("det"):
            prod = det.find("nfe:prod", NS) or det.find("prod")
            if prod is None: continue
            items.append({
                "descricao": gt(prod, "xProd"),
                "codigo": gt(prod, "cProd"),
                "ncm": gt(prod, "NCM"),
                "cfop": gt(prod, "CFOP"),
                "unidade": gt(prod, "uCom"),
                "quantidade": float(gt(prod, "qCom") or 0),
                "valor_unitario": float(gt(prod, "vUnCom") or 0),
                "valor_total": float(gt(prod, "vProd") or 0),
            })
        return {
            "chave": chave,
            "numero": gt(ide, "nNF"),
            "serie": gt(ide, "serie"),
            "data_emissao": gt(ide, "dhEmi")[:10] if gt(ide, "dhEmi") else gt(ide, "dEmi"),
            "emit_cnpj": gt(emit, "CNPJ"),
            "emit_nome": gt(emit, "xNome") or gt(emit, "xFant"),
            "dest_cnpj": gt(dest, "CNPJ") or gt(dest, "CPF"),
            "total_produtos": float(gt(total, "vProd") or 0),
            "total_icms": float(gt(total, "vICMS") or 0),
            "total_pis": float(gt(total, "vPIS") or 0),
            "total_cofins": float(gt(total, "vCOFINS") or 0),
            "total_nota": float(gt(total, "vNF") or 0),
            "items": items,
        }
    except Exception as e:
        return {"erro": str(e)}


@router.get("/api/nfe-manifest/list")
def list_manifest(
    status: Optional[str] = None,
    limit: int = 100,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    q = "SELECT * FROM nfe_manifest WHERE company_id=?"
    params: list = [company_id]
    if status:
        q += " AND status=?"
        params.append(status)
    q += f" ORDER BY data_emissao DESC LIMIT {min(limit, 500)}"
    rows = rows_to_dicts(conn.execute(q, params).fetchall())
    conn.close()
    return rows


@router.post("/api/nfe-manifest/upload")
async def upload_nfe(
    files: List[UploadFile] = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Importa uma ou mais NF-e pelo upload de XMLs."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    results = []
    for f in files:
        content = await f.read()
        data = _parse_nfe_xml(content)
        if "erro" in data:
            results.append({"arquivo": f.filename, "status": "erro", "erro": data["erro"]})
            continue
        chave = data.get("chave", "")
        # Check duplicate
        exists = conn.execute(
            "SELECT id FROM nfe_manifest WHERE company_id=? AND chave=?", (company_id, chave)
        ).fetchone()
        if exists:
            results.append({"arquivo": f.filename, "chave": chave, "status": "duplicada"})
            continue
        import json
        conn.execute("""
            INSERT INTO nfe_manifest
            (company_id, chave, numero, serie, data_emissao, emit_cnpj, emit_nome,
             total_nota, total_icms, total_pis, total_cofins, status, xml_items, origem)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (company_id, chave, data.get("numero"), data.get("serie"),
              data.get("data_emissao"), data.get("emit_cnpj"), data.get("emit_nome"),
              data.get("total_nota", 0), data.get("total_icms", 0),
              data.get("total_pis", 0), data.get("total_cofins", 0),
              "pendente", json.dumps(data.get("items", [])), "upload"))
        results.append({"arquivo": f.filename, "chave": chave, "emit": data.get("emit_nome"),
                        "total": data.get("total_nota"), "status": "importada"})
    conn.commit()
    conn.close()
    return {"results": results, "total": len(results)}


@router.post("/api/nfe-manifest/{mid}/manifestar")
def manifestar_nfe(
    mid: int,
    operacao: str = "confirmacao",  # confirmacao, desconhecimento, nao_realizada
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Registra o manifesto do destinatário (confirmação/desconhecimento)."""
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    nfe = conn.execute("SELECT * FROM nfe_manifest WHERE id=? AND company_id=?", (mid, company_id)).fetchone()
    if not nfe:
        conn.close()
        raise HTTPException(404, "NF-e não encontrada.")
    status_map = {
        "confirmacao": "confirmada",
        "desconhecimento": "desconhecida",
        "nao_realizada": "nao_realizada",
    }
    new_status = status_map.get(operacao, "confirmada")
    conn.execute("UPDATE nfe_manifest SET status=?, manifestado_em=? WHERE id=?",
                 (new_status, date.today().isoformat(), mid))
    conn.commit()
    conn.close()
    return {"message": f"NF-e {new_status} com sucesso.", "operacao": operacao}


@router.post("/api/nfe-manifest/{mid}/importar-estoque")
def importar_estoque(mid: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Importa itens da NF-e para o estoque e gera conta a pagar."""
    import json
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    nfe = conn.execute("SELECT * FROM nfe_manifest WHERE id=? AND company_id=?", (mid, company_id)).fetchone()
    if not nfe:
        conn.close()
        raise HTTPException(404, "NF-e não encontrada.")
    if nfe["status"] == "importada_estoque":
        conn.close()
        return {"message": "NF-e já foi importada para o estoque."}
    items = json.loads(nfe["xml_items"] or "[]")
    imported = 0
    for item in items:
        prod = conn.execute(
            "SELECT id, quantity FROM products WHERE company_id=? AND sku=?",
            (company_id, item.get("codigo", ""))
        ).fetchone()
        if prod:
            new_qty = float(prod["quantity"] or 0) + float(item.get("quantidade", 0))
            conn.execute("UPDATE products SET quantity=?, cost_price=? WHERE id=?",
                         (new_qty, item.get("valor_unitario", 0), prod["id"]))
        else:
            conn.execute("""
                INSERT INTO products (company_id, sku, name, unit, quantity, cost_price, sale_price, ncm)
                VALUES (?,?,?,?,?,?,?,?)
            """, (company_id, item.get("codigo", ""), item.get("descricao", ""),
                  item.get("unidade", "UN"), item.get("quantidade", 0),
                  item.get("valor_unitario", 0), item.get("valor_unitario", 0),
                  item.get("ncm", "")))
        imported += 1
    # Gera conta a pagar
    conn.execute("""
        INSERT INTO financial_entries
        (company_id, type, description, amount, due_date, status, category_id)
        VALUES (?,?,?,?,?,?,?)
    """, (company_id, "despesa",
          f"NF-e {nfe['numero']} — {nfe['emit_nome']}",
          float(nfe["total_nota"] or 0),
          nfe["data_emissao"] or date.today().isoformat(),
          "pendente", None))
    conn.execute("UPDATE nfe_manifest SET status='importada_estoque' WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    return {"message": f"{imported} item(s) importados para o estoque. Conta a pagar gerada.", "imported": imported}


@router.get("/api/nfe-manifest/summary")
def manifest_summary(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    rows = rows_to_dicts(conn.execute(
        "SELECT status, COUNT(*) as cnt, COALESCE(SUM(total_nota),0) as total FROM nfe_manifest WHERE company_id=? GROUP BY status",
        (company_id,)
    ).fetchall())
    conn.close()
    summary = {r["status"]: {"count": r["cnt"], "total": round(float(r["total"]),2)} for r in rows}
    return {"by_status": summary, "total_nfe": sum(r["cnt"] for r in rows)}

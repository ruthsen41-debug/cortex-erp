import re
import httpx
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Dict, Any, List

try:
    from ..database import get_conn
    from ..auth import get_current_user, log_audit
    from ..utils import rows_to_dicts
    from ..schemas.contacts import ContactCreate
except ImportError:
    from database import get_conn
    from auth import get_current_user, log_audit
    from utils import rows_to_dicts
    from schemas.contacts import ContactCreate

router = APIRouter(tags=["Contatos & Consultas"])


@router.get("/api/contacts")
def list_contacts(type: Optional[str] = None, q: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    company_id = current_user.get("company_id", 1)
    sql = "SELECT * FROM contacts WHERE active = 1 AND company_id = ?"
    params = [company_id]
    if type and type != "todos":
        sql += " AND (type = ? OR type = 'ambos')"
        params.append(type)
    if q:
        sql += " AND (name LIKE ? OR trade_name LIKE ? OR document LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    sql += " ORDER BY name ASC"
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    conn.close()
    return rows


@router.post("/api/contacts")
def save_contact(req: ContactCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)

    cur.execute("""
        INSERT INTO contacts (
            company_id, type, person_type, name, trade_name, document,
            state_registration, municipal_registration, email, phone,
            cep, street, number, complement, neighborhood, city, state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        company_id,
        req.type,
        req.person_type or "PJ",
        req.name.strip(),
        req.trade_name.strip() if req.trade_name else "",
        req.document.strip() if req.document else "",
        req.state_registration.strip() if req.state_registration else "",
        req.municipal_registration.strip() if req.municipal_registration else "",
        req.email.strip() if req.email else "",
        req.phone.strip() if req.phone else "",
        req.cep.strip() if req.cep else "",
        req.street.strip() if req.street else "",
        req.number.strip() if req.number else "",
        req.complement.strip() if req.complement else "",
        req.neighborhood.strip() if req.neighborhood else "",
        req.city.strip() if req.city else "",
        req.state.strip() if req.state else "MT",
    ))
    cid = cur.lastrowid
    conn.commit()
    log_audit(conn, action="create", entity="contacts", entity_id=cid, new_data=req.dict(), user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok", "id": cid}


@router.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    company_id = current_user.get("company_id", 1)
    cur.execute("UPDATE contacts SET active = 0 WHERE id = ? AND company_id = ?", (contact_id, company_id))
    conn.commit()
    log_audit(conn, action="delete", entity="contacts", entity_id=contact_id, user_id=current_user.get("id"))
    conn.close()
    return {"status": "ok"}


@router.get("/api/lookup/cnpj/{cnpj}")
async def lookup_cnpj(cnpj: str):
    clean = re.sub(r"\D", "", cnpj)
    if len(clean) != 14:
        raise HTTPException(status_code=400, detail="CNPJ deve ter 14 dígitos.")
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(f"https://brasilapi.com.br/api/cnpj/v1/{clean}")
            if r.status_code == 200:
                d = r.json()
                return {
                    "name": d.get("razao_social", ""),
                    "trade_name": d.get("nome_fantasia") or d.get("razao_social", ""),
                    "cep": d.get("cep", ""),
                    "street": d.get("logradouro", ""),
                    "number": d.get("numero", ""),
                    "complement": d.get("complemento", ""),
                    "neighborhood": d.get("bairro", ""),
                    "city": d.get("municipio", ""),
                    "state": d.get("uf", ""),
                    "phone": d.get("ddd_telefone_1", ""),
                    "email": d.get("email", "") or "",
                }
            elif r.status_code == 404:
                raise HTTPException(status_code=404, detail="CNPJ não encontrado na Receita Federal.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar serviço da BrasilAPI: {str(e)}")

    raise HTTPException(status_code=404, detail="CNPJ não encontrado.")


@router.get("/api/lookup/cep/{cep}")
async def lookup_cep(cep: str):
    clean = re.sub(r"\D", "", cep)
    if len(clean) != 8:
        raise HTTPException(status_code=400, detail="CEP deve ter 8 dígitos.")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"https://viacep.com.br/ws/{clean}/json/")
            if r.status_code == 200:
                d = r.json()
                if not d.get("erro"):
                    return {
                        "street": d.get("logradouro", ""),
                        "neighborhood": d.get("bairro", ""),
                        "city": d.get("localidade", ""),
                        "state": d.get("uf", ""),
                        "ibge_code": d.get("ibge", ""),
                    }
                raise HTTPException(status_code=404, detail="CEP não encontrado.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar serviço ViaCEP: {str(e)}")

    raise HTTPException(status_code=404, detail="CEP não encontrado.")

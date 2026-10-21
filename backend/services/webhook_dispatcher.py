import hmac
import hashlib
import json
import httpx
import ipaddress
import socket
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, Any, List

try:
    from ..database import get_conn
except ImportError:
    from database import get_conn


def validate_target_url(url: str) -> None:
    """Rejeita destinos que não sejam http(s) público (loopback, rede privada, link-local, metadados de nuvem)."""
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("A URL do webhook deve usar http:// ou https://.")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        raise ValueError("Não foi possível resolver o host da URL do webhook.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("A URL do webhook não pode apontar para endereços internos ou privados.")


class WebhookDispatcher:
    @staticmethod
    async def dispatch_event(event_name: str, payload: Dict[str, Any], company_id: int = 1) -> List[Dict[str, Any]]:
        """
        Dispara evento para todas as URLs inscritas no webhook com assinatura HMAC-SHA256
        e registra o status de entrega no banco de dados.
        """
        conn = get_conn()
        cur = conn.cursor()
        subs = cur.execute("""
            SELECT * FROM webhook_subscriptions
            WHERE company_id = ? AND active = 1
        """, (company_id,)).fetchall()

        results = []
        payload_data = {
            "event": event_name,
            "timestamp": datetime.now().isoformat(),
            "company_id": company_id,
            "data": payload
        }
        payload_bytes = json.dumps(payload_data, ensure_ascii=False).encode("utf-8")

        for s in subs:
            sub_id = s["id"]
            target_url = s["target_url"]
            events_sub = s["events"] or "all"
            secret = s["secret"] or ""

            # Verifica se está inscrito no evento
            if events_sub != "all" and event_name not in events_sub.split(","):
                continue

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Cortex-ERP-Webhook/1.0",
                "X-Cortex-Event": event_name
            }
            if secret:
                signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
                headers["X-Cortex-Signature"] = signature

            status_code = 0
            success = 0
            try:
                validate_target_url(target_url)
                async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
                    resp = await client.post(target_url, content=payload_bytes, headers=headers)
                    status_code = resp.status_code
                    success = 1 if 200 <= status_code < 300 else 0
            except Exception:
                status_code = 500
                success = 0

            cur.execute("""
                INSERT INTO webhook_deliveries (company_id, subscription_id, event_name, payload_json, response_status, success)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (company_id, sub_id, event_name, json.dumps(payload_data, ensure_ascii=False), status_code, success))
            conn.commit()

            results.append({
                "subscription_id": sub_id,
                "target_url": target_url,
                "status_code": status_code,
                "success": bool(success)
            })

        conn.close()
        return results

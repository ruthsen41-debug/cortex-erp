import os
from fastapi import APIRouter, Request, Depends
from typing import Dict, Any

try:
    from ..config import GEMINI_API_KEY
    from ..auth import get_current_user
    from .dashboard import get_dashboard
except ImportError:
    from config import GEMINI_API_KEY
    from auth import get_current_user
    from routers.dashboard import get_dashboard

router = APIRouter(prefix="/api/cfo", tags=["CFO Virtual IA"])


@router.post("/ask")
async def ask_virtual_cfo(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """CFO Virtual que analisa os dados reais do banco e responde com diagnóstico financeiro."""
    data = await req.json()
    question = (data.get("prompt") or data.get("question") or "Faça um diagnóstico completo da saúde financeira da empresa.").strip()

    dash = get_dashboard(current_user)
    kpis = dash.get("kpis", {})

    total_bal = kpis.get("total_balance", 0.0)
    month_rec = kpis.get("month_receivables", 0.0)
    overdue_rec = kpis.get("overdue_receivables", 0.0)
    month_pay = kpis.get("month_payables", 0.0)
    overdue_pay = kpis.get("overdue_payables", 0.0)
    net_income = kpis.get("net_income", 0.0)

    context_summary = (
        f"Saldo em caixa/bancos: R$ {total_bal:,.2f} | "
        f"A receber no mês: R$ {month_rec:,.2f} (Vencidos: R$ {overdue_rec:,.2f}) | "
        f"A pagar no mês: R$ {month_pay:,.2f} (Vencidos: R$ {overdue_pay:,.2f}) | "
        f"Lucro líquido previsto no mês: R$ {net_income:,.2f}."
    )

    # Gemini IA
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=(
                    "Você é o CFO Virtual Executivo do sistema Cortex ERP Pro+. "
                    f"Dados reais em tempo real da empresa: {context_summary}. "
                    f"Pergunta do diretor: {question}\n"
                    "Responda de forma objetiva, estratégica e elegante em português (máximo 3 parágrafos com bullet points práticos)."
                ),
            )
            if resp and resp.text:
                return {"reply": resp.text, "answer": resp.text, "engine": "Gemini 2.5 Flash Live CFO"}
        except Exception:
            pass

    # Diagnóstico determinístico
    liquidez = round(total_bal / max(1.0, month_pay), 2)
    answer = (
        f"📊 **Diagnóstico Executivo do CFO Virtual:**\n\n"
        f"- **Posição de Liquidez Imediata:** Sua empresa dispõe de **R$ {total_bal:,.2f}** em contas bancárias, "
        f"representando um índice de cobertura de **{liquidez}x** sobre as despesas do mês (R$ {month_pay:,.2f}).\n"
        f"- **Gestão de Inadimplência:** Há **R$ {overdue_rec:,.2f}** em títulos vencidos aguardando recebimento. "
        f"Recomendo intensificar as cobranças para manter a robustez do capital de giro.\n"
        f"- **Resultado Operacional:** O resultado previsto para o período é de **R$ {net_income:,.2f}**. "
        f"A estrutura de caixa encontra-se {'estável' if liquidez >= 1.0 else 'em alerta de liquidez'}."
    )
    return {"reply": answer, "answer": answer, "engine": "Cortex Financial Analytics Engine"}

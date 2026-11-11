// ============================================================
// DEVOLUÇÕES & RMA — Cortex ERP Pro+
// Devolução de vendas · Reestocagem · Estorno financeiro
// ============================================================

function authHeaders() { return {}; }

let retList      = [];
let retSales     = [];
let retContainer = null;

// ── helpers ──────────────────────────────────────────────────
const fBRL5  = v => parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fDate5 = s => s ? s.slice(0, 10).split('-').reverse().join('/') : '-';
const card5  = html => `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs">${html}</div>`;

const REFUND_LABEL = {
  credito:            'Crédito ao Cliente',
  estorno_financeiro: 'Estorno Financeiro',
};
const REFUND_CLS = {
  credito:            'text-blue-600 bg-blue-50 dark:bg-blue-900/30',
  estorno_financeiro: 'text-rose-500 bg-rose-50 dark:bg-rose-900/20',
};

function refundBadge(m) {
  const cls   = REFUND_CLS[m]   || REFUND_CLS.credito;
  const label = REFUND_LABEL[m] || m;
  return `<span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold ${cls}">${label}</span>`;
}

function kpiRet(label, value, sub, icon, color) {
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
    <div class="flex items-center justify-between text-slate-500 text-xs font-semibold mb-2">
      <span>${label}</span><i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
    </div>
    <div class="text-2xl font-extrabold ${color}">${value}</div>
    ${sub ? `<div class="text-[11px] text-slate-400 mt-1">${sub}</div>` : ''}
  </div>`;
}

function inputR() {
  return 'w-full text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-500';
}
function lblR(t) {
  return `<label class="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">${t}</label>`;
}

// ── entry point ───────────────────────────────────────────────
async function renderReturns(container) {
  retContainer = container;
  await Promise.all([
    fetch('/api/sales/returns', { headers: authHeaders() }).then(r => r.json()).then(d => { retList = Array.isArray(d) ? d : []; }).catch(() => { retList = []; }),
    fetch('/api/sales', { headers: authHeaders() }).then(r => r.json()).then(d => { retSales = Array.isArray(d) ? d : []; }).catch(() => { retSales = []; }),
  ]);

  await renderRetLista(container);
  if (window.lucide) lucide.createIcons();
}

// ── LISTA DE DEVOLUÇÕES ───────────────────────────────────────
async function renderRetLista(el) {
  const totalVal     = retList.reduce((s, r) => s + parseFloat(r.total_returned || 0), 0);
  const estornos     = retList.filter(r => r.refund_method === 'estorno_financeiro');
  const creditos     = retList.filter(r => r.refund_method === 'credito');
  const valEstornos  = estornos.reduce((s, r) => s + parseFloat(r.total_returned || 0), 0);

  const rows = retList.map(ret => `
    <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
      <td class="px-4 py-3 text-sm font-mono font-bold text-slate-500">#${ret.id}</td>
      <td class="px-4 py-3 text-sm font-mono text-indigo-500">
        <button onclick="openRetDetail(${ret.id})" class="hover:underline">Venda #${ret.sale_number}</button>
      </td>
      <td class="px-4 py-3 text-sm text-slate-700 dark:text-slate-200">${ret.client_name || '-'}</td>
      <td class="px-4 py-3 text-sm text-slate-600 dark:text-slate-300 max-w-[200px]">
        <div class="truncate" title="${ret.reason}">${ret.reason}</div>
      </td>
      <td class="px-4 py-3 text-sm font-bold text-rose-500">${fBRL5(ret.total_returned)}</td>
      <td class="px-4 py-3">${refundBadge(ret.refund_method)}</td>
      <td class="px-4 py-3">
        <span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20">
          ${ret.status || 'concluido'}
        </span>
      </td>
      <td class="px-4 py-3 text-xs text-slate-400">${fDate5(ret.created_at)}</td>
      <td class="px-4 py-3 text-right">
        <button onclick="openRetDetail(${ret.id})" class="text-xs text-indigo-500 hover:underline">Detalhe</button>
      </td>
    </tr>`).join('');

  el.innerHTML = `
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      ${kpiRet('Total de Devoluções', retList.length, 'registradas', 'undo-2', 'text-rose-500')}
      ${kpiRet('Valor Total Devolvido', fBRL5(totalVal), 'soma geral', 'banknote', 'text-rose-500')}
      ${kpiRet('Estornos Financeiros', estornos.length, fBRL5(valEstornos), 'circle-dollar-sign', 'text-orange-500')}
      ${kpiRet('Créditos Concedidos', creditos.length, 'crédito ao cliente', 'award', 'text-blue-600')}
    </div>

    <div class="flex items-center justify-between mb-4">
      <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">Devoluções & RMA</h2>
      <button onclick="openNovaDevModal()"
        class="bg-rose-500 hover:bg-rose-600 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
        <i data-lucide="undo-2" class="w-3.5 h-3.5"></i> Nova Devolução
      </button>
    </div>

    ${card5(`
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2 text-left font-semibold">RMA #</th>
            <th class="px-4 py-2 text-left font-semibold">Venda Origem</th>
            <th class="px-4 py-2 text-left font-semibold">Cliente</th>
            <th class="px-4 py-2 text-left font-semibold">Motivo</th>
            <th class="px-4 py-2 text-left font-semibold">Valor</th>
            <th class="px-4 py-2 text-left font-semibold">Reembolso</th>
            <th class="px-4 py-2 text-left font-semibold">Status</th>
            <th class="px-4 py-2 text-left font-semibold">Data</th>
            <th class="px-4 py-2 text-right font-semibold">Ações</th>
          </tr></thead>
          <tbody>${rows || '<tr><td colspan="9" class="px-4 py-8 text-center text-slate-400 text-xs">Nenhuma devolução registrada.</td></tr>'}</tbody>
        </table>
      </div>`)}
    <div id="ret-detail-area" class="mt-6"></div>`;
}

// ── DETALHE DE DEVOLUÇÃO ──────────────────────────────────────
async function openRetDetail(id) {
  const area = document.getElementById('ret-detail-area');
  if (!area) return;
  area.innerHTML = '<div class="text-xs text-slate-400 p-4">Carregando...</div>';
  try {
    const r = await fetch(`/api/sales/returns/${id}`, { headers: authHeaders() });
    const d = await r.json();

    const itemRows = (d.items || []).map(it => `
      <tr class="border-b border-slate-100 dark:border-slate-800">
        <td class="px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200">${it.product_name || '-'}</td>
        <td class="px-4 py-2.5 text-xs font-mono text-slate-400">${it.sku || '-'}</td>
        <td class="px-4 py-2.5 text-sm text-right">${parseFloat(it.quantity || 0).toLocaleString('pt-BR')}</td>
        <td class="px-4 py-2.5 text-sm text-right">${fBRL5(it.unit_price)}</td>
        <td class="px-4 py-2.5 text-sm font-semibold text-right">${fBRL5(parseFloat(it.quantity || 0) * parseFloat(it.unit_price || 0))}</td>
        <td class="px-4 py-2.5 text-center">
          ${it.return_to_stock
            ? '<span class="text-[10px] font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full">SIM</span>'
            : '<span class="text-[10px] font-bold text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">NÃO</span>'}
        </td>
      </tr>`).join('');

    area.innerHTML = `
      <div class="mb-3 flex items-center justify-between">
        <h3 class="font-bold text-slate-700 dark:text-slate-200 flex items-center gap-2">
          RMA #${d.id} — Venda #${d.sale_number}
          <span class="ml-1">${refundBadge(d.refund_method)}</span>
        </h3>
        <button onclick="document.getElementById('ret-detail-area').innerHTML=''"
          class="text-xs text-slate-400 hover:text-slate-600">Fechar ✕</button>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-xs text-slate-500">
        <div><span class="font-semibold text-slate-600 dark:text-slate-300">Cliente</span><br>${d.client_name || '-'}</div>
        <div><span class="font-semibold text-slate-600 dark:text-slate-300">Motivo</span><br>${d.reason}</div>
        <div><span class="font-semibold text-slate-600 dark:text-slate-300">Registrado em</span><br>${fDate5(d.created_at)}</div>
        <div><span class="font-semibold text-slate-600 dark:text-slate-300">Status</span><br>${d.status || 'concluido'}</div>
      </div>
      ${card5(`
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
              <th class="px-4 py-2 text-left font-semibold">Produto</th>
              <th class="px-4 py-2 text-left font-semibold">SKU</th>
              <th class="px-4 py-2 text-right font-semibold">Qtd</th>
              <th class="px-4 py-2 text-right font-semibold">Preço Unit.</th>
              <th class="px-4 py-2 text-right font-semibold">Total</th>
              <th class="px-4 py-2 text-center font-semibold">Reestocado</th>
            </tr></thead>
            <tbody>${itemRows}</tbody>
            <tfoot><tr class="border-t-2 border-slate-200 dark:border-slate-700">
              <td colspan="4" class="px-4 py-3 text-sm font-bold text-slate-700 dark:text-slate-200 text-right">Total Devolvido</td>
              <td class="px-4 py-3 text-lg font-extrabold text-rose-500 text-right">${fBRL5(d.total_returned)}</td>
              <td></td>
            </tr></tfoot>
          </table>
        </div>`)}`;
    area.scrollIntoView({ behavior: 'smooth' });
    if (window.lucide) lucide.createIcons();
  } catch { area.innerHTML = '<div class="text-xs text-rose-500 p-4">Erro ao carregar detalhe.</div>'; }
}

// ── MODAL NOVA DEVOLUÇÃO ──────────────────────────────────────
let retFoundSale = null;

function openNovaDevModal() {
  retFoundSale = null;
  openModal(`
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-6 max-w-2xl w-full">
      <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-5 text-lg flex items-center gap-2">
        <i data-lucide="undo-2" class="w-5 h-5 text-rose-500"></i> Nova Devolução / RMA
      </h3>

      <!-- Passo 1: buscar venda -->
      <div id="ret-step1">
        <p class="text-xs text-slate-400 mb-3">Informe o número da venda ou busque pelo cliente.</p>
        <div class="flex gap-3 mb-4">
          <input id="ret-search" class="flex-1 text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-500"
            placeholder="Nº da venda ou nome do cliente..." oninput="filterRetSales()">
        </div>
        <div id="ret-sale-list" class="space-y-2 max-h-48 overflow-y-auto"></div>
      </div>

      <!-- Passo 2: itens + dados da devolução -->
      <div id="ret-step2" class="hidden">
        <div id="ret-sale-info" class="p-3 bg-rose-50 dark:bg-rose-900/20 rounded-xl mb-4 text-sm"></div>

        <div class="mb-4">
          ${lblR('Motivo da Devolução *')}
          <input id="ret-reason" class="${inputR()}" placeholder="ex: Produto com defeito, tamanho incorreto...">
        </div>

        <div class="mb-5">
          ${lblR('Método de Reembolso')}
          <div class="flex gap-3">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="radio" name="ret-refund" value="credito" checked class="accent-rose-500">
              <span class="text-sm text-slate-700 dark:text-slate-200">Crédito ao cliente</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="radio" name="ret-refund" value="estorno_financeiro" class="accent-rose-500">
              <span class="text-sm text-slate-700 dark:text-slate-200">Estorno financeiro
                <span class="text-xs text-slate-400">(gera lançamento no Contas a Pagar)</span>
              </span>
            </label>
          </div>
        </div>

        <div class="mb-2 flex items-center justify-between">
          <span class="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase">Itens a Devolver</span>
          <button onclick="selectAllRetItems(true)" class="text-xs text-rose-500 hover:underline">Todos</button>
        </div>
        <div id="ret-items-list" class="space-y-2 mb-5 max-h-52 overflow-y-auto"></div>

        <div id="ret-total-preview" class="text-sm font-bold text-rose-500 text-right mb-4"></div>

        <div class="flex justify-between items-center">
          <button onclick="retBackToStep1()" class="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1">
            <i data-lucide="arrow-left" class="w-3.5 h-3.5"></i> Trocar venda
          </button>
          <div class="flex gap-3">
            <button onclick="closeModal()" class="px-4 py-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
            <button onclick="salvarDevolucao()"
              class="bg-rose-500 hover:bg-rose-600 text-white text-sm font-semibold px-5 py-2 rounded-xl">
              Registrar Devolução
            </button>
          </div>
        </div>
      </div>
    </div>`);

  filterRetSales();
  if (window.lucide) lucide.createIcons();
}

function filterRetSales() {
  const q   = (document.getElementById('ret-search')?.value || '').toLowerCase().trim();
  const box = document.getElementById('ret-sale-list');
  if (!box) return;

  const filtered = q
    ? retSales.filter(s =>
        String(s.number || '').includes(q) ||
        (s.client_name || '').toLowerCase().includes(q)
      )
    : retSales.slice(0, 20);

  if (filtered.length === 0) {
    box.innerHTML = '<p class="text-xs text-slate-400 p-2">Nenhuma venda encontrada.</p>';
    return;
  }

  box.innerHTML = filtered.map(s => `
    <button onclick="selectRetSale(${s.id})"
      class="w-full text-left p-3 rounded-xl border border-slate-100 dark:border-slate-800 hover:bg-rose-50 dark:hover:bg-rose-900/20 hover:border-rose-200 transition">
      <div class="flex items-center justify-between">
        <div>
          <span class="text-sm font-mono font-bold text-slate-700 dark:text-slate-200">Venda #${s.number}</span>
          <span class="ml-2 text-xs text-slate-400">${s.client_name || 'Sem cliente'}</span>
        </div>
        <div class="text-right">
          <div class="text-sm font-bold text-emerald-600">${fBRL5(s.total_amount)}</div>
          <div class="text-xs text-slate-400">${fDate5(s.sale_date || s.created_at)}</div>
        </div>
      </div>
      <div class="text-xs text-slate-400 mt-1">${(s.items || []).length} item(ns)</div>
    </button>`).join('');
}

function selectRetSale(saleId) {
  const sale = retSales.find(s => s.id === saleId);
  if (!sale) return;
  retFoundSale = sale;

  // Troca para step 2
  document.getElementById('ret-step1').classList.add('hidden');
  document.getElementById('ret-step2').classList.remove('hidden');

  document.getElementById('ret-sale-info').innerHTML = `
    <div class="flex items-center justify-between">
      <div>
        <span class="font-bold text-rose-600">Venda #${sale.number}</span>
        <span class="ml-2 text-slate-500">${sale.client_name || '-'}</span>
      </div>
      <span class="font-bold text-emerald-600">${fBRL5(sale.total_amount)}</span>
    </div>
    <div class="text-xs text-slate-400 mt-1">${fDate5(sale.sale_date || sale.created_at)}</div>`;

  const itemsBox = document.getElementById('ret-items-list');
  const items = sale.items || [];

  if (items.length === 0) {
    itemsBox.innerHTML = '<p class="text-xs text-slate-400 p-2">Esta venda não possui itens.</p>';
    return;
  }

  itemsBox.innerHTML = items.map((it, idx) => `
    <div class="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
      <div class="flex items-start gap-3">
        <input type="checkbox" id="ret-chk-${idx}" value="${idx}" checked
          class="mt-0.5 accent-rose-500 rounded" onchange="calcRetTotal()">
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">
            ${it.product_name || `Produto #${it.product_id}`}
            ${it.sku ? `<span class="text-xs font-mono text-slate-400 ml-1">[${it.sku}]</span>` : ''}
          </div>
          <div class="flex items-center gap-4 mt-1.5">
            <div>
              ${lblR('Qtd a devolver')}
              <input id="ret-qty-${idx}" type="number" min="0.001" step="0.001"
                value="${parseFloat(it.quantity || 1).toFixed(3)}"
                max="${parseFloat(it.quantity || 1)}"
                class="w-24 text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-rose-500"
                onchange="calcRetTotal()">
            </div>
            <div class="text-xs text-slate-400">
              Preço unit.: <strong class="text-slate-600 dark:text-slate-300">${fBRL5(it.unit_price)}</strong>
            </div>
            <label class="flex items-center gap-1.5 ml-auto cursor-pointer">
              <input type="checkbox" id="ret-stock-${idx}" checked class="accent-emerald-500 rounded">
              <span class="text-xs text-slate-500">Reestocar</span>
            </label>
          </div>
        </div>
      </div>
    </div>`).join('');

  calcRetTotal();
  if (window.lucide) lucide.createIcons();
}

function retBackToStep1() {
  retFoundSale = null;
  document.getElementById('ret-step1').classList.remove('hidden');
  document.getElementById('ret-step2').classList.add('hidden');
}

function selectAllRetItems(checked) {
  const sale = retFoundSale;
  if (!sale) return;
  (sale.items || []).forEach((_, idx) => {
    const chk = document.getElementById(`ret-chk-${idx}`);
    if (chk) chk.checked = checked;
  });
  calcRetTotal();
}

function calcRetTotal() {
  const sale = retFoundSale;
  if (!sale) return;
  let total = 0;
  (sale.items || []).forEach((it, idx) => {
    const chk = document.getElementById(`ret-chk-${idx}`);
    const qty = parseFloat(document.getElementById(`ret-qty-${idx}`)?.value || 0);
    if (chk?.checked && qty > 0) {
      total += qty * parseFloat(it.unit_price || 0);
    }
  });
  const el = document.getElementById('ret-total-preview');
  if (el) el.textContent = `Total a devolver: ${fBRL5(total)}`;
}

async function salvarDevolucao() {
  const sale = retFoundSale;
  if (!sale) { alert('Selecione a venda de origem.'); return; }

  const reason = document.getElementById('ret-reason')?.value.trim();
  if (!reason) { alert('Informe o motivo da devolução.'); return; }

  const refund_method = document.querySelector('input[name="ret-refund"]:checked')?.value || 'credito';

  const items = [];
  (sale.items || []).forEach((it, idx) => {
    const chk = document.getElementById(`ret-chk-${idx}`);
    if (!chk?.checked) return;
    const qty   = parseFloat(document.getElementById(`ret-qty-${idx}`)?.value || 0);
    const stock = document.getElementById(`ret-stock-${idx}`)?.checked ? 1 : 0;
    if (qty > 0) {
      items.push({
        product_id:      it.product_id,
        quantity:        qty,
        unit_price:      parseFloat(it.unit_price || 0),
        return_to_stock: stock,
      });
    }
  });

  if (items.length === 0) { alert('Selecione ao menos um item para devolver.'); return; }

  try {
    const r = await fetch('/api/sales/returns', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ sale_id: sale.id, reason, refund_method, items }),
    });
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Erro ao registrar devolução.'); return; }
    const d = await r.json();

    let msg = `✓ ${d.message || 'Devolução registrada!'}\n\nRMA #${d.return_id} — ${fBRL5(d.total_returned)}`;
    if (d.financial_entry_id) msg += `\nEstorno financeiro gerado (ID #${d.financial_entry_id})`;
    alert(msg);

    closeModal();
    // Recarrega lista e vendas
    const [retR, salesR] = await Promise.all([
      fetch('/api/sales/returns', { headers: authHeaders() }),
      fetch('/api/sales', { headers: authHeaders() }),
    ]);
    retList  = await retR.json();
    retSales = await salesR.json();
    if (retContainer) await renderRetLista(retContainer);
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

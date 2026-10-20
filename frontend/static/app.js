// Cortex ERP Pro+ Frontend SPA Application
let currentTab = 'dashboard';
let chartInstance = null;
let currentProducts = [];
let currentBankAccounts = [];
let currentCategories = [];
let currentContacts = [];

// Formatters
const formatCurrency = (val) => {
  const num = parseFloat(val) || 0.0;
  return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
};

const formatDate = (dateStr) => {
  if (!dateStr) return '-';
  const d = dateStr.slice(0, 10).split('-');
  if (d.length === 3) return `${d[2]}/${d[1]}/${d[0]}`;
  return dateStr;
};

// UI Feedback
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const colors = {
    success: 'bg-emerald-600 text-white',
    error: 'bg-rose-600 text-white',
    info: 'bg-blue-600 text-white',
    warning: 'bg-amber-600 text-white',
  };
  const toast = document.createElement('div');
  toast.className = `px-4 py-3 rounded-xl shadow-lg text-xs font-semibold flex items-center gap-2 transition-all transform duration-300 ${colors[type] || colors.info}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-x-4');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Modal Management
function openModal(htmlContent) {
  const backdrop = document.getElementById('modal-backdrop');
  const box = document.getElementById('modal-box');
  if (!backdrop || !box) return;
  box.innerHTML = htmlContent;
  backdrop.classList.remove('hidden');
  backdrop.classList.add('flex');
  if (window.lucide) lucide.createIcons();
}

function closeModal() {
  const backdrop = document.getElementById('modal-backdrop');
  const box = document.getElementById('modal-box');
  if (!backdrop || !box) return;
  backdrop.classList.add('hidden');
  backdrop.classList.remove('flex');
  box.innerHTML = '';
}

// Dark Mode Toggle
function toggleDarkMode() {
  const isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('cortex_theme', isDark ? 'dark' : 'light');
}

// AI Quick Launch in Header
async function executeAiLaunch() {
  const input = document.getElementById('ai-quick-input');
  if (!input || !input.value.trim()) return;
  const text = input.value.trim();
  input.value = '';
  showToast('Processando comando mágico com IA...', 'info');

  try {
    const res = await fetch('/api/financial/ai-launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    if (res.ok) {
      showToast(`Lançamento realizado: ${data.description || text} (${formatCurrency(data.amount)})`, 'success');
      if (['dashboard', 'receivables', 'payables'].includes(currentTab)) {
        switchTab(currentTab);
      }
    } else {
      showToast(`Erro ao lançar: ${data.detail || 'Falha no processamento'}`, 'error');
    }
  } catch (err) {
    showToast('Falha na comunicação com o servidor.', 'error');
  }
}

// Cache global lookups
async function preloadLookups() {
  try {
    const [pRes, bRes, cRes, ctRes] = await Promise.all([
      fetch('/api/products').then(r => r.json()),
      fetch('/api/bank-accounts').then(r => r.json()),
      fetch('/api/categories').then(r => r.json()),
      fetch('/api/contacts').then(r => r.json()),
    ]);
    currentProducts = Array.isArray(pRes) ? pRes : [];
    currentBankAccounts = Array.isArray(bRes) ? bRes : [];
    currentCategories = Array.isArray(cRes) ? cRes : [];
    currentContacts = Array.isArray(ctRes) ? ctRes : [];
  } catch (e) {
    console.warn('Erro ao carregar dados auxiliares:', e);
  }
}

// Navigation & Tab Switching
async function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const activeNav = document.getElementById(`nav-${tab}`);
  if (activeNav) activeNav.classList.add('active');

  const main = document.getElementById('main-content');
  main.innerHTML = '<div class="flex items-center justify-center p-12 text-slate-400"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>Carregando módulo...</div>';

  await preloadLookups();

  switch (tab) {
    case 'dashboard':
      await renderDashboard(main);
      break;
    case 'receivables':
      await renderFinancial(main, 'receita');
      break;
    case 'payables':
      await renderFinancial(main, 'despesa');
      break;
    case 'ofx':
      await renderOfx(main);
      break;
    case 'crm':
      await renderCrm(main);
      break;
    case 'sales':
      await renderSales(main);
      break;
    case 'pdv':
      await renderPdv(main);
      break;
    case 'os':
      await renderServiceOrders(main);
      break;
    case 'inventory':
      await renderInventory(main);
      break;
    case 'invoices':
      await renderInvoices(main);
      break;
    case 'reports':
      await renderReports(main);
      break;
    default:
      main.innerHTML = `<div class="p-6">Módulo "${tab}" em desenvolvimento.</div>`;
  }
  if (window.lucide) lucide.createIcons();
}

// ==============================================================================
// 1. DASHBOARD & CFO IA
// ==============================================================================
async function renderDashboard(container) {
  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();

    const kpis = data.kpis || {};
    const flow = data.monthly_cash_flow || [];
    const accounts = data.bank_accounts || [];
    const pendingPay = data.upcoming_payables || [];
    const pendingRec = data.upcoming_receivables || [];

    let accountsHtml = accounts.map(a => `
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs flex justify-between items-center">
        <div>
          <div class="text-xs text-slate-500 font-medium">${a.bank_name || 'Banco'} (${a.agency || '0001'})</div>
          <div class="font-bold text-slate-800 dark:text-slate-100 text-sm mt-0.5">${a.name}</div>
        </div>
        <div class="text-right">
          <div class="text-xs text-slate-400">Saldo Atual</div>
          <div class="font-extrabold text-sm ${a.current_balance >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600'}">
            ${formatCurrency(a.current_balance)}
          </div>
        </div>
      </div>
    `).join('');

    container.innerHTML = `
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between text-slate-500 text-xs font-semibold">
            <span>Saldo Bancário Total</span>
            <i data-lucide="wallet" class="w-4 h-4 text-blue-500"></i>
          </div>
          <div class="text-2xl font-extrabold mt-2 text-slate-900 dark:text-slate-50">${formatCurrency(kpis.total_balance)}</div>
          <div class="text-[11px] text-slate-400 mt-1">Soma de todas as contas ativas</div>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between text-slate-500 text-xs font-semibold">
            <span>A Receber (Mês)</span>
            <i data-lucide="arrow-up-right" class="w-4 h-4 text-emerald-500"></i>
          </div>
          <div class="text-2xl font-extrabold mt-2 text-emerald-600">${formatCurrency(kpis.month_receivables)}</div>
          <div class="text-[11px] text-rose-500 mt-1">Vencidos: ${formatCurrency(kpis.overdue_receivables)}</div>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between text-slate-500 text-xs font-semibold">
            <span>A Pagar (Mês)</span>
            <i data-lucide="arrow-down-left" class="w-4 h-4 text-rose-500"></i>
          </div>
          <div class="text-2xl font-extrabold mt-2 text-rose-600">${formatCurrency(kpis.month_payables)}</div>
          <div class="text-[11px] text-rose-500 mt-1">Vencidos: ${formatCurrency(kpis.overdue_payables)}</div>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between text-slate-500 text-xs font-semibold">
            <span>Lucro Líquido Previsto</span>
            <i data-lucide="trending-up" class="w-4 h-4 text-indigo-500"></i>
          </div>
          <div class="text-2xl font-extrabold mt-2 ${kpis.net_income >= 0 ? 'text-indigo-600' : 'text-rose-600'}">
            ${formatCurrency(kpis.net_income)}
          </div>
          <div class="text-[11px] text-slate-400 mt-1">Faturamento: ${formatCurrency(kpis.month_revenue)}</div>
        </div>
      </div>

      <!-- CFO VIRTUAL IA -->
      <div class="bg-gradient-to-r from-blue-900 to-indigo-900 rounded-2xl p-6 text-white shadow-lg">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-10 h-10 rounded-xl bg-blue-500/30 flex items-center justify-center border border-blue-400/30">
            <i data-lucide="bot" class="w-5 h-5 text-blue-300"></i>
          </div>
          <div>
            <h3 class="font-bold text-base">CFO Virtual com IA (Gemini)</h3>
            <p class="text-xs text-blue-200">Análise financeira executiva, riscos e recomendações estratégicas</p>
          </div>
        </div>
        <div id="cfo-reply" class="bg-black/30 backdrop-blur-xs rounded-xl p-4 text-xs md:text-sm leading-relaxed border border-white/10 text-blue-50 max-h-48 overflow-y-auto">
          Clique no botão abaixo ou pergunte algo ao CFO Virtual sobre o fluxo de caixa, inadimplência ou redução de custos.
        </div>
        <div class="mt-4 flex gap-2">
          <input id="cfo-question" type="text" placeholder="Ex: 'Faça um diagnóstico do meu fluxo de caixa deste mês e aponte os 3 maiores riscos.'" class="flex-1 bg-white/10 border border-white/20 rounded-xl px-4 py-2 text-xs md:text-sm text-white placeholder-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-400">
          <button onclick="askCfo()" class="bg-white text-blue-900 hover:bg-blue-50 font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-1.5 transition">
            <i data-lucide="send" class="w-3.5 h-3.5"></i> Perguntar
          </button>
        </div>
      </div>

      <!-- FLUXO DE CAIXA GRÁFICO & CONTAS -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <i data-lucide="bar-chart-3" class="w-4 h-4 text-blue-600"></i> Fluxo de Caixa Mensal
            </h3>
            <span class="text-xs text-slate-400">Últimos meses</span>
          </div>
          <div class="h-64">
            <canvas id="cashFlowChart"></canvas>
          </div>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs flex flex-col">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <i data-lucide="landmark" class="w-4 h-4 text-blue-600"></i> Contas Bancárias
            </h3>
            <button onclick="openTransferModal()" class="text-xs bg-blue-50 text-blue-700 hover:bg-blue-100 font-semibold px-2 py-1 rounded-lg">
              Transferir
            </button>
          </div>
          <div class="space-y-3 flex-1 overflow-y-auto">
            ${accountsHtml || '<div class="text-xs text-slate-400">Nenhuma conta bancária cadastrada.</div>'}
          </div>
        </div>
      </div>
    `;

    // Render chart
    const ctx = document.getElementById('cashFlowChart');
    if (ctx && window.Chart) {
      if (chartInstance) chartInstance.destroy();
      const labels = flow.map(f => f.month);
      const recData = flow.map(f => f.receitas);
      const despData = flow.map(f => f.despesas);
      chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            { label: 'Receitas', data: recData, backgroundColor: '#10b981', borderRadius: 6 },
            { label: 'Despesas', data: despData, backgroundColor: '#f43f5e', borderRadius: 6 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { grid: { color: 'rgba(150,150,150,0.1)' } },
            x: { grid: { display: false } },
          },
        },
      });
    }
  } catch (err) {
    container.innerHTML = `<div class="p-6 text-rose-500 font-semibold">Erro ao carregar Dashboard: ${err.message}</div>`;
  }
}

async function askCfo() {
  const qInput = document.getElementById('cfo-question');
  const rDiv = document.getElementById('cfo-reply');
  if (!qInput || !rDiv) return;
  const question = qInput.value.trim() || 'Faça um diagnóstico do meu fluxo de caixa deste mês e aponte os 3 maiores riscos.';
  rDiv.innerHTML = '<span class="animate-pulse">Consultando CFO Virtual IA... aguarde.</span>';
  try {
    const res = await fetch('/api/cfo/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: question }),
    });
    const d = await res.json();
    rDiv.innerHTML = `<div class="font-bold mb-1 text-blue-200">Parecer do CFO:</div><div>${(d.reply || 'Sem resposta.').replace(/\n/g, '<br>')}</div>`;
  } catch (e) {
    rDiv.innerHTML = 'Falha ao consultar CFO IA.';
  }
}

// ==============================================================================
// 2. FINANCEIRO (CONTAS A RECEBER E A PAGAR)
// ==============================================================================
async function renderFinancial(container, type) {
  const isRec = type === 'receita';
  const title = isRec ? 'Contas a Receber' : 'Contas a Pagar';
  const badgeColor = isRec ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700';

  try {
    const res = await fetch(`/api/financial?type=${type}`);
    const entries = await res.json();

    let rowsHtml = entries.map(e => `
      <tr class="border-b border-slate-100 dark:border-slate-800/80 hover:bg-slate-50/60 dark:hover:bg-slate-800/40 text-xs">
        <td class="py-3 px-4">
          <div class="font-bold text-slate-800 dark:text-slate-100">${e.description}</div>
          <div class="text-[11px] text-slate-400">${e.contact_name || 'Sem contato'} · ${e.category_name || 'Geral'}</div>
        </td>
        <td class="py-3 px-4 font-medium">${formatDate(e.due_date)}</td>
        <td class="py-3 px-4 font-bold text-slate-900 dark:text-slate-100">${formatCurrency(e.amount)}</td>
        <td class="py-3 px-4 font-semibold text-emerald-600">${formatCurrency(e.paid_amount)}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${
            e.status === 'pago' ? 'bg-emerald-500/20 text-emerald-600' :
            e.status === 'parcial' ? 'bg-amber-500/20 text-amber-600' :
            'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
          }">
            ${e.status.toUpperCase()}
          </span>
        </td>
        <td class="py-3 px-4 text-right space-x-1">
          ${e.status !== 'pago' ? `
            <button onclick="openPayModal(${e.id}, '${e.type}', ${e.amount - e.paid_amount})" class="bg-emerald-600 hover:bg-emerald-700 text-white px-2.5 py-1 rounded-lg font-semibold text-[11px] transition">
              ${isRec ? 'Receber' : 'Pagar'}
            </button>
          ` : `
            <button onclick="reverseEntry(${e.id})" class="bg-amber-600 hover:bg-amber-700 text-white px-2 py-1 rounded-lg font-semibold text-[11px] transition" title="Estornar baixa">
              Estorno
            </button>
          `}
          <button onclick="deleteEntry(${e.id})" class="text-rose-500 hover:text-rose-700 p-1" title="Excluir">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            ${isRec ? '<i data-lucide="arrow-up-right-circle" class="w-5 h-5 text-emerald-500"></i>' : '<i data-lucide="arrow-down-left-circle" class="w-5 h-5 text-rose-500"></i>'}
            ${title}
          </h2>
          <p class="text-xs text-slate-400">Gerenciamento completo de lançamentos, parcelamentos e baixas</p>
        </div>
        <button onclick="openFinancialModal('${type}')" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
          <i data-lucide="plus-circle" class="w-4 h-4"></i> ${isRec ? 'Nova Receita' : 'Nova Despesa'}
        </button>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <th class="py-3 px-4">Descrição / Categoria</th>
                <th class="py-3 px-4">Vencimento</th>
                <th class="py-3 px-4">Valor Total</th>
                <th class="py-3 px-4">Valor Pago</th>
                <th class="py-3 px-4">Status</th>
                <th class="py-3 px-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml || `<tr><td colspan="6" class="py-8 text-center text-slate-400 text-xs">Nenhum lançamento de ${type} encontrado.</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro ao carregar lista de ${type}: ${err.message}</div>`;
  }
}

// Modal Nova Receita / Despesa
function openFinancialModal(type = 'despesa') {
  const isRec = type === 'receita';
  const catOptions = currentCategories
    .filter(c => c.type === type)
    .map(c => `<option value="${c.id}">${c.code} - ${c.name}</option>`)
    .join('');

  const accOptions = currentBankAccounts
    .map(a => `<option value="${a.id}">${a.name} (${formatCurrency(a.current_balance)})</option>`)
    .join('');

  const contactOptions = currentContacts
    .map(ct => `<option value="${ct.id}">${ct.name} (${ct.document || ct.type})</option>`)
    .join('');

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100 flex items-center gap-2">
        ${isRec ? '<i data-lucide="plus-circle" class="w-5 h-5 text-emerald-500"></i> Nova Receita' : '<i data-lucide="minus-circle" class="w-5 h-5 text-rose-500"></i> Nova Despesa'}
      </h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form onsubmit="submitFinancial(event, '${type}')" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Descrição *</label>
        <input required name="description" placeholder="Ex: Prestação de serviços ou Fatura de Energia" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Valor Total (R$) *</label>
          <input required type="number" step="0.01" name="amount" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Vencimento *</label>
          <input required type="date" name="due_date" value="${new Date().toISOString().slice(0, 10)}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Categoria DRE</label>
          <select name="category_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${catOptions}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Conta Bancária</label>
          <select name="bank_account_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${accOptions}
          </select>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Cliente / Fornecedor</label>
          <select name="contact_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="">Nenhum</option>
            ${contactOptions}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Parcelas</label>
          <input type="number" min="1" max="120" name="installments" value="1" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Método de Pagamento</label>
          <select name="payment_method" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="Pix">Pix</option>
            <option value="Boleto">Boleto</option>
            <option value="Cartão de Crédito">Cartão de Crédito</option>
            <option value="Transferência/TED">Transferência/TED</option>
            <option value="Dinheiro">Dinheiro</option>
          </select>
        </div>
      </div>

      <div class="flex items-center gap-2 pt-2">
        <input type="checkbox" id="already_paid" name="already_paid" class="rounded">
        <label for="already_paid" class="font-semibold text-slate-700 dark:text-slate-300">Já está pago / baixado hoje na conta selecionada</label>
      </div>

      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">Salvar Lançamento</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitFinancial(e, type) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    type,
    description: form.description.value,
    amount: parseFloat(form.amount.value),
    due_date: form.due_date.value,
    category_id: form.category_id.value ? parseInt(form.category_id.value) : null,
    bank_account_id: form.bank_account_id.value ? parseInt(form.bank_account_id.value) : null,
    contact_id: form.contact_id.value ? parseInt(form.contact_id.value) : null,
    installments: parseInt(form.installments.value) || 1,
    payment_method: form.payment_method.value,
    already_paid: form.already_paid.checked,
  };

  try {
    const res = await fetch('/api/financial', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Lançamento salvo com sucesso!', 'success');
      closeModal();
      switchTab(currentTab);
    } else {
      const err = await res.json();
      showToast(`Erro ao salvar: ${err.detail || 'Falha'}`, 'error');
    }
  } catch (err) {
    showToast('Falha na comunicação com o backend.', 'error');
  }
}

// Modal Baixa / Pagamento
function openPayModal(entryId, type, remainingAmount) {
  const isRec = type === 'receita';
  const accOptions = currentBankAccounts
    .map(a => `<option value="${a.id}">${a.name}</option>`)
    .join('');

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">
        ${isRec ? 'Confirmar Recebimento' : 'Confirmar Pagamento'} (ID #${entryId})
      </h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form onsubmit="submitPay(event, ${entryId})" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1">Valor a Baixar (R$) *</label>
        <input required type="number" step="0.01" name="amount" value="${remainingAmount.toFixed(2)}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div>
        <label class="block font-semibold mb-1">Conta Bancária de Liquidação</label>
        <select name="bank_account_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
          ${accOptions}
        </select>
      </div>
      <div>
        <label class="block font-semibold mb-1">Data do Pagamento</label>
        <input type="date" name="payment_date" value="${new Date().toISOString().slice(0, 10)}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold">Confirmar Baixa</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitPay(e, entryId) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    amount: parseFloat(form.amount.value),
    bank_account_id: parseInt(form.bank_account_id.value),
    payment_date: form.payment_date.value,
  };
  try {
    const res = await fetch(`/api/financial/${entryId}/pay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Baixa realizada com sucesso!', 'success');
      closeModal();
      switchTab(currentTab);
    } else {
      const err = await res.json();
      showToast(`Erro na baixa: ${err.detail || 'Falha'}`, 'error');
    }
  } catch (err) {
    showToast('Falha na comunicação.', 'error');
  }
}

async function reverseEntry(entryId) {
  if (!confirm('Deseja estornar as baixas realizadas para este lançamento?')) return;
  try {
    const res = await fetch(`/api/financial/${entryId}/reverse`, { method: 'POST' });
    if (res.ok) {
      showToast('Estorno realizado!', 'success');
      switchTab(currentTab);
    } else {
      showToast('Erro ao estornar.', 'error');
    }
  } catch (e) {
    showToast('Erro de comunicação.', 'error');
  }
}

async function deleteEntry(entryId) {
  if (!confirm('Deseja realmente excluir este lançamento?')) return;
  try {
    const res = await fetch(`/api/financial/${entryId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Lançamento excluído!', 'success');
      switchTab(currentTab);
    } else {
      showToast('Erro ao excluir.', 'error');
    }
  } catch (e) {
    showToast('Erro de conexão.', 'error');
  }
}

// Transfer Modal
function openTransferModal() {
  const accOptions = currentBankAccounts
    .map(a => `<option value="${a.id}">${a.name} (${formatCurrency(a.current_balance)})</option>`)
    .join('');

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100 flex items-center gap-2">
        <i data-lucide="arrow-left-right" class="w-5 h-5 text-blue-500"></i> Transferência entre Contas
      </h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form onsubmit="submitTransfer(event)" class="mt-4 space-y-4 text-xs">
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Conta de Origem (Saída)</label>
          <select name="from_account_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${accOptions}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Conta de Destino (Entrada)</label>
          <select name="to_account_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${accOptions}
          </select>
        </div>
      </div>
      <div>
        <label class="block font-semibold mb-1">Valor da Transferência (R$)</label>
        <input required type="number" step="0.01" name="amount" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div>
        <label class="block font-semibold mb-1">Descrição</label>
        <input name="description" value="Transferência entre contas" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">Transferir Agora</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitTransfer(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    from_account_id: parseInt(form.from_account_id.value),
    to_account_id: parseInt(form.to_account_id.value),
    amount: parseFloat(form.amount.value),
    description: form.description.value,
  };
  try {
    const res = await fetch('/api/bank-accounts/transfer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Transferência efetuada com sucesso!', 'success');
      closeModal();
      switchTab(currentTab);
    } else {
      const err = await res.json();
      showToast(`Erro na transferência: ${err.detail || 'Falha'}`, 'error');
    }
  } catch (err) {
    showToast('Falha de conexão.', 'error');
  }
}

// ==============================================================================
// 3. CONCILIAÇÃO BANCÁRIA OFX
// ==============================================================================
async function renderOfx(container) {
  try {
    const res = await fetch('/api/ofx');
    const items = await res.json();
    const countBadge = document.getElementById('badge-ofx');
    if (countBadge) countBadge.innerText = items.filter(i => !i.reconciled).length;

    let rowsHtml = items.map(it => `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
        <td class="py-3 px-4 font-medium">${formatDate(it.date)}</td>
        <td class="py-3 px-4 font-bold text-slate-800 dark:text-slate-100">${it.memo || it.payee || 'Lançamento OFX'}</td>
        <td class="py-3 px-4 font-bold ${it.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${formatCurrency(it.amount)}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${it.reconciled ? 'bg-emerald-500/20 text-emerald-600' : 'bg-amber-500/20 text-amber-600'}">
            ${it.reconciled ? 'CONCILIADO' : 'PENDENTE'}
          </span>
        </td>
        <td class="py-3 px-4 text-right">
          ${!it.reconciled ? `
            <button onclick="reconcileOfx(${it.id})" class="bg-blue-600 hover:bg-blue-700 text-white px-2.5 py-1 rounded-lg font-semibold text-[11px] transition">
              Conciliar
            </button>
          ` : '<span class="text-slate-400 text-[11px]">✓ Pronto</span>'}
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="file-check-2" class="w-5 h-5 text-amber-500"></i> Conciliação OFX
          </h2>
          <p class="text-xs text-slate-400">Importe extratos OFX de qualquer banco e faça a conciliação automática</p>
        </div>
        <div class="flex gap-2">
          <input type="file" id="ofx-file-input" accept=".ofx,.txt" class="hidden" onchange="uploadOfxFile(event)">
          <button onclick="document.getElementById('ofx-file-input').click()" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
            <i data-lucide="upload" class="w-4 h-4"></i> Importar Extrato OFX
          </button>
        </div>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="py-3 px-4">Data</th>
              <th class="py-3 px-4">Histórico / Descrição</th>
              <th class="py-3 px-4">Valor Extrato</th>
              <th class="py-3 px-4">Status</th>
              <th class="py-3 px-4 text-right">Ação</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || `<tr><td colspan="5" class="py-8 text-center text-slate-400 text-xs">Nenhum extrato OFX importado.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro ao carregar OFX: ${e.message}</div>`;
  }
}

async function uploadOfxFile(e) {
  const file = e.target.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  showToast('Enviando extrato OFX...', 'info');
  try {
    const res = await fetch('/api/ofx/import', { method: 'POST', body: formData });
    if (res.ok) {
      showToast('Extrato OFX importado com sucesso!', 'success');
      renderOfx(document.getElementById('main-content'));
    } else {
      showToast('Erro ao importar arquivo OFX.', 'error');
    }
  } catch (err) {
    showToast('Falha no upload.', 'error');
  }
}

async function reconcileOfx(ofxId) {
  try {
    const res = await fetch(`/api/ofx/${ofxId}/reconcile`, { method: 'POST' });
    if (res.ok) {
      showToast('Transação OFX conciliada!', 'success');
      renderOfx(document.getElementById('main-content'));
    } else {
      showToast('Não foi possível conciliar automaticamente.', 'error');
    }
  } catch (e) {
    showToast('Falha na requisição.', 'error');
  }
}

// ==============================================================================
// 4. CRM FUNIL KANBAN
// ==============================================================================
async function renderCrm(container) {
  try {
    const res = await fetch('/api/crm');
    const deals = await res.json();

    const stages = [
      { id: 'prospeccao', name: 'Prospecção' },
      { id: 'qualificacao', name: 'Qualificação' },
      { id: 'proposta', name: 'Proposta Enviada' },
      { id: 'negociacao', name: 'Negociação' },
      { id: 'ganho', name: 'Fechado Ganho' },
      { id: 'perdido', name: 'Perdido' },
    ];

    let columnsHtml = stages.map(s => {
      const stageDeals = deals.filter(d => d.stage === s.id);
      const totalStage = stageDeals.reduce((sum, d) => sum + (parseFloat(d.value) || 0), 0);

      const cardsHtml = stageDeals.map(d => `
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 shadow-xs space-y-2">
          <div class="flex justify-between items-start">
            <h4 class="font-bold text-slate-800 dark:text-slate-100 text-xs">${d.title}</h4>
            <span class="text-[10px] font-bold text-blue-600">${formatCurrency(d.value)}</span>
          </div>
          <div class="text-[11px] text-slate-400">${d.contact_name || 'Sem contato'}</div>
          <div class="flex justify-between items-center pt-2 border-t border-slate-100 dark:border-slate-800">
            <select onchange="updateDealStage(${d.id}, this.value)" class="text-[10px] bg-slate-100 dark:bg-slate-800 rounded p-1">
              ${stages.map(st => `<option value="${st.id}" ${st.id === d.stage ? 'selected' : ''}>${st.name}</option>`).join('')}
            </select>
            ${s.id === 'ganho' && !d.converted_to_sale_id ? `
              <button onclick="convertDealToSale(${d.id})" class="text-[10px] bg-emerald-600 text-white px-2 py-0.5 rounded font-semibold">
                Gerar Venda
              </button>
            ` : ''}
          </div>
        </div>
      `).join('');

      return `
        <div class="bg-slate-100 dark:bg-slate-900/50 rounded-2xl p-3 flex flex-col min-w-[240px]">
          <div class="flex justify-between items-center mb-2 px-1">
            <span class="font-bold text-xs text-slate-700 dark:text-slate-300">${s.name} (${stageDeals.length})</span>
            <span class="text-[10px] text-slate-400 font-semibold">${formatCurrency(totalStage)}</span>
          </div>
          <div class="space-y-2 flex-1 overflow-y-auto max-h-[65vh]">
            ${cardsHtml || '<div class="text-[11px] text-slate-400 text-center py-6">Vazio</div>'}
          </div>
        </div>
      `;
    }).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="kanban" class="w-5 h-5 text-purple-500"></i> CRM & Funil Comercial
          </h2>
          <p class="text-xs text-slate-400">Pipeline de oportunidades, negociações e conversão em vendas</p>
        </div>
        <button onclick="openDealModal()" class="bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
          <i data-lucide="plus-circle" class="w-4 h-4"></i> Nova Oportunidade
        </button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-3 overflow-x-auto pb-4">
        ${columnsHtml}
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro no CRM: ${e.message}</div>`;
  }
}

function openDealModal() {
  const contactOpts = currentContacts.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Nova Oportunidade (CRM)</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>
    <form onsubmit="submitDeal(event)" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1">Título da Negociação *</label>
        <input required name="title" placeholder="Ex: Projeto Implantação ERP - Empresa X" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Valor Estimado (R$) *</label>
          <input required type="number" step="0.01" name="value" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Cliente / Prospect</label>
          <select name="contact_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="">Nenhum</option>
            ${contactOpts}
          </select>
        </div>
      </div>
      <div>
        <label class="block font-semibold mb-1">Estágio Inicial</label>
        <select name="stage" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
          <option value="prospeccao">Prospecção</option>
          <option value="qualificacao">Qualificação</option>
          <option value="proposta">Proposta Enviada</option>
          <option value="negociacao">Negociação</option>
        </select>
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold">Criar Oportunidade</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitDeal(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    title: form.title.value,
    value: parseFloat(form.value.value),
    contact_id: form.contact_id.value ? parseInt(form.contact_id.value) : null,
    stage: form.stage.value,
  };
  try {
    const res = await fetch('/api/crm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Oportunidade cadastrada no funil!', 'success');
      closeModal();
      renderCrm(document.getElementById('main-content'));
    } else {
      showToast('Erro ao cadastrar deal.', 'error');
    }
  } catch (err) {
    showToast('Falha na requisição.', 'error');
  }
}

async function updateDealStage(dealId, newStage) {
  try {
    const res = await fetch(`/api/crm/${dealId}/stage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stage: newStage }),
    });
    if (res.ok) {
      showToast('Estágio atualizado!', 'success');
      renderCrm(document.getElementById('main-content'));
    }
  } catch (e) {
    showToast('Falha ao atualizar estágio.', 'error');
  }
}

async function convertDealToSale(dealId) {
  try {
    const res = await fetch(`/api/crm/${dealId}/convert`, { method: 'POST' });
    if (res.ok) {
      showToast('Oportunidade convertida em Venda com sucesso!', 'success');
      switchTab('sales');
    } else {
      showToast('Erro ao converter em venda.', 'error');
    }
  } catch (e) {
    showToast('Erro na requisição.', 'error');
  }
}

// ==============================================================================
// 5. VENDAS & ORÇAMENTOS
// ==============================================================================
async function renderSales(container) {
  try {
    const res = await fetch('/api/sales');
    const sales = await res.json();

    let rowsHtml = sales.map(s => `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
        <td class="py-3 px-4 font-bold text-slate-800 dark:text-slate-100">#${s.id}</td>
        <td class="py-3 px-4 font-medium">${formatDate(s.created_at)}</td>
        <td class="py-3 px-4">${s.client_name || 'Consumidor Final'}</td>
        <td class="py-3 px-4 font-bold text-slate-900 dark:text-slate-100">${formatCurrency(s.total_amount)}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${
            s.status === 'aprovado' ? 'bg-emerald-500/20 text-emerald-600' :
            s.status === 'faturado' ? 'bg-blue-500/20 text-blue-600' :
            'bg-amber-500/20 text-amber-600'
          }">
            ${s.status.toUpperCase()}
          </span>
        </td>
        <td class="py-3 px-4 text-right space-x-1">
          ${s.status === 'orcamento' ? `
            <button onclick="approveSale(${s.id})" class="bg-emerald-600 hover:bg-emerald-700 text-white px-2.5 py-1 rounded-lg font-semibold text-[11px] transition">
              Aprovar Venda
            </button>
          ` : ''}
          <a href="/api/sales/${s.id}/print" target="_blank" class="inline-block bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 px-2.5 py-1 rounded-lg font-semibold text-[11px] transition">
            Imprimir
          </a>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="shopping-bag" class="w-5 h-5 text-blue-500"></i> Vendas & Orçamentos
          </h2>
          <p class="text-xs text-slate-400">Controle comercial, propostas comerciais, pedidos e faturamento</p>
        </div>
        <button onclick="openSaleModal('venda')" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
          <i data-lucide="plus-circle" class="w-4 h-4"></i> Nova Venda / Orçamento
        </button>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="py-3 px-4">Pedido #</th>
              <th class="py-3 px-4">Data</th>
              <th class="py-3 px-4">Cliente</th>
              <th class="py-3 px-4">Valor Total</th>
              <th class="py-3 px-4">Status</th>
              <th class="py-3 px-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || `<tr><td colspan="6" class="py-8 text-center text-slate-400 text-xs">Nenhuma venda encontrada.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro ao carregar vendas: ${e.message}</div>`;
  }
}

function openSaleModal(defaultType = 'venda') {
  const contactOpts = currentContacts.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  const productOpts = currentProducts.map(p => `<option value="${p.id}" data-price="${p.sale_price}">${p.name} - ${formatCurrency(p.sale_price)}</option>`).join('');

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Nova Venda ou Orçamento</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form onsubmit="submitSale(event)" class="mt-4 space-y-4 text-xs">
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Tipo de Registro</label>
          <select name="type" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="venda" ${defaultType === 'venda' ? 'selected' : ''}>Pedido de Venda (Direto)</option>
            <option value="orcamento" ${defaultType === 'orcamento' ? 'selected' : ''}>Orçamento / Proposta Comercial</option>
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Cliente</label>
          <select name="contact_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="">Consumidor Final</option>
            ${contactOpts}
          </select>
        </div>
      </div>

      <div class="border border-slate-200 dark:border-slate-700 rounded-xl p-3 bg-slate-50/50 dark:bg-slate-800/30">
        <label class="block font-bold mb-2">Item Inicial</label>
        <div class="grid grid-cols-3 gap-3">
          <div class="col-span-2">
            <select id="sale-product-select" class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
              ${productOpts}
            </select>
          </div>
          <div>
            <input id="sale-product-qty" type="number" min="1" value="1" placeholder="Qtd" class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Condição de Pagamento</label>
          <select name="payment_method" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="Pix">Pix à Vista</option>
            <option value="Cartão de Crédito">Cartão de Crédito</option>
            <option value="Boleto">Boleto Bancário</option>
            <option value="Dinheiro">Dinheiro</option>
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Observações</label>
          <input name="notes" placeholder="Detalhes do pedido ou frete" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">Criar Registro</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitSale(e) {
  e.preventDefault();
  const form = e.target;
  const prodSelect = document.getElementById('sale-product-select');
  const qtyInput = document.getElementById('sale-product-qty');
  const prodId = prodSelect ? parseInt(prodSelect.value) : null;
  const qty = qtyInput ? parseFloat(qtyInput.value) || 1 : 1;
  const prod = currentProducts.find(p => p.id === prodId);
  const unitPrice = prod ? prod.sale_price : 100.0;

  const payload = {
    type: form.type.value,
    contact_id: form.contact_id.value ? parseInt(form.contact_id.value) : null,
    payment_method: form.payment_method.value,
    notes: form.notes.value,
    items: prodId ? [{ product_id: prodId, quantity: qty, unit_price: unitPrice }] : [],
    total_amount: prodId ? (unitPrice * qty) : 0.0,
  };

  try {
    const res = await fetch('/api/sales', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Venda/Orçamento criado com sucesso!', 'success');
      closeModal();
      switchTab('sales');
    } else {
      showToast('Erro ao criar venda.', 'error');
    }
  } catch (err) {
    showToast('Falha na conexão.', 'error');
  }
}

async function approveSale(saleId) {
  try {
    const res = await fetch(`/api/sales/${saleId}/approve`, { method: 'POST' });
    if (res.ok) {
      showToast('Orçamento aprovado e faturado!', 'success');
      renderSales(document.getElementById('main-content'));
    } else {
      showToast('Erro ao aprovar orçamento.', 'error');
    }
  } catch (e) {
    showToast('Erro na requisição.', 'error');
  }
}

// ==============================================================================
// 6. PDV FRENTE DE CAIXA RÁPIDO
// ==============================================================================
let pdvCart = [];

async function renderPdv(container) {
  pdvCart = [];
  container.innerHTML = `
    <div class="h-full flex flex-col md:flex-row gap-6">
      <!-- LADO ESQUERDO: CATÁLOGO DE PRODUTOS -->
      <div class="flex-1 flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="monitor-smartphone" class="w-5 h-5 text-cyan-500"></i> PDV Frente de Caixa
          </h2>
          <input
            id="pdv-search"
            type="text"
            placeholder="Buscar produto por nome, SKU ou leitor de código de barras..."
            oninput="filterPdvProducts(this.value)"
            class="bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-1.5 text-xs w-72 focus:outline-none"
          />
        </div>
        <div id="pdv-products-grid" class="grid grid-cols-2 lg:grid-cols-3 gap-3 flex-1 overflow-y-auto max-h-[60vh] p-1">
          ${renderPdvCards(currentProducts)}
        </div>
      </div>

      <!-- LADO DIREITO: CUPOM & CARRINHO -->
      <div class="w-full md:w-96 flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
        <div class="font-bold text-sm text-slate-800 dark:text-slate-100 pb-3 border-b border-slate-100 dark:border-slate-800 flex justify-between">
          <span>Cupom de Venda</span>
          <button onclick="clearPdvCart()" class="text-xs text-rose-500 hover:underline">Limpar</button>
        </div>

        <div id="pdv-cart-items" class="flex-1 overflow-y-auto space-y-2 py-3 min-h-[200px]">
          <div class="text-xs text-slate-400 text-center py-12">Nenhum item adicionado</div>
        </div>

        <div class="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
          <div class="flex justify-between items-center text-sm font-extrabold">
            <span>Total a Pagar:</span>
            <span id="pdv-cart-total" class="text-xl text-blue-600">R$ 0,00</span>
          </div>
          <div>
            <label class="block text-[11px] font-semibold text-slate-500 mb-1">Forma de Pagamento:</label>
            <select id="pdv-payment-method" class="w-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 text-xs font-semibold">
              <option value="Pix">Pix Instantâneo</option>
              <option value="Cartão de Débito">Cartão de Débito</option>
              <option value="Cartão de Crédito">Cartão de Crédito</option>
              <option value="Dinheiro">Dinheiro</option>
            </select>
          </div>
          <button onclick="finalizePdvSale()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl shadow-lg transition text-sm flex items-center justify-center gap-2">
            <i data-lucide="check-circle" class="w-4 h-4"></i> Finalizar Venda & Emitir NFC-e
          </button>
        </div>
      </div>
    </div>
  `;
}

function renderPdvCards(products) {
  if (!products.length) return '<div class="col-span-3 text-center text-slate-400 text-xs py-8">Nenhum produto cadastrado.</div>';
  return products.map(p => `
    <div onclick="addPdvItem(${p.id})" class="cursor-pointer border border-slate-200 dark:border-slate-800 hover:border-blue-500 rounded-xl p-3 bg-slate-50/50 dark:bg-slate-800/40 hover:bg-blue-50/20 transition flex flex-col justify-between">
      <div>
        <div class="font-bold text-xs text-slate-800 dark:text-slate-100 line-clamp-1">${p.name}</div>
        <div class="text-[10px] text-slate-400">SKU: ${p.sku || '-'} · Est: ${p.stock_current}</div>
      </div>
      <div class="mt-2 flex justify-between items-center">
        <span class="font-extrabold text-blue-600 dark:text-blue-400 text-xs">${formatCurrency(p.sale_price)}</span>
        <span class="text-[10px] bg-blue-100 text-blue-700 font-bold px-1.5 py-0.5 rounded">+</span>
      </div>
    </div>
  `).join('');
}

function filterPdvProducts(term) {
  const filtered = currentProducts.filter(p =>
    p.name.toLowerCase().includes(term.toLowerCase()) ||
    (p.sku && p.sku.toLowerCase().includes(term.toLowerCase()))
  );
  const grid = document.getElementById('pdv-products-grid');
  if (grid) grid.innerHTML = renderPdvCards(filtered);
}

function addPdvItem(prodId) {
  const prod = currentProducts.find(p => p.id === prodId);
  if (!prod) return;
  const existing = pdvCart.find(i => i.product_id === prodId);
  if (existing) {
    existing.quantity += 1;
  } else {
    pdvCart.push({
      product_id: prod.id,
      name: prod.name,
      unit_price: prod.sale_price,
      quantity: 1,
    });
  }
  updatePdvCartUi();
}

function removePdvItem(prodId) {
  pdvCart = pdvCart.filter(i => i.product_id !== prodId);
  updatePdvCartUi();
}

function clearPdvCart() {
  pdvCart = [];
  updatePdvCartUi();
}

function updatePdvCartUi() {
  const container = document.getElementById('pdv-cart-items');
  const totalEl = document.getElementById('pdv-cart-total');
  if (!container || !totalEl) return;

  if (pdvCart.length === 0) {
    container.innerHTML = '<div class="text-xs text-slate-400 text-center py-12">Nenhum item adicionado</div>';
    totalEl.innerText = formatCurrency(0);
    return;
  }

  let total = 0;
  container.innerHTML = pdvCart.map(item => {
    const sub = item.unit_price * item.quantity;
    total += sub;
    return `
      <div class="flex justify-between items-center text-xs p-2 rounded-lg bg-slate-50 dark:bg-slate-800">
        <div class="truncate pr-2">
          <div class="font-bold truncate text-slate-800 dark:text-slate-100">${item.name}</div>
          <div class="text-[10px] text-slate-400">${item.quantity}x ${formatCurrency(item.unit_price)}</div>
        </div>
        <div class="flex items-center gap-2">
          <span class="font-bold text-slate-900 dark:text-slate-100">${formatCurrency(sub)}</span>
          <button onclick="removePdvItem(${item.product_id})" class="text-rose-500 hover:text-rose-700"><i data-lucide="x" class="w-3.5 h-3.5"></i></button>
        </div>
      </div>
    `;
  }).join('');
  totalEl.innerText = formatCurrency(total);
  if (window.lucide) lucide.createIcons();
}

async function finalizePdvSale() {
  if (pdvCart.length === 0) {
    showToast('Adicione produtos ao cupom antes de finalizar.', 'warning');
    return;
  }
  const payMethod = document.getElementById('pdv-payment-method').value;
  const total = pdvCart.reduce((sum, i) => sum + (i.unit_price * i.quantity), 0);

  const payload = {
    type: 'pdv',
    payment_method: payMethod,
    items: pdvCart,
    total_amount: total,
    notes: 'Venda rápida balcão PDV',
  };

  try {
    const res = await fetch('/api/sales', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const data = await res.json();
      showToast(`Venda PDV #${data.id} realizada com sucesso!`, 'success');
      clearPdvCart();
    } else {
      showToast('Erro ao concluir venda no PDV.', 'error');
    }
  } catch (e) {
    showToast('Falha ao comunicar com PDV.', 'error');
  }
}

// ==============================================================================
// 7. ORDENS DE SERVIÇO & CONTRATOS RECORRENTES
// ==============================================================================
async function renderServiceOrders(container) {
  try {
    const [osRes, contRes] = await Promise.all([
      fetch('/api/service-orders').then(r => r.json()),
      fetch('/api/contracts').then(r => r.json()),
    ]);

    const osList = Array.isArray(osRes) ? osRes : [];
    const contracts = Array.isArray(contRes) ? contRes : [];

    let osRows = osList.map(os => `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
        <td class="py-3 px-4 font-bold">#${os.id}</td>
        <td class="py-3 px-4 font-bold text-slate-800 dark:text-slate-100">${os.title}</td>
        <td class="py-3 px-4">${os.client_name || 'Sem cliente'}</td>
        <td class="py-3 px-4 font-bold text-slate-900 dark:text-slate-100">${formatCurrency(os.total_amount)}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${
            os.status === 'concluido' ? 'bg-emerald-500/20 text-emerald-600' :
            os.status === 'faturado' ? 'bg-blue-500/20 text-blue-600' :
            'bg-amber-500/20 text-amber-600'
          }">
            ${os.status.toUpperCase()}
          </span>
        </td>
        <td class="py-3 px-4 text-right space-x-1">
          ${os.status !== 'faturado' ? `
            <button onclick="billServiceOrder(${os.id})" class="bg-blue-600 hover:bg-blue-700 text-white px-2.5 py-1 rounded-lg font-semibold text-[11px] transition">
              Faturar OS
            </button>
          ` : ''}
          <a href="/api/service-orders/${os.id}/print" target="_blank" class="inline-block bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2.5 py-1 rounded-lg font-semibold text-[11px]">
            Imprimir
          </a>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="wrench" class="w-5 h-5 text-orange-500"></i> Ordens de Serviço & Contratos Recorrentes
          </h2>
          <p class="text-xs text-slate-400">Prestação de serviços técnicos, faturamento recorrente e emissão de NFS-e</p>
        </div>
        <button onclick="openOsModal()" class="bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
          <i data-lucide="plus-circle" class="w-4 h-4"></i> Nova Ordem de Serviço
        </button>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="py-3 px-4">OS #</th>
              <th class="py-3 px-4">Serviço / Título</th>
              <th class="py-3 px-4">Cliente</th>
              <th class="py-3 px-4">Valor Total</th>
              <th class="py-3 px-4">Status</th>
              <th class="py-3 px-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            ${osRows || `<tr><td colspan="6" class="py-8 text-center text-slate-400 text-xs">Nenhuma Ordem de Serviço registrada.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro em OS: ${e.message}</div>`;
  }
}

function openOsModal() {
  const contactOpts = currentContacts.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Nova Ordem de Serviço</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>
    <form onsubmit="submitOs(event)" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1">Título / Equipamento / Escopo do Serviço *</label>
        <input required name="title" placeholder="Ex: Manutenção Servidor Dell ou Instalação Cabeamento" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Cliente</label>
          <select name="contact_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${contactOpts}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Valor do Serviço (R$) *</label>
          <input required type="number" step="0.01" name="total_amount" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>
      <div>
        <label class="block font-semibold mb-1">Laudo / Descrição dos Trabalhos</label>
        <textarea name="description" rows="3" placeholder="Diagnóstico do problema e serviços executados" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5"></textarea>
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white font-bold">Salvar OS</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitOs(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    title: form.title.value,
    contact_id: form.contact_id.value ? parseInt(form.contact_id.value) : null,
    total_amount: parseFloat(form.total_amount.value),
    description: form.description.value,
  };
  try {
    const res = await fetch('/api/service-orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Ordem de Serviço criada com sucesso!', 'success');
      closeModal();
      renderServiceOrders(document.getElementById('main-content'));
    } else {
      showToast('Erro ao criar OS.', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação.', 'error');
  }
}

async function billServiceOrder(osId) {
  try {
    const res = await fetch(`/api/service-orders/${osId}/bill`, { method: 'POST' });
    if (res.ok) {
      showToast('OS faturada e enviada para o Contas a Receber!', 'success');
      renderServiceOrders(document.getElementById('main-content'));
    } else {
      showToast('Erro ao faturar OS.', 'error');
    }
  } catch (e) {
    showToast('Falha na conexão.', 'error');
  }
}

// ==============================================================================
// 8. ESTOQUE, PRODUTOS & CLIENTES / FORNECEDORES
// ==============================================================================
async function renderInventory(container) {
  try {
    const products = currentProducts;

    let prodRows = products.map(p => `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
        <td class="py-3 px-4 font-bold text-slate-800 dark:text-slate-100">${p.name}</td>
        <td class="py-3 px-4 text-slate-400 font-mono">${p.sku || '-'}</td>
        <td class="py-3 px-4">${p.ncm || '-'}</td>
        <td class="py-3 px-4 font-bold ${p.stock_current <= p.stock_min ? 'text-rose-600' : 'text-slate-800 dark:text-slate-100'}">
          ${p.stock_current} ${p.unit || 'UN'}
        </td>
        <td class="py-3 px-4 text-slate-500">${formatCurrency(p.cost_price)}</td>
        <td class="py-3 px-4 font-extrabold text-blue-600 dark:text-blue-400">${formatCurrency(p.sale_price)}</td>
        <td class="py-3 px-4 text-right">
          <button onclick="openStockAdjustModal(${p.id}, '${p.name}', ${p.stock_current})" class="bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 px-2 py-1 rounded-lg font-semibold text-[11px] transition">
            Ajustar Estoque
          </button>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="package-search" class="w-5 h-5 text-indigo-500"></i> Catálogo de Produtos, Estoque & XML
          </h2>
          <p class="text-xs text-slate-400">Controle de inventário, kardex, ficha fiscal e importação de XML de compras</p>
        </div>
        <div class="flex gap-2">
          <input type="file" id="xml-purchase-input" accept=".xml" class="hidden" onchange="uploadPurchaseXml(event)">
          <button onclick="document.getElementById('xml-purchase-input').click()" class="bg-indigo-50 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300 font-semibold px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 transition">
            <i data-lucide="file-code" class="w-4 h-4"></i> Importar XML Compra
          </button>
          <button onclick="openProductModal()" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
            <i data-lucide="plus-circle" class="w-4 h-4"></i> Novo Produto
          </button>
          <button onclick="openContactModal()" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
            <i data-lucide="user-plus" class="w-4 h-4"></i> Novo Cliente/Fornecedor
          </button>
        </div>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="py-3 px-4">Produto</th>
              <th class="py-3 px-4">SKU / Código</th>
              <th class="py-3 px-4">NCM</th>
              <th class="py-3 px-4">Estoque Atual</th>
              <th class="py-3 px-4">Custo Médio</th>
              <th class="py-3 px-4">Preço Venda</th>
              <th class="py-3 px-4 text-right">Ação</th>
            </tr>
          </thead>
          <tbody>
            ${prodRows || `<tr><td colspan="7" class="py-8 text-center text-slate-400 text-xs">Nenhum produto em estoque.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro em Produtos: ${e.message}</div>`;
  }
}

function openProductModal() {
  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Novo Produto / Serviço</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>
    <form onsubmit="submitProduct(event)" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1">Nome do Produto *</label>
        <input required name="name" placeholder="Ex: Teclado Mecânico RGB ou Licença Software" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="block font-semibold mb-1">SKU / Código Interno</label>
          <input name="sku" placeholder="PRD-001" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">NCM Fiscal</label>
          <input name="ncm" placeholder="8471.60.52" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">CFOP Padrão</label>
          <input name="cfop" value="5102" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="block font-semibold mb-1">Preço de Custo (R$)</label>
          <input type="number" step="0.01" name="cost_price" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Preço de Venda (R$) *</label>
          <input required type="number" step="0.01" name="sale_price" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Estoque Inicial</label>
          <input type="number" name="stock_current" value="0" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">Cadastrar Produto</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitProduct(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    name: form.name.value,
    sku: form.sku.value,
    ncm: form.ncm.value,
    cfop: form.cfop.value,
    cost_price: parseFloat(form.cost_price.value) || 0.0,
    sale_price: parseFloat(form.sale_price.value) || 0.0,
    stock_current: parseFloat(form.stock_current.value) || 0.0,
  };
  try {
    const res = await fetch('/api/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Produto cadastrado!', 'success');
      closeModal();
      switchTab('inventory');
    } else {
      showToast('Erro ao cadastrar produto.', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação.', 'error');
  }
}

function openStockAdjustModal(prodId, prodName, currentStock) {
  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Ajustar Estoque: ${prodName}</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>
    <form onsubmit="submitStockAdjust(event, ${prodId})" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1">Novo Saldo de Estoque Real</label>
        <input required type="number" step="1" name="new_stock" value="${currentStock}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div>
        <label class="block font-semibold mb-1">Motivo do Ajuste</label>
        <input name="reason" placeholder="Ex: Inventário Físico ou Avaria" value="Inventário de rotina" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">Salvar Ajuste</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitStockAdjust(e, prodId) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    new_stock: parseFloat(form.new_stock.value),
    reason: form.reason.value,
  };
  try {
    const res = await fetch(`/api/products/${prodId}/stock-adjust`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Estoque ajustado com sucesso!', 'success');
      closeModal();
      switchTab('inventory');
    } else {
      showToast('Erro ao ajustar estoque.', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação.', 'error');
  }
}

async function uploadPurchaseXml(e) {
  const file = e.target.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  showToast('Processando XML de Compra (NF-e)...', 'info');
  try {
    const res = await fetch('/api/xml-purchases/import', { method: 'POST', body: formData });
    if (res.ok) {
      showToast('Nota de compra importada, produtos atualizados e contas geradas!', 'success');
      switchTab('inventory');
    } else {
      showToast('Erro ao importar XML de compra.', 'error');
    }
  } catch (err) {
    showToast('Falha no upload do XML.', 'error');
  }
}

// Modal Cadastro de Contatos com Busca CNPJ e CEP
function openContactModal() {
  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Novo Cliente / Fornecedor</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>
    <form onsubmit="submitContact(event)" class="mt-4 space-y-4 text-xs">
      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block font-semibold mb-1">Tipo de Cadastro</label>
          <select name="type" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="cliente">Cliente</option>
            <option value="fornecedor">Fornecedor</option>
            <option value="ambos">Cliente & Fornecedor</option>
          </select>
        </div>
        <div class="col-span-2">
          <label class="block font-semibold mb-1">CNPJ / CPF</label>
          <div class="flex gap-2">
            <input id="contact-doc" name="document" placeholder="00.000.000/0000-00" class="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <button type="button" onclick="lookupCnpj()" class="bg-blue-600 text-white font-semibold px-3 py-2 rounded-xl text-xs flex items-center gap-1">
              <i data-lucide="search" class="w-3.5 h-3.5"></i> Consultar
            </button>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Razão Social / Nome Completo *</label>
          <input required id="contact-name" name="name" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Nome Fantasia</label>
          <input id="contact-trade-name" name="trade_name" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>

      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block font-semibold mb-1">CEP</label>
          <div class="flex gap-2">
            <input id="contact-cep" name="cep" placeholder="00000-000" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <button type="button" onclick="lookupCep()" class="bg-slate-200 dark:bg-slate-700 px-2.5 rounded-xl font-bold">CEP</button>
          </div>
        </div>
        <div class="col-span-2">
          <label class="block font-semibold mb-1">Logradouro / Rua</label>
          <input id="contact-street" name="street" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>

      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block font-semibold mb-1">Número</label>
          <input id="contact-number" name="number" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Bairro</label>
          <input id="contact-neighborhood" name="neighborhood" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Cidade / UF</label>
          <div class="flex gap-1">
            <input id="contact-city" name="city" placeholder="Cidade" class="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <input id="contact-state" name="state" placeholder="UF" maxlength="2" class="w-12 text-center bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold">Salvar Contato</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function lookupCnpj() {
  const docInput = document.getElementById('contact-doc');
  if (!docInput || !docInput.value) return;
  const raw = docInput.value.replace(/\D/g, '');
  if (raw.length !== 14) {
    showToast('CNPJ deve ter 14 dígitos.', 'warning');
    return;
  }
  showToast('Consultando Receita Federal via BrasilAPI...', 'info');
  try {
    const res = await fetch(`/api/lookup/cnpj/${raw}`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById('contact-name').value = data.name || '';
      document.getElementById('contact-trade-name').value = data.trade_name || '';
      document.getElementById('contact-cep').value = data.cep || '';
      document.getElementById('contact-street').value = data.street || '';
      document.getElementById('contact-number').value = data.number || '';
      document.getElementById('contact-neighborhood').value = data.neighborhood || '';
      document.getElementById('contact-city').value = data.city || '';
      document.getElementById('contact-state').value = data.state || '';
      showToast('Dados do CNPJ preenchidos automaticamente!', 'success');
    } else {
      showToast('CNPJ não encontrado ou serviço indisponível.', 'error');
    }
  } catch (e) {
    showToast('Falha na consulta do CNPJ.', 'error');
  }
}

async function lookupCep() {
  const cepInput = document.getElementById('contact-cep');
  if (!cepInput || !cepInput.value) return;
  const raw = cepInput.value.replace(/\D/g, '');
  if (raw.length !== 8) {
    showToast('CEP deve ter 8 dígitos.', 'warning');
    return;
  }
  try {
    const res = await fetch(`/api/lookup/cep/${raw}`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById('contact-street').value = data.street || '';
      document.getElementById('contact-neighborhood').value = data.neighborhood || '';
      document.getElementById('contact-city').value = data.city || '';
      document.getElementById('contact-state').value = data.state || '';
      showToast('Endereço preenchido!', 'success');
    } else {
      showToast('CEP não encontrado.', 'error');
    }
  } catch (e) {
    showToast('Falha ao buscar CEP.', 'error');
  }
}

async function submitContact(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    type: form.type.value,
    document: form.document.value,
    name: form.name.value,
    trade_name: form.trade_name.value,
    cep: form.cep.value,
    street: form.street.value,
    number: form.number.value,
    neighborhood: form.neighborhood.value,
    city: form.city.value,
    state: form.state.value,
  };
  try {
    const res = await fetch('/api/contacts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Contato cadastrado com sucesso!', 'success');
      closeModal();
      await preloadLookups();
      switchTab('inventory');
    } else {
      showToast('Erro ao cadastrar contato.', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação.', 'error');
  }
}

// ==============================================================================
// 9. EMISSOR FISCAL (NF-e, NFC-e, NFS-e)
// ==============================================================================
async function renderInvoices(container) {
  try {
    const res = await fetch('/api/invoices');
    const invoices = await res.json();

    let rowsHtml = invoices.map(inv => `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
        <td class="py-3 px-4 font-bold text-slate-800 dark:text-slate-100">
          ${inv.model ? inv.model.toUpperCase() : 'NF-E'} #${inv.number || inv.id}
        </td>
        <td class="py-3 px-4 font-medium">${formatDate(inv.issue_date || inv.created_at)}</td>
        <td class="py-3 px-4">${inv.recipient_name || 'Consumidor'}</td>
        <td class="py-3 px-4 font-bold text-slate-900 dark:text-slate-100">${formatCurrency(inv.total_amount)}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${
            inv.status === 'autorizada' ? 'bg-emerald-500/20 text-emerald-600' :
            inv.status === 'cancelada' ? 'bg-rose-500/20 text-rose-600' :
            'bg-amber-500/20 text-amber-600'
          }">
            ${(inv.status || 'AUTORIZADA').toUpperCase()}
          </span>
        </td>
        <td class="py-3 px-4 text-right space-x-1">
          <a href="/api/invoices/${inv.id}/danfe" target="_blank" class="inline-block bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 px-2 py-1 rounded-lg font-semibold text-[11px] transition">
            DANFE
          </a>
          <a href="/api/invoices/${inv.id}/xml" target="_blank" class="inline-block bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-1 rounded-lg font-semibold text-[11px]">
            XML
          </a>
          ${inv.status === 'autorizada' ? `
            <button onclick="cancelInvoicePrompt(${inv.id})" class="text-rose-600 hover:text-rose-800 px-2 py-1 text-[11px] font-semibold">
              Cancelar
            </button>
          ` : ''}
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="receipt" class="w-5 h-5 text-emerald-500"></i> Emissor Fiscal Inteligente (NF-e, NFC-e, NFS-e)
          </h2>
          <p class="text-xs text-slate-400">Emissão de notas fiscais com assinatura digital, DANFE em PDF e arquivo XML</p>
        </div>
        <div class="flex gap-2">
          <a href="/api/invoices/export-zip" class="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-semibold px-3 py-2 rounded-xl flex items-center gap-1.5 transition">
            <i data-lucide="archive" class="w-4 h-4"></i> Exportar ZIP Contabilidade
          </a>
          <button onclick="openEmitInvoiceModal()" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
            <i data-lucide="file-check" class="w-4 h-4"></i> Emitir Nova Nota Fiscal
          </button>
        </div>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="py-3 px-4">Nota / Modelo</th>
              <th class="py-3 px-4">Data Emissão</th>
              <th class="py-3 px-4">Destinatário</th>
              <th class="py-3 px-4">Valor Total</th>
              <th class="py-3 px-4">Status SEFAZ</th>
              <th class="py-3 px-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || `<tr><td colspan="6" class="py-8 text-center text-slate-400 text-xs">Nenhuma nota fiscal emitida ainda.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro no Emissor Fiscal: ${e.message}</div>`;
  }
}

function openEmitInvoiceModal() {
  const contactOpts = currentContacts.map(c => `<option value="${c.id}">${c.name} (${c.document || 'Sem doc'})</option>`).join('');
  const prodOpts = currentProducts.map(p => `<option value="${p.id}" data-price="${p.sale_price}">${p.name} - ${formatCurrency(p.sale_price)}</option>`).join('');

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100 flex items-center gap-2">
        <i data-lucide="file-check" class="w-5 h-5 text-emerald-500"></i> Emissão de Documento Fiscal
      </h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form onsubmit="submitEmitInvoice(event)" class="mt-4 space-y-4 text-xs">
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Modelo do Documento</label>
          <select name="model" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="55">NF-e (Modelo 55 - Mercadorias)</option>
            <option value="65">NFC-e (Modelo 65 - Consumidor)</option>
            <option value="nfse">NFS-e (Nota de Serviços Municipal)</option>
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Destinatário</label>
          <select name="recipient_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="">Consumidor Final Não Identificado</option>
            ${contactOpts}
          </select>
        </div>
      </div>

      <div class="border border-slate-200 dark:border-slate-700 rounded-xl p-3 bg-slate-50/50 dark:bg-slate-800/30">
        <label class="block font-bold mb-2">Item Fiscal Principal</label>
        <div class="grid grid-cols-3 gap-3">
          <div class="col-span-2">
            <select id="inv-product-select" class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
              ${prodOpts}
            </select>
          </div>
          <div>
            <input id="inv-product-qty" type="number" min="1" value="1" placeholder="Qtd" class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
          </div>
        </div>
      </div>

      <div>
        <label class="block font-semibold mb-1">Natureza da Operação</label>
        <input name="natureza_operacao" value="VENDA DE MERCADORIA DENTRO DO ESTADO" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>

      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold">Transmitir para SEFAZ</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitEmitInvoice(e) {
  e.preventDefault();
  const form = e.target;
  const prodSelect = document.getElementById('inv-product-select');
  const qtyInput = document.getElementById('inv-product-qty');
  const prodId = prodSelect ? parseInt(prodSelect.value) : null;
  const qty = qtyInput ? parseFloat(qtyInput.value) || 1 : 1;
  const prod = currentProducts.find(p => p.id === prodId);
  const price = prod ? prod.sale_price : 100.0;

  const payload = {
    model: form.model.value,
    recipient_id: form.recipient_id.value ? parseInt(form.recipient_id.value) : null,
    natureza_operacao: form.natureza_operacao.value,
    items: prodId ? [{ product_id: prodId, name: prod.name, quantity: qty, unit_price: price, ncm: prod.ncm || '84716052' }] : [],
    total_amount: price * qty,
  };

  showToast('Transmitindo XML e obtendo protocolo SEFAZ...', 'info');
  try {
    const res = await fetch('/api/invoices/emit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const data = await res.json();
      showToast(`Nota Fiscal emitida e autorizada! Protocolo: ${data.protocol || data.id}`, 'success');
      closeModal();
      switchTab('invoices');
    } else {
      showToast('Erro na autorização da nota fiscal.', 'error');
    }
  } catch (err) {
    showToast('Falha na transmissão.', 'error');
  }
}

async function cancelInvoicePrompt(invId) {
  const reason = prompt('Informe a justificativa do cancelamento (mínimo 15 caracteres):');
  if (!reason || reason.length < 15) {
    showToast('A justificativa deve conter no mínimo 15 caracteres.', 'warning');
    return;
  }
  try {
    const res = await fetch(`/api/invoices/${invId}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    });
    if (res.ok) {
      showToast('Nota fiscal cancelada na SEFAZ com sucesso!', 'success');
      renderInvoices(document.getElementById('main-content'));
    } else {
      showToast('Erro ao cancelar nota.', 'error');
    }
  } catch (e) {
    showToast('Falha na requisição.', 'error');
  }
}

// ==============================================================================
// 10. RELATÓRIOS (DRE) & CERTIFICADO A1
// ==============================================================================
async function renderReports(container) {
  try {
    const [dreRes, compRes] = await Promise.all([
      fetch('/api/reports/dre?regime=competencia').then(r => r.json()),
      fetch('/api/company').then(r => r.json()),
    ]);

    const lines = dreRes.lines || [];
    const comp = compRes || {};

    let dreTableRows = lines.map(l => `
      <tr class="border-b border-slate-100 dark:border-slate-800 ${l.bold ? 'font-bold bg-slate-50/60 dark:bg-slate-800/40 text-slate-900 dark:text-slate-100' : 'text-slate-700 dark:text-slate-300'} text-xs">
        <td class="py-2.5 px-4">${l.label}</td>
        <td class="py-2.5 px-4 text-right ${l.color}">${formatCurrency(l.value)}</td>
        <td class="py-2.5 px-4 text-right text-slate-400">${l.av_percent !== undefined ? `${l.av_percent}%` : '-'}</td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- DRE DEMONSTRATIVO DE RESULTADO -->
        <div class="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <i data-lucide="bar-chart-4" class="w-5 h-5 text-pink-500"></i> DRE Gerencial (Regime de Competência)
              </h2>
              <p class="text-xs text-slate-400">Demonstrativo de Resultado do Exercício com Análise Vertical</p>
            </div>
            <div class="flex gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl text-xs font-semibold">
              <button onclick="toggleDreRegime('competencia')" class="px-2.5 py-1 rounded-lg bg-white dark:bg-slate-700 shadow-xs text-slate-800 dark:text-slate-100">Competência</button>
              <button onclick="toggleDreRegime('caixa')" class="px-2.5 py-1 rounded-lg text-slate-500 hover:text-slate-800">Caixa</button>
            </div>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th class="py-2.5 px-4">Estrutura DRE</th>
                  <th class="py-2.5 px-4 text-right">Valor Líquido</th>
                  <th class="py-2.5 px-4 text-right">Análise Vertical (%)</th>
                </tr>
              </thead>
              <tbody id="dre-table-body">
                ${dreTableRows}
              </tbody>
            </table>
          </div>
        </div>

        <!-- CONFIGURAÇÃO DA EMPRESA & CERTIFICADO A1 -->
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
          <h3 class="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <i data-lucide="shield-check" class="w-5 h-5 text-blue-500"></i> Certificado A1 & Empresa
          </h3>

          <form onsubmit="submitCompanyInfo(event)" class="space-y-3 text-xs">
            <div>
              <label class="block font-semibold mb-1">Razão Social</label>
              <input name="razao_social" value="${comp.razao_social || ''}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            </div>
            <div>
              <label class="block font-semibold mb-1">CNPJ da Empresa</label>
              <input name="cnpj" value="${comp.cnpj || ''}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            </div>
            <div>
              <label class="block font-semibold mb-1">Inscrição Estadual (IE)</label>
              <input name="ie" value="${comp.ie || ''}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            </div>
            <div class="flex justify-end">
              <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-3 py-1.5 rounded-lg">Atualizar Empresa</button>
            </div>
          </form>

          <div class="pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
            <div class="font-bold text-xs text-slate-800 dark:text-slate-100">Upload Certificado Digital (.PFX ou .P12)</div>
            <input type="file" id="cert-file" accept=".pfx,.p12" class="text-xs w-full">
            <input type="password" id="cert-pass" placeholder="Senha do Certificado A1" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 text-xs">
            <button onclick="uploadCertificate()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded-xl text-xs transition">
              Salvar Certificado Digital
            </button>
          </div>
        </div>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro em Relatórios: ${e.message}</div>`;
  }
}

async function toggleDreRegime(regime) {
  try {
    const res = await fetch(`/api/reports/dre?regime=${regime}`);
    const data = await res.json();
    const tbody = document.getElementById('dre-table-body');
    if (!tbody) return;
    tbody.innerHTML = (data.lines || []).map(l => `
      <tr class="border-b border-slate-100 dark:border-slate-800 ${l.bold ? 'font-bold bg-slate-50/60 dark:bg-slate-800/40 text-slate-900 dark:text-slate-100' : 'text-slate-700 dark:text-slate-300'} text-xs">
        <td class="py-2.5 px-4">${l.label}</td>
        <td class="py-2.5 px-4 text-right ${l.color}">${formatCurrency(l.value)}</td>
        <td class="py-2.5 px-4 text-right text-slate-400">${l.av_percent !== undefined ? `${l.av_percent}%` : '-'}</td>
      </tr>
    `).join('');
  } catch (e) {
    showToast('Erro ao alternar regime DRE.', 'error');
  }
}

async function submitCompanyInfo(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    razao_social: form.razao_social.value,
    cnpj: form.cnpj.value,
    ie: form.ie.value,
  };
  try {
    const res = await fetch('/api/company', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Dados da empresa atualizados!', 'success');
    } else {
      showToast('Erro ao atualizar dados.', 'error');
    }
  } catch (e) {
    showToast('Falha na requisição.', 'error');
  }
}

async function uploadCertificate() {
  const fileInput = document.getElementById('cert-file');
  const passInput = document.getElementById('cert-pass');
  if (!fileInput.files[0] || !passInput.value) {
    showToast('Selecione o arquivo do certificado e digite a senha.', 'warning');
    return;
  }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('password', passInput.value);

  showToast('Enviando e validando certificado A1...', 'info');
  try {
    const res = await fetch('/api/company/certificate', { method: 'POST', body: formData });
    if (res.ok) {
      showToast('Certificado A1 configurado com sucesso!', 'success');
      passInput.value = '';
    } else {
      showToast('Falha ao configurar certificado.', 'error');
    }
  } catch (e) {
    showToast('Erro no envio do certificado.', 'error');
  }
}

// Initial Boot
document.addEventListener('DOMContentLoaded', () => {
  const theme = localStorage.getItem('cortex_theme');
  if (theme === 'dark') {
    document.documentElement.classList.add('dark');
  }
  switchTab('dashboard');
});

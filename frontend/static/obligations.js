// ============================================================
// CALENDÁRIO DE OBRIGAÇÕES FISCAIS — Cortex ERP Pro+
// SPED, DCTFWeb, EFD-Reinf, eSocial, IRPF e demais prazos
// ============================================================

const OBL_MONTHS = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];

// Obrigações fixas anuais (mês base 1=jan)
const OBLIGATIONS_FIXED = [
  // Mensais (todo mês)
  { id:'das',       name:'DAS — Simples Nacional',         day:20, monthly:true, regime:['simples_nacional','mei'], color:'bg-green-500/20 text-green-400 border-green-500/30', icon:'landmark' },
  { id:'dctfweb',   name:'DCTFWeb / DARF Folha',           day:20, monthly:true, regime:['lucro_real','lucro_presumido','simples_nacional'], color:'bg-blue-500/20 text-blue-400 border-blue-500/30', icon:'file-check' },
  { id:'efd_reinf', name:'EFD-Reinf',                      day:15, monthly:true, regime:['lucro_real','lucro_presumido'], color:'bg-indigo-500/20 text-indigo-400 border-indigo-500/30', icon:'file-code' },
  { id:'esocial',   name:'eSocial — Eventos Periódicos',   day:15, monthly:true, regime:['lucro_real','lucro_presumido','simples_nacional'], color:'bg-teal-500/20 text-teal-400 border-teal-500/30', icon:'users' },
  { id:'fgts',      name:'FGTS',                           day:7,  monthly:true, regime:['lucro_real','lucro_presumido','simples_nacional'], color:'bg-orange-500/20 text-orange-400 border-orange-500/30', icon:'wallet' },
  { id:'inss',      name:'GPS — INSS',                     day:20, monthly:true, regime:['lucro_real','lucro_presumido'], color:'bg-cyan-500/20 text-cyan-400 border-cyan-500/30', icon:'shield' },
  { id:'sped_efd',  name:'SPED Fiscal (EFD ICMS/IPI)',     day:25, monthly:true, regime:['lucro_real','lucro_presumido'], color:'bg-amber-500/20 text-amber-400 border-amber-500/30', icon:'file-code-2' },
  { id:'efd_cont',  name:'EFD Contribuições (PIS/COFINS)', day:10, monthly:true, next_month:true, regime:['lucro_real','lucro_presumido'], color:'bg-rose-500/20 text-rose-400 border-rose-500/30', icon:'file-text' },

  // Trimestrais / Anuais
  { id:'irpj_q1',  name:'IRPJ/CSLL Estimativa',  month:3,  day:31, regime:['lucro_real'], color:'bg-violet-500/20 text-violet-400 border-violet-500/30', icon:'calculator', note:'Trimestre 1' },
  { id:'irpj_q2',  name:'IRPJ/CSLL Estimativa',  month:6,  day:30, regime:['lucro_real'], color:'bg-violet-500/20 text-violet-400 border-violet-500/30', icon:'calculator', note:'Trimestre 2' },
  { id:'irpj_q3',  name:'IRPJ/CSLL Estimativa',  month:9,  day:30, regime:['lucro_real'], color:'bg-violet-500/20 text-violet-400 border-violet-500/30', icon:'calculator', note:'Trimestre 3' },
  { id:'irpj_q4',  name:'IRPJ/CSLL Estimativa',  month:12, day:31, regime:['lucro_real'], color:'bg-violet-500/20 text-violet-400 border-violet-500/30', icon:'calculator', note:'Trimestre 4' },
  { id:'ecf',      name:'ECF (IRPJ/CSLL Anual)',  month:7,  day:31, regime:['lucro_real','lucro_presumido'], color:'bg-fuchsia-500/20 text-fuchsia-400 border-fuchsia-500/30', icon:'file-spreadsheet', note:'Ano anterior' },
  { id:'ecd',      name:'SPED ECD',               month:5,  day:31, regime:['lucro_real','lucro_presumido'], color:'bg-sky-500/20 text-sky-400 border-sky-500/30', icon:'book-open', note:'Ano anterior' },
  { id:'dmed',     name:'DMED',                   month:2,  day:28, regime:['lucro_real','lucro_presumido','simples_nacional'], color:'bg-pink-500/20 text-pink-400 border-pink-500/30', icon:'heart', note:'Planos de saúde' },
  { id:'dimob',    name:'DIMOB',                  month:2,  day:28, regime:['lucro_real','lucro_presumido'], color:'bg-lime-500/20 text-lime-400 border-lime-500/30', icon:'home', note:'Imobiliárias' },
  { id:'dirbi',    name:'DIRBI',                  month:7,  day:20, monthly:true, regime:['lucro_real','lucro_presumido'], color:'bg-orange-500/20 text-orange-400 border-orange-500/30', icon:'receipt', note:'Benefícios Fiscais' },
  { id:'defis',    name:'DEFIS',                  month:3,  day:31, regime:['simples_nacional'], color:'bg-green-500/20 text-green-400 border-green-500/30', icon:'file-check-2', note:'Simples Nacional' },
];

let oblSubTab = 'calendario';
let oblCompetencia = new Date().toISOString().slice(0, 7);

async function renderObligations(container) {
  const tabs = [
    { id: 'calendario', label: 'Calendário Fiscal', icon: 'calendar-check' },
    { id: 'processos',  label: 'Processos & Protocolo Digital', icon: 'clipboard-check' },
    { id: 'cnds',       label: 'Monitoramento de CNDs', icon: 'file-badge-2' },
    { id: 'cruzamento', label: 'Auditoria Fiscal Cruzada', icon: 'git-compare' },
  ];
  container.innerHTML = `
    <div class="space-y-5">
      <div class="flex flex-wrap gap-2">
        ${tabs.map(t => `
          <button onclick="oblSubTab='${t.id}';renderObligations(document.getElementById('main-content'))"
            class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition
              ${oblSubTab === t.id
                ? 'bg-sky-600 text-white'
                : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'}">
            <i data-lucide="${t.icon}" class="w-3.5 h-3.5"></i>${t.label}
          </button>`).join('')}
      </div>
      <div id="obl-tab-body"></div>
    </div>`;
  const body = document.getElementById('obl-tab-body');
  if (oblSubTab === 'calendario') await renderOblCalendario(body);
  else if (oblSubTab === 'processos') await renderOblProcessos(body);
  else if (oblSubTab === 'cnds') await renderOblCnds(body);
  else if (oblSubTab === 'cruzamento') await renderOblCruzamento(body);
  if (window.lucide) lucide.createIcons();
}

async function renderOblCalendario(container) {
  const cfg = await apiFetch('/api/simples/config').catch(() => ({}));
  const regime = cfg.regime || 'simples_nacional';
  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth(); // 0-indexed

  // Build upcoming obligations
  const upcoming = [];
  OBLIGATIONS_FIXED.forEach(obl => {
    if (!obl.regime.includes(regime)) return;
    if (obl.monthly) {
      // next 3 months
      for (let m = month; m <= month + 2 && m < 12; m++) {
        const d = new Date(year, m, obl.day);
        upcoming.push({ ...obl, date: d, label: `${String(obl.day).padStart(2,'0')}/${String(m+1).padStart(2,'0')}/${year}` });
      }
    } else if (obl.month) {
      const d = new Date(year, obl.month - 1, obl.day);
      upcoming.push({ ...obl, date: d, label: `${String(obl.day).padStart(2,'0')}/${String(obl.month).padStart(2,'0')}/${year}` });
    }
  });
  upcoming.sort((a,b) => a.date - b.date);

  const thisMonth = upcoming.filter(o => o.date.getMonth() === month && o.date.getFullYear() === year);
  const nextMonth = upcoming.filter(o => o.date.getMonth() === month+1 && o.date.getFullYear() === year);
  const future    = upcoming.filter(o => o.date.getMonth() > month+1);

  container.innerHTML = `
  <div class="space-y-5">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h2 class="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <i data-lucide="calendar-check" class="w-5 h-5 text-sky-400"></i> Calendário de Obrigações Fiscais
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">Regime: <span class="text-sky-400 font-semibold">${regime.replace('_',' ')}</span> — ${year}</p>
      </div>
      <div class="flex gap-2">
        <div class="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs px-3 py-1.5 rounded-lg font-semibold">${thisMonth.length} este mês</div>
        <div class="bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs px-3 py-1.5 rounded-lg font-semibold">${nextMonth.length} próximo mês</div>
      </div>
    </div>

    <!-- Este mês -->
    ${oblSection(`Obrigações de ${OBL_MONTHS[month]}/${year}`, thisMonth, today)}

    <!-- Próximo mês -->
    ${oblSection(`Obrigações de ${OBL_MONTHS[month+1] || '—'}/${year}`, nextMonth, today)}

    <!-- Próximas -->
    ${future.length ? oblSection('Próximas Obrigações', future.slice(0,10), today) : ''}

    <!-- Legenda -->
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
      <div class="font-semibold text-slate-600 dark:text-slate-300 text-xs mb-3">Legenda — Obrigações do Regime ${regime}</div>
      <div class="flex flex-wrap gap-2">
        ${OBLIGATIONS_FIXED.filter(o=>o.regime.includes(regime)).map(o=>`
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-semibold ${o.color}">
            <i data-lucide="${o.icon}" class="w-3 h-3"></i>${o.name}
          </span>`).join('')}
      </div>
    </div>
  </div>`;
  if (window.lucide) lucide.createIcons();
}

async function renderOblProcessos(container) {
  const procs = await apiFetch(`/api/office/processes?competencia=${oblCompetencia}`).catch(() => []);
  const statusBadge = {
    pendente: 'bg-amber-500/15 text-amber-500',
    em_andamento: 'bg-blue-500/15 text-blue-500',
    protocolado: 'bg-indigo-500/15 text-indigo-500',
    confirmado_cliente: 'bg-emerald-500/15 text-emerald-500',
  };
  const rows = (procs || []).map(p => `
    <tr class="border-b border-slate-100 dark:border-slate-800 text-sm">
      <td class="px-4 py-2.5 font-medium text-slate-800 dark:text-slate-200">${p.obrigacao}</td>
      <td class="px-4 py-2.5 font-mono text-xs text-slate-500">${p.vencimento}</td>
      <td class="px-4 py-2.5 text-xs text-slate-500">${p.responsavel || '—'}</td>
      <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${statusBadge[p.status] || 'bg-slate-200 text-slate-600'}">${p.status}</span></td>
      <td class="px-4 py-2.5 font-mono text-xs text-indigo-500">${p.protocolo_hash || '—'}</td>
      <td class="px-4 py-2.5 text-right space-x-2">
        ${p.status === 'pendente' || p.status === 'em_andamento'
          ? `<button onclick="oblProtocolar(${p.id})" class="text-xs bg-indigo-600 text-white px-2.5 py-1 rounded-lg font-semibold">Protocolar Entrega</button>` : ''}
        ${p.status === 'protocolado'
          ? `<button onclick="oblConfirmarCliente(${p.id})" class="text-xs bg-emerald-600 text-white px-2.5 py-1 rounded-lg font-semibold">Confirmar Leitura</button>` : ''}
      </td>
    </tr>`).join('') || '<tr><td colspan="6" class="text-center text-slate-400 py-8 text-sm">Nenhum processo gerado para esta competência. Clique em "Gerar Agenda do Mês".</td></tr>';

  container.innerHTML = `
    <div class="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-white">Domínio Processos &amp; Protocolo Digital</h2>
          <p class="text-xs text-slate-400">Agenda automática por regime tributário, hash de entrega e confirmação do cliente</p>
        </div>
        <div class="flex items-center gap-2">
          <input type="month" value="${oblCompetencia}" onchange="oblCompetencia=this.value;renderObligations(document.getElementById('main-content'))"
            class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-lg px-2.5 py-1.5"/>
          <button onclick="oblGerarProcessos()" class="bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold px-4 py-2 rounded-xl">
            + Gerar Agenda do Mês
          </button>
        </div>
      </div>
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
              <th class="px-4 py-2.5 text-left">Obrigação</th>
              <th class="px-4 py-2.5 text-left">Vencimento</th>
              <th class="px-4 py-2.5 text-left">Responsável</th>
              <th class="px-4 py-2.5 text-left">Status</th>
              <th class="px-4 py-2.5 text-left">Protocolo Digital</th>
              <th class="px-4 py-2.5 text-right">Ações</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>
    </div>`;
}

async function oblGerarProcessos() {
  await apiFetch(`/api/office/processes/generate?competencia=${oblCompetencia}`, { method: 'POST' });
  showToast(`Agenda de processos gerada para ${oblCompetencia}!`, 'success');
  renderObligations(document.getElementById('main-content'));
}

async function oblProtocolar(id) {
  const res = await apiFetch(`/api/office/processes/${id}/protocolar`, { method: 'POST' });
  showToast(`Protocolado! Hash: ${res.protocolo_hash}`, 'success');
  renderObligations(document.getElementById('main-content'));
}

async function oblConfirmarCliente(id) {
  await apiFetch(`/api/office/processes/${id}/confirmar-leitura`, { method: 'POST' });
  showToast('Leitura confirmada pelo cliente!', 'success');
  renderObligations(document.getElementById('main-content'));
}

async function renderOblCnds(container) {
  const cnds = await apiFetch('/api/office/cnds').catch(() => []);
  const rows = (cnds || []).map(c => {
    const cls = c.status_alerta === 'vencida' ? 'bg-rose-500/15 text-rose-500'
      : c.status_alerta === 'vencendo' ? 'bg-amber-500/15 text-amber-500' : 'bg-emerald-500/15 text-emerald-500';
    return `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-sm">
        <td class="px-4 py-2.5 font-semibold">${c.tipo}</td>
        <td class="px-4 py-2.5 font-mono text-xs">${c.numero_certidao || '—'}</td>
        <td class="px-4 py-2.5 text-xs">${c.data_emissao}</td>
        <td class="px-4 py-2.5 text-xs font-semibold">${c.data_validade}</td>
        <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${cls}">${c.status_alerta} (${c.dias_para_vencer}d)</span></td>
        <td class="px-4 py-2.5 text-right">
          <button onclick="oblDeleteCnd(${c.id})" class="text-xs text-rose-500 hover:underline">Excluir</button>
        </td>
      </tr>`;
  }).join('') || '<tr><td colspan="6" class="text-center text-slate-400 py-8 text-sm">Nenhuma CND cadastrada.</td></tr>';

  container.innerHTML = `
    <div class="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-white">Monitoramento de Certidões Negativas (CNDs)</h2>
          <p class="text-xs text-slate-400">Federal RFB/PGFN, FGTS CRF, Estadual, Municipal e Trabalhista CNDT</p>
        </div>
        <button onclick="oblOpenCndModal()" class="bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold px-4 py-2 rounded-xl">+ Cadastrar CND</button>
      </div>
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
        <table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2.5 text-left">Tipo</th>
            <th class="px-4 py-2.5 text-left">Número</th>
            <th class="px-4 py-2.5 text-left">Emissão</th>
            <th class="px-4 py-2.5 text-left">Validade</th>
            <th class="px-4 py-2.5 text-left">Situação / Alerta</th>
            <th class="px-4 py-2.5 text-right">Ações</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function oblOpenCndModal() {
  const hoje = new Date().toISOString().slice(0, 10);
  openModal(`
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-6 space-y-4">
      <h3 class="font-bold text-lg text-slate-800 dark:text-white">Nova Certidão Negativa (CND)</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div><label class="label">Tipo</label>
          <select id="cnd-tipo" class="input w-full">
            <option value="RFB_PGFN">Federal RFB / PGFN</option>
            <option value="FGTS_CRF">FGTS (CRF Caixa)</option>
            <option value="ESTADUAL">Estadual (SEFAZ)</option>
            <option value="MUNICIPAL">Municipal (Prefeitura)</option>
            <option value="TRABALHISTA_CNDT">Trabalhista (CNDT)</option>
          </select></div>
        <div><label class="label">Número da Certidão</label><input id="cnd-num" class="input w-full" placeholder="2026.000123-4"/></div>
        <div><label class="label">Data Emissão</label><input id="cnd-emi" type="date" class="input w-full" value="${hoje}"/></div>
        <div><label class="label">Data Validade</label><input id="cnd-val" type="date" class="input w-full" value="${hoje}"/></div>
      </div>
      <div class="flex gap-2 justify-end">
        <button onclick="closeModal()" class="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-xs">Cancelar</button>
        <button onclick="oblSaveCnd()" class="bg-sky-600 text-white px-4 py-2 rounded-xl text-xs font-semibold">Salvar CND</button>
      </div>
    </div>`);
}

async function oblSaveCnd() {
  const payload = {
    tipo: document.getElementById('cnd-tipo').value,
    numero_certidao: document.getElementById('cnd-num').value.trim(),
    data_emissao: document.getElementById('cnd-emi').value,
    data_validade: document.getElementById('cnd-val').value,
  };
  await apiFetch('/api/office/cnds', { method: 'POST', body: JSON.stringify(payload) });
  showToast('CND cadastrada!', 'success');
  closeModal();
  renderObligations(document.getElementById('main-content'));
}

async function oblDeleteCnd(id) {
  await apiFetch(`/api/office/cnds/${id}`, { method: 'DELETE' });
  showToast('CND removida.', 'success');
  renderObligations(document.getElementById('main-content'));
}

async function renderOblCruzamento(container) {
  const res = await apiFetch(`/api/audit/cruzamento-fiscal?competencia=${oblCompetencia}`).catch(() => null);
  if (!res) { container.innerHTML = '<div class="text-rose-500 p-4">Erro ao executar auditoria cruzada.</div>'; return; }
  const fM = v => parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const scoreCls = res.score_conformidade === 100 ? 'text-emerald-500' : res.score_conformidade >= 60 ? 'text-amber-500' : 'text-rose-500';
  const rows = (res.cruzamentos || []).map(c => `
    <tr class="border-b border-slate-100 dark:border-slate-800 text-sm">
      <td class="px-4 py-2.5 font-semibold">${c.eixo}</td>
      <td class="px-4 py-2.5 text-xs">${c.modulo_a}: <strong class="font-mono">${fM(c.valor_a)}</strong></td>
      <td class="px-4 py-2.5 text-xs">${c.modulo_b}: <strong class="font-mono">${fM(c.valor_b)}</strong></td>
      <td class="px-4 py-2.5 text-right font-mono font-bold ${c.ok ? 'text-emerald-500' : 'text-rose-500'}">${fM(c.diferenca)}</td>
      <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${c.ok ? 'bg-emerald-500/15 text-emerald-500' : 'bg-rose-500/15 text-rose-500'}">${c.ok ? 'OK' : 'DIVERGENTE'}</span></td>
    </tr>`).join('');

  container.innerHTML = `
    <div class="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-white">Domínio Auditoria Fiscal Cruzada</h2>
          <p class="text-xs text-slate-400">Cruzamento automático NF-e × Livros Fiscais × Contabilidade × Folha × Diário</p>
        </div>
        <div class="flex items-center gap-3">
          <input type="month" value="${oblCompetencia}" onchange="oblCompetencia=this.value;renderObligations(document.getElementById('main-content'))"
            class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-lg px-2.5 py-1.5"/>
          <div class="px-4 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-bold">
            Conformidade: <span class="text-base ${scoreCls}">${res.score_conformidade}%</span>
          </div>
        </div>
      </div>
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
        <table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2.5 text-left">Eixo de Auditoria</th>
            <th class="px-4 py-2.5 text-left">Origem A</th>
            <th class="px-4 py-2.5 text-left">Origem B</th>
            <th class="px-4 py-2.5 text-right">Diferença</th>
            <th class="px-4 py-2.5 text-left">Status</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function oblSection(title, items, today) {
  if (!items.length) return '';
  return `
  <div>
    <div class="font-semibold text-slate-600 dark:text-slate-300 text-xs mb-3 uppercase tracking-wide">${title}</div>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      ${items.map(obl => {
        const isPast    = obl.date < today;
        const isToday   = obl.date.toDateString() === today.toDateString();
        const daysLeft  = Math.ceil((obl.date - today) / 86400000);
        const urgency   = daysLeft <= 3 && !isPast ? 'ring-2 ring-rose-500/50' : daysLeft <= 7 ? 'ring-1 ring-amber-500/30' : '';
        return `
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 ${urgency} ${isPast ? 'opacity-50' : ''}">
          <div class="flex items-start gap-3">
            <div class="p-2 rounded-lg border ${obl.color}">
              <i data-lucide="${obl.icon}" class="w-4 h-4"></i>
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-sm text-slate-700 dark:text-slate-200 leading-tight">${obl.name}</div>
              ${obl.note ? `<div class="text-[10px] text-slate-400">${obl.note}</div>` : ''}
              <div class="mt-1.5 flex items-center gap-2">
                <span class="font-mono text-xs font-bold text-slate-500">${obl.label}</span>
                ${isToday ? '<span class="text-[10px] bg-rose-500 text-white px-1.5 rounded font-bold">HOJE</span>'
                  : isPast ? '<span class="text-[10px] text-slate-400">vencida</span>'
                  : daysLeft <= 5 ? `<span class="text-[10px] text-amber-400 font-semibold">${daysLeft}d</span>` : ''}
              </div>
            </div>
          </div>
        </div>`;
      }).join('')}
    </div>
  </div>`;
}

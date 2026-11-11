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

async function renderObligations(container) {
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

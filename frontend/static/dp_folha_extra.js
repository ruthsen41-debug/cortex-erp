// ============================================================
// DEPARTAMENTO PESSOAL — Folha complementar, dissídio retroativo e escalas (12x36 etc.)
// Usa os helpers de dp.js: authHeaders, fBRL2, card2, inputCls, labelCls, _dpEsc, dpEmployees.
// ============================================================

const DP_TIPO_FOLHA = {
  mensal: ['Mensal', 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'],
  complementar: ['Complementar', 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'],
  dissidio: ['Dissídio', 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300'],
};

function dpTipoFolhaBadge(tipo) {
  const [rot, cls] = DP_TIPO_FOLHA[tipo || 'mensal'] || [tipo, DP_TIPO_FOLHA.mensal[1]];
  return `<span class="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${cls}">${_dpEsc(rot)}</span>`;
}

function _dpxModal(id, titulo, corpo, largura = 'max-w-4xl') {
  document.getElementById(id)?.remove();
  const div = document.createElement('div');
  div.id = id;
  div.className = 'fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto';
  div.innerHTML = `
    <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full ${largura} my-6">
      <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800">
        <h3 class="font-bold text-slate-800 dark:text-slate-100">${titulo}</h3>
        <button onclick="document.getElementById('${id}').remove()" class="text-slate-400 hover:text-slate-600 text-xl leading-none">&times;</button>
      </div>
      <div class="p-6">${corpo}</div>
    </div>`;
  document.body.appendChild(div);
  if (window.lucide) lucide.createIcons();
  return div;
}

async function _dpxPost(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
                               body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'Erro ao processar.');
  return j;
}

function _dpxCompAnterior(comp, n = 1) {
  let [a, m] = comp.split('-').map(Number);
  m -= n;
  while (m <= 0) { m += 12; a -= 1; }
  return `${a}-${String(m).padStart(2, '0')}`;
}

function _dpxEmpOptions(sel) {
  return dpEmployees.filter(e => e.active !== 0 && e.active !== false)
    .map(e => `<option value="${e.id}" ${String(sel) === String(e.id) ? 'selected' : ''}>${_dpEsc(e.name)}</option>`).join('');
}

// Resultado da simulação (complementar ou dissídio): uma linha por funcionário, rubricas ao clicar
function _dpxResultado(calc, mostrarMeses) {
  const linhas = (calc.results || []).map((r, i) => `
    <tr class="border-b border-slate-100 dark:border-slate-800 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40"
        onclick="document.getElementById('dpx-det-${i}').classList.toggle('hidden')">
      <td class="px-3 py-2 text-sm font-medium">${_dpEsc(r.employee_name)}${r.avisos.length ? ' <span title="Há avisos">⚠</span>' : ''}</td>
      ${mostrarMeses ? `<td class="px-3 py-2 text-xs text-slate-500">${(r.meses || []).map(m => m.split('-').reverse().join('/')).join(', ')}</td>` : ''}
      <td class="px-3 py-2 text-sm">${fBRL2(r.total_proventos)}</td>
      <td class="px-3 py-2 text-sm text-rose-500">-${fBRL2(r.inss)}</td>
      <td class="px-3 py-2 text-sm text-orange-500">-${fBRL2(r.irrf)}</td>
      <td class="px-3 py-2 text-sm font-bold text-emerald-600">${fBRL2(r.liquido)}</td>
      <td class="px-3 py-2 text-xs text-blue-500">${fBRL2(r.fgts)}</td>
    </tr>
    <tr id="dpx-det-${i}" class="hidden bg-slate-50/60 dark:bg-slate-900/40">
      <td colspan="${mostrarMeses ? 7 : 6}" class="px-5 py-3">
        <table class="w-full text-xs">
          ${r.lines.filter(l => l.tipo !== 'informativo').map(l => `
            <tr><td class="py-0.5 font-mono text-slate-400 w-14">${_dpEsc(l.codigo)}</td>
              <td class="py-0.5">${_dpEsc(l.nome)}</td>
              <td class="py-0.5 text-slate-400">${_dpEsc(l.referencia || '')}</td>
              <td class="py-0.5 text-right ${l.tipo === 'desconto' ? 'text-rose-500' : ''}">${l.tipo === 'desconto' ? '-' : ''}${fBRL2(l.valor)}</td></tr>`).join('')}
        </table>
        ${r.avisos.length ? `<ul class="mt-2 text-[11px] text-amber-600 list-disc ml-4">${r.avisos.map(a => `<li>${_dpEsc(a)}</li>`).join('')}</ul>` : ''}
      </td>
    </tr>`).join('');
  const t = calc.totais || {};
  const ign = (calc.ignorados || []).map(g => `<li>${_dpEsc(g.employee_name || ('Funcionário ' + g.employee_id))}: ${_dpEsc(g.motivo)}</li>`).join('');
  return `
    <div class="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
      <table class="w-full text-sm">
        <thead><tr class="text-[11px] text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
          <th class="px-3 py-2 text-left">Funcionário</th>${mostrarMeses ? '<th class="px-3 py-2 text-left">Meses</th>' : ''}
          <th class="px-3 py-2 text-left">Proventos</th><th class="px-3 py-2 text-left">INSS</th>
          <th class="px-3 py-2 text-left">IRRF</th><th class="px-3 py-2 text-left">Líquido</th><th class="px-3 py-2 text-left">FGTS</th>
        </tr></thead>
        <tbody>${linhas || `<tr><td colspan="7" class="px-3 py-6 text-center text-xs text-slate-400">Nenhuma diferença a pagar.</td></tr>`}</tbody>
        ${linhas ? `<tfoot><tr class="text-sm font-semibold"><td class="px-3 py-2">Total</td>${mostrarMeses ? '<td></td>' : ''}
          <td class="px-3 py-2">${fBRL2(t.proventos)}</td><td class="px-3 py-2 text-rose-500">-${fBRL2(t.inss)}</td>
          <td class="px-3 py-2 text-orange-500">-${fBRL2(t.irrf)}</td><td class="px-3 py-2 text-emerald-600">${fBRL2(t.liquido)}</td>
          <td class="px-3 py-2 text-blue-500">${fBRL2(t.fgts)}</td></tr></tfoot>` : ''}
      </table>
    </div>
    <p class="text-[11px] text-slate-400 mt-1">Clique no funcionário para ver as rubricas.</p>
    ${ign ? `<div class="mt-3 text-xs text-amber-700 bg-amber-50 dark:bg-amber-900/20 rounded-xl p-3"><b>Fora do cálculo:</b><ul class="list-disc ml-4 mt-1">${ign}</ul></div>` : ''}`;
}

async function _dpxAposProcessar(out) {
  document.querySelectorAll('#dpx-compl,#dpx-diss').forEach(m => m.remove());
  await renderFolha(document.getElementById('dp-body'));
  if (window.lucide) lucide.createIcons();
  if (out.run) await openFolhaDetail(out.run.id);
  const avisos = (out.avisos || []).map(a => `${a.employee_name}: ${a.avisos.join('; ')}`);
  if (out.salarios_reajustados) avisos.unshift(`${out.salarios_reajustados} salário(s) reajustado(s) no cadastro e no histórico salarial.`);
  if (avisos.length) alert('Folha gravada.\n\n' + avisos.join('\n'));
}

// ── FOLHA COMPLEMENTAR ───────────────────────────────────────
let _dpxRubricas = [];

async function abrirFolhaComplementar() {
  if (!_dpxRubricas.length) {
    _dpxRubricas = await fetch('/api/dp/rubrics', { headers: authHeaders() }).then(r => r.json()).catch(() => []);
  }
  const comp = document.getElementById('folha-comp')?.value || '';
  _dpxModal('dpx-compl', 'Folha complementar', `
    <p class="text-xs text-slate-500 mb-4">Para pagar o que ficou de fora da folha mensal já processada (hora extra esquecida,
      prêmio, correção de rubrica). O mês é recalculado com os lançamentos novos e só a <b>diferença</b> é paga; INSS e IRRF
      consideram o total do mês, descontando o que já foi retido.</p>
    <div class="grid grid-cols-3 gap-3 mb-4">
      <div>${labelCls('Competência')}<input id="dpx-c-comp" type="month" value="${comp}" onchange="_dpxComplCarregar()" class="${inputCls()}"></div>
      <div class="col-span-2">${labelCls('Descrição')}<input id="dpx-c-desc" value="Folha complementar" class="${inputCls()}"></div>
    </div>
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs font-semibold text-slate-500">Lançamentos</span>
      <button onclick="_dpxComplLinha()" class="text-xs text-violet-600 hover:underline">+ adicionar lançamento</button>
    </div>
    <div id="dpx-c-linhas" class="space-y-2 mb-4"></div>
    <div class="flex justify-end gap-2">
      <button onclick="_dpxComplRodar(false)" class="text-xs px-4 py-2 rounded-xl border border-violet-200 text-violet-700 bg-violet-50 hover:bg-violet-100">Simular</button>
      <button onclick="_dpxComplRodar(true)" class="text-xs px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold">Processar complementar</button>
    </div>
    <div id="dpx-c-res" class="mt-5"></div>`);
  await _dpxComplCarregar();
}

// Funcionários da folha mensal da competência + rubricas que não aceitam lançamento (calculadas pelo sistema)
let _dpxComplOpcoes = { funcionarios: [], rubricas_bloqueadas: [] };

async function _dpxComplCarregar() {
  const comp = document.getElementById('dpx-c-comp')?.value;
  const box = document.getElementById('dpx-c-linhas');
  if (!box) return;
  box.innerHTML = '';
  const res = document.getElementById('dpx-c-res');
  if (res) res.innerHTML = '';
  _dpxComplOpcoes ={ funcionarios: [], rubricas_bloqueadas: [] };
  if (comp) {
    _dpxComplOpcoes = await fetch(`/api/dp/payroll/complementar/opcoes?competence=${comp}`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : _dpxComplOpcoes).catch(() => _dpxComplOpcoes);
  }
  if (!_dpxComplOpcoes.funcionarios.length) {
    box.innerHTML = `<div class="text-xs text-amber-700 bg-amber-50 rounded-xl px-3 py-2">Não há folha mensal processada em
      ${_dpEsc(comp || '—')}. Processe a folha mensal antes da complementar.</div>`;
    return;
  }
  _dpxComplLinha();
}

function _dpxComplLinha() {
  const box = document.getElementById('dpx-c-linhas');
  if (!box || !_dpxComplOpcoes.funcionarios.length) return;
  const bloq = new Set(_dpxComplOpcoes.rubricas_bloqueadas || []);
  const opts = _dpxRubricas.filter(r => r.ativo !== 0 && r.tipo !== 'informativo' && !bloq.has(r.codigo))
    .map(r => `<option value="${_dpEsc(r.codigo)}">${_dpEsc(r.codigo)} — ${_dpEsc(r.nome)}</option>`).join('');
  const emps = _dpxComplOpcoes.funcionarios
    .map(e => `<option value="${e.id}">${_dpEsc(e.name)} (#${e.id})</option>`).join('');
  const row = document.createElement('div');
  row.className = 'grid grid-cols-12 gap-2 items-center dpx-c-linha';
  row.innerHTML = `
    <select class="col-span-4 ${inputCls()}" data-f="employee_id">${emps}</select>
    <select class="col-span-4 ${inputCls()}" data-f="codigo">${opts}</select>
    <input class="col-span-1 ${inputCls()}" data-f="quantidade" type="number" step="0.01" placeholder="Qtd/horas" title="Quantidade ou horas">
    <input class="col-span-2 ${inputCls()}" data-f="valor" type="number" step="0.01" placeholder="Valor (R$)" title="Valor informado (se a rubrica não tiver fórmula)">
    <button class="col-span-1 text-rose-500 text-lg" title="Remover" onclick="this.parentElement.remove()">&times;</button>`;
  box.appendChild(row);
}

async function _dpxComplRodar(gravar) {
  const lancamentos = [...document.querySelectorAll('.dpx-c-linha')].map(r => {
    const o = {};
    r.querySelectorAll('[data-f]').forEach(i => { o[i.dataset.f] = i.value; });
    return { employee_id: Number(o.employee_id), codigo: o.codigo, quantidade: Number(o.quantidade || 0), valor: Number(o.valor || 0) };
  }).filter(l => l.employee_id && l.codigo && (l.quantidade || l.valor));
  const body = { competence: document.getElementById('dpx-c-comp').value, lancamentos,
                 descricao: document.getElementById('dpx-c-desc').value };
  const res = document.getElementById('dpx-c-res');
  if (!lancamentos.length) { res.innerHTML = '<div class="text-xs text-rose-500">Informe ao menos um lançamento com quantidade ou valor.</div>'; return; }
  if (gravar && !confirm(`Gravar a folha complementar de ${body.competence}?`)) return;
  res.innerHTML = '<div class="text-xs text-slate-400">Calculando...</div>';
  try {
    if (gravar) return _dpxAposProcessar(await _dpxPost('/api/dp/payroll/complementar', body));
    res.innerHTML = _dpxResultado(await _dpxPost('/api/dp/payroll/complementar/preview', body), false);
  } catch (e) { res.innerHTML = `<div class="text-xs text-rose-500">${_dpEsc(e.message)}</div>`; }
}

// ── DISSÍDIO / ACORDO / CONVENÇÃO RETROATIVOS ────────────────
function abrirDissidio() {
  const comp = document.getElementById('folha-comp')?.value || '';
  const hoje = new Date().toISOString().slice(0, 10);
  _dpxModal('dpx-diss', 'Dissídio / acordo retroativo', `
    <p class="text-xs text-slate-500 mb-4">Paga as diferenças salariais de meses já fechados quando a convenção, o acordo ou a
      sentença normativa sai depois da data-base. O percentual é aplicado sobre as rubricas ligadas ao salário (salário, horas
      extras, adicional noturno, periculosidade, DSR, férias e rubricas com fórmula sobre o salário). O INSS é recalculado mês a
      mês com a tabela de cada mês; o IRRF entra no mês do pagamento (anos anteriores como RRA). No eSocial as diferenças vão no
      S-1200 da competência de pagamento, grupo <b>infoPerAnt</b>.</p>
    <div class="grid grid-cols-4 gap-3">
      <div>${labelCls('Pagar na competência')}<input id="dpx-d-pg" type="month" value="${comp}" class="${inputCls()}"></div>
      <div>${labelCls('Diferenças desde (data-base)')}<input id="dpx-d-ini" type="month" value="${comp ? _dpxCompAnterior(comp, 4) : ''}" class="${inputCls()}"></div>
      <div>${labelCls('Até')}<input id="dpx-d-fim" type="month" value="${comp ? _dpxCompAnterior(comp, 1) : ''}" class="${inputCls()}"></div>
      <div>${labelCls('Reajuste (%)')}<input id="dpx-d-pct" type="number" step="0.01" min="0" class="${inputCls()}" placeholder="ex.: 5,5"></div>
      <div class="col-span-2">${labelCls('Instrumento')}
        <select id="dpx-d-tp" class="${inputCls()}">
          <option value="C">C — Convenção Coletiva de Trabalho</option>
          <option value="A">A — Acordo Coletivo de Trabalho</option>
          <option value="D">D — Sentença normativa (dissídio)</option>
          <option value="B">B — Legislação federal, estadual ou municipal</option>
        </select></div>
      <div>${labelCls('Data de assinatura')}<input id="dpx-d-dt" type="date" value="${hoje}" class="${inputCls()}"></div>
      <div>${labelCls('Funcionários')}
        <select id="dpx-d-emp" class="${inputCls()}"><option value="">Todos com folha no período</option>${_dpxEmpOptions()}</select></div>
      <div class="col-span-4">${labelCls('Descrição (vai para o eSocial)')}<input id="dpx-d-desc" class="${inputCls()}" placeholder="ex.: CCT 2026/2027 — reajuste de 5,5% a partir de maio"></div>
    </div>
    <label class="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300 mt-3">
      <input id="dpx-d-sal" type="checkbox" checked> Reajustar também o salário do cadastro a partir da competência de pagamento
      (registra no histórico salarial — desmarque se já reajustou)</label>
    <div class="flex justify-end gap-2 mt-4">
      <button onclick="_dpxDissRodar(false)" class="text-xs px-4 py-2 rounded-xl border border-violet-200 text-violet-700 bg-violet-50 hover:bg-violet-100">Simular diferenças</button>
      <button onclick="_dpxDissRodar(true)" class="text-xs px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold">Processar dissídio</button>
    </div>
    <div id="dpx-d-res" class="mt-5"></div>`, 'max-w-5xl');
}

async function _dpxDissRodar(gravar) {
  const emp = document.getElementById('dpx-d-emp').value;
  const body = {
    competencia_pagamento: document.getElementById('dpx-d-pg').value,
    competencia_inicio: document.getElementById('dpx-d-ini').value,
    competencia_fim: document.getElementById('dpx-d-fim').value,
    percentual: Number(String(document.getElementById('dpx-d-pct').value).replace(',', '.') || 0),
    tp_acordo: document.getElementById('dpx-d-tp').value,
    dt_acordo: document.getElementById('dpx-d-dt').value,
    descricao: document.getElementById('dpx-d-desc').value,
    employee_ids: emp ? [Number(emp)] : [],
    atualizar_salarios: document.getElementById('dpx-d-sal').checked,
  };
  const res = document.getElementById('dpx-d-res');
  if (gravar && !confirm(`Gravar a folha de diferenças em ${body.competencia_pagamento}?` +
      (body.atualizar_salarios ? '\nOs salários do cadastro também serão reajustados.' : ''))) return;
  res.innerHTML = '<div class="text-xs text-slate-400">Calculando...</div>';
  try {
    if (gravar) return _dpxAposProcessar(await _dpxPost('/api/dp/payroll/dissidio', body));
    const calc = await _dpxPost('/api/dp/payroll/dissidio/preview', body);
    const sem = (calc.meses_sem_folha || []).map(m => m.split('-').reverse().join('/'));
    res.innerHTML = (sem.length ? `<div class="text-xs text-amber-700 bg-amber-50 dark:bg-amber-900/20 rounded-xl p-3 mb-3">
        Sem folha processada em: ${sem.join(', ')} — esses meses não geram diferença.</div>` : '') + _dpxResultado(calc, true);
  } catch (e) { res.innerHTML = `<div class="text-xs text-rose-500">${_dpEsc(e.message)}</div>`; }
}

// ── ESCALAS E HORÁRIOS ───────────────────────────────────────
const DPX_DIAS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
let _dpxEscalas = [];
let _dpxEscalaSel = null;

async function renderEscalas(el) {
  _dpxEscalas = await fetch('/api/dp/work-schedules', { headers: authHeaders() }).then(r => r.json()).catch(() => []);
  const cards = _dpxEscalas.map(s => {
    const ciclica = s.tipo === 'ciclica';
    const desc = ciclica ? `Ciclo ${_dpEsc(s.ciclo)} desde ${fDate2(s.data_inicio_ciclo)}`
      : `Dias: ${String(s.dias_trabalho || '').split(',').map(d => DPX_DIAS[Number(d) % 7] || '').join(' ')}`;
    return `
      <div class="p-4 border rounded-2xl cursor-pointer transition ${_dpxEscalaSel === s.id
        ? 'border-violet-400 bg-violet-50/60 dark:bg-violet-900/20' : 'border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40'}"
        onclick="_dpxVerEscala(${s.id})">
        <div class="flex items-center justify-between">
          <div class="font-semibold text-sm text-slate-800 dark:text-slate-100">${_dpEsc(s.nome)}</div>
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${ciclica ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600'}">${ciclica ? 'Escala' : 'Fixo'}</span>
        </div>
        <div class="text-xs text-slate-500 mt-1">${_dpEsc(s.hora_entrada)} às ${_dpEsc(s.hora_saida)} · ${s.intervalo_min || 0} min de intervalo · ${Number(s.horas_diarias || 0).toLocaleString('pt-BR')}h/dia</div>
        <div class="text-[11px] text-slate-400 mt-0.5">${desc}${s.adicional_noturno_auto ? ' · adicional noturno automático' : ''}</div>
      </div>`;
  }).join('');
  el.innerHTML = `
    <div class="flex items-center justify-between mb-5">
      <div>
        <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">Escalas e horários de trabalho</h2>
        <p class="text-xs text-slate-400 mt-0.5">Horário fixo semanal ou escala cíclica (12x36, 24x48, 24x72, 5x1, 6x1...).
          O ponto e a folha usam a escala vinculada a cada funcionário.</p>
      </div>
      <button onclick="_dpxFormEscala()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
        <i data-lucide="plus" class="w-3.5 h-3.5"></i> Nova escala / horário</button>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <div class="space-y-3">${cards || '<div class="text-xs text-slate-400 p-6 text-center border border-dashed rounded-2xl">Nenhum horário cadastrado.</div>'}</div>
      <div class="lg:col-span-2" id="dpx-escala-area">
        <div class="text-xs text-slate-400 p-10 text-center border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl">
          Selecione uma escala para ver o calendário do mês e os funcionários vinculados.</div>
      </div>
    </div>`;
  if (window.lucide) lucide.createIcons();
  if (_dpxEscalaSel && _dpxEscalas.some(s => s.id === _dpxEscalaSel)) _dpxVerEscala(_dpxEscalaSel);
}

async function _dpxFormEscala(id) {
  const s = _dpxEscalas.find(x => x.id === id) || { tipo: 'ciclica', ciclo: 'T,F', hora_entrada: '19:00', hora_saida: '07:00',
    intervalo_min: 60, horas_semanais: 42, dias_trabalho: '1,2,3,4,5', prorrogacao_noturna: 1, feriados_compensados: 1,
    adicional_noturno_auto: 1, data_inicio_ciclo: new Date().toISOString().slice(0, 10) };
  const presets = await fetch('/api/dp/escalas/presets', { headers: authHeaders() }).then(r => r.json()).catch(() => ({}));
  window._dpxPresets = presets;
  const dias = String(s.dias_trabalho || '').split(',').map(Number);
  const presetAtual = Object.keys(presets).find(k => presets[k].ciclo === s.ciclo) || 'personalizado';
  _dpxModal('dpx-esc-form', id ? 'Editar escala / horário' : 'Nova escala / horário', `
    <div class="grid grid-cols-4 gap-3">
      <div class="col-span-2">${labelCls('Nome')}<input id="dpx-e-nome" value="${_dpEsc(s.nome || '')}" class="${inputCls()}" placeholder="ex.: Portaria 12x36 noturno"></div>
      <div class="col-span-2">${labelCls('Tipo')}
        <select id="dpx-e-tipo" class="${inputCls()}" onchange="_dpxTipoEscala()">
          <option value="ciclica" ${s.tipo === 'ciclica' ? 'selected' : ''}>Escala cíclica (12x36, 24x48, 5x1...)</option>
          <option value="fixo" ${s.tipo !== 'ciclica' ? 'selected' : ''}>Horário fixo semanal</option>
        </select></div>
      <div class="dpx-cic col-span-2">${labelCls('Escala')}
        <select id="dpx-e-preset" class="${inputCls()}" onchange="_dpxPresetEscala()">
          ${Object.entries(presets).map(([k, p]) => `<option value="${k}" ${k === presetAtual ? 'selected' : ''}>${k} — ${_dpEsc(p.descricao)}</option>`).join('')}
          <option value="personalizado" ${presetAtual === 'personalizado' ? 'selected' : ''}>Personalizada</option>
        </select></div>
      <div class="dpx-cic">${labelCls('Ciclo (T trabalho, F folga)')}<input id="dpx-e-ciclo" value="${_dpEsc(s.ciclo || '')}" class="${inputCls()}"></div>
      <div class="dpx-cic">${labelCls('1º dia de trabalho do ciclo')}<input id="dpx-e-ini" type="date" value="${_dpEsc(s.data_inicio_ciclo || '')}" class="${inputCls()}"></div>
      <div class="dpx-fix col-span-4">${labelCls('Dias de trabalho')}
        <div class="flex gap-3 flex-wrap">${DPX_DIAS.map((d, i) => `<label class="text-xs flex items-center gap-1">
          <input type="checkbox" class="dpx-e-dia" value="${i}" ${dias.includes(i) || (i === 0 && dias.includes(7)) ? 'checked' : ''}>${d}</label>`).join('')}</div></div>
      <div>${labelCls('Entrada')}<input id="dpx-e-ent" type="time" value="${_dpEsc(s.hora_entrada || '')}" class="${inputCls()}"></div>
      <div>${labelCls('Saída')}<input id="dpx-e-sai" type="time" value="${_dpEsc(s.hora_saida || '')}" class="${inputCls()}"></div>
      <div>${labelCls('Intervalo (min)')}<input id="dpx-e-int" type="number" min="0" value="${s.intervalo_min ?? 60}" class="${inputCls()}"></div>
      <div>${labelCls('Início do intervalo (opcional)')}<input id="dpx-e-intini" type="time" value="${_dpEsc(s.intervalo_inicio || '')}" class="${inputCls()}"></div>
      <div>${labelCls('Horas semanais (divisor)')}<input id="dpx-e-sem" type="number" step="0.5" value="${s.horas_semanais ?? 44}" class="${inputCls()}"
        title="12x36: média de 42h semanais. O divisor do salário-hora do funcionário vem do campo horas/semana da ficha."></div>
    </div>
    <div class="space-y-1.5 mt-4 text-xs text-slate-600 dark:text-slate-300">
      <label class="flex items-center gap-2"><input id="dpx-e-not" type="checkbox" ${s.adicional_noturno_auto ? 'checked' : ''}>
        Calcular o adicional noturno na folha pela escala (hora reduzida de 52min30s; usa o ponto quando houver marcação)</label>
      <label class="flex items-center gap-2"><input id="dpx-e-pro" type="checkbox" ${s.prorrogacao_noturna ? 'checked' : ''}>
        Horas depois das 5h também são noturnas quando o plantão cobre a noite toda (Súmula 60 do TST)</label>
      <label class="flex items-center gap-2 dpx-cic"><input id="dpx-e-fer" type="checkbox" ${s.feriados_compensados ? 'checked' : ''}>
        Feriados trabalhados já compensados na escala (12x36 — CLT art. 59-A); desmarcado, o feriado trabalhado vira hora extra 100%</label>
    </div>
    <div id="dpx-e-erro" class="text-xs text-rose-500 mt-3"></div>
    <div class="flex justify-between mt-5">
      <div>${id ? `<button onclick="_dpxExcluirEscala(${id})" class="text-xs text-rose-600 border border-rose-200 hover:bg-rose-50 px-3 py-2 rounded-xl">Excluir</button>` : ''}</div>
      <button onclick="_dpxSalvarEscala(${id || 0})" class="text-xs px-5 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold">Salvar</button>
    </div>`, 'max-w-3xl');
  _dpxTipoEscala();
}

function _dpxTipoEscala() {
  const cic = document.getElementById('dpx-e-tipo')?.value === 'ciclica';
  document.querySelectorAll('#dpx-esc-form .dpx-cic').forEach(e => { e.style.display = cic ? '' : 'none'; });
  document.querySelectorAll('#dpx-esc-form .dpx-fix').forEach(e => { e.style.display = cic ? 'none' : ''; });
}

function _dpxPresetEscala() {
  const k = document.getElementById('dpx-e-preset').value;
  const p = (window._dpxPresets || {})[k];
  if (!p) return;
  document.getElementById('dpx-e-ciclo').value = p.ciclo;
  document.getElementById('dpx-e-sem').value = p.horas_semanais;
}

async function _dpxSalvarEscala(id) {
  const v = sel => document.getElementById(sel).value;
  const body = {
    nome: v('dpx-e-nome'), tipo: v('dpx-e-tipo'), ciclo: v('dpx-e-ciclo'), data_inicio_ciclo: v('dpx-e-ini'),
    hora_entrada: v('dpx-e-ent'), hora_saida: v('dpx-e-sai'), intervalo_min: Number(v('dpx-e-int') || 0),
    intervalo_inicio: v('dpx-e-intini'), horas_semanais: Number(v('dpx-e-sem') || 44),
    dias_trabalho: [...document.querySelectorAll('.dpx-e-dia:checked')].map(c => c.value).join(','),
    adicional_noturno_auto: document.getElementById('dpx-e-not').checked,
    prorrogacao_noturna: document.getElementById('dpx-e-pro').checked,
    feriados_compensados: document.getElementById('dpx-e-fer').checked,
  };
  try {
    const r = await fetch(id ? `/api/dp/work-schedules/${id}` : '/api/dp/work-schedules', {
      method: id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { document.getElementById('dpx-e-erro').textContent = j.detail || 'Erro ao salvar.'; return; }
    document.getElementById('dpx-esc-form')?.remove();
    _dpxEscalaSel = id || j.id;
    await renderEscalas(document.getElementById('dp-body'));
  } catch { document.getElementById('dpx-e-erro').textContent = 'Erro de conexão.'; }
}

async function _dpxExcluirEscala(id) {
  if (!confirm('Excluir esta escala/horário? Os funcionários vinculados ficam sem escala.')) return;
  await fetch(`/api/dp/work-schedules/${id}`, { method: 'DELETE', headers: authHeaders() });
  document.getElementById('dpx-esc-form')?.remove();
  _dpxEscalaSel = null;
  await renderEscalas(document.getElementById('dp-body'));
}

async function _dpxVerEscala(id, comp, empId) {
  _dpxEscalaSel = id;
  document.querySelectorAll('#dp-body [onclick^="_dpxVerEscala"]').forEach(c => {
    const sel = c.getAttribute('onclick') === `_dpxVerEscala(${id})`;
    c.classList.toggle('border-violet-400', sel);
  });
  const area = document.getElementById('dpx-escala-area');
  if (!area) return;
  const hoje = new Date();
  comp = comp || document.getElementById('dpx-cal-comp')?.value || `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}`;
  const s = _dpxEscalas.find(x => x.id === id);
  const [cal, funcs] = await Promise.all([
    fetch(`/api/dp/work-schedules/${id}/calendario?competencia=${comp}${empId ? `&employee_id=${empId}` : ''}`, { headers: authHeaders() }).then(r => r.json()),
    fetch(`/api/dp/work-schedules/${id}/funcionarios`, { headers: authHeaders() }).then(r => r.json()).catch(() => []),
  ]);
  if (!cal.dias) { area.innerHTML = `<div class="text-xs text-rose-500">${_dpEsc(cal.detail || 'Erro ao montar o calendário.')}</div>`; return; }
  const vazio = Array(cal.dias[0].dia_semana).fill('<div></div>').join('');
  const dias = cal.dias.map(d => `
    <div class="rounded-lg p-1.5 min-h-[54px] text-[11px] border ${d.trabalha
      ? 'bg-indigo-50 border-indigo-200 dark:bg-indigo-900/30 dark:border-indigo-800' : 'bg-slate-50 border-slate-100 dark:bg-slate-800/40 dark:border-slate-800'}">
      <div class="flex justify-between"><b>${Number(d.data.slice(8))}</b>${d.feriado ? '<span title="Feriado" class="text-rose-500">●</span>' : ''}</div>
      ${d.trabalha ? `<div class="text-indigo-700 dark:text-indigo-300">${_dpEsc(d.entrada)}–${_dpEsc(d.saida)}</div>
        ${d.noturnas ? `<div class="text-slate-400">${d.noturnas.toLocaleString('pt-BR')}h not.</div>` : ''}` : '<div class="text-slate-400">folga</div>'}
    </div>`).join('');
  const r = cal.resumo;
  const empSel = funcs.map(f => `<option value="${f.id}" ${String(empId) === String(f.id) ? 'selected' : ''}>${_dpEsc(f.name)}</option>`).join('');
  area.innerHTML = card2(`
    <div class="p-5">
      <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div class="font-bold text-slate-800 dark:text-slate-100">${_dpEsc(s?.nome || '')}</div>
          <div class="text-xs text-slate-400">Plantão: ${cal.turno.horas.toLocaleString('pt-BR')}h trabalhadas,
            ${cal.turno.noturnas_relogio.toLocaleString('pt-BR')}h noturnas no relógio = ${cal.turno.noturnas.toLocaleString('pt-BR')}h reduzidas</div>
        </div>
        <div class="flex items-center gap-2">
          <select id="dpx-cal-emp" class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-2 py-1.5"
            onchange="_dpxVerEscala(${id}, null, this.value)"><option value="">Calendário da escala</option>${empSel}</select>
          <input id="dpx-cal-comp" type="month" value="${comp}" onchange="_dpxVerEscala(${id}, this.value, document.getElementById('dpx-cal-emp').value)"
            class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-2 py-1.5">
          <button onclick="_dpxFormEscala(${id})" class="text-xs text-violet-700 bg-violet-50 border border-violet-200 hover:bg-violet-100 px-3 py-1.5 rounded-lg">Editar</button>
        </div>
      </div>
      <div class="grid grid-cols-4 sm:grid-cols-6 gap-2 mb-4 text-center">
        ${[['Plantões', r.plantoes], ['Folgas', r.folgas], ['Horas', r.horas.toLocaleString('pt-BR')], ['Noturnas', r.noturnas.toLocaleString('pt-BR')],
           ['Domingos', r.domingos_trabalhados], ['Feriados', r.feriados_trabalhados]].map(([k, v]) => `
          <div class="rounded-xl bg-slate-50 dark:bg-slate-800/50 py-2"><div class="text-[10px] uppercase text-slate-400">${k}</div><div class="font-bold text-sm">${v}</div></div>`).join('')}
      </div>
      <div class="grid grid-cols-7 gap-1 text-center text-[10px] font-semibold text-slate-400 mb-1">${DPX_DIAS.map(d => `<div>${d}</div>`).join('')}</div>
      <div class="grid grid-cols-7 gap-1">${vazio}${dias}</div>
      <div class="mt-6">
        <div class="text-xs font-semibold text-slate-500 mb-2">Funcionários nesta escala</div>
        <table class="w-full text-sm mb-3">
          ${funcs.map(f => `<tr class="border-b border-slate-100 dark:border-slate-800">
            <td class="py-1.5">${_dpEsc(f.name)}</td><td class="py-1.5 text-xs text-slate-400">${_dpEsc(f.role || '')}</td>
            <td class="py-1.5 text-xs">${s?.tipo === 'ciclica' ? `turma desde ${fDate2(f.escala_inicio || s.data_inicio_ciclo)}` : ''}</td>
            <td class="py-1.5 text-right"><button onclick="_dpxVincular(${f.id}, null, '')" class="text-xs text-rose-500 hover:underline">desvincular</button></td>
          </tr>`).join('') || '<tr><td class="py-2 text-xs text-slate-400">Nenhum funcionário vinculado.</td></tr>'}
        </table>
        <div class="grid grid-cols-12 gap-2 items-end">
          <div class="col-span-6">${labelCls('Vincular funcionário')}<select id="dpx-v-emp" class="${inputCls()}">${_dpxEmpOptions()}</select></div>
          <div class="col-span-4 ${s?.tipo === 'ciclica' ? '' : 'hidden'}">${labelCls('1º dia de trabalho (turma)')}<input id="dpx-v-ini" type="date" value="${_dpEsc(s?.data_inicio_ciclo || '')}" class="${inputCls()}"></div>
          <div class="col-span-2"><button onclick="_dpxVincular(Number(document.getElementById('dpx-v-emp').value), ${id}, document.getElementById('dpx-v-ini')?.value || '')"
            class="w-full text-xs px-3 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold">Vincular</button></div>
        </div>
        <p class="text-[11px] text-slate-400 mt-2">Em 12x36 com duas turmas, a turma B começa um dia depois da turma A.
          Lembre de ajustar as horas semanais na ficha do funcionário (divisor do salário-hora).</p>
      </div>
    </div>`);
}

async function _dpxVincular(empId, schedId, inicio) {
  if (!empId) return;
  const r = await fetch(`/api/dp/employees/${empId}/escala`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ work_schedule_id: schedId, escala_inicio: inicio }) });
  if (!r.ok) { const j = await r.json().catch(() => ({})); alert(j.detail || 'Erro ao vincular.'); return; }
  _dpxVerEscala(_dpxEscalaSel, document.getElementById('dpx-cal-comp')?.value);
}

// ── PARÂMETROS DA FOLHA (por empresa) ────────────────────────
async function renderParametrosFolha(el) {
  el.innerHTML = '<div class="text-xs text-slate-400">Carregando...</div>';
  let d;
  try {
    d = await fetch('/api/dp/parametros', { headers: authHeaders() }).then(r => r.json());
  } catch { el.innerHTML = '<div class="text-xs text-rose-500">Erro ao carregar os parâmetros.</div>'; return; }
  const p = d.parametros || {};
  const linha = (rot, ajuda, campo) => `
    <div class="grid md:grid-cols-3 gap-3 items-start py-3 border-b border-slate-100 dark:border-slate-800">
      <div class="md:col-span-1"><div class="text-sm font-semibold text-slate-700 dark:text-slate-200">${rot}</div>
        <div class="text-[11px] text-slate-400 mt-0.5">${ajuda}</div></div>
      <div class="md:col-span-2">${campo}</div>
    </div>`;
  el.innerHTML = `
    <div class="flex items-center justify-between mb-4">
      <div><h2 class="text-lg font-bold text-slate-800 dark:text-slate-100">Parâmetros da folha</h2>
        <p class="text-xs text-slate-400">Regras da empresa usadas no cálculo da folha, no adiantamento, nas férias e nos holerites.</p></div>
      <button onclick="_dpxSalvarParametros()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
        <i data-lucide="save" class="w-3.5 h-3.5"></i> Salvar parâmetros</button>
    </div>
    ${card2(`<div class="px-5 py-2">
      <div class="text-[11px] font-bold uppercase tracking-wide text-violet-600 mt-3">Cálculo da folha</div>
      ${linha('Cálculo proporcional do salário',
        'Como dividir o salário em admissões, afastamentos e férias no meio do mês. O mês comercial (30 dias) é o padrão de mercado; "dias do mês" divide pelos dias corridos (28 a 31).',
        `<select id="par-base_dias" class="${inputCls()}">
           <option value="30" ${p.base_dias === '30' ? 'selected' : ''}>Sempre 30 dias (mês comercial)</option>
           <option value="mes" ${p.base_dias === 'mes' ? 'selected' : ''}>Dias do mês (28 a 31)</option></select>`)}
      ${linha('Descontar DSR por falta',
        'Falta injustificada na semana faz perder o descanso semanal remunerado (Lei 605/49, art. 6º). Desmarque se a convenção dispensar.',
        `<label class="flex items-center gap-2 text-sm"><input id="par-descontar_dsr_faltas" type="checkbox" ${p.descontar_dsr_faltas ? 'checked' : ''}> Descontar o DSR da semana com falta</label>`)}
      <div class="text-[11px] font-bold uppercase tracking-wide text-violet-600 mt-5">Adiantamento salarial</div>
      ${linha('Percentual sugerido', 'Preenchido automaticamente ao lançar um adiantamento.',
        `<input id="par-adiantamento_percentual" type="number" step="0.01" min="1" max="100" value="${p.adiantamento_percentual}" class="${inputCls()} max-w-[140px]">`)}
      ${linha('Percentual máximo', 'Lançamentos acima deste limite são recusados.',
        `<input id="par-adiantamento_limite" type="number" step="0.01" min="1" max="100" value="${p.adiantamento_limite}" class="${inputCls()} max-w-[140px]">`)}
      ${linha('Dia de pagamento', 'Data sugerida para o pagamento do adiantamento.',
        `<input id="par-adiantamento_dia_pagamento" type="number" min="1" max="28" value="${p.adiantamento_dia_pagamento}" class="${inputCls()} max-w-[140px]">`)}
      <div class="text-[11px] font-bold uppercase tracking-wide text-violet-600 mt-5">Férias</div>
      ${linha('Aviso de férias a vencer', 'Quantos dias antes do fim do período concessivo as férias aparecem como "vence em breve".',
        `<div class="flex items-center gap-2"><input id="par-ferias_alerta_dias" type="number" min="0" max="365" value="${p.ferias_alerta_dias}" class="${inputCls()} max-w-[140px]"><span class="text-xs text-slate-500">dias</span></div>`)}
      <div class="text-[11px] font-bold uppercase tracking-wide text-violet-600 mt-5">Empréstimo consignado</div>
      ${linha('Margem consignável', 'Percentual máximo da remuneração disponível (bruto menos INSS, IRRF e pensão) que as parcelas podem descontar, pela Lei 10.820/2003. O padrão é 35%; confira o percentual vigente antes de alterar.',
        `<div class="flex items-center gap-2"><input id="par-consignado_margem_pct" type="number" step="0.01" min="1" max="100" value="${p.consignado_margem_pct ?? 35}" class="${inputCls()} max-w-[140px]"><span class="text-xs text-slate-500">%</span></div>`)}
      <div class="text-[11px] font-bold uppercase tracking-wide text-violet-600 mt-5">Holerite</div>
      ${linha('Mensagem no holerite', 'Texto impresso em todos os recibos de pagamento (até 300 caracteres).',
        `<textarea id="par-mensagem_recibo" rows="2" maxlength="300" class="${inputCls()}" placeholder="ex.: Feliz aniversário aos colaboradores do mês!">${_dpEsc(p.mensagem_recibo || '')}</textarea>`)}
      <div id="par-msg" class="text-xs my-3"></div>
    </div>`)}
    <div id="par-email" class="mt-6"></div>`;
  if (typeof renderEmailConfig === 'function') await renderEmailConfig(document.getElementById('par-email'));
  if (window.lucide) lucide.createIcons();
}

async function _dpxSalvarParametros() {
  const v = id => document.getElementById('par-' + id);
  const body = {
    base_dias: v('base_dias').value,
    descontar_dsr_faltas: v('descontar_dsr_faltas').checked,
    adiantamento_percentual: v('adiantamento_percentual').value,
    adiantamento_limite: v('adiantamento_limite').value,
    adiantamento_dia_pagamento: v('adiantamento_dia_pagamento').value,
    ferias_alerta_dias: v('ferias_alerta_dias').value,
    mensagem_recibo: v('mensagem_recibo').value,
    consignado_margem_pct: v('consignado_margem_pct').value,
  };
  const msg = document.getElementById('par-msg');
  try {
    const r = await fetch('/api/dp/parametros', { method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() },
                                                  body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'Erro ao salvar.');
    msg.innerHTML = '<span class="text-emerald-600 font-semibold">Parâmetros salvos. Valem para os próximos cálculos.</span>';
    if (typeof showToast === 'function') showToast('Parâmetros da folha salvos.', 'success');
  } catch (e) { msg.innerHTML = `<span class="text-rose-500">${_dpEsc(e.message)}</span>`; }
}

// ── FÉRIAS: PROGRAMAÇÃO ANUAL ────────────────────────────────
async function abrirProgramacaoFerias(ano) {
  ano = ano || new Date().getFullYear();
  const lista = await fetch(`/api/dp/ferias/programacao?ano=${ano}`, { headers: authHeaders() }).then(r => r.json()).catch(() => []);
  const sit = { programada: ['Programada', 'bg-sky-100 text-sky-700'], calculada: ['Calculada', 'bg-emerald-100 text-emerald-700'] };
  const linhas = (Array.isArray(lista) ? lista : []).map(p => {
    const [rot, cls] = sit[p.status] || [p.status, 'bg-slate-100 text-slate-600'];
    return `<tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
      <td class="px-2 py-2 font-medium">${_dpEsc(p.employee_name)}</td>
      <td class="px-2 py-2">${fDate2(p.periodo_inicio)}</td>
      <td class="px-2 py-2">${fDate2(p.data_inicio)} a ${fDate2(p.data_fim)}</td>
      <td class="px-2 py-2 text-right">${p.dias_gozo}d${p.dias_abono ? ` + ${p.dias_abono} abono` : ''}${p.adiantar_13 ? ' · 13º' : ''}</td>
      <td class="px-2 py-2">${fDate2(p.limite_concessivo)}</td>
      <td class="px-2 py-2"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${cls}">${rot}</span>
        ${p.alertas.length ? `<div class="text-[10px] text-amber-600 mt-0.5">⚠ ${_dpEsc(p.alertas.join(' · '))}</div>` : ''}</td>
      <td class="px-2 py-2 text-right whitespace-nowrap">${p.status === 'programada' ? `
        <button onclick="_dpxProgCalcular(${p.id}, ${ano})" class="text-violet-600 hover:underline mr-2">Calcular</button>
        <button onclick="_dpxProgExcluir(${p.id}, ${ano})" class="text-rose-500 hover:underline">Excluir</button>` : ''}</td></tr>`;
  }).join('');
  const emps = dpEmployees.filter(e => e.active !== 0 && e.active !== false && !e.is_prolabore)
    .map(e => `<option value="${e.id}">${_dpEsc(e.name)}</option>`).join('');
  _dpxModal('dpx-prog', `Programação de férias — ${ano}`, `
    <div class="flex items-center justify-between mb-3 gap-2">
      <div class="flex items-center gap-2 text-xs">
        <button onclick="abrirProgramacaoFerias(${ano - 1})" class="px-2 py-1 rounded-lg border">‹ ${ano - 1}</button>
        <button onclick="abrirProgramacaoFerias(${ano + 1})" class="px-2 py-1 rounded-lg border">${ano + 1} ›</button>
      </div>
      <a href="#" onclick="_dpxProgRelatorio(${ano});return false" class="text-xs text-violet-600 hover:underline">Imprimir relatório do ano</a>
    </div>
    <div class="grid grid-cols-12 gap-2 items-end mb-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl p-3">
      <div class="col-span-4">${labelCls('Funcionário')}<select id="dpx-p-emp" class="${inputCls()}">${emps}</select></div>
      <div class="col-span-3">${labelCls('Início previsto')}<input id="dpx-p-ini" type="date" value="${ano}-01-01" class="${inputCls()}"></div>
      <div class="col-span-1">${labelCls('Dias')}<input id="dpx-p-dias" type="number" min="5" max="30" value="30" class="${inputCls()}"></div>
      <div class="col-span-1">${labelCls('Abono')}<input id="dpx-p-abono" type="number" min="0" max="10" value="0" class="${inputCls()}"></div>
      <label class="col-span-1 text-[11px] flex items-center gap-1 pb-2"><input id="dpx-p-13" type="checkbox"> 13º</label>
      <div class="col-span-2"><button onclick="_dpxProgSalvar(${ano})" class="w-full text-xs bg-violet-600 hover:bg-violet-700 text-white font-semibold px-3 py-2 rounded-xl">Programar</button></div>
    </div>
    <div id="dpx-p-msg" class="text-xs mb-2"></div>
    <div class="overflow-x-auto"><table class="w-full text-sm">
      <thead><tr class="text-[10px] text-slate-400 uppercase border-b"><th class="px-2 py-1 text-left">Funcionário</th>
        <th class="px-2 py-1 text-left">Per. aquisitivo</th><th class="px-2 py-1 text-left">Gozo</th><th class="px-2 py-1 text-right">Dias</th>
        <th class="px-2 py-1 text-left">Limite</th><th class="px-2 py-1 text-left">Situação</th><th></th></tr></thead>
      <tbody>${linhas || '<tr><td colspan="7" class="text-center text-xs text-slate-400 py-6">Nenhuma férias programada para o ano.</td></tr>'}</tbody>
    </table></div>`, 'max-w-5xl');
}

async function _dpxProgSalvar(ano) {
  const msg = document.getElementById('dpx-p-msg');
  try {
    await _dpxPost('/api/dp/ferias/programacao', {
      employee_id: Number(document.getElementById('dpx-p-emp').value),
      data_inicio: document.getElementById('dpx-p-ini').value,
      dias_gozo: Number(document.getElementById('dpx-p-dias').value),
      dias_abono: Number(document.getElementById('dpx-p-abono').value || 0),
      adiantar_13: document.getElementById('dpx-p-13').checked });
    await abrirProgramacaoFerias(ano);
  } catch (e) { msg.innerHTML = `<span class="text-rose-500">${_dpEsc(e.message)}</span>`; }
}

async function _dpxProgCalcular(id, ano) {
  if (!confirm('Calcular e gravar o recibo de férias desta programação?')) return;
  try {
    await _dpxPost(`/api/dp/ferias/programacao/${id}/calcular`, {});
    await abrirProgramacaoFerias(ano);
    const body = document.getElementById('dp-body');
    if (body && typeof renderFerias === 'function') { await renderFerias(body); if (window.lucide) lucide.createIcons(); }
  } catch (e) { document.getElementById('dpx-p-msg').innerHTML = `<span class="text-rose-500">${_dpEsc(e.message)}</span>`; }
}

async function _dpxProgExcluir(id, ano) {
  if (!confirm('Excluir esta programação?')) return;
  const r = await fetch(`/api/dp/ferias/programacao/${id}`, { method: 'DELETE', headers: authHeaders() });
  if (!r.ok) { const j = await r.json().catch(() => ({})); alert(j.detail || 'Erro ao excluir.'); return; }
  await abrirProgramacaoFerias(ano);
}

async function _dpxProgRelatorio(ano) {
  const r = await fetch(`/api/dp/ferias/programacao/relatorio?ano=${ano}`, { headers: authHeaders() });
  const w = window.open('', '_blank');
  if (w) { w.document.write(await r.text()); w.document.close(); }
}

// ── FÉRIAS EM GRUPO / COLETIVAS ──────────────────────────────
function abrirFeriasGrupo() {
  const ativos = dpEmployees.filter(e => e.active !== 0 && e.active !== false);
  const deptos = [...new Set(ativos.map(e => (e.department || '').trim()).filter(Boolean))].sort();
  const emps = ativos.filter(e => !e.is_prolabore)
    .map(e => `<label class="flex items-center gap-2 text-xs py-0.5"><input type="checkbox" class="dpx-g-emp" value="${e.id}"> ${_dpEsc(e.name)}
      <span class="text-slate-400">${_dpEsc(e.department || '')}</span></label>`).join('');
  const optDeptos = deptos.map(d => `<option>${_dpEsc(d)}</option>`).join('') || '<option value="">(nenhum cadastrado)</option>';
  _dpxModal('dpx-grupo', 'Férias em grupo / coletivas', `
    <p class="text-xs text-slate-500 mb-4">Calcula as férias de vários funcionários com o mesmo início. Nas <b>coletivas</b>
      (CLT arts. 139 a 141) o mínimo é 10 dias e é preciso comunicar o Ministério do Trabalho e o sindicato com 15 dias de antecedência.</p>
    <div class="grid grid-cols-4 gap-3 mb-3">
      <div>${labelCls('Início')}<input id="dpx-g-ini" type="date" class="${inputCls()}"></div>
      <div>${labelCls('Dias de gozo')}<input id="dpx-g-dias" type="number" min="1" max="30" value="30" class="${inputCls()}"></div>
      <div class="col-span-2 flex items-end pb-2"><label class="text-xs flex items-center gap-2"><input id="dpx-g-col" type="checkbox" checked> Férias coletivas</label></div>
    </div>
    <div class="grid grid-cols-3 gap-3 mb-3">
      <div>${labelCls('Quem')}<select id="dpx-g-modo" onchange="_dpxGrupoModo()" class="${inputCls()}">
        <option value="todos">Todos os funcionários</option><option value="depto">Um departamento</option><option value="lista">Escolher na lista</option></select></div>
      <div id="dpx-g-depto-box" class="hidden">${labelCls('Departamento')}<select id="dpx-g-depto" class="${inputCls()}">${optDeptos}</select></div>
    </div>
    <div id="dpx-g-lista" class="hidden max-h-48 overflow-y-auto border rounded-xl p-2 mb-3">${emps}</div>
    <div class="flex justify-end gap-2">
      <button onclick="_dpxGrupoRodar(false)" class="text-xs px-4 py-2 rounded-xl border border-violet-200 text-violet-700 bg-violet-50 hover:bg-violet-100">Simular</button>
      <button onclick="_dpxGrupoRodar(true)" class="text-xs px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold">Gravar férias</button>
    </div>
    <div id="dpx-g-res" class="mt-5"></div>`, 'max-w-4xl');
}

function _dpxGrupoModo() {
  const m = document.getElementById('dpx-g-modo').value;
  document.getElementById('dpx-g-depto-box').classList.toggle('hidden', m !== 'depto');
  document.getElementById('dpx-g-lista').classList.toggle('hidden', m !== 'lista');
}

async function _dpxGrupoRodar(gravar) {
  const modo = document.getElementById('dpx-g-modo').value;
  const body = { data_inicio: document.getElementById('dpx-g-ini').value,
                 dias_gozo: Number(document.getElementById('dpx-g-dias').value),
                 coletivas: document.getElementById('dpx-g-col').checked };
  if (modo === 'todos') body.todos = true;
  if (modo === 'depto') body.departamento = document.getElementById('dpx-g-depto').value;
  if (modo === 'lista') body.employee_ids = [...document.querySelectorAll('.dpx-g-emp:checked')].map(i => Number(i.value));
  const res = document.getElementById('dpx-g-res');
  if (!body.data_inicio) { res.innerHTML = '<div class="text-xs text-rose-500">Informe a data de início.</div>'; return; }
  if (gravar && !confirm('Gravar as férias de todos os funcionários aptos?')) return;
  res.innerHTML = '<div class="text-xs text-slate-400">Calculando...</div>';
  try {
    const d = await _dpxPost(gravar ? '/api/dp/ferias/grupo' : '/api/dp/ferias/grupo/preview', body);
    const linhas = d.funcionarios.map(f => `<tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
      <td class="px-2 py-1.5">${_dpEsc(f.employee_name)}</td><td class="px-2 py-1.5">${fDate2(f.data_inicio)} a ${fDate2(f.data_fim)}</td>
      <td class="px-2 py-1.5 text-right">${f.dias_gozo}d${f.dias_dobro ? ` <span class="text-rose-600">(${f.dias_dobro} em dobro)</span>` : ''}</td>
      <td class="px-2 py-1.5 text-right">${fBRL2(f.bruto)}</td><td class="px-2 py-1.5 text-right font-semibold">${fBRL2(f.liquido)}</td></tr>`).join('');
    const ign = d.ignorados.map(g => `<li>${_dpEsc(g.employee_name)}: ${_dpEsc(g.motivo)}</li>`).join('');
    const ok = gravar ? `<div class="text-xs text-emerald-700 bg-emerald-50 rounded-xl px-3 py-2 mb-2">${d.funcionarios.length} recibo(s) de férias gravado(s).</div>` : '';
    const avisos = d.avisos.map(a => `<div class="text-xs text-amber-700 bg-amber-50 rounded-xl px-3 py-2 mb-2">${_dpEsc(a)}</div>`).join('');
    res.innerHTML = `${ok}${avisos}
      <table class="w-full"><thead><tr class="text-[10px] text-slate-400 uppercase border-b"><th class="px-2 py-1 text-left">Funcionário</th>
        <th class="px-2 py-1 text-left">Gozo</th><th class="px-2 py-1 text-right">Dias</th><th class="px-2 py-1 text-right">Bruto</th><th class="px-2 py-1 text-right">Líquido</th></tr></thead>
        <tbody>${linhas || '<tr><td colspan="5" class="text-center text-xs text-slate-400 py-4">Nenhum funcionário apto.</td></tr>'}
        <tr class="text-xs font-bold"><td colspan="3" class="px-2 py-1.5">Total</td><td class="px-2 py-1.5 text-right">${fBRL2(d.total_bruto)}</td>
        <td class="px-2 py-1.5 text-right">${fBRL2(d.total_liquido)}</td></tr></tbody></table>
      ${ign ? `<div class="text-xs text-slate-600 mt-3"><b>Não incluídos:</b><ul class="list-disc ml-5 mt-1">${ign}</ul></div>` : ''}`;
    if (gravar) {
      const b = document.getElementById('dp-body');
      if (b && typeof renderFerias === 'function') { await renderFerias(b); if (window.lucide) lucide.createIcons(); }
    }
  } catch (e) { res.innerHTML = `<div class="text-xs text-rose-500">${_dpEsc(e.message)}</div>`; }
}

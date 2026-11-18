// ============================================================
// DEPARTAMENTO PESSOAL — Aviso prévio como processo, rescisão em grupo e rescisão complementar
// Usa os helpers de dp.js e dp_folha_extra.js: authHeaders, fBRL2, fDate2, inputCls, labelCls,
// _dpEsc, dpEmployees, _dpxModal, _dpxPost, _dpHoleriteTable, openEspecialDocumento.
// ============================================================

const DPR_STATUS_AVISO = {
  ativo: ['Em andamento', 'bg-amber-100 text-amber-700'],
  convertido: ['Rescisão gravada', 'bg-emerald-100 text-emerald-700'],
  cancelado: ['Cancelado', 'bg-slate-100 text-slate-500'],
};
const DPR_MODOS = {
  empregador: [['trabalhado', 'Trabalhado'], ['indenizado', 'Indenizado']],
  empregado: [['trabalhado', 'Trabalhado'], ['dispensado', 'Dispensado pela empresa'], ['nao_cumprido', 'Não cumprido (desconto)']],
  acordo: [['trabalhado', 'Trabalhado'], ['indenizado', 'Indenizado (metade)']],
};

function _dprAviso(msg, cor = 'amber') {
  return `<div class="text-xs text-${cor}-700 bg-${cor}-50 rounded-xl px-3 py-2 mb-2">${_dpEsc(msg)}</div>`;
}

async function _dprAbrirHtml(url) {
  const r = await fetch(url, { headers: authHeaders() });
  if (!r.ok) { alert('Erro ao gerar documento.'); return; }
  const win = window.open('', '_blank');
  if (win) { win.document.write(await r.text()); win.document.close(); }
}

// ── Aviso prévio ─────────────────────────────────────────────
async function abrirAvisosPrevios() {
  const opts = dpEmployees.filter(e => e.active !== 0 && e.active !== false && !e.is_prolabore)
    .map(e => `<option value="${e.id}">${_dpEsc(e.name)}</option>`).join('');
  const hoje = new Date().toISOString().slice(0, 10);
  _dpxModal('dpr-aviso', 'Aviso prévio', `
    <p class="text-xs text-slate-500 mb-4">Registre o aviso quando ele é dado. O prazo começa no dia seguinte à comunicação
      (Súmula 380 do TST): 30 dias + 3 por ano completo, até 90 (Lei 12.506/2011). Ao calcular a rescisão do funcionário,
      a data e os dias indenizados vêm deste aviso.</p>
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
      <div class="md:col-span-2">${labelCls('Funcionário')}<select id="dpr-a-emp" class="${inputCls()}"><option value="">Selecione...</option>${opts}</select></div>
      <div>${labelCls('Data da comunicação')}<input id="dpr-a-data" type="date" value="${hoje}" class="${inputCls()}"></div>
      <div>${labelCls('Iniciativa')}<select id="dpr-a-ini" onchange="_dprModos()" class="${inputCls()}">
        <option value="empregador">Empregador (dispensa)</option><option value="empregado">Empregado (pedido de demissão)</option>
        <option value="acordo">Acordo (art. 484-A)</option></select></div>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3 items-end">
      <div>${labelCls('Aviso')}<select id="dpr-a-modo" onchange="_dprModos(true)" class="${inputCls()}"></select></div>
      <div id="dpr-a-red-box">${labelCls('Redução (art. 488)')}<select id="dpr-a-red" class="${inputCls()}">
        <option value="">Escolha do empregado depois</option><option value="2h">2 horas por dia</option><option value="7dias">7 dias corridos no fim</option></select></div>
      <label id="dpr-a-prop-box" class="md:col-span-2 text-xs flex items-center gap-2 pb-2"><input id="dpr-a-prop" type="checkbox">
        Exigir trabalho também nos dias proporcionais (acima de 30)</label>
    </div>
    <div class="flex justify-end gap-2">
      <button onclick="_dprAvisoRodar(false)" class="text-xs px-4 py-2 rounded-xl border border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100">Simular</button>
      <button onclick="_dprAvisoRodar(true)" class="text-xs px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-semibold">Registrar aviso</button>
    </div>
    <div id="dpr-a-res" class="mt-4"></div>
    <h4 class="font-semibold text-sm text-slate-700 dark:text-slate-200 mt-6 mb-2">Avisos registrados</h4>
    <div id="dpr-a-lista" class="text-xs text-slate-400">Carregando...</div>`, 'max-w-5xl');
  _dprModos();
  await _dprAvisoLista();
}

function _dprModos(soReducao = false) {
  const ini = document.getElementById('dpr-a-ini').value;
  const sel = document.getElementById('dpr-a-modo');
  if (!soReducao) sel.innerHTML = DPR_MODOS[ini].map(([v, t]) => `<option value="${v}">${t}</option>`).join('');
  const trabEmpregador = ini === 'empregador' && sel.value === 'trabalhado';
  document.getElementById('dpr-a-red-box').classList.toggle('hidden', !trabEmpregador);
  document.getElementById('dpr-a-prop-box').classList.toggle('hidden', !trabEmpregador);
}

async function _dprAvisoRodar(gravar) {
  const res = document.getElementById('dpr-a-res');
  const ini = document.getElementById('dpr-a-ini').value;
  const modo = document.getElementById('dpr-a-modo').value;
  const trabEmpregador = ini === 'empregador' && modo === 'trabalhado';
  const body = { employee_id: Number(document.getElementById('dpr-a-emp').value) || null,
                 data_aviso: document.getElementById('dpr-a-data').value, iniciativa: ini, modo,
                 reducao: trabEmpregador ? document.getElementById('dpr-a-red').value : '',
                 proporcional_trabalhado: trabEmpregador && document.getElementById('dpr-a-prop').checked };
  if (!body.employee_id || !body.data_aviso) { res.innerHTML = _dprAviso('Escolha o funcionário e a data.', 'rose'); return; }
  try {
    const d = await _dpxPost(gravar ? '/api/dp/avisos-previos' : '/api/dp/avisos-previos/preview', body);
    res.innerHTML = `${gravar ? _dprAviso('Aviso prévio registrado.', 'emerald') : ''}
      <div class="flex flex-wrap gap-4 text-xs text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/40 rounded-xl px-4 py-3 mb-2">
        <span>Total: <b>${d.dias_total} dias</b></span><span>Trabalhados: <b>${d.dias_trabalhados}</b></span>
        <span>Indenizados: <b>${d.dias_indenizados}</b></span>${d.dias_desconto ? `<span class="text-rose-600">Desconto: <b>${d.dias_desconto} dias</b></span>` : ''}
        <span>Desligamento: <b>${fDate2(d.data_desligamento)}</b></span><span>Projeção: <b>${fDate2(d.data_projetada)}</b></span>
      </div>${(d.avisos || []).map(a => _dprAviso(a)).join('')}`;
    if (gravar) await _dprAvisoLista();
  } catch (e) { res.innerHTML = _dprAviso(e.message, 'rose'); }
}

async function _dprAvisoLista() {
  const box = document.getElementById('dpr-a-lista');
  if (!box) return;
  let rows = [];
  try { rows = await apiFetch('/api/dp/avisos-previos'); } catch { box.innerHTML = 'Erro ao carregar.'; return; }
  if (!rows.length) { box.innerHTML = 'Nenhum aviso registrado.'; return; }
  box.innerHTML = `<table class="w-full"><thead><tr class="text-[10px] text-slate-400 uppercase border-b">
      <th class="px-2 py-1 text-left">Funcionário</th><th class="px-2 py-1 text-left">Iniciativa</th><th class="px-2 py-1 text-left">Comunicação</th>
      <th class="px-2 py-1 text-left">Dias (trab./ind.)</th><th class="px-2 py-1 text-left">Desligamento</th><th class="px-2 py-1 text-left">Situação</th>
      <th class="px-2 py-1 text-right">Ações</th></tr></thead><tbody>${rows.map(a => {
        const [rot, cls] = DPR_STATUS_AVISO[a.status] || [a.status, ''];
        return `<tr class="border-b border-slate-100 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300">
          <td class="px-2 py-1.5">${_dpEsc(a.employee_name)}</td><td class="px-2 py-1.5">${_dpEsc(a.iniciativa_nome)} · ${_dpEsc(a.modo)}</td>
          <td class="px-2 py-1.5">${fDate2(a.data_aviso)}</td><td class="px-2 py-1.5">${a.dias_total} (${a.dias_trabalhados}/${a.dias_indenizados})</td>
          <td class="px-2 py-1.5">${fDate2(a.data_desligamento)}</td>
          <td class="px-2 py-1.5"><span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${cls}" title="${_dpEsc(a.motivo_cancelamento || '')}">${rot}</span></td>
          <td class="px-2 py-1.5 text-right whitespace-nowrap">
            <button onclick="_dprAbrirHtml('/api/dp/avisos-previos/${a.id}/documento')" class="text-violet-600 hover:underline mr-2">Carta</button>
            ${a.status === 'ativo' ? `<button onclick="_dprAvisoCancelar(${a.id})" class="text-amber-600 hover:underline mr-2">Cancelar</button>` : ''}
            ${a.status !== 'convertido' ? `<button onclick="_dprAvisoExcluir(${a.id})" class="text-rose-500 hover:underline">Excluir</button>` : ''}
          </td></tr>`;
      }).join('')}</tbody></table>`;
}

async function _dprAvisoCancelar(id) {
  const motivo = prompt('Motivo do cancelamento (a reconsideração precisa ser aceita pela outra parte, CLT art. 489):');
  if (!motivo) return;
  try { await _dpxPost(`/api/dp/avisos-previos/${id}/cancelar`, { motivo }); await _dprAvisoLista(); }
  catch (e) { alert(e.message); }
}

async function _dprAvisoExcluir(id) {
  if (!confirm('Excluir este aviso prévio? Use "Cancelar" se ele foi reconsiderado.')) return;
  try { await apiFetch(`/api/dp/avisos-previos/${id}`, { method: 'DELETE' }); await _dprAvisoLista(); }
  catch (e) { alert(e.message); }
}

// ── Rescisão em grupo ────────────────────────────────────────
function abrirRescisaoGrupo() {
  const ativos = dpEmployees.filter(e => e.active !== 0 && e.active !== false && !e.is_prolabore);
  const deptos = [...new Set(ativos.map(e => (e.department || '').trim()).filter(Boolean))].sort();
  const emps = ativos.map(e => `<label class="flex items-center gap-2 text-xs py-0.5"><input type="checkbox" class="dpr-g-emp" value="${e.id}"> ${_dpEsc(e.name)}
      <span class="text-slate-400">${_dpEsc(e.department || '')}</span></label>`).join('');
  const optDeptos = deptos.map(d => `<option>${_dpEsc(d)}</option>`).join('') || '<option value="">(nenhum cadastrado)</option>';
  _dpxModal('dpr-grupo', 'Rescisão em grupo', `
    <p class="text-xs text-slate-500 mb-4">Calcula a rescisão de vários funcionários com a mesma data e o mesmo tipo
      (encerramento de filial, fim de obra, dispensa coletiva). Avisos prévios registrados não são usados aqui.</p>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
      <div>${labelCls('Desligamento')}<input id="dpr-g-data" type="date" class="${inputCls()}"></div>
      <div>${labelCls('Tipo')}<select id="dpr-g-tipo" class="${inputCls()}">
        <option value="sem_justa_causa">Sem justa causa</option><option value="termino_contrato">Término de contrato</option>
        <option value="acordo">Acordo (CLT 484-A)</option></select></div>
      <div>${labelCls('Aviso prévio')}<select id="dpr-g-aviso" class="${inputCls()}">
        <option value="">Padrão do tipo</option><option value="indenizado">Indenizado</option><option value="trabalhado">Trabalhado</option></select></div>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
      <div>${labelCls('Quem')}<select id="dpr-g-modo" onchange="_dprGrupoModo()" class="${inputCls()}">
        <option value="depto">Um departamento</option><option value="lista">Escolher na lista</option><option value="todos">Todos os funcionários</option></select></div>
      <div id="dpr-g-depto-box">${labelCls('Departamento')}<select id="dpr-g-depto" class="${inputCls()}">${optDeptos}</select></div>
    </div>
    <div id="dpr-g-lista" class="hidden max-h-48 overflow-y-auto border rounded-xl p-2 mb-3">${emps}</div>
    <div class="flex justify-end gap-2">
      <button onclick="_dprGrupoRodar(false)" class="text-xs px-4 py-2 rounded-xl border border-rose-200 text-rose-700 bg-rose-50 hover:bg-rose-100">Simular</button>
      <button onclick="_dprGrupoRodar(true)" class="text-xs px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold">Gravar rescisões</button>
    </div>
    <div id="dpr-g-res" class="mt-5"></div>`, 'max-w-4xl');
}

function _dprGrupoModo() {
  const m = document.getElementById('dpr-g-modo').value;
  document.getElementById('dpr-g-depto-box').classList.toggle('hidden', m !== 'depto');
  document.getElementById('dpr-g-lista').classList.toggle('hidden', m !== 'lista');
}

async function _dprGrupoRodar(gravar) {
  const modo = document.getElementById('dpr-g-modo').value;
  const body = { data_desligamento: document.getElementById('dpr-g-data').value,
                 tipo: document.getElementById('dpr-g-tipo').value };
  const aviso = document.getElementById('dpr-g-aviso').value;
  if (aviso) body.aviso_modo = aviso;
  if (modo === 'todos') body.todos = true;
  if (modo === 'depto') body.departamento = document.getElementById('dpr-g-depto').value;
  if (modo === 'lista') body.employee_ids = [...document.querySelectorAll('.dpr-g-emp:checked')].map(i => Number(i.value));
  const res = document.getElementById('dpr-g-res');
  if (!body.data_desligamento) { res.innerHTML = _dprAviso('Informe a data de desligamento.', 'rose'); return; }
  if (gravar && !confirm('Gravar a rescisão e desligar todos os funcionários listados?')) return;
  res.innerHTML = '<div class="text-xs text-slate-400">Calculando...</div>';
  try {
    const d = await _dpxPost(gravar ? '/api/dp/rescisao/grupo' : '/api/dp/rescisao/grupo/preview', body);
    const linhas = d.funcionarios.map(f => `<tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
      <td class="px-2 py-1.5">${_dpEsc(f.employee_name)}</td><td class="px-2 py-1.5 text-right">${f.aviso_dias}d</td>
      <td class="px-2 py-1.5">${fDate2(f.data_projetada)}</td><td class="px-2 py-1.5 text-right">${fBRL2(f.bruto)}</td>
      <td class="px-2 py-1.5 text-right font-semibold">${fBRL2(f.liquido)}</td><td class="px-2 py-1.5 text-right text-blue-600">${fBRL2(f.multa_fgts)}</td></tr>`).join('');
    const ign = d.ignorados.map(g => `<li>${_dpEsc(g.employee_name)}: ${_dpEsc(g.motivo)}</li>`).join('');
    res.innerHTML = `${gravar ? _dprAviso(`${d.funcionarios.length} rescisão(ões) gravada(s).`, 'emerald') : ''}${d.avisos.map(a => _dprAviso(a)).join('')}
      <table class="w-full"><thead><tr class="text-[10px] text-slate-400 uppercase border-b"><th class="px-2 py-1 text-left">Funcionário</th>
        <th class="px-2 py-1 text-right">Aviso ind.</th><th class="px-2 py-1 text-left">Projeção</th><th class="px-2 py-1 text-right">Bruto</th>
        <th class="px-2 py-1 text-right">Líquido</th><th class="px-2 py-1 text-right">Multa FGTS</th></tr></thead>
        <tbody>${linhas || '<tr><td colspan="6" class="text-center text-xs text-slate-400 py-4">Nenhum funcionário apto.</td></tr>'}
        <tr class="text-xs font-bold"><td colspan="3" class="px-2 py-1.5">Total</td><td class="px-2 py-1.5 text-right">${fBRL2(d.total_bruto)}</td>
        <td class="px-2 py-1.5 text-right">${fBRL2(d.total_liquido)}</td><td class="px-2 py-1.5 text-right">${fBRL2(d.total_multa_fgts)}</td></tr></tbody></table>
      ${ign ? `<div class="text-xs text-slate-600 mt-3"><b>Não incluídos:</b><ul class="list-disc ml-5 mt-1">${ign}</ul></div>` : ''}`;
    if (gravar) {
      const er = await fetch('/api/dp/employees?active_only=false', { headers: authHeaders() });
      if (er.ok) dpEmployees = await er.json();
      const b = document.getElementById('dp-body');
      if (b && typeof renderRescisao === 'function') await renderRescisao(b);
    }
  } catch (e) { res.innerHTML = _dprAviso(e.message, 'rose'); }
}

// ── Rescisão complementar ────────────────────────────────────
function abrirRescisaoComplementar(rescisaoId, employeeId) {
  const nome = (dpEmployees.find(e => e.id === employeeId) || {}).name || `rescisão #${rescisaoId}`;
  const hoje = new Date().toISOString().slice(0, 10);
  const verba = i => `<div class="grid grid-cols-3 gap-2 mb-2">
      <input id="dpr-c-cod-${i}" placeholder="Código da rubrica" class="${inputCls()}">
      <input id="dpr-c-nome-${i}" placeholder="Descrição (opcional)" class="${inputCls()}">
      <input id="dpr-c-val-${i}" type="number" step="0.01" min="0" placeholder="Valor" class="${inputCls()}"></div>`;
  _dpxModal('dpr-compl', `Rescisão complementar — ${_dpEsc(nome)}`, `
    <p class="text-xs text-slate-500 mb-4">Paga diferenças depois da rescisão. Com reajuste, o sistema recalcula a rescisão com o
      salário novo (mesmas datas e avos) e lança só a diferença de cada verba. INSS e IRRF são recalculados sobre o total, descontando o que já foi retido.</p>
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
      <div>${labelCls('Motivo')}<select id="dpr-c-motivo" class="${inputCls()}">
        <option value="dissidio">Dissídio / reajuste retroativo</option><option value="convencao">Convenção coletiva</option>
        <option value="comissoes">Comissões e variáveis</option><option value="multa_477">Multa do art. 477</option><option value="outros">Outros</option></select></div>
      <div>${labelCls('Reajuste (%)')}<input id="dpr-c-pct" type="number" step="0.01" min="0" class="${inputCls()}"></div>
      <div>${labelCls('ou novo salário')}<input id="dpr-c-sal" type="number" step="0.01" min="0" class="${inputCls()}"></div>
      <div>${labelCls('Data de pagamento')}<input id="dpr-c-pag" type="date" value="${hoje}" class="${inputCls()}"></div>
    </div>
    <div class="flex flex-wrap gap-5 mb-3 text-xs">
      <label class="flex items-center gap-2"><input id="dpr-c-477" type="checkbox"> Multa do art. 477 §8º (verbas pagas após 10 dias)</label>
      <label class="flex items-center gap-2"><input id="dpr-c-db" type="checkbox"> Indenização adicional (dispensa nos 30 dias antes da data-base, Lei 7.238/84)</label>
    </div>
    <div class="mb-3">${labelCls('Outras verbas (rubricas da empresa)')}${verba(0)}${verba(1)}${verba(2)}</div>
    <div class="flex justify-end gap-2">
      <button onclick="_dprComplRodar(${rescisaoId}, false)" class="text-xs px-4 py-2 rounded-xl border border-violet-200 text-violet-700 bg-violet-50 hover:bg-violet-100">Simular</button>
      <button onclick="_dprComplRodar(${rescisaoId}, true)" class="text-xs px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold">Gravar complementar</button>
    </div>
    <div id="dpr-c-res" class="mt-5"></div>`, 'max-w-4xl');
}

async function _dprComplRodar(rescisaoId, gravar) {
  const v = id => document.getElementById(id).value;
  const body = { motivo: v('dpr-c-motivo'), data_pagamento: v('dpr-c-pag'),
                 multa_477: document.getElementById('dpr-c-477').checked,
                 indenizacao_data_base: document.getElementById('dpr-c-db').checked, verbas: [] };
  if (v('dpr-c-sal')) body.novo_salario = Number(v('dpr-c-sal'));
  else if (v('dpr-c-pct')) body.percentual_reajuste = Number(v('dpr-c-pct'));
  for (let i = 0; i < 3; i++) {
    if (v(`dpr-c-cod-${i}`) && Number(v(`dpr-c-val-${i}`)) > 0)
      body.verbas.push({ codigo: v(`dpr-c-cod-${i}`), nome: v(`dpr-c-nome-${i}`) || undefined, valor: Number(v(`dpr-c-val-${i}`)) });
  }
  const res = document.getElementById('dpr-c-res');
  if (gravar && !confirm('Gravar a rescisão complementar?')) return;
  res.innerHTML = '<div class="text-xs text-slate-400">Calculando...</div>';
  try {
    const d = await _dpxPost(`/api/dp/rescisao/${rescisaoId}/complementar${gravar ? '' : '/preview'}`, body);
    res.innerHTML = `${gravar ? _dprAviso('Rescisão complementar gravada.', 'emerald') : ''}
      <div class="flex flex-wrap gap-4 text-xs text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/40 rounded-xl px-4 py-2.5 mb-3">
        ${d.salario_novo ? `<span>Salário: <b>${fBRL2(d.salario_anterior)}</b> → <b>${fBRL2(d.salario_novo)}</b></span>` : ''}
        <span>FGTS s/ diferenças: <b class="text-blue-600">${fBRL2(d.fgts)}</b></span>
        <span>Multa FGTS: <b class="text-blue-600">${fBRL2(d.multa_fgts)}</b></span>
      </div>${(d.avisos || []).map(a => _dprAviso(a)).join('')}${_dpHoleriteTable(d)}`;
    if (gravar) {
      const b = document.getElementById('dp-body');
      if (b && typeof renderRescisao === 'function') await renderRescisao(b);
    }
  } catch (e) { res.innerHTML = _dprAviso(e.message, 'rose'); }
}

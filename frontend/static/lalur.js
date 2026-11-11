// LALUR — Livro de Apuração do Lucro Real
async function renderLalur() {
  const app = document.getElementById('app');
  const yr = new Date().getFullYear();
  app.innerHTML = `
    <div class="page-header">
      <h2>LALUR — Livro de Apuração do Lucro Real</h2>
      <div class="btn-group">
        <button class="btn btn-secondary" onclick="lalurApuracao()">Apurar Lucro Real</button>
        <button class="btn btn-primary" onclick="lalurOpenModal()">+ Lançamento</button>
      </div>
    </div>
    <div class="card mb-4" id="lalurApuracaoCard" style="display:none"></div>
    <div class="tabs mb-4">
      <button class="tab-btn active" onclick="lalurTab('partea')">Parte A — Lançamentos</button>
      <button class="tab-btn" onclick="lalurTab('parteb')">Parte B — Saldos</button>
    </div>
    <div id="lalurPartea">
      <div class="d-flex gap-2 mb-3">
        <select id="lalurAno" class="form-control" style="width:120px" onchange="lalurLoadLancamentos()">
          ${[yr-1,yr,yr+1].map(y=>`<option value="${y}" ${y===yr?'selected':''}>${y}</option>`).join('')}
        </select>
        <select id="lalurTipo" class="form-control" style="width:150px" onchange="lalurLoadLancamentos()">
          <option value="">Todos</option>
          <option value="adicao">Adições</option>
          <option value="exclusao">Exclusões</option>
        </select>
      </div>
      <div class="table-responsive">
        <table class="table">
          <thead><tr><th>Tipo</th><th>Descrição</th><th>Valor</th><th>Trimestre</th><th>Parte B</th><th></th></tr></thead>
          <tbody id="lalurTableBody"><tr><td colspan="6" class="text-center text-muted">Carregando...</td></tr></tbody>
        </table>
      </div>
    </div>
    <div id="lalurParteb" style="display:none">
      <div class="table-responsive">
        <table class="table">
          <thead><tr><th>Descrição</th><th>Saldo</th><th>Ano</th></tr></thead>
          <tbody id="parteBTableBody"><tr><td colspan="3" class="text-center text-muted">Carregando...</td></tr></tbody>
        </table>
      </div>
    </div>
    <div id="lalurModal" class="modal-overlay" style="display:none">
      <div class="modal-box">
        <h3>Novo Lançamento LALUR</h3>
        <div class="form-group">
          <label>Tipo</label>
          <select id="lalurTipoInput" class="form-control" onchange="lalurTipoChange()">
            <option value="adicao">Adição</option>
            <option value="exclusao">Exclusão</option>
          </select>
        </div>
        <div class="form-group">
          <label>Descrição</label>
          <div class="d-flex gap-2">
            <input type="text" id="lalurDesc" class="form-control" placeholder="Descrição do ajuste">
            <button class="btn btn-secondary" onclick="lalurSugestoes()" style="white-space:nowrap">Sugestões</button>
          </div>
          <div id="lalurSugList" class="mt-2" style="display:none"></div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Valor (R$)</label>
            <input type="number" id="lalurValor" class="form-control" step="0.01" placeholder="0,00">
          </div>
          <div class="form-group">
            <label>Ano</label>
            <input type="number" id="lalurAnoInput" class="form-control" value="${yr}">
          </div>
          <div class="form-group">
            <label>Trimestre</label>
            <select id="lalurTrimestre" class="form-control">
              <option value="">Anual</option>
              <option value="1">1º Trim</option>
              <option value="2">2º Trim</option>
              <option value="3">3º Trim</option>
              <option value="4">4º Trim</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label><input type="checkbox" id="lalurParteB"> Controla saldo na Parte B</label>
        </div>
        <div class="form-group" id="parteBDescGroup" style="display:none">
          <label>Descrição Parte B</label>
          <input type="text" id="lalurParteBDesc" class="form-control">
        </div>
        <div class="d-flex gap-2 justify-content-end mt-3">
          <button class="btn btn-secondary" onclick="lalurCloseModal()">Cancelar</button>
          <button class="btn btn-primary" onclick="lalurSave()">Salvar</button>
        </div>
      </div>
    </div>`;
  lalurLoadLancamentos();
}

function lalurTab(tab) {
  document.getElementById('lalurPartea').style.display = tab === 'partea' ? '' : 'none';
  document.getElementById('lalurParteb').style.display = tab === 'parteb' ? '' : 'none';
  document.querySelectorAll('.tab-btn').forEach((b, i) => b.classList.toggle('active', (i===0 && tab==='partea') || (i===1 && tab==='parteb')));
  if (tab === 'parteb') lalurLoadParteB();
}

async function lalurLoadLancamentos() {
  const ano = document.getElementById('lalurAno').value;
  const tipo = document.getElementById('lalurTipo').value;
  const tbody = document.getElementById('lalurTableBody');
  try {
    let url = `/api/lalur/lancamentos?ano=${ano}`;
    if (tipo) url += `&tipo=${tipo}`;
    const rows = await apiFetch(url);
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nenhum lançamento encontrado.</td></tr>'; return; }
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td><span class="badge ${r.tipo==='adicao'?'badge-danger':'badge-success'}">${r.tipo==='adicao'?'Adição':'Exclusão'}</span></td>
        <td>${r.descricao}</td>
        <td>${fmtCurrency(r.valor)}</td>
        <td>${r.trimestre ? r.trimestre + 'º Trim' : 'Anual'}</td>
        <td>${r.parte_b ? '✓ ' + (r.parte_b_descricao || '') : '—'}</td>
        <td><button class="btn btn-sm btn-danger" onclick="lalurDelete(${r.id})">Excluir</button></td>
      </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="6" class="text-danger">Erro: ${e.message}</td></tr>`; }
}

async function lalurLoadParteB() {
  const ano = document.getElementById('lalurAno').value;
  const tbody = document.getElementById('parteBTableBody');
  try {
    const rows = await apiFetch(`/api/lalur/parte-b?ano=${ano}`);
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Sem saldos na Parte B.</td></tr>'; return; }
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td>${r.descricao}</td>
        <td class="${r.saldo>=0?'text-success':'text-danger'}">${fmtCurrency(r.saldo)}</td>
        <td>${r.ano}</td>
      </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="3" class="text-danger">Erro: ${e.message}</td></tr>`; }
}

async function lalurApuracao() {
  const ano = document.getElementById('lalurAno').value;
  const card = document.getElementById('lalurApuracaoCard');
  card.style.display = '';
  card.innerHTML = '<div class="text-center p-3">Calculando...</div>';
  try {
    const d = await apiFetch(`/api/lalur/apuracao?ano=${ano}`);
    card.innerHTML = `
      <div class="p-3">
        <h4 class="mb-3">Apuração do Lucro Real — ${ano}</h4>
        <div class="row">
          <div class="col-md-6">
            <table class="table table-sm">
              <tr><td>Lucro Contábil</td><td class="text-right">${fmtCurrency(d.lucro_contabil)}</td></tr>
              <tr><td>(+) Adições</td><td class="text-right text-danger">${fmtCurrency(d.adicoes)}</td></tr>
              <tr><td>(−) Exclusões</td><td class="text-right text-success">${fmtCurrency(d.exclusoes)}</td></tr>
              <tr><td>(−) Prejuízos Compensados</td><td class="text-right text-muted">${fmtCurrency(d.prejuizo_compensado)}</td></tr>
              <tr class="font-weight-bold"><td>= Lucro Real</td><td class="text-right">${fmtCurrency(d.lucro_real)}</td></tr>
            </table>
          </div>
          <div class="col-md-6">
            <table class="table table-sm">
              <tr><td>IRPJ 15%</td><td class="text-right">${fmtCurrency(d.irpj_15pct)}</td></tr>
              <tr><td>IRPJ Adicional 10%</td><td class="text-right">${fmtCurrency(d.irpj_adicional_10pct)}</td></tr>
              <tr><td>CSLL 9%</td><td class="text-right">${fmtCurrency(d.csll_9pct)}</td></tr>
              <tr class="font-weight-bold text-danger"><td>Total Tributos</td><td class="text-right">${fmtCurrency(d.total_tributos)}</td></tr>
            </table>
          </div>
        </div>
        <button class="btn btn-sm btn-secondary" onclick="document.getElementById('lalurApuracaoCard').style.display='none'">Fechar</button>
      </div>`;
  } catch(e) { card.innerHTML = `<div class="text-danger p-3">Erro: ${e.message}</div>`; }
}

function lalurOpenModal() { document.getElementById('lalurModal').style.display = 'flex'; }
function lalurCloseModal() { document.getElementById('lalurModal').style.display = 'none'; }

function lalurTipoChange() {
  document.getElementById('lalurSugList').style.display = 'none';
}

async function lalurSugestoes() {
  const tipo = document.getElementById('lalurTipoInput').value;
  const sugList = document.getElementById('lalurSugList');
  try {
    const d = await apiFetch('/api/lalur/sugestoes');
    const items = tipo === 'adicao' ? d.adicoes : d.exclusoes;
    sugList.style.display = '';
    sugList.innerHTML = items.map(s => `
      <div class="suggestion-item" onclick="document.getElementById('lalurDesc').value='${s.replace(/'/g,"\\'").replace(/"/g,"&quot;")}'; document.getElementById('lalurSugList').style.display='none'" style="cursor:pointer; padding:4px 8px; border-radius:4px; hover:background:#eee">
        ${s}
      </div>`).join('');
  } catch(e) {}
}

document.getElementById && document.addEventListener('click', function(e) {
  if (document.getElementById('lalurParteB') && e.target && e.target.id === 'lalurParteB') {
    document.getElementById('parteBDescGroup').style.display = e.target.checked ? '' : 'none';
  }
});

async function lalurSave() {
  const body = {
    tipo: document.getElementById('lalurTipoInput').value,
    descricao: document.getElementById('lalurDesc').value,
    valor: parseFloat(document.getElementById('lalurValor').value) || 0,
    ano: parseInt(document.getElementById('lalurAnoInput').value),
    trimestre: document.getElementById('lalurTrimestre').value ? parseInt(document.getElementById('lalurTrimestre').value) : null,
    parte_b: document.getElementById('lalurParteB').checked ? 1 : 0,
    parte_b_descricao: document.getElementById('lalurParteBDesc').value,
  };
  try {
    await apiFetch('/api/lalur/lancamentos', { method: 'POST', body: JSON.stringify(body) });
    lalurCloseModal();
    lalurLoadLancamentos();
  } catch(e) { alert('Erro: ' + e.message); }
}

async function lalurDelete(id) {
  if (!confirm('Excluir este lançamento?')) return;
  await apiFetch(`/api/lalur/lancamentos/${id}`, { method: 'DELETE' });
  lalurLoadLancamentos();
}

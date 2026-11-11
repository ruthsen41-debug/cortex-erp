// Honorários — Gestão de contratos de honorários contábeis
async function renderHonorarios() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="page-header">
      <h2>Honorários</h2>
      <div class="btn-group">
        <button class="btn btn-secondary" onclick="honorariosFaturarMes()">Faturar Mês</button>
        <button class="btn btn-primary" onclick="honorariosOpenModal()">+ Contrato</button>
      </div>
    </div>
    <div id="honorariosSummary" class="row mb-4"></div>
    <div class="tabs mb-4">
      <button class="tab-btn active" onclick="honorariosTab('contratos')">Contratos</button>
      <button class="tab-btn" onclick="honorariosTab('faturas')">Faturas</button>
    </div>
    <div id="honorariosContratos">
      <div class="table-responsive">
        <table class="table">
          <thead><tr><th>Cliente</th><th>CNPJ/CPF</th><th>Regime</th><th>Mensalidade</th><th>Vencimento</th><th>Status</th><th></th></tr></thead>
          <tbody id="honorariosContratosBody"><tr><td colspan="7" class="text-center text-muted">Carregando...</td></tr></tbody>
        </table>
      </div>
    </div>
    <div id="honorariosFaturas" style="display:none">
      <div class="d-flex gap-2 mb-3">
        <input type="month" id="honFatCompetencia" class="form-control" style="width:170px" value="${new Date().toISOString().slice(0,7)}" onchange="honorariosLoadFaturas()">
        <select id="honFatStatus" class="form-control" style="width:150px" onchange="honorariosLoadFaturas()">
          <option value="">Todos</option>
          <option value="pendente">Pendentes</option>
          <option value="pago">Pagas</option>
        </select>
      </div>
      <div class="table-responsive">
        <table class="table">
          <thead><tr><th>Cliente</th><th>Competência</th><th>Valor</th><th>Vencimento</th><th>Status</th><th></th></tr></thead>
          <tbody id="honorariosFaturasBody"><tr><td colspan="6" class="text-center text-muted">Carregando...</td></tr></tbody>
        </table>
      </div>
    </div>
    <div id="honorariosModal" class="modal-overlay" style="display:none">
      <div class="modal-box">
        <h3 id="honorariosModalTitle">Novo Contrato</h3>
        <input type="hidden" id="honorariosEditId">
        <div class="form-row">
          <div class="form-group">
            <label>Nome do Cliente</label>
            <input type="text" id="honClientName" class="form-control">
          </div>
          <div class="form-group">
            <label>CNPJ/CPF</label>
            <input type="text" id="honCnpj" class="form-control" placeholder="00.000.000/0001-00">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>E-mail</label>
            <input type="email" id="honEmail" class="form-control">
          </div>
          <div class="form-group">
            <label>Telefone</label>
            <input type="text" id="honPhone" class="form-control">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Regime Tributário</label>
            <select id="honRegime" class="form-control">
              <option value="simples_nacional">Simples Nacional</option>
              <option value="lucro_presumido">Lucro Presumido</option>
              <option value="lucro_real">Lucro Real</option>
              <option value="mei">MEI</option>
            </select>
          </div>
          <div class="form-group">
            <label>Valor Mensal (R$)</label>
            <input type="number" id="honValor" class="form-control" step="0.01">
          </div>
          <div class="form-group">
            <label>Dia Vencimento</label>
            <input type="number" id="honDia" class="form-control" value="10" min="1" max="28">
          </div>
        </div>
        <div class="form-group">
          <label>Serviços</label>
          <div id="honServicos" class="d-flex flex-wrap gap-2 p-2 border rounded"></div>
        </div>
        <div class="form-group">
          <label>Observações</label>
          <textarea id="honObs" class="form-control" rows="2"></textarea>
        </div>
        <div class="form-group">
          <label><input type="checkbox" id="honAtivo" checked> Contrato Ativo</label>
        </div>
        <div class="d-flex gap-2 justify-content-end mt-3">
          <button class="btn btn-secondary" onclick="honorariosCloseModal()">Cancelar</button>
          <button class="btn btn-primary" onclick="honorariosSave()">Salvar</button>
        </div>
      </div>
    </div>`;
  honorariosLoadSummary();
  honorariosLoadContratos();
  honorariosLoadServicos();
}

function honorariosTab(tab) {
  document.getElementById('honorariosContratos').style.display = tab === 'contratos' ? '' : 'none';
  document.getElementById('honorariosFaturas').style.display = tab === 'faturas' ? '' : 'none';
  document.querySelectorAll('.tab-btn').forEach((b, i) => b.classList.toggle('active', (i===0 && tab==='contratos') || (i===1 && tab==='faturas')));
  if (tab === 'faturas') honorariosLoadFaturas();
}

async function honorariosLoadSummary() {
  try {
    const d = await apiFetch('/api/honorarios/summary');
    document.getElementById('honorariosSummary').innerHTML = `
      <div class="col-md-2 col-6"><div class="kpi-card"><div class="kpi-value">${d.total_contratos_ativos}</div><div class="kpi-label">Contratos Ativos</div></div></div>
      <div class="col-md-2 col-6"><div class="kpi-card"><div class="kpi-value">${fmtCurrency(d.mrr)}</div><div class="kpi-label">MRR</div></div></div>
      <div class="col-md-2 col-6"><div class="kpi-card"><div class="kpi-value">${fmtCurrency(d.mrr_anual)}</div><div class="kpi-label">ARR</div></div></div>
      <div class="col-md-2 col-6"><div class="kpi-card"><div class="kpi-value text-warning">${fmtCurrency(d.pendente_mes)}</div><div class="kpi-label">Pendente Mês</div></div></div>
      <div class="col-md-2 col-6"><div class="kpi-card"><div class="kpi-value text-success">${fmtCurrency(d.pago_mes)}</div><div class="kpi-label">Recebido Mês</div></div></div>
      <div class="col-md-2 col-6"><div class="kpi-card"><div class="kpi-value text-danger">${d.inadimplentes}</div><div class="kpi-label">Inadimplentes</div></div></div>`;
  } catch(e) {}
}

async function honorariosLoadContratos() {
  const tbody = document.getElementById('honorariosContratosBody');
  try {
    const rows = await apiFetch('/api/honorarios/contratos');
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Nenhum contrato.</td></tr>'; return; }
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td>${r.client_name}</td>
        <td>${r.cnpj_cpf || '—'}</td>
        <td><span class="badge badge-info">${r.regime}</span></td>
        <td>${fmtCurrency(r.valor_mensal)}</td>
        <td>Dia ${r.dia_vencimento}</td>
        <td><span class="badge ${r.ativo?'badge-success':'badge-secondary'}">${r.ativo?'Ativo':'Inativo'}</span></td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="honorariosEdit(${JSON.stringify(r).replace(/"/g,'&quot;')})">Editar</button>
          <button class="btn btn-sm btn-danger" onclick="honorariosDelete(${r.id})">Excluir</button>
        </td>
      </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="7" class="text-danger">Erro: ${e.message}</td></tr>`; }
}

async function honorariosLoadFaturas() {
  const comp = document.getElementById('honFatCompetencia').value;
  const status = document.getElementById('honFatStatus').value;
  const tbody = document.getElementById('honorariosFaturasBody');
  try {
    let url = `/api/honorarios/faturas?competencia=${comp}`;
    if (status) url += `&status=${status}`;
    const rows = await apiFetch(url);
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nenhuma fatura.</td></tr>'; return; }
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td>${r.client_name}</td>
        <td>${r.competencia}</td>
        <td>${fmtCurrency(r.valor)}</td>
        <td>${r.due_date}</td>
        <td><span class="badge ${r.status==='pago'?'badge-success':'badge-warning'}">${r.status}</span></td>
        <td>${r.status!=='pago'?`<button class="btn btn-sm btn-success" onclick="honorariosPagar(${r.id})">Pagar</button>`:''}</td>
      </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="6" class="text-danger">Erro: ${e.message}</td></tr>`; }
}

async function honorariosLoadServicos() {
  try {
    const d = await apiFetch('/api/honorarios/servicos');
    const container = document.getElementById('honServicos');
    if (!container) return;
    container.innerHTML = d.servicos.map(s => `
      <label class="d-flex align-items-center gap-1" style="font-size:0.85rem; cursor:pointer">
        <input type="checkbox" class="hon-servico" value="${s}"> ${s}
      </label>`).join('');
  } catch(e) {}
}

function honorariosOpenModal() {
  document.getElementById('honorariosModalTitle').textContent = 'Novo Contrato';
  document.getElementById('honorariosEditId').value = '';
  ['honClientName','honCnpj','honEmail','honPhone','honObs'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('honValor').value = '';
  document.getElementById('honDia').value = 10;
  document.getElementById('honAtivo').checked = true;
  document.getElementById('honRegime').value = 'simples_nacional';
  document.querySelectorAll('.hon-servico').forEach(c => c.checked = false);
  document.getElementById('honorariosModal').style.display = 'flex';
}

function honorariosEdit(r) {
  document.getElementById('honorariosModalTitle').textContent = 'Editar Contrato';
  document.getElementById('honorariosEditId').value = r.id;
  document.getElementById('honClientName').value = r.client_name || '';
  document.getElementById('honCnpj').value = r.cnpj_cpf || '';
  document.getElementById('honEmail').value = r.email || '';
  document.getElementById('honPhone').value = r.phone || '';
  document.getElementById('honRegime').value = r.regime || 'simples_nacional';
  document.getElementById('honValor').value = r.valor_mensal || '';
  document.getElementById('honDia').value = r.dia_vencimento || 10;
  document.getElementById('honObs').value = r.observacoes || '';
  document.getElementById('honAtivo').checked = !!r.ativo;
  const servs = r.servicos ? JSON.parse(r.servicos) : [];
  document.querySelectorAll('.hon-servico').forEach(c => c.checked = servs.includes(c.value));
  document.getElementById('honorariosModal').style.display = 'flex';
}

function honorariosCloseModal() { document.getElementById('honorariosModal').style.display = 'none'; }

async function honorariosSave() {
  const id = document.getElementById('honorariosEditId').value;
  const servicos = JSON.stringify([...document.querySelectorAll('.hon-servico:checked')].map(c => c.value));
  const body = {
    client_name: document.getElementById('honClientName').value,
    cnpj_cpf: document.getElementById('honCnpj').value,
    email: document.getElementById('honEmail').value,
    phone: document.getElementById('honPhone').value,
    regime: document.getElementById('honRegime').value,
    valor_mensal: parseFloat(document.getElementById('honValor').value) || 0,
    dia_vencimento: parseInt(document.getElementById('honDia').value) || 10,
    servicos,
    observacoes: document.getElementById('honObs').value,
    ativo: document.getElementById('honAtivo').checked ? 1 : 0,
  };
  try {
    if (id) {
      await apiFetch(`/api/honorarios/contratos/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    } else {
      await apiFetch('/api/honorarios/contratos', { method: 'POST', body: JSON.stringify(body) });
    }
    honorariosCloseModal();
    honorariosLoadContratos();
    honorariosLoadSummary();
  } catch(e) { alert('Erro: ' + e.message); }
}

async function honorariosDelete(id) {
  if (!confirm('Excluir este contrato?')) return;
  await apiFetch(`/api/honorarios/contratos/${id}`, { method: 'DELETE' });
  honorariosLoadContratos();
  honorariosLoadSummary();
}

async function honorariosFaturarMes() {
  const comp = new Date().toISOString().slice(0,7);
  if (!confirm(`Gerar faturas para todos os contratos ativos — competência ${comp}?`)) return;
  try {
    const d = await apiFetch(`/api/honorarios/faturar-mes?competencia=${comp}`, { method: 'POST' });
    alert(d.message);
    honorariosLoadSummary();
  } catch(e) { alert('Erro: ' + e.message); }
}

async function honorariosPagar(id) {
  if (!confirm('Marcar fatura como paga?')) return;
  await apiFetch(`/api/honorarios/faturas/${id}/pagar`, { method: 'POST' });
  honorariosLoadFaturas();
  honorariosLoadSummary();
}

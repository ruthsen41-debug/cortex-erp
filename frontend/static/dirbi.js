// DIRBI — Declaração de Incentivos, Renúncias, Benefícios e Imunidades
async function renderDirbi(container) {
  const app = container;
  const comp = new Date().toISOString().slice(0,7);
  app.innerHTML = `
    <div class="page-header">
      <h2>DIRBI</h2>
      <div class="btn-group">
        <button class="btn btn-secondary" onclick="dirbiPreview()">Prévia</button>
        <button class="btn btn-secondary" onclick="dirbiGerar()">Gerar Arquivo</button>
        <button class="btn btn-primary" onclick="dirbiOpenModal()">+ Registrar Benefício</button>
      </div>
    </div>
    <div class="alert alert-info mb-3">
      <strong>DIRBI</strong> (IN RFB nº 2198/2024) — Declaração obrigatória para empresas que usufruíram de incentivos ou benefícios fiscais tributários.
      Vencimento: todo dia 20 do mês seguinte à competência.
    </div>
    <div class="d-flex gap-2 mb-3">
      <input type="month" id="dirbiCompetencia" class="form-control" style="width:170px" value="${comp}" onchange="dirbiLoad()">
    </div>
    <div id="dirbiPreviewCard" class="card mb-4" style="display:none"></div>
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Código</th><th>Benefício</th><th>Valor Benefício</th><th>Base de Cálculo</th><th>Observação</th><th></th></tr></thead>
        <tbody id="dirbiTableBody"><tr><td colspan="6" class="text-center text-muted">Carregando...</td></tr></tbody>
      </table>
    </div>
    <div id="dirbiModal" class="modal-overlay" style="display:none">
      <div class="modal-box">
        <h3>Registrar Benefício Fiscal</h3>
        <div class="form-row">
          <div class="form-group">
            <label>Competência</label>
            <input type="month" id="dirbiBenCompetencia" class="form-control" value="${comp}">
          </div>
        </div>
        <div class="form-group">
          <label>Benefício</label>
          <div class="d-flex gap-2">
            <input type="text" id="dirbiBenDesc" class="form-control" placeholder="Descrição do benefício">
            <button class="btn btn-secondary" onclick="dirbiShowBeneficios()" style="white-space:nowrap">Listar</button>
          </div>
          <input type="hidden" id="dirbiBenCodigo">
          <div id="dirbiBenList" style="display:none" class="mt-1 border rounded p-2 bg-light"></div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Valor do Benefício (R$)</label>
            <input type="number" id="dirbiValor" class="form-control" step="0.01">
          </div>
          <div class="form-group">
            <label>Base de Cálculo (R$)</label>
            <input type="number" id="dirbiBase" class="form-control" step="0.01">
          </div>
        </div>
        <div class="form-group">
          <label>Observação</label>
          <input type="text" id="dirbiObs" class="form-control">
        </div>
        <div class="d-flex gap-2 justify-content-end mt-3">
          <button class="btn btn-secondary" onclick="dirbiCloseModal()">Cancelar</button>
          <button class="btn btn-primary" onclick="dirbiSave()">Salvar</button>
        </div>
      </div>
    </div>`;
  dirbiLoad();
}

async function dirbiLoad() {
  const comp = document.getElementById('dirbiCompetencia').value;
  const tbody = document.getElementById('dirbiTableBody');
  try {
    const rows = await apiFetch(`/api/dirbi/lancamentos?competencia=${comp}`);
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nenhum benefício registrado para esta competência.</td></tr>'; return; }
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td><code>${r.codigo_beneficio}</code></td>
        <td>${r.descricao}</td>
        <td>${fmtCurrency(r.valor_beneficio)}</td>
        <td>${fmtCurrency(r.base_calculo)}</td>
        <td>${r.observacao || '—'}</td>
        <td><button class="btn btn-sm btn-danger" onclick="dirbiDelete(${r.id})">Excluir</button></td>
      </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="6" class="text-danger">Erro: ${e.message}</td></tr>`; }
}

async function dirbiPreview() {
  const comp = document.getElementById('dirbiCompetencia').value;
  const card = document.getElementById('dirbiPreviewCard');
  card.style.display = '';
  card.innerHTML = '<div class="text-center p-3">Calculando prévia...</div>';
  try {
    const d = await apiFetch(`/api/dirbi/preview?competencia=${comp}`);
    card.innerHTML = `
      <div class="p-3">
        <h4>Prévia DIRBI — ${comp}</h4>
        <div class="row">
          <div class="col-md-6">
            <table class="table table-sm">
              <tr><td>Empresa</td><td><strong>${d.razao_social}</strong></td></tr>
              <tr><td>CNPJ</td><td>${d.cnpj}</td></tr>
              <tr><td>Regime</td><td>${d.regime}</td></tr>
              <tr><td>Receita Bruta Mês</td><td>${fmtCurrency(d.receita_bruta_mes)}</td></tr>
            </table>
          </div>
          <div class="col-md-6">
            <table class="table table-sm">
              <tr><td>Benefícios Declarados</td><td><strong>${fmtCurrency(d.total_beneficios_declarados)}</strong></td></tr>
              ${d.simples_estimado > 0 ? `<tr><td>Simples Estimado</td><td>${fmtCurrency(d.simples_estimado)}</td></tr>` : ''}
              <tr><td>Vencimento</td><td><strong>${d.vencimento}</strong></td></tr>
              <tr><td>Obrigatório?</td><td>${d.obrigatorio ? '<span class="badge badge-danger">Sim</span>' : '<span class="badge badge-secondary">Não</span>'}</td></tr>
            </table>
          </div>
        </div>
        <p class="text-muted small">${d.observacao}</p>
        <button class="btn btn-sm btn-secondary" onclick="document.getElementById('dirbiPreviewCard').style.display='none'">Fechar</button>
      </div>`;
  } catch(e) { card.innerHTML = `<div class="text-danger p-3">Erro: ${e.message}</div>`; }
}

async function dirbiGerar() {
  const comp = document.getElementById('dirbiCompetencia').value;
  try {
    const token = localStorage.getItem('cortex_token');
    const resp = await fetch(`/api/dirbi/gerar?competencia=${comp}`, {
      headers: token ? { 'Authorization': 'Bearer ' + token } : {},
    });
    if (!resp.ok) { const d = await resp.json(); throw new Error(d.detail || 'Erro'); }
    const blob = await resp.blob();
    const cd = resp.headers.get('Content-Disposition') || '';
    const fname = cd.match(/filename="(.+?)"/)?.[1] || `DIRBI_${comp}.txt`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = fname; a.click();
    URL.revokeObjectURL(url);
  } catch(e) { alert('Erro: ' + e.message); }
}

function dirbiOpenModal() {
  document.getElementById('dirbiBenDesc').value = '';
  document.getElementById('dirbiBenCodigo').value = '';
  document.getElementById('dirbiValor').value = '';
  document.getElementById('dirbiBase').value = '';
  document.getElementById('dirbiObs').value = '';
  document.getElementById('dirbiBenList').style.display = 'none';
  document.getElementById('dirbiModal').style.display = 'flex';
}
function dirbiCloseModal() { document.getElementById('dirbiModal').style.display = 'none'; }

async function dirbiShowBeneficios() {
  const list = document.getElementById('dirbiBenList');
  if (list.style.display !== 'none') { list.style.display = 'none'; return; }
  try {
    const d = await apiFetch('/api/dirbi/beneficios-disponiveis');
    list.style.display = '';
    if (!d.beneficios.length) { list.innerHTML = '<div class="text-muted">Nenhum benefício aplicável ao regime da empresa.</div>'; return; }
    list.innerHTML = d.beneficios.map(b => `
      <div style="cursor:pointer; padding:3px 6px; border-radius:3px" onmouseover="this.style.background='#eee'" onmouseout="this.style.background=''"
        onclick="document.getElementById('dirbiBenDesc').value='${b.descricao.replace(/'/g,"\\'")}'; document.getElementById('dirbiBenCodigo').value='${b.codigo}'; document.getElementById('dirbiBenList').style.display='none'">
        <code>${b.codigo}</code> — ${b.descricao}
      </div>`).join('');
  } catch(e) {}
}

async function dirbiSave() {
  const body = {
    codigo_beneficio: document.getElementById('dirbiBenCodigo').value || '00000',
    descricao: document.getElementById('dirbiBenDesc').value,
    competencia: document.getElementById('dirbiBenCompetencia').value,
    valor_beneficio: parseFloat(document.getElementById('dirbiValor').value) || 0,
    base_calculo: parseFloat(document.getElementById('dirbiBase').value) || 0,
    observacao: document.getElementById('dirbiObs').value,
  };
  if (!body.descricao) { alert('Informe a descrição do benefício.'); return; }
  try {
    await apiFetch('/api/dirbi/lancamentos', { method: 'POST', body: JSON.stringify(body) });
    dirbiCloseModal();
    dirbiLoad();
  } catch(e) { alert('Erro: ' + e.message); }
}

async function dirbiDelete(id) {
  if (!confirm('Excluir este lançamento?')) return;
  await apiFetch(`/api/dirbi/lancamentos/${id}`, { method: 'DELETE' });
  dirbiLoad();
}

// Manifesto do Destinatário — NF-e recebidas
async function renderNfeManifest() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="page-header">
      <h2>Manifesto do Destinatário</h2>
      <div class="btn-group">
        <button class="btn btn-primary" onclick="manifestOpenUpload()">Importar XMLs</button>
      </div>
    </div>
    <div id="manifestSummary" class="row mb-4"></div>
    <div class="d-flex gap-2 mb-3">
      <select id="manifestStatus" class="form-control" style="width:200px" onchange="manifestLoad()">
        <option value="">Todos</option>
        <option value="pendente">Pendentes</option>
        <option value="confirmada">Confirmadas</option>
        <option value="desconhecida">Desconhecidas</option>
        <option value="nao_realizada">Não Realizadas</option>
        <option value="importada_estoque">Importadas p/ Estoque</option>
      </select>
    </div>
    <div class="table-responsive">
      <table class="table">
        <thead>
          <tr>
            <th>Emitente</th><th>Número</th><th>Data Emissão</th>
            <th>Total</th><th>Status</th><th>Ações</th>
          </tr>
        </thead>
        <tbody id="manifestTableBody">
          <tr><td colspan="6" class="text-center text-muted">Carregando...</td></tr>
        </tbody>
      </table>
    </div>
    <div id="manifestUploadModal" class="modal-overlay" style="display:none">
      <div class="modal-box">
        <h3>Importar NF-e (XMLs)</h3>
        <p class="text-muted">Selecione um ou mais arquivos XML de NF-e destinadas à sua empresa.</p>
        <div class="form-group">
          <label>Arquivos XML</label>
          <input type="file" id="manifestFiles" class="form-control" accept=".xml" multiple>
        </div>
        <div id="manifestUploadResult" class="mt-3" style="display:none"></div>
        <div class="d-flex gap-2 justify-content-end mt-3">
          <button class="btn btn-secondary" onclick="manifestCloseUpload()">Fechar</button>
          <button class="btn btn-primary" onclick="manifestUpload()">Importar</button>
        </div>
      </div>
    </div>
    <div id="manifestDetalhesModal" class="modal-overlay" style="display:none">
      <div class="modal-box" style="max-width:600px">
        <h3>Detalhes da NF-e</h3>
        <div id="manifestDetalhesContent"></div>
        <div class="d-flex justify-content-end mt-3">
          <button class="btn btn-secondary" onclick="document.getElementById('manifestDetalhesModal').style.display='none'">Fechar</button>
        </div>
      </div>
    </div>`;
  manifestLoadSummary();
  manifestLoad();
}

async function manifestLoadSummary() {
  try {
    const d = await apiFetch('/api/nfe-manifest/summary');
    const bs = d.by_status || {};
    const pend = bs.pendente || { count: 0, total: 0 };
    const conf = bs.confirmada || { count: 0, total: 0 };
    const imp = bs.importada_estoque || { count: 0, total: 0 };
    document.getElementById('manifestSummary').innerHTML = `
      <div class="col-md-3 col-6"><div class="kpi-card"><div class="kpi-value">${d.total_nfe}</div><div class="kpi-label">Total NF-e</div></div></div>
      <div class="col-md-3 col-6"><div class="kpi-card"><div class="kpi-value text-warning">${pend.count}</div><div class="kpi-label">Pendentes</div></div></div>
      <div class="col-md-3 col-6"><div class="kpi-card"><div class="kpi-value text-success">${conf.count}</div><div class="kpi-label">Confirmadas</div></div></div>
      <div class="col-md-3 col-6"><div class="kpi-card"><div class="kpi-value">${imp.count}</div><div class="kpi-label">Importadas Estoque</div></div></div>`;
  } catch(e) {}
}

async function manifestLoad() {
  const status = document.getElementById('manifestStatus').value;
  const tbody = document.getElementById('manifestTableBody');
  try {
    let url = '/api/nfe-manifest/list';
    if (status) url += `?status=${status}`;
    const rows = await apiFetch(url);
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nenhuma NF-e encontrada.</td></tr>'; return; }
    const statusMap = {
      pendente: ['warning', 'Pendente'],
      confirmada: ['success', 'Confirmada'],
      desconhecida: ['danger', 'Desconhecida'],
      nao_realizada: ['secondary', 'Não Realizada'],
      importada_estoque: ['info', 'No Estoque'],
    };
    tbody.innerHTML = rows.map(r => {
      const [sc, sl] = statusMap[r.status] || ['secondary', r.status];
      return `<tr>
        <td>${r.emit_nome || '—'}<br><small class="text-muted">${r.emit_cnpj || ''}</small></td>
        <td>${r.numero || '—'} / Série ${r.serie || '?'}</td>
        <td>${r.data_emissao || '—'}</td>
        <td>${fmtCurrency(r.total_nota)}</td>
        <td><span class="badge badge-${sc}">${sl}</span></td>
        <td>
          ${r.status==='pendente'?`
            <button class="btn btn-sm btn-success" onclick="manifestar(${r.id},'confirmacao')" title="Confirmar">✓</button>
            <button class="btn btn-sm btn-warning" onclick="manifestar(${r.id},'desconhecimento')" title="Desconhecer">?</button>
            <button class="btn btn-sm btn-secondary" onclick="manifestar(${r.id},'nao_realizada')" title="Não Realizada">✗</button>
          `:''}
          ${r.status==='confirmada'?`<button class="btn btn-sm btn-primary" onclick="manifestImportarEstoque(${r.id})">Importar Estoque</button>`:''}
        </td>
      </tr>`;
    }).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="6" class="text-danger">Erro: ${e.message}</td></tr>`; }
}

function manifestOpenUpload() {
  document.getElementById('manifestUploadResult').style.display = 'none';
  document.getElementById('manifestFiles').value = '';
  document.getElementById('manifestUploadModal').style.display = 'flex';
}
function manifestCloseUpload() { document.getElementById('manifestUploadModal').style.display = 'none'; }

async function manifestUpload() {
  const files = document.getElementById('manifestFiles').files;
  if (!files.length) { alert('Selecione ao menos um arquivo XML.'); return; }
  const formData = new FormData();
  for (const f of files) formData.append('files', f);
  const resultDiv = document.getElementById('manifestUploadResult');
  resultDiv.style.display = '';
  resultDiv.innerHTML = '<div class="text-muted">Importando...</div>';
  try {
    const token = localStorage.getItem('cortex_token');
    const resp = await fetch('/api/nfe-manifest/upload', {
      method: 'POST',
      headers: token ? { 'Authorization': 'Bearer ' + token } : {},
      body: formData,
    });
    const d = await resp.json();
    if (!resp.ok) throw new Error(d.detail || 'Erro');
    const statusColors = { importada: 'success', duplicada: 'warning', erro: 'danger' };
    resultDiv.innerHTML = d.results.map(r => `
      <div class="alert alert-${statusColors[r.status]||'secondary'} py-1 mb-1">
        <strong>${r.arquivo}</strong>: ${r.status}
        ${r.emit ? ` — ${r.emit}` : ''}
        ${r.total !== undefined ? ` — ${fmtCurrency(r.total)}` : ''}
        ${r.erro ? ` — ${r.erro}` : ''}
      </div>`).join('');
    manifestLoad();
    manifestLoadSummary();
  } catch(e) { resultDiv.innerHTML = `<div class="text-danger">Erro: ${e.message}</div>`; }
}

async function manifestar(id, operacao) {
  const labels = { confirmacao: 'confirmar', desconhecimento: 'desconhecer', nao_realizada: 'marcar como não realizada' };
  if (!confirm(`Deseja ${labels[operacao]||operacao} esta NF-e?`)) return;
  try {
    await apiFetch(`/api/nfe-manifest/${id}/manifestar?operacao=${operacao}`, { method: 'POST' });
    manifestLoad();
    manifestLoadSummary();
  } catch(e) { alert('Erro: ' + e.message); }
}

async function manifestImportarEstoque(id) {
  if (!confirm('Importar itens desta NF-e para o estoque e gerar conta a pagar?')) return;
  try {
    const d = await apiFetch(`/api/nfe-manifest/${id}/importar-estoque`, { method: 'POST' });
    alert(d.message);
    manifestLoad();
    manifestLoadSummary();
  } catch(e) { alert('Erro: ' + e.message); }
}

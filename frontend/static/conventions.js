// Convenções Coletivas de Trabalho (CCT)
async function renderConventions(container) {
  const app = container;
  app.innerHTML = `
    <div class="page-header">
      <h2>Convenções Coletivas (CCT)</h2>
      <div class="btn-group">
        <button class="btn btn-primary" onclick="convOpenModal()">+ Registrar CCT</button>
      </div>
    </div>
    <div id="convSummary" class="row mb-4"></div>
    <div class="d-flex gap-2 mb-3">
      <select id="convUf" class="form-control" style="width:100px" onchange="convLoad()">
        <option value="">Todos UFs</option>
        ${['AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO'].map(u=>`<option value="${u}">${u}</option>`).join('')}
      </select>
    </div>
    <div class="table-responsive">
      <table class="table">
        <thead>
          <tr><th>Categoria</th><th>Sindicato dos Empregados</th><th>UF</th><th>Vigência</th><th>Piso Salarial</th><th>Reajuste</th><th>Status</th><th></th></tr>
        </thead>
        <tbody id="convTableBody">
          <tr><td colspan="8" class="text-center text-muted">Carregando...</td></tr>
        </tbody>
      </table>
    </div>
    <div id="convModal" class="modal-overlay" style="display:none">
      <div class="modal-box" style="max-width:600px">
        <h3 id="convModalTitle">Registrar CCT</h3>
        <input type="hidden" id="convEditId">
        <div class="form-row">
          <div class="form-group">
            <label>Categoria</label>
            <div class="d-flex gap-2">
              <input type="text" id="convCategoria" class="form-control" placeholder="Ex: Comerciários">
              <button class="btn btn-secondary btn-sm" onclick="convShowCategorias()" style="white-space:nowrap">Listar</button>
            </div>
            <div id="convCatList" style="display:none" class="mt-1 border rounded p-2 bg-light" style="max-height:150px; overflow-y:auto"></div>
          </div>
          <div class="form-group">
            <label>UF</label>
            <select id="convUfInput" class="form-control">
              ${['AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO'].map(u=>`<option value="${u}">${u}</option>`).join('')}
            </select>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Sindicato dos Empregados</label>
            <input type="text" id="convSindEmp" class="form-control">
          </div>
          <div class="form-group">
            <label>Sindicato dos Empregadores</label>
            <input type="text" id="convSindEmpregadores" class="form-control">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Município</label>
            <input type="text" id="convMunicipio" class="form-control">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Início Vigência</label>
            <input type="date" id="convInicio" class="form-control">
          </div>
          <div class="form-group">
            <label>Fim Vigência</label>
            <input type="date" id="convFim" class="form-control">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Piso Salarial (R$)</label>
            <input type="number" id="convPiso" class="form-control" step="0.01">
          </div>
          <div class="form-group">
            <label>Reajuste (%)</label>
            <input type="number" id="convReajuste" class="form-control" step="0.01">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Jornada Semanal (h)</label>
            <input type="number" id="convJornada" class="form-control" value="44">
          </div>
          <div class="form-group">
            <label>Intervalo Jornada (min)</label>
            <input type="number" id="convIntervalo" class="form-control" value="60">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Adicional Noturno (%)</label>
            <input type="number" id="convNoturno" class="form-control" value="20" step="0.01">
          </div>
          <div class="form-group">
            <label>Hora Extra (%)</label>
            <input type="number" id="convHoraExtra" class="form-control" value="50" step="0.01">
          </div>
          <div class="form-group">
            <label>VR Diário (R$)</label>
            <input type="number" id="convVR" class="form-control" value="0" step="0.01">
          </div>
        </div>
        <div class="form-group">
          <label><input type="checkbox" id="convVT" checked> Vale-Transporte obrigatório</label>
        </div>
        <div class="form-group">
          <label>Observações / URL do arquivo</label>
          <textarea id="convObs" class="form-control" rows="2"></textarea>
        </div>
        <div class="d-flex gap-2 justify-content-end mt-3">
          <button class="btn btn-secondary" onclick="convCloseModal()">Cancelar</button>
          <button class="btn btn-primary" onclick="convSave()">Salvar</button>
        </div>
      </div>
    </div>`;
  convLoadSummary();
  convLoad();
}

async function convLoadSummary() {
  try {
    const d = await apiFetch('/api/conventions/summary');
    document.getElementById('convSummary').innerHTML = `
      <div class="col-md-3 col-6"><div class="kpi-card"><div class="kpi-value">${d.total}</div><div class="kpi-label">CCTs Registradas</div></div></div>
      <div class="col-md-3 col-6"><div class="kpi-card"><div class="kpi-value text-success">${d.vigentes}</div><div class="kpi-label">Vigentes</div></div></div>
      <div class="col-md-3 col-6"><div class="kpi-card"><div class="kpi-value text-warning">${d.vencendo_90_dias}</div><div class="kpi-label">Vencendo em 90 dias</div></div></div>
      <div class="col-md-3 col-6"><div class="kpi-card"><div class="kpi-value text-danger">${d.vencidas}</div><div class="kpi-label">Vencidas</div></div></div>`;
  } catch(e) {}
}

async function convLoad() {
  const uf = document.getElementById('convUf').value;
  const tbody = document.getElementById('convTableBody');
  try {
    let url = '/api/conventions/list';
    if (uf) url += `?uf=${uf}`;
    const rows = await apiFetch(url);
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">Nenhuma CCT registrada.</td></tr>'; return; }
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td>${r.categoria}</td>
        <td>${r.sindicato_empregados}</td>
        <td>${r.uf}</td>
        <td>${r.data_inicio} a ${r.data_fim}</td>
        <td>${fmtCurrency(r.piso_salarial)}</td>
        <td>${r.reajuste_pct ? r.reajuste_pct + '%' : '—'}</td>
        <td>
          <span class="badge badge-${r.status==='vigente'?'success':'danger'}">${r.status}</span>
          ${r.dias_para_vencer !== null && r.dias_para_vencer <= 90 && r.dias_para_vencer >= 0 ? `<span class="badge badge-warning ml-1">${r.dias_para_vencer}d</span>` : ''}
        </td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="convEdit(${JSON.stringify(r).replace(/"/g,'&quot;')})">Editar</button>
          <button class="btn btn-sm btn-danger" onclick="convDelete(${r.id})">Excluir</button>
        </td>
      </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="8" class="text-danger">Erro: ${e.message}</td></tr>`; }
}

async function convShowCategorias() {
  const list = document.getElementById('convCatList');
  if (list.style.display !== 'none') { list.style.display = 'none'; return; }
  try {
    const d = await apiFetch('/api/conventions/categorias');
    list.style.display = '';
    list.innerHTML = d.categorias.map(c => `
      <div style="cursor:pointer; padding:3px 6px; border-radius:3px" onmouseover="this.style.background='#eee'" onmouseout="this.style.background=''" onclick="document.getElementById('convCategoria').value='${c.descricao}'; document.getElementById('convSindEmp').value='${c.cno||c.sindicato}'; document.getElementById('convCatList').style.display='none'">
        ${c.descricao} — <small class="text-muted">${c.sindicato}</small>
      </div>`).join('');
  } catch(e) {}
}

function convOpenModal() {
  document.getElementById('convModalTitle').textContent = 'Registrar CCT';
  document.getElementById('convEditId').value = '';
  ['convCategoria','convSindEmp','convSindEmpregadores','convMunicipio','convInicio','convFim','convObs'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('convPiso').value = 0;
  document.getElementById('convReajuste').value = 0;
  document.getElementById('convJornada').value = 44;
  document.getElementById('convIntervalo').value = 60;
  document.getElementById('convNoturno').value = 20;
  document.getElementById('convHoraExtra').value = 50;
  document.getElementById('convVR').value = 0;
  document.getElementById('convVT').checked = true;
  document.getElementById('convUfInput').value = 'SP';
  document.getElementById('convModal').style.display = 'flex';
}

function convEdit(r) {
  document.getElementById('convModalTitle').textContent = 'Editar CCT';
  document.getElementById('convEditId').value = r.id;
  document.getElementById('convCategoria').value = r.categoria || '';
  document.getElementById('convSindEmp').value = r.sindicato_empregados || '';
  document.getElementById('convSindEmpregadores').value = r.sindicato_empregadores || '';
  document.getElementById('convUfInput').value = r.uf || 'SP';
  document.getElementById('convMunicipio').value = r.municipio || '';
  document.getElementById('convInicio').value = r.data_inicio || '';
  document.getElementById('convFim').value = r.data_fim || '';
  document.getElementById('convPiso').value = r.piso_salarial || 0;
  document.getElementById('convReajuste').value = r.reajuste_pct || 0;
  document.getElementById('convJornada').value = r.jornada_semanal || 44;
  document.getElementById('convIntervalo').value = r.intervalo_jornada_min || 60;
  document.getElementById('convNoturno').value = r.adicional_noturno_pct || 20;
  document.getElementById('convHoraExtra').value = r.adicional_hora_extra_pct || 50;
  document.getElementById('convVR').value = r.vale_refeicao_diario || 0;
  document.getElementById('convVT').checked = !!r.vale_transporte;
  document.getElementById('convObs').value = r.observacoes || '';
  document.getElementById('convModal').style.display = 'flex';
}

function convCloseModal() { document.getElementById('convModal').style.display = 'none'; }

async function convSave() {
  const id = document.getElementById('convEditId').value;
  const body = {
    categoria: document.getElementById('convCategoria').value,
    sindicato_empregados: document.getElementById('convSindEmp').value,
    sindicato_empregadores: document.getElementById('convSindEmpregadores').value,
    uf: document.getElementById('convUfInput').value,
    municipio: document.getElementById('convMunicipio').value,
    data_inicio: document.getElementById('convInicio').value,
    data_fim: document.getElementById('convFim').value,
    piso_salarial: parseFloat(document.getElementById('convPiso').value) || 0,
    reajuste_pct: parseFloat(document.getElementById('convReajuste').value) || 0,
    jornada_semanal: parseInt(document.getElementById('convJornada').value) || 44,
    intervalo_jornada_min: parseInt(document.getElementById('convIntervalo').value) || 60,
    adicional_noturno_pct: parseFloat(document.getElementById('convNoturno').value) || 20,
    adicional_hora_extra_pct: parseFloat(document.getElementById('convHoraExtra').value) || 50,
    vale_refeicao_diario: parseFloat(document.getElementById('convVR').value) || 0,
    vale_transporte: document.getElementById('convVT').checked ? 1 : 0,
    observacoes: document.getElementById('convObs').value,
    arquivo_url: '',
  };
  try {
    if (id) {
      await apiFetch(`/api/conventions/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    } else {
      await apiFetch('/api/conventions', { method: 'POST', body: JSON.stringify(body) });
    }
    convCloseModal();
    convLoad();
    convLoadSummary();
  } catch(e) { alert('Erro: ' + e.message); }
}

async function convDelete(id) {
  if (!confirm('Excluir esta convenção?')) return;
  await apiFetch(`/api/conventions/${id}`, { method: 'DELETE' });
  convLoad();
  convLoadSummary();
}

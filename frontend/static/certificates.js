// Certificados Digitais
async function renderCertificates() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="page-header">
      <h2>Certificados Digitais</h2>
      <div class="btn-group">
        <button class="btn btn-secondary" onclick="certCheckExpiry()">Verificar Vencimentos</button>
        <button class="btn btn-primary" onclick="certOpenUpload()">Importar Certificado A1</button>
      </div>
    </div>
    <div id="certAlerts" class="mb-3"></div>
    <div id="certList" class="mb-4">
      <div class="text-center p-4 text-muted">Carregando...</div>
    </div>
    <div class="card">
      <div class="card-header"><h5>Gerar CSR para Renovação</h5></div>
      <div class="card-body">
        <p class="text-muted">O CSR (Certificate Signing Request) é necessário para solicitar um novo certificado A1 junto à Autoridade Certificadora.</p>
        <button class="btn btn-secondary" onclick="certGenerateCSR()">Gerar CSR</button>
        <div id="certCSRResult" class="mt-3" style="display:none"></div>
      </div>
    </div>
    <div id="certUploadModal" class="modal-overlay" style="display:none">
      <div class="modal-box">
        <h3>Importar Certificado A1</h3>
        <div class="form-group">
          <label>Arquivo .pfx / .p12</label>
          <input type="file" id="certFile" class="form-control" accept=".pfx,.p12">
        </div>
        <div class="form-group">
          <label>Senha do Certificado</label>
          <input type="password" id="certSenha" class="form-control" placeholder="Senha do PFX">
        </div>
        <div class="d-flex gap-2 justify-content-end mt-3">
          <button class="btn btn-secondary" onclick="certCloseUpload()">Cancelar</button>
          <button class="btn btn-primary" onclick="certUpload()">Importar</button>
        </div>
      </div>
    </div>`;
  certLoadList();
}

async function certLoadList() {
  const container = document.getElementById('certList');
  try {
    const d = await apiFetch('/api/certificates');
    if (!d.certificates || !d.certificates.length) {
      container.innerHTML = `
        <div class="text-center p-5">
          <div style="font-size:3rem">🔐</div>
          <h5 class="mt-3">Nenhum certificado cadastrado</h5>
          <p class="text-muted">Importe seu certificado A1 (PFX) para habilitar a emissão de NF-e, NFS-e e obrigações eletrônicas.</p>
        </div>`;
      return;
    }
    container.innerHTML = d.certificates.map(c => {
      const statusColor = c.status === 'valido' ? 'success' : (c.status === 'vencendo' ? 'warning' : 'danger');
      const statusLabel = c.status === 'valido' ? 'Válido' : (c.status === 'vencendo' ? 'Vencendo' : 'Vencido');
      return `
        <div class="card mb-3">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start">
              <div>
                <h5 class="mb-1">🔐 ${c.nome}</h5>
                <p class="text-muted mb-1">Titular: ${c.titular || '—'}</p>
                <p class="text-muted mb-1">Validade: <strong>${c.validade || '—'}</strong>
                  ${c.dias_restantes !== undefined ? `(${c.dias_restantes >= 0 ? c.dias_restantes + ' dias restantes' : 'VENCIDO há ' + Math.abs(c.dias_restantes) + ' dias'})` : ''}
                </p>
                <p class="text-muted">Tipo: ${c.tipo || 'A1'}</p>
              </div>
              <div class="text-right">
                <span class="badge badge-${statusColor} mb-2">${statusLabel}</span>
                <br>
                <button class="btn btn-sm btn-danger mt-2" onclick="certDelete()">Remover</button>
              </div>
            </div>
          </div>
        </div>`;
    }).join('');
  } catch(e) { container.innerHTML = `<div class="text-danger p-3">Erro: ${e.message}</div>`; }
}

async function certCheckExpiry() {
  const alertsDiv = document.getElementById('certAlerts');
  try {
    const d = await apiFetch('/api/certificates/check-expiry', { method: 'POST' });
    if (!d.alerts.length) {
      alertsDiv.innerHTML = '<div class="alert alert-success">✓ Certificados dentro do prazo de validade.</div>';
    } else {
      alertsDiv.innerHTML = d.alerts.map(a => `
        <div class="alert alert-${a.urgencia==='critico'?'danger':a.urgencia==='alerta'?'warning':'info'}">
          <strong>${a.urgencia === 'critico' ? '⚠️ CRÍTICO' : '⚠️ Aviso'}:</strong>
          Certificado "${a.nome}" vence em <strong>${a.dias_restantes} dias</strong> (${a.validade}).
          ${a.urgencia === 'critico' ? 'Renove imediatamente!' : 'Providencie a renovação.'}
        </div>`).join('');
    }
  } catch(e) { alertsDiv.innerHTML = `<div class="alert alert-danger">Erro: ${e.message}</div>`; }
}

function certOpenUpload() { document.getElementById('certUploadModal').style.display = 'flex'; }
function certCloseUpload() { document.getElementById('certUploadModal').style.display = 'none'; }

async function certUpload() {
  const file = document.getElementById('certFile').files[0];
  if (!file) { alert('Selecione um arquivo PFX/P12.'); return; }
  const senha = document.getElementById('certSenha').value;
  const formData = new FormData();
  formData.append('file', file);
  formData.append('senha', senha);
  try {
    const token = localStorage.getItem('cortex_token');
    const resp = await fetch('/api/certificates/upload', {
      method: 'POST',
      headers: token ? { 'Authorization': 'Bearer ' + token } : {},
      body: formData,
    });
    const d = await resp.json();
    if (!resp.ok) throw new Error(d.detail || 'Erro no upload');
    if (d.erro) {
      alert(`Certificado salvo, mas houve aviso: ${d.erro}\nO arquivo foi armazenado, mas as informações podem estar incompletas.`);
    } else {
      alert(`Certificado importado!\nTitular: ${d.titular}\nValidade: ${d.validade}\nDias restantes: ${d.dias_restantes}`);
    }
    certCloseUpload();
    certLoadList();
  } catch(e) { alert('Erro: ' + e.message); }
}

async function certDelete() {
  if (!confirm('Remover o certificado digital da empresa? Esta ação não pode ser desfeita.')) return;
  try {
    await apiFetch('/api/certificates', { method: 'DELETE' });
    certLoadList();
  } catch(e) { alert('Erro: ' + e.message); }
}

async function certGenerateCSR() {
  const result = document.getElementById('certCSRResult');
  result.style.display = '';
  result.innerHTML = '<div class="text-muted">Gerando CSR...</div>';
  try {
    const d = await apiFetch('/api/certificates/generate-csr');
    if (!d.csr_pem) {
      result.innerHTML = `<div class="alert alert-warning">${d.message}</div>`;
      return;
    }
    result.innerHTML = `
      <div class="alert alert-info">${d.message}</div>
      <div class="form-group">
        <label>CSR (envie para a Autoridade Certificadora)</label>
        <textarea class="form-control font-monospace" rows="8" readonly>${d.csr_pem}</textarea>
      </div>
      <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText(document.querySelector('#certCSRResult textarea').value).then(()=>alert('CSR copiado!'))">Copiar CSR</button>
      <p class="text-muted mt-2 small">⚠️ A chave privada foi gerada apenas para visualização. Em produção, guarde-a em local seguro.</p>`;
  } catch(e) { result.innerHTML = `<div class="text-danger">Erro: ${e.message}</div>`; }
}

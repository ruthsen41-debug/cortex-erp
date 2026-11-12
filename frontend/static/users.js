// Usuários do Sistema — gestão de logins e perfis de acesso
const USER_ROLES = [
  ['admin',      'Administrador — acesso total'],
  ['dp',         'Depto. Pessoal — Folha, Funcionários, CCT'],
  ['fiscal',     'Fiscal — NF-e, SPED, DIRBI, Manifesto'],
  ['contabil',   'Contábil — Contabilidade, LALUR, Honorários'],
  ['comercial',  'Comercial — Vendas, CRM, Estoque, PDV'],
  ['financeiro', 'Financeiro — Contas, Conciliação'],
];

async function renderUsers(container) {
  container.innerHTML = `
    <div class="page-header">
      <div>
        <h2 style="font-family:var(--font-display);font-size:1.4rem;font-weight:700;color:var(--text);margin:0">
          Usuários do Sistema
        </h2>
        <p style="font-size:.8rem;color:var(--muted);margin:.25rem 0 0">
          Gerencie logins e restrinja o acesso por módulo (perfil).
        </p>
      </div>
      <button class="btn btn-primary" onclick="usersOpenModal()">+ Novo Usuário</button>
    </div>

    <div class="alert alert-info" style="display:flex;align-items:flex-start;gap:.75rem">
      <span style="font-size:1.1rem">ℹ️</span>
      <div>
        <strong>Como funciona:</strong> cada login pertence a um perfil que determina quais módulos são visíveis.
        O perfil <strong>Administrador</strong> acessa tudo. Os demais perfis veem apenas os módulos do seu departamento.
      </div>
    </div>

    <div id="usersTableWrap" class="table-responsive">
      <table class="table">
        <thead>
          <tr>
            <th>Nome</th>
            <th>E-mail</th>
            <th>Perfil</th>
            <th>Status</th>
            <th>Criado em</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody id="usersTableBody">
          <tr><td colspan="6" class="text-center text-muted">Carregando...</td></tr>
        </tbody>
      </table>
    </div>

    <div id="usersModal" class="modal-overlay" style="display:none">
      <div class="modal-box">
        <h3 id="usersModalTitle">Novo Usuário</h3>
        <input type="hidden" id="usersEditId">

        <div class="form-row">
          <div class="form-group">
            <label>Nome Completo</label>
            <input type="text" id="usersName" class="form-control" placeholder="João da Silva">
          </div>
          <div class="form-group">
            <label>E-mail de Acesso</label>
            <input type="email" id="usersEmail" class="form-control" placeholder="joao@empresa.com.br">
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>Perfil de Acesso</label>
            <select id="usersRole" class="form-control">
              ${USER_ROLES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label>Senha <span id="usersPassHint" style="color:var(--muted);font-weight:400">(obrigatória)</span></label>
            <input type="password" id="usersPassword" class="form-control" placeholder="Mínimo 6 caracteres" autocomplete="new-password">
          </div>
        </div>

        <div class="form-group">
          <label style="cursor:pointer">
            <input type="checkbox" id="usersActive" checked> Usuário ativo
          </label>
        </div>

        <div id="usersModalError" class="alert alert-danger" style="display:none"></div>

        <div class="d-flex gap-2 justify-content-end mt-3">
          <button class="btn btn-secondary" onclick="usersCloseModal()">Cancelar</button>
          <button class="btn btn-primary" onclick="usersSave()">Salvar</button>
        </div>
      </div>
    </div>`;

  usersLoadTable();
}

async function usersLoadTable() {
  const tbody = document.getElementById('usersTableBody');
  if (!tbody) return;
  try {
    const rows = await apiFetch('/api/auth/users-list');
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nenhum usuário cadastrado.</td></tr>';
      return;
    }
    const me = (() => { try { return JSON.parse(localStorage.getItem('cortex_user') || '{}'); } catch (e) { return {}; } })();
    const roleLabel = Object.fromEntries(USER_ROLES.map(([v]) => [v, v]));
    const roleColors = {
      admin: 'badge-info', dp: 'badge-warning', fiscal: 'badge-success',
      contabil: 'badge-secondary', comercial: 'badge-danger', financeiro: 'badge-warning',
    };
    tbody.innerHTML = rows.map(u => `
      <tr>
        <td>
          <strong>${u.name}</strong>
          ${u.id === me.id ? ' <span class="badge badge-info" style="font-size:.65rem">você</span>' : ''}
        </td>
        <td style="font-family:var(--font-mono);font-size:.8rem">${u.email}</td>
        <td><span class="badge ${roleColors[u.role] || 'badge-secondary'}">${(USER_ROLES.find(r => r[0] === u.role) || [u.role, u.role])[0]}</span></td>
        <td><span class="badge ${u.active ? 'badge-success' : 'badge-secondary'}">${u.active ? 'Ativo' : 'Inativo'}</span></td>
        <td style="font-size:.8rem;color:var(--muted)">${u.created_at ? u.created_at.slice(0, 10) : '—'}</td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="usersEdit(${JSON.stringify(u).replace(/"/g, '&quot;')})">Editar</button>
          ${u.id !== me.id ? `<button class="btn btn-sm btn-danger" onclick="usersDelete(${u.id}, '${u.name.replace(/'/g, "\\'")}')">Excluir</button>` : ''}
        </td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-danger">Erro: ${e.message}</td></tr>`;
  }
}

function usersOpenModal() {
  document.getElementById('usersModalTitle').textContent = 'Novo Usuário';
  document.getElementById('usersEditId').value = '';
  document.getElementById('usersName').value = '';
  document.getElementById('usersEmail').value = '';
  document.getElementById('usersEmail').disabled = false;
  document.getElementById('usersRole').value = 'operador';
  document.getElementById('usersPassword').value = '';
  document.getElementById('usersPassword').placeholder = 'Mínimo 6 caracteres';
  document.getElementById('usersActive').checked = true;
  document.getElementById('usersPassHint').textContent = '(obrigatória)';
  document.getElementById('usersModalError').style.display = 'none';
  document.getElementById('usersModal').style.display = 'flex';
}

function usersEdit(u) {
  document.getElementById('usersModalTitle').textContent = 'Editar Usuário';
  document.getElementById('usersEditId').value = u.id;
  document.getElementById('usersName').value = u.name || '';
  document.getElementById('usersEmail').value = u.email || '';
  document.getElementById('usersEmail').disabled = true;
  document.getElementById('usersRole').value = u.role || 'admin';
  document.getElementById('usersPassword').value = '';
  document.getElementById('usersPassword').placeholder = 'Deixe vazio para manter a atual';
  document.getElementById('usersActive').checked = !!u.active;
  document.getElementById('usersPassHint').textContent = '(deixe vazio para não alterar)';
  document.getElementById('usersModalError').style.display = 'none';
  document.getElementById('usersModal').style.display = 'flex';
}

function usersCloseModal() {
  document.getElementById('usersModal').style.display = 'none';
}

async function usersSave() {
  const errBox = document.getElementById('usersModalError');
  errBox.style.display = 'none';
  const id = document.getElementById('usersEditId').value;
  const name = document.getElementById('usersName').value.trim();
  const email = document.getElementById('usersEmail').value.trim();
  const role = document.getElementById('usersRole').value;
  const password = document.getElementById('usersPassword').value;
  const active = document.getElementById('usersActive').checked ? 1 : 0;

  if (!name) { errBox.textContent = 'Nome é obrigatório.'; errBox.style.display = ''; return; }
  if (!id && !email) { errBox.textContent = 'E-mail é obrigatório.'; errBox.style.display = ''; return; }
  if (!id && password.length < 6) { errBox.textContent = 'Senha deve ter no mínimo 6 caracteres.'; errBox.style.display = ''; return; }
  if (id && password && password.length < 6) { errBox.textContent = 'Senha deve ter no mínimo 6 caracteres.'; errBox.style.display = ''; return; }

  try {
    if (id) {
      const body = { name, role, active };
      if (password) body.password = password;
      await apiFetch(`/api/auth/users/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    } else {
      await apiFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ name, email, password, role }),
      });
    }
    usersCloseModal();
    usersLoadTable();
    showToast(id ? 'Usuário atualizado.' : 'Usuário criado com sucesso.', 'success');
  } catch (e) {
    errBox.textContent = 'Erro: ' + e.message;
    errBox.style.display = '';
  }
}

async function usersDelete(id, name) {
  if (!confirm(`Excluir o usuário "${name}"? Esta ação não pode ser desfeita.`)) return;
  try {
    await apiFetch(`/api/auth/users/${id}`, { method: 'DELETE' });
    usersLoadTable();
    showToast('Usuário excluído.', 'success');
  } catch (e) {
    showToast('Erro: ' + e.message, 'error');
  }
}

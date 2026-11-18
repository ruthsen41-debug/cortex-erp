; Instalador único do Cortex ERP — pergunta o tipo de instalação, como no Domínio:
;
;   Servidor (multiusuário)  guarda os dados; os outros computadores do escritório acessam
;   Monousuário              tudo neste computador; nada fica aberto na rede
;   Estação                  só o programa; usa os dados de um servidor da rede
;
; Compile com installer\build_instalador.ps1 (monta build\CortexServidor e build\Cortex antes).
;
; Instalação sem perguntas (TI / implantação em lote):
;   CortexERP-Setup.exe /VERYSILENT /TIPO=servidor /SENHA=minhasenha [/PORTA=47800]
;   CortexERP-Setup.exe /VERYSILENT /TIPO=mono /SENHA=minhasenha
;   CortexERP-Setup.exe /VERYSILENT /TIPO=estacao [/SERVIDOR=NOME-DO-SERVIDOR]

#define AppName "Cortex ERP"
#define AppVersion "4.5.0"
#define ServiceExe "CortexServico.exe"
#define RegChave "Software\CortexERP"

[Setup]
AppId={{6E0B7C2A-5F3D-4C1B-9A7E-C0A7E4E2B1D5}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Cortex ERP
DefaultDirName=C:\CortexERP
DefaultGroupName=Cortex ERP
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=Output
OutputBaseFilename=CortexERP-Setup
SetupIconFile=cliente\cortex.ico
UninstallDisplayIcon={app}\cliente\Cortex.exe
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "Criar atalho do Cortex ERP na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "build\CortexServidor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: TemServidor
Source: "build\Cortex\*"; DestDir: "{app}\cliente"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "cache\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: PrecisaWebView2

[Dirs]
Name: "{app}\app\data"; Flags: uninsneveruninstall; Check: TemServidor
Name: "{app}\Backups"; Flags: uninsneveruninstall; Check: TemServidor
Name: "{app}\logs"; Check: TemServidor

[InstallDelete]
; atalhos de navegador da primeira versão do instalador
Type: files; Name: "{commondesktop}\Cortex ERP.url"
Type: files; Name: "{group}\Abrir o Cortex ERP.url"
Type: files; Name: "{group}\Endereço para as estações.lnk"
Type: files; Name: "{group}\Fazer backup agora.lnk"
Type: files; Name: "{group}\Pasta de backups.lnk"
Type: files; Name: "{group}\Logs do servidor.lnk"

[Icons]
Name: "{commondesktop}\Cortex ERP"; Filename: "{app}\cliente\Cortex.exe"; Tasks: atalho
Name: "{group}\Cortex ERP"; Filename: "{app}\cliente\Cortex.exe"
Name: "{group}\Endereço para as estações"; Filename: "{app}\ENDERECO_DAS_ESTACOES.txt"; Check: EhServidor
Name: "{group}\Fazer backup agora"; Filename: "{app}\backup_agora.cmd"; WorkingDir: "{app}"; Check: TemServidor
Name: "{group}\Pasta de backups"; Filename: "{app}\Backups"; Check: TemServidor
Name: "{group}\Logs do servidor"; Filename: "{app}\logs"; Check: TemServidor
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Instalando o componente de exibição da Microsoft (WebView2)..."; Flags: waituntilterminated; Check: PrecisaWebView2
Filename: "{app}\ENDERECO_DAS_ESTACOES.txt"; Description: "Ver o endereço para os outros computadores"; Flags: postinstall shellexec skipifsilent unchecked; Check: EhServidor
Filename: "{app}\cliente\Cortex.exe"; Description: "Abrir o Cortex ERP agora"; Flags: postinstall skipifsilent nowait

[UninstallRun]
Filename: "{app}\{#ServiceExe}"; Parameters: "stop"; Flags: runhidden; RunOnceId: "StopSvc"; Check: TemServidor
Filename: "{app}\{#ServiceExe}"; Parameters: "uninstall"; Flags: runhidden; RunOnceId: "DelSvc"; Check: TemServidor
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Cortex ERP"""; Flags: runhidden; RunOnceId: "DelFw"; Check: TemServidor
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Cortex ERP - Busca na rede"""; Flags: runhidden; RunOnceId: "DelFwUdp"; Check: TemServidor
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /F /TN ""CortexERP_Backup"""; Flags: runhidden; RunOnceId: "DelTask"; Check: TemServidor

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\cliente"
Type: filesandordirs; Name: "{app}\app\backend"
Type: filesandordirs; Name: "{app}\app\frontend"
Type: filesandordirs; Name: "{app}\app\scripts"
Type: filesandordirs; Name: "{app}\app\alembic"
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\ENDERECO_DAS_ESTACOES.txt"

[Registry]
Root: HKLM; Subkey: "{#RegChave}"; ValueType: string; ValueName: "Tipo"; ValueData: "{code:GetTipo}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "{#RegChave}"; ValueType: string; ValueName: "Pasta"; ValueData: "{app}"

[Code]
const
  TIPO_SERVIDOR = 'servidor';
  TIPO_MONO = 'mono';
  TIPO_ESTACAO = 'estacao';

var
  PaginaTipo: TWizardPage;
  RbServidor, RbMono, RbEstacao: TNewRadioButton;
  PaginaConfig: TInputQueryWizardPage;
  PaginaServidor: TInputQueryWizardPage;
  TipoAnterior: String;

{ ── tipo escolhido ─────────────────────────────────────────────────────────── }
function GetTipo(Param: String): String;
begin
  if RbEstacao.Checked then Result := TIPO_ESTACAO
  else if RbMono.Checked then Result := TIPO_MONO
  else Result := TIPO_SERVIDOR;
end;

function EhServidor(): Boolean;
begin
  Result := GetTipo('') = TIPO_SERVIDOR;
end;

function EhMono(): Boolean;
begin
  Result := GetTipo('') = TIPO_MONO;
end;

function EhEstacao(): Boolean;
begin
  Result := GetTipo('') = TIPO_ESTACAO;
end;

{ Servidor e monousuário instalam o sistema completo (banco + serviço). }
function TemServidor(): Boolean;
begin
  Result := not EhEstacao();
end;

function NomeDoTipo(T: String): String;
begin
  if T = TIPO_ESTACAO then Result := 'Estação'
  else if T = TIPO_MONO then Result := 'Monousuário'
  else Result := 'Servidor (multiusuário)';
end;

function InstalacaoNova(): Boolean;
begin
  Result := not FileExists(ExpandConstant('{app}\app\.env'));
end;

function PrecisaWebView2(): Boolean;
var
  Versao: String;
begin
  Result := not (
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Versao) and (Versao <> '') and (Versao <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Versao) and (Versao <> '') and (Versao <> '0.0.0.0')));
end;

function GetPorta(Param: String): String;
begin
  Result := Trim(PaginaConfig.Values[0]);
end;

function SenhaAdmin(): String;
begin
  Result := PaginaConfig.Values[1];
end;

function PortaAnterior(): String;
var
  Linhas: TArrayOfString;
  I: Integer;
begin
  Result := '47800';
  if LoadStringsFromFile(ExpandConstant('{app}\app\.env'), Linhas) then
    for I := 0 to GetArrayLength(Linhas) - 1 do
      if Pos('CORTEX_PORT=', Linhas[I]) = 1 then
        Result := Trim(Copy(Linhas[I], 13, 10));
end;

function ExecOculto(const Arquivo, Params: String): Integer;
begin
  if not Exec(Arquivo, Params, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Result) then
    Result := -1;
end;

{ ── tela "Tipo de instalação" ──────────────────────────────────────────────── }
function CriarOpcao(var Topo: Integer; const Titulo, Descricao: String): TNewRadioButton;
var
  Texto: TNewStaticText;
begin
  Result := TNewRadioButton.Create(PaginaTipo);
  Result.Parent := PaginaTipo.Surface;
  Result.Caption := Titulo;
  Result.Font.Style := [fsBold];
  Result.Left := 0;
  Result.Top := Topo;
  Result.Width := PaginaTipo.SurfaceWidth;
  Result.Height := ScaleY(18);

  Texto := TNewStaticText.Create(PaginaTipo);
  Texto.Parent := PaginaTipo.Surface;
  { largura antes de WordWrap/Caption: senão o AutoSize mede uma linha só e corta o texto }
  Texto.Left := ScaleX(18);
  Texto.Top := Topo + ScaleY(20);
  Texto.Width := PaginaTipo.SurfaceWidth - ScaleX(18);
  Texto.AutoSize := True;
  Texto.WordWrap := True;
  Texto.Caption := Descricao;
  Topo := Texto.Top + Texto.Height + ScaleY(14);
end;

procedure CriarPaginaTipo();
var
  Topo: Integer;
begin
  PaginaTipo := CreateCustomPage(wpWelcome, 'Tipo de instalação',
    'Como o Cortex ERP vai ser usado neste computador?');
  Topo := 0;
  RbServidor := CriarOpcao(Topo, 'Servidor (multiusuário)',
    'Este computador guarda o banco de dados e os outros computadores do escritório acessam ' +
    'por ele. Escolha no computador que fica sempre ligado. Depois instale "Estação" nos demais.');
  RbMono := CriarOpcao(Topo, 'Monousuário',
    'Tudo fica neste computador e só ele usa o sistema. Nada é aberto na rede. ' +
    'Ideal para quem trabalha sozinho. Dá para mudar para Servidor depois sem perder os dados.');
  RbEstacao := CriarOpcao(Topo, 'Estação',
    'Instala só o programa. Os dados ficam no computador servidor do escritório, ' +
    'que precisa estar instalado e ligado. O servidor é encontrado na rede automaticamente.');
end;

procedure MarcarTipo(T: String);
begin
  RbServidor.Checked := (T <> TIPO_MONO) and (T <> TIPO_ESTACAO);
  RbMono.Checked := T = TIPO_MONO;
  RbEstacao.Checked := T = TIPO_ESTACAO;
end;

{ ── montagem do assistente ─────────────────────────────────────────────────── }
procedure InitializeWizard();
var
  T: String;
begin
  CriarPaginaTipo();

  PaginaConfig := CreateInputQueryPage(wpSelectDir,
    'Configuração do sistema',
    'Porta de acesso e senha do administrador',
    'A senha é do usuário admin@cortex.com.br (só é pedida na primeira instalação). ' +
    'Deixe a porta 47800 se não souber.');
  PaginaConfig.Add('Porta:', False);
  PaginaConfig.Add('Senha do administrador (mínimo 8 caracteres):', True);
  PaginaConfig.Add('Confirme a senha:', True);

  PaginaServidor := CreateInputQueryPage(PaginaConfig.ID,
    'Servidor do Cortex',
    'Em qual computador o Cortex ERP está instalado como servidor?',
    'Normalmente não é preciso preencher: o programa procura o servidor na rede sozinho. ' +
    'Preencha só se o servidor estiver em outra rede ou não for encontrado ' +
    '(o nome está em "Endereço para as estações", no menu Iniciar do servidor).');
  PaginaServidor.Add('Nome ou IP do servidor (opcional):', False);

  { Tipo: parâmetro /TIPO= > instalação anterior > Servidor }
  RegQueryStringValue(HKLM, '{#RegChave}', 'Tipo', TipoAnterior);
  T := Lowercase(ExpandConstant('{param:TIPO|}'));
  if T = '' then T := TipoAnterior;
  MarcarTipo(T);

  PaginaConfig.Values[0] := ExpandConstant('{param:PORTA|47800}');
  PaginaConfig.Values[1] := ExpandConstant('{param:SENHA|}');
  PaginaConfig.Values[2] := PaginaConfig.Values[1];
  PaginaServidor.Values[0] := ExpandConstant('{param:SERVIDOR|}');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = PaginaConfig.ID then Result := EhEstacao()
  else if PageID = PaginaServidor.ID then Result := not EhEstacao();
end;

procedure CurPageChanged(CurPageID: Integer);
var
  Nova: Boolean;
begin
  if CurPageID = PaginaConfig.ID then
  begin
    Nova := InstalacaoNova();
    if not Nova then PaginaConfig.Values[0] := PortaAnterior();
    PaginaConfig.Edits[1].Enabled := Nova;
    PaginaConfig.Edits[2].Enabled := Nova;
    PaginaConfig.PromptLabels[1].Enabled := Nova;
    PaginaConfig.PromptLabels[2].Enabled := Nova;
    if not Nova then
      PaginaConfig.SubCaptionLabel.Caption :=
        'Já existe uma instalação nesta pasta: os dados e a senha atual serão mantidos. ' +
        'Você pode mudar só a porta.'
    else if EhMono() then
      PaginaConfig.SubCaptionLabel.Caption :=
        'A senha é do usuário admin@cortex.com.br. A porta só é usada dentro deste computador; ' +
        'deixe 47800 se não souber.'
    else
      PaginaConfig.SubCaptionLabel.Caption :=
        'A senha é do usuário admin@cortex.com.br. As estações descobrem a porta sozinhas; ' +
        'deixe 47800 se não souber.';
  end
  else if (CurPageID = PaginaServidor.ID) and (PaginaServidor.Values[0] = '') then
    PaginaServidor.Values[0] := GetIniString('servidor', 'endereco', '', ExpandConstant('{app}\cliente\cortex.ini'))
  else if CurPageID = wpFinished then
  begin
    if EhEstacao() then
      WizardForm.FinishedLabel.Caption :=
        'O Cortex ERP foi instalado como estação.' + #13#10#13#10 +
        'Abra pelo atalho "Cortex ERP". Na primeira vez o programa procura o servidor do ' +
        'escritório na rede; se não encontrar, ele pergunta o nome do servidor.'
    else if EhMono() then
      WizardForm.FinishedLabel.Caption :=
        'O Cortex ERP foi instalado como monousuário e já está funcionando.' + #13#10#13#10 +
        'Só este computador acessa o sistema. Os dados ficam em ' + ExpandConstant('{app}') +
        '\app\data e o backup é feito todo dia em ' + ExpandConstant('{app}') + '\Backups.'
    else
      WizardForm.FinishedLabel.Caption :=
        'O servidor do Cortex ERP foi instalado e já está funcionando.' + #13#10#13#10 +
        'Ele inicia sozinho sempre que este computador for ligado. Nos outros computadores ' +
        'do escritório, rode este mesmo instalador e escolha "Estação". Os dados ficam em ' +
        ExpandConstant('{app}') + '\app\data e o backup diário em ' + ExpandConstant('{app}') + '\Backups.';
  end;
end;

function ValidarConfig(Silencioso: Boolean; var Erro: String): Boolean;
var
  P: Integer;
begin
  Erro := '';
  P := StrToIntDef(GetPorta(''), 0);
  if (P < 1024) or (P > 65535) then
    Erro := 'Informe uma porta entre 1024 e 65535 (padrão: 47800).'
  else if InstalacaoNova() then
  begin
    if Length(SenhaAdmin()) < 8 then
      Erro := 'A senha do administrador precisa ter pelo menos 8 caracteres.'
    else if (not Silencioso) and (PaginaConfig.Values[1] <> PaginaConfig.Values[2]) then
      Erro := 'As senhas não conferem.';
  end;
  Result := Erro = '';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Erro: String;
begin
  Result := True;
  if (CurPageID = PaginaTipo.ID) and EhEstacao() and (TipoAnterior <> '') and (TipoAnterior <> TIPO_ESTACAO) then
    Result := MsgBox('Este computador hoje é ' + NomeDoTipo(TipoAnterior) + '.' + #13#10#13#10 +
      'Ao instalar como Estação, o sistema deixa de rodar aqui e passa a usar os dados de outro ' +
      'computador. O banco e os backups atuais NÃO são apagados (ficam na pasta de instalação).' + #13#10#13#10 +
      'Deseja continuar?', mbConfirmation, MB_YESNO) = IDYES
  else if CurPageID = PaginaConfig.ID then
  begin
    Result := ValidarConfig(False, Erro);
    if not Result then MsgBox(Erro, mbError, MB_OK);
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  S: String;
begin
  S := 'Tipo de instalação:' + NewLine + Space + NomeDoTipo(GetTipo('')) + NewLine + NewLine;
  S := S + MemoDirInfo + NewLine + NewLine;
  if TemServidor() then
  begin
    S := S + 'Sistema:' + NewLine +
      Space + 'Porta ' + GetPorta('') + NewLine +
      Space + 'Serviço do Windows "Cortex ERP - Servidor" (inicia com o computador)' + NewLine +
      Space + 'Backup automático todo dia às 12:30' + NewLine;
    if EhServidor() then
      S := S + Space + 'Acesso liberado para os computadores da rede local' + NewLine
    else
      S := S + Space + 'Acesso só por este computador (nada aberto na rede)' + NewLine;
  end
  else if Trim(PaginaServidor.Values[0]) <> '' then
    S := S + 'Servidor:' + NewLine + Space + Trim(PaginaServidor.Values[0]) + NewLine
  else
    S := S + 'Servidor:' + NewLine + Space + 'procurar automaticamente na rede' + NewLine;
  if MemoTasksInfo <> '' then S := S + NewLine + MemoTasksInfo;
  Result := S;
end;

{ ── instalação ─────────────────────────────────────────────────────────────── }
procedure RemoverRegrasFirewall();
begin
  ExecOculto(ExpandConstant('{sys}\netsh.exe'), 'advfirewall firewall delete rule name="Cortex ERP"');
  ExecOculto(ExpandConstant('{sys}\netsh.exe'), 'advfirewall firewall delete rule name="Cortex ERP - Busca na rede"');
end;

{ Virou estação: desliga o servidor local, mantendo banco e backups. }
procedure DesmontarServidorLocal();
var
  App: String;
begin
  App := ExpandConstant('{app}');
  ExecOculto(App + '\{#ServiceExe}', 'stop');
  ExecOculto(App + '\{#ServiceExe}', 'uninstall');
  RemoverRegrasFirewall();
  ExecOculto(ExpandConstant('{sys}\schtasks.exe'), '/Delete /F /TN "CortexERP_Backup"');
  DelTree(App + '\python', True, True, True);
  DelTree(App + '\app\backend', True, True, True);
  DelTree(App + '\app\frontend', True, True, True);
  DelTree(App + '\app\scripts', True, True, True);
  DelTree(App + '\app\alembic', True, True, True);
  DeleteFile(App + '\{#ServiceExe}');
  DeleteFile(App + '\ENDERECO_DAS_ESTACOES.txt');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Erro: String;
begin
  Result := '';
  if TemServidor() and not ValidarConfig(True, Erro) then
  begin
    Result := Erro;  { instalação silenciosa sem /SENHA ou com porta inválida }
    Exit;
  end;
  if FileExists(ExpandConstant('{app}\{#ServiceExe}')) then
  begin
    if EhEstacao() then
      DesmontarServidorLocal()
    else
      ExecOculto(ExpandConstant('{app}\{#ServiceExe}'), 'stop');  { atualização }
  end;
end;

procedure ConfigurarSistema();
var
  App, Porta, ArqSenha, Params, Modo: String;
  Linhas: TArrayOfString;
  Codigo: Integer;
  Nova: Boolean;
begin
  App := ExpandConstant('{app}');
  Porta := GetPorta('');
  Nova := InstalacaoNova();
  if EhMono() then Modo := TIPO_MONO else Modo := TIPO_SERVIDOR;

  WizardForm.StatusLabel.Caption := 'Configurando o banco de dados...';
  Params := '"' + App + '\configurar.py" --porta ' + Porta + ' --modo ' + Modo;
  ArqSenha := '';
  if Nova then
  begin
    ArqSenha := ExpandConstant('{tmp}\senha_admin.txt');
    SetArrayLength(Linhas, 1);
    Linhas[0] := SenhaAdmin();
    SaveStringsToUTF8File(ArqSenha, Linhas, False);
    Params := Params + ' --arquivo-senha "' + ArqSenha + '"';
  end;
  Codigo := ExecOculto(App + '\python\python.exe', Params);
  if (ArqSenha <> '') and FileExists(ArqSenha) then DeleteFile(ArqSenha);
  if Codigo <> 0 then
    SuppressibleMsgBox('A configuração do banco retornou erro (código ' + IntToStr(Codigo) + '). ' +
      'Veja a pasta de logs ou execute "' + App + '\configurar.py" manualmente.', mbError, MB_OK, IDOK);

  WizardForm.StatusLabel.Caption := 'Registrando o serviço do Windows...';
  ExecOculto(App + '\{#ServiceExe}', 'install');  { já instalado: retorna erro e segue }
  ExecOculto(App + '\{#ServiceExe}', 'refresh');
  if ExecOculto(App + '\{#ServiceExe}', 'start') <> 0 then
    SuppressibleMsgBox('O serviço "Cortex ERP - Servidor" não iniciou. Veja os arquivos em ' + App + '\logs.',
      mbError, MB_OK, IDOK);

  RemoverRegrasFirewall();
  if EhServidor() then
  begin
    WizardForm.StatusLabel.Caption := 'Liberando o acesso da rede local no firewall...';
    ExecOculto(ExpandConstant('{sys}\netsh.exe'),
      'advfirewall firewall add rule name="Cortex ERP" dir=in action=allow protocol=TCP localport=' + Porta +
      ' profile=any remoteip=localsubnet description="Acesso das estacoes ao Cortex ERP"');
    ExecOculto(ExpandConstant('{sys}\netsh.exe'),
      'advfirewall firewall add rule name="Cortex ERP - Busca na rede" dir=in action=allow protocol=UDP localport=47801' +
      ' profile=any remoteip=localsubnet description="Estacoes encontram o servidor do Cortex ERP sozinhas"');
  end;

  WizardForm.StatusLabel.Caption := 'Agendando o backup diário...';
  ExecOculto(ExpandConstant('{sys}\schtasks.exe'),
    '/Create /F /TN "CortexERP_Backup" /SC DAILY /ST 12:30 /RU SYSTEM /RL HIGHEST /TR "\"' +
    App + '\backup_agora.cmd\" /silencioso"');

  SetIniString('servidor', 'endereco', 'localhost:' + Porta, App + '\cliente\cortex.ini');
end;

procedure ConfigurarEstacao();
var
  Servidor, Ini: String;
begin
  Ini := ExpandConstant('{app}\cliente\cortex.ini');
  Servidor := Trim(PaginaServidor.Values[0]);
  if Pos('http://', Lowercase(Servidor)) = 1 then
    Servidor := Copy(Servidor, 8, Length(Servidor));
  if (Length(Servidor) > 0) and (Servidor[Length(Servidor)] = '/') then
    Servidor := Copy(Servidor, 1, Length(Servidor) - 1);
  if Servidor <> '' then
    SetIniString('servidor', 'endereco', Servidor, Ini)
  else if FileExists(Ini) then
    DeleteFile(Ini);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then Exit;
  if TemServidor() then ConfigurarSistema() else ConfigurarEstacao();
end;

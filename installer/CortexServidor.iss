; Instalador do Cortex ERP — Servidor do escritório
; Compile com installer\build_servidor.ps1 (monta a pasta build\CortexServidor antes).

#define AppName "Cortex ERP - Servidor"
#define AppVersion "4.5.0"
#define ServiceExe "CortexServico.exe"

[Setup]
AppId={{6E0B7C2A-5F3D-4C1B-9A7E-C0A7E4E2B1D5}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Cortex ERP
DefaultDirName=C:\CortexERP
DefaultGroupName=Cortex ERP
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=Output
OutputBaseFilename=CortexERP-Servidor-Setup
SetupIconFile=cliente\cortex.ico
UninstallDisplayIcon={app}\cliente\Cortex.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
CloseApplications=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "build\CortexServidor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "build\Cortex\*"; DestDir: "{app}\cliente"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "cache\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: PrecisaWebView2

[Dirs]
Name: "{app}\app\data"; Flags: uninsneveruninstall
Name: "{app}\Backups"; Flags: uninsneveruninstall
Name: "{app}\logs"

[INI]
Filename: "{app}\cliente\cortex.ini"; Section: "servidor"; Key: "endereco"; String: "localhost:{code:GetPorta}"

[InstallDelete]
; atalhos de navegador da versão anterior do instalador
Type: files; Name: "{commondesktop}\Cortex ERP.url"
Type: files; Name: "{group}\Abrir o Cortex ERP.url"

[Icons]
Name: "{commondesktop}\Cortex ERP"; Filename: "{app}\cliente\Cortex.exe"
Name: "{group}\Cortex ERP"; Filename: "{app}\cliente\Cortex.exe"
Name: "{group}\Endereço para as estações"; Filename: "{app}\ENDERECO_DAS_ESTACOES.txt"
Name: "{group}\Fazer backup agora"; Filename: "{app}\backup_agora.cmd"; WorkingDir: "{app}"
Name: "{group}\Pasta de backups"; Filename: "{app}\Backups"
Name: "{group}\Logs do servidor"; Filename: "{app}\logs"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Instalando o componente de exibição da Microsoft (WebView2)..."; Flags: waituntilterminated; Check: PrecisaWebView2
Filename: "{app}\ENDERECO_DAS_ESTACOES.txt"; Description: "Ver o endereço para os outros computadores"; Flags: postinstall shellexec skipifsilent
Filename: "{app}\cliente\Cortex.exe"; Description: "Abrir o Cortex ERP agora"; Flags: postinstall skipifsilent nowait

[UninstallRun]
Filename: "{app}\{#ServiceExe}"; Parameters: "stop"; Flags: runhidden; RunOnceId: "StopSvc"
Filename: "{app}\{#ServiceExe}"; Parameters: "uninstall"; Flags: runhidden; RunOnceId: "DelSvc"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Cortex ERP"""; Flags: runhidden; RunOnceId: "DelFw"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Cortex ERP - Busca na rede"""; Flags: runhidden; RunOnceId: "DelFwUdp"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /F /TN ""CortexERP_Backup"""; Flags: runhidden; RunOnceId: "DelTask"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\cliente"
Type: filesandordirs; Name: "{app}\app\backend"
Type: filesandordirs; Name: "{app}\app\frontend"
Type: filesandordirs; Name: "{app}\app\scripts"
Type: filesandordirs; Name: "{app}\app\alembic"
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\ENDERECO_DAS_ESTACOES.txt"

[Messages]
ptbr.FinishedLabel=O servidor do Cortex ERP foi instalado e já está rodando como serviço do Windows.%n%nEle inicia sozinho sempre que este computador for ligado. Os dados ficam em [name]\app\data e os backups diários em [name]\Backups.

[Code]
var
  PaginaConfig: TInputQueryWizardPage;
  InstalacaoNova: Boolean;

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

function PortaAnterior(): String;
var
  Linhas: TArrayOfString;
  I: Integer;
begin
  Result := '47800';
  if LoadStringsFromFile(ExpandConstant('{app}\app\.env'), Linhas) then
    for I := 0 to GetArrayLength(Linhas) - 1 do
      if Pos('CORTEX_PORT=', Linhas[I]) = 1 then
        Result := Copy(Linhas[I], 13, 10);
end;

procedure InitializeWizard();
begin
  PaginaConfig := CreateInputQueryPage(wpSelectDir,
    'Configuração do servidor',
    'Porta de acesso e senha do administrador',
    'A porta é usada pelos outros computadores do escritório para acessar o Cortex. ' +
    'Deixe 47800 se não souber (as estações descobrem a porta sozinhas). A senha é do usuário admin@cortex.com.br ' +
    '(só é pedida na primeira instalação).');
  PaginaConfig.Add('Porta:', False);
  PaginaConfig.Add('Senha do administrador (mínimo 8 caracteres):', True);
  PaginaConfig.Add('Confirme a senha:', True);
  PaginaConfig.Values[0] := '47800';
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = PaginaConfig.ID then
  begin
    InstalacaoNova := not FileExists(ExpandConstant('{app}\app\.env'));
    if not InstalacaoNova then
      PaginaConfig.Values[0] := PortaAnterior();
    PaginaConfig.Edits[1].Enabled := InstalacaoNova;
    PaginaConfig.Edits[2].Enabled := InstalacaoNova;
    PaginaConfig.PromptLabels[1].Enabled := InstalacaoNova;
    PaginaConfig.PromptLabels[2].Enabled := InstalacaoNova;
    if not InstalacaoNova then
      PaginaConfig.SubCaptionLabel.Caption :=
        'Já existe uma instalação nesta pasta: os dados e a senha atual serão mantidos. ' +
        'Você pode mudar só a porta.';
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  P: Integer;
begin
  Result := True;
  if CurPageID = PaginaConfig.ID then
  begin
    P := StrToIntDef(GetPorta(''), 0);
    if (P < 1024) or (P > 65535) then
    begin
      MsgBox('Informe uma porta entre 1024 e 65535 (padrão: 47800).', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if InstalacaoNova then
    begin
      if Length(PaginaConfig.Values[1]) < 8 then
      begin
        MsgBox('A senha do administrador precisa ter pelo menos 8 caracteres.', mbError, MB_OK);
        Result := False;
      end
      else if PaginaConfig.Values[1] <> PaginaConfig.Values[2] then
      begin
        MsgBox('As senhas não conferem.', mbError, MB_OK);
        Result := False;
      end;
    end;
  end;
end;

function ExecOculto(const Arquivo, Params: String): Integer;
begin
  if not Exec(Arquivo, Params, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Result) then
    Result := -1;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  // Atualização: para o serviço antes de substituir os arquivos
  if FileExists(ExpandConstant('{app}\{#ServiceExe}')) then
    ExecOculto(ExpandConstant('{app}\{#ServiceExe}'), 'stop');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  App, Porta, ArqSenha, Params: String;
  Linhas: TArrayOfString;
  Codigo: Integer;
begin
  if CurStep <> ssPostInstall then Exit;
  App := ExpandConstant('{app}');
  Porta := GetPorta('');

  WizardForm.StatusLabel.Caption := 'Configurando o banco de dados...';
  Params := '"' + App + '\configurar.py" --porta ' + Porta;
  if InstalacaoNova then
  begin
    ArqSenha := ExpandConstant('{tmp}\senha_admin.txt');
    SetArrayLength(Linhas, 1);
    Linhas[0] := PaginaConfig.Values[1];
    SaveStringsToUTF8File(ArqSenha, Linhas, False);
    Params := Params + ' --arquivo-senha "' + ArqSenha + '"';
  end;
  Codigo := ExecOculto(App + '\python\python.exe', Params);
  if (ArqSenha <> '') and FileExists(ArqSenha) then DeleteFile(ArqSenha);
  if Codigo <> 0 then
    MsgBox('A configuração do banco retornou erro (código ' + IntToStr(Codigo) + '). ' +
           'Veja a pasta de logs ou execute "' + App + '\configurar.py" manualmente.', mbError, MB_OK);

  WizardForm.StatusLabel.Caption := 'Registrando o serviço do Windows...';
  ExecOculto(App + '\{#ServiceExe}', 'install');   // já instalado: retorna erro e segue
  ExecOculto(App + '\{#ServiceExe}', 'refresh');
  if ExecOculto(App + '\{#ServiceExe}', 'start') <> 0 then
    MsgBox('O serviço "Cortex ERP - Servidor" não iniciou. Veja os arquivos em ' + App + '\logs.', mbError, MB_OK);

  WizardForm.StatusLabel.Caption := 'Liberando a porta ' + Porta + ' no firewall...';
  ExecOculto(ExpandConstant('{sys}\netsh.exe'), 'advfirewall firewall delete rule name="Cortex ERP"');
  ExecOculto(ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall add rule name="Cortex ERP" dir=in action=allow protocol=TCP localport=' + Porta +
    ' profile=any remoteip=localsubnet description="Acesso das estacoes ao Cortex ERP"');
  ExecOculto(ExpandConstant('{sys}\netsh.exe'), 'advfirewall firewall delete rule name="Cortex ERP - Busca na rede"');
  ExecOculto(ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall add rule name="Cortex ERP - Busca na rede" dir=in action=allow protocol=UDP localport=47801' +
    ' profile=any remoteip=localsubnet description="Estacoes encontram o servidor do Cortex ERP sozinhas"');

  WizardForm.StatusLabel.Caption := 'Agendando o backup diário...';
  ExecOculto(ExpandConstant('{sys}\schtasks.exe'),
    '/Create /F /TN "CortexERP_Backup" /SC DAILY /ST 12:30 /RU SYSTEM /RL HIGHEST /TR "\"' +
    App + '\backup_agora.cmd\" /silencioso"');
end;

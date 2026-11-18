; Instalador do Cortex ERP — Estações do escritório
; Compile com installer\build_cliente.ps1 (monta build\Cortex antes).
;
; Instala só o programa Cortex.exe (janela própria). Ao abrir, ele procura o
; servidor na rede sozinho; o nome do servidor pode ser informado aqui ou depois.

#define AppName "Cortex ERP"
#define AppVersion "4.5.0"

[Setup]
AppId={{9C4A1E37-2B8D-4F60-A5C3-7D1E0B9F4A62}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Cortex ERP
DefaultDirName={autopf}\Cortex ERP
DefaultGroupName=Cortex ERP
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=Output
OutputBaseFilename=CortexERP-Estacao-Setup
SetupIconFile=cliente\cortex.ico
UninstallDisplayIcon={app}\Cortex.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
CloseApplications=yes

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "build\Cortex\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "cache\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: PrecisaWebView2

[Icons]
Name: "{commondesktop}\Cortex ERP"; Filename: "{app}\Cortex.exe"
Name: "{group}\Cortex ERP"; Filename: "{app}\Cortex.exe"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Instalando o componente de exibição da Microsoft (WebView2)..."; Flags: waituntilterminated; Check: PrecisaWebView2
Filename: "{app}\Cortex.exe"; Description: "Abrir o Cortex ERP agora"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\cortex.ini"

[Messages]
ptbr.FinishedLabel=O Cortex ERP foi instalado.%n%nUse o atalho "Cortex ERP" na área de trabalho. Na primeira vez o programa procura o servidor do escritório na rede; se não encontrar, ele pergunta o nome do servidor.

[Code]
var
  PaginaServidor: TInputQueryWizardPage;

function PrecisaWebView2(): Boolean;
var
  Versao: String;
begin
  // Runtime do WebView2 (por máquina ou por usuário). Windows 11 e Windows 10 atualizado já têm.
  Result := not (
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Versao) and (Versao <> '') and (Versao <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Versao) and (Versao <> '') and (Versao <> '0.0.0.0')));
end;

function ServidorAnterior(): String;
begin
  Result := GetIniString('servidor', 'endereco', '', ExpandConstant('{app}\cortex.ini'));
end;

procedure InitializeWizard();
begin
  PaginaServidor := CreateInputQueryPage(wpSelectDir,
    'Servidor do Cortex',
    'Em qual computador o Cortex ERP está instalado?',
    'Normalmente não é preciso preencher: o programa procura o servidor na rede sozinho. ' +
    'Preencha só se o servidor estiver em outra rede ou não for encontrado ' +
    '(o nome está no arquivo "Endereço para as estações", no menu Iniciar do servidor).');
  PaginaServidor.Add('Nome ou IP do servidor (opcional):', False);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = PaginaServidor.ID) and (PaginaServidor.Values[0] = '') then
    PaginaServidor.Values[0] := ServidorAnterior();
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Servidor, Ini: String;
begin
  if CurStep <> ssPostInstall then Exit;
  Ini := ExpandConstant('{app}\cortex.ini');
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

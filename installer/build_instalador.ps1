<#
  Monta o instalador único do Cortex ERP. Na instalação ele pergunta o tipo:
  Servidor (multiusuário), Monousuário ou Estação.

  Uso (na raiz do repositório ou em qualquer lugar):
      powershell -ExecutionPolicy Bypass -File installer\build_instalador.ps1

  Resultado:
      installer\build\CortexServidor\       sistema montado (Python embutido + app + serviço)
      installer\build\Cortex\               programa Cortex.exe
      installer\Output\CortexERP-Setup.exe  instalador (se o Inno Setup 6 estiver instalado)
#>
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$PyVersion   = "3.12.7"
$WinSWVersion = "v2.12.0"

$Here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo   = Split-Path -Parent $Here
$Cache  = Join-Path $Here "cache"
$Build  = Join-Path $Here "build\CortexServidor"
$PyDir  = Join-Path $Build "python"
$AppDir = Join-Path $Build "app"

function Get-Arquivo($Url, $Destino) {
    if (-not (Test-Path $Destino)) {
        Write-Host "Baixando $Url"
        Invoke-WebRequest -Uri $Url -OutFile $Destino -UseBasicParsing
    }
}

New-Item -ItemType Directory -Force $Cache | Out-Null
$PyZip = Join-Path $Cache "python-$PyVersion-embed-amd64.zip"
$GetPip = Join-Path $Cache "get-pip.py"
$WinSW = Join-Path $Cache "WinSW-x64-$WinSWVersion.exe"
Get-Arquivo "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-embed-amd64.zip" $PyZip
Get-Arquivo "https://bootstrap.pypa.io/get-pip.py" $GetPip
Get-Arquivo "https://github.com/winsw/winsw/releases/download/$WinSWVersion/WinSW-x64.exe" $WinSW

Write-Host "Limpando pasta de build"
if (Test-Path $Build) { Remove-Item -Recurse -Force $Build }
New-Item -ItemType Directory -Force $PyDir, $AppDir, (Join-Path $Build "logs") | Out-Null

Write-Host "Preparando Python embutido $PyVersion"
Expand-Archive -Path $PyZip -DestinationPath $PyDir -Force
# Habilita site-packages no Python embutido (necessário para o pip)
$Pth = Get-ChildItem $PyDir -Filter "python*._pth" | Select-Object -First 1
$PyZipName = (Get-ChildItem $PyDir -Filter "python3*.zip" | Select-Object -First 1).Name
Set-Content -Path $Pth.FullName -Encoding ascii -Value @($PyZipName, ".", "Lib\site-packages", "import site")

$Py = Join-Path $PyDir "python.exe"
& $Py $GetPip --no-warn-script-location --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "get-pip falhou" }
& $Py -m pip install --no-warn-script-location --disable-pip-version-check -r (Join-Path $Repo "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install falhou" }

Write-Host "Copiando código do Cortex"
foreach ($item in "backend", "frontend", "scripts", "alembic") {
    Copy-Item -Recurse (Join-Path $Repo $item) (Join-Path $AppDir $item)
}
Copy-Item (Join-Path $Repo "alembic.ini"), (Join-Path $Repo "requirements.txt") $AppDir
Get-ChildItem $AppDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem $Build -Recurse -Include *.pfx, *.p12, *.pem, *.key, *.db, .env, .jwt_secret -File |
    Where-Object { $_.FullName -notlike "$PyDir*" } | Remove-Item -Force

Write-Host "Copiando arquivos do servidor"
$Srv = Join-Path $Here "servidor"
Copy-Item (Join-Path $Srv "cortex_servidor.py"), (Join-Path $Srv "configurar.py"), (Join-Path $Srv "backup_agora.cmd") $Build
Copy-Item (Join-Path $Srv "CortexServico.xml") (Join-Path $Build "CortexServico.xml")
Copy-Item $WinSW (Join-Path $Build "CortexServico.exe")

Write-Host "Testando importação do app com o Python embutido"
Push-Location $AppDir
try {
    & $Py -c "import sys; sys.path.insert(0, '.'); import backend.main; print('app OK')"
    if ($LASTEXITCODE -ne 0) { throw "o app não importou com o Python embutido" }
} finally { Pop-Location }
# O teste de importação pode criar data\ e .jwt_secret — não podem ir no instalador
if (Test-Path (Join-Path $AppDir "data")) { Remove-Item -Recurse -Force (Join-Path $AppDir "data") }

Write-Host "Montando o programa Cortex.exe"
& (Join-Path $Here "build_cliente.ps1")

$Iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($Iscc) {
    Write-Host "Compilando instalador com Inno Setup"
    # os instaladores separados da versão anterior foram substituídos pelo único
    Remove-Item (Join-Path $Here "Output\CortexERP-Servidor-Setup.exe"), (Join-Path $Here "Output\CortexERP-Estacao-Setup.exe") -ErrorAction SilentlyContinue
    & $Iscc /Q (Join-Path $Here "CortexERP.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou" }
    Write-Host "Pronto: $(Join-Path $Here 'Output\CortexERP-Setup.exe')"
} else {
    Write-Warning "Inno Setup 6 não encontrado. Instale com: winget install JRSoftware.InnoSetup"
}

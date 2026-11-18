<#
  Monta o programa Cortex.exe (janela própria que acha o servidor na rede).

  Uso:
      powershell -ExecutionPolicy Bypass -File installer\build_cliente.ps1

  Resultado:
      installer\build\Cortex\Cortex.exe   programa (modo pasta, abre rápido)

  O build_instalador.ps1 chama este script antes de compilar o CortexERP-Setup.exe.
#>
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Cache  = Join-Path $Here "cache"
$Venv   = Join-Path $Cache "venv_cliente"
$Work   = Join-Path $Here "build\_pyinstaller"
$Dist   = Join-Path $Here "build"
$Cli    = Join-Path $Here "cliente"
$Py     = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path $Py)) {
    Write-Host "Criando ambiente de build do cliente"
    $PyBase = (Get-Command py -ErrorAction SilentlyContinue)
    if ($PyBase) { & py -3.12 -m venv $Venv } else { & python -m venv $Venv }
    if ($LASTEXITCODE -ne 0) { throw "não foi possível criar o venv (precisa de Python 3.12 instalado)" }
}
& $Py -m pip install --disable-pip-version-check -q "pywebview==6.2.1" "pyinstaller==6.22.3" "pillow"
if ($LASTEXITCODE -ne 0) { throw "pip install do cliente falhou" }

$WebView2 = Join-Path $Cache "MicrosoftEdgeWebview2Setup.exe"
if (-not (Test-Path $WebView2)) {
    Write-Host "Baixando o instalador do WebView2 (Microsoft)"
    Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile $WebView2 -UseBasicParsing
}

$Ico = Join-Path $Cli "cortex.ico"
& $Py (Join-Path $Cli "gerar_icone.py") $Ico
if ($LASTEXITCODE -ne 0) { throw "falha ao gerar o ícone" }

Write-Host "Compilando Cortex.exe com PyInstaller"
if (Test-Path (Join-Path $Dist "Cortex")) { Remove-Item -Recurse -Force (Join-Path $Dist "Cortex") }
& $Py -m PyInstaller --noconfirm --clean --onedir --windowed --name Cortex `
    --icon $Ico --add-data "$Ico;." `
    --distpath $Dist --workpath $Work --specpath $Work `
    --collect-submodules webview.platforms `
    --exclude-module webview.platforms.qt --exclude-module webview.platforms.gtk `
    --exclude-module webview.platforms.cocoa --exclude-module webview.platforms.android `
    (Join-Path $Cli "cortex_cliente.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }
Write-Host "Pronto: $(Join-Path $Dist 'Cortex\Cortex.exe')"


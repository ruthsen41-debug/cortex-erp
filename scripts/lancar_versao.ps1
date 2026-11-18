<#
  Lança uma versão nova do Cortex ERP com um comando só.

  Uso (na raiz do repositório):
      powershell -ExecutionPolicy Bypass -File scripts\lancar_versao.ps1 -Versao 4.6.0 -Notas "PLR; correções na folha"
      powershell -ExecutionPolicy Bypass -File scripts\lancar_versao.ps1 -Versao 4.6.0 -ArquivoNotas notas.md
      (sem -Versao: sobe o último número, ex.: 4.5.0 -> 4.5.1)

  O que faz:
    1. confere se não há alterações sem commit
    2. roda os testes (pule com -PularTestes)
    3. grava a versão em backend/version.py
    4. gera o instalador (installer\build_instalador.ps1)
    5. calcula o SHA-256 e gera installer\Output\cortex-update.json
    6. commit + tag vX.Y.Z + push   -> a nuvem (Render) atualiza sozinha
    7. cria a Release no GitHub com o instalador -> os servidores dos clientes
       veem "Nova versão disponível" em Painel do Sistema > Atualizações
#>
param(
    [string]$Versao = "",
    [string]$Notas = "",
    [string]$ArquivoNotas = "",
    [switch]$PularTestes,
    [switch]$SemPublicar
)
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Repo
# o GITHUB_TOKEN deste computador está inválido; git e gh usam o login salvo (keyring)
Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue

function Passo([string]$Texto) { Write-Host ""; Write-Host "==> $Texto" -ForegroundColor Cyan }
function Checar([string]$Oque) { if ($LASTEXITCODE -ne 0) { throw "$Oque falhou (código $LASTEXITCODE)" } }

$ArqVersao = Join-Path $Repo "backend\version.py"
$conteudo = [IO.File]::ReadAllText($ArqVersao)
$m = [regex]::Match($conteudo, '(?m)^APP_VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"')
if (-not $m.Success) { throw "APP_VERSION não encontrado em backend\version.py" }
$Atual = "$($m.Groups[1].Value).$($m.Groups[2].Value).$($m.Groups[3].Value)"
if (-not $Versao) { $Versao = "$($m.Groups[1].Value).$($m.Groups[2].Value).$([int]$m.Groups[3].Value + 1)" }
if ($Versao -notmatch '^\d+\.\d+\.\d+$') { throw "Versão inválida: $Versao (use o formato 4.6.0)" }
if ([version]$Versao -le [version]$Atual) { throw "A versão nova ($Versao) precisa ser maior que a atual ($Atual)." }

if ($ArquivoNotas) { $Notas = [IO.File]::ReadAllText((Resolve-Path $ArquivoNotas)) }
if (-not $Notas) { $Notas = "Melhorias e correções." }
Write-Host "Cortex ERP: $Atual -> $Versao" -ForegroundColor Green

Passo "Conferindo alterações sem commit"
git diff --quiet HEAD -- .
if ($LASTEXITCODE -ne 0) { throw "Há alterações sem commit. Faça o commit antes de lançar a versão." }

if (-not $PularTestes) {
    Passo "Rodando os testes"
    python -m pytest -q
    Checar "Testes"
}

Passo "Gravando a versão $Versao"
$novo = [regex]::Replace($conteudo, '(?m)^APP_VERSION\s*=\s*"[^"]+"', "APP_VERSION = `"$Versao`"")
[IO.File]::WriteAllText($ArqVersao, $novo, (New-Object System.Text.UTF8Encoding($false)))

try {
    Passo "Gerando o instalador"
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Repo "installer\build_instalador.ps1")
    Checar "Geração do instalador"
    $Setup = Join-Path $Repo "installer\Output\CortexERP-Setup.exe"
    if (-not (Test-Path $Setup)) { throw "Instalador não foi gerado (o Inno Setup 6 está instalado?)" }
} catch {
    [IO.File]::WriteAllText($ArqVersao, $conteudo, (New-Object System.Text.UTF8Encoding($false)))
    throw
}

Passo "Gerando o manifesto da atualização"
$hash = (Get-FileHash -Algorithm SHA256 $Setup).Hash.ToLower()
$manifesto = [ordered]@{
    versao       = $Versao
    sha256       = $hash
    tamanho      = (Get-Item $Setup).Length
    arquivo      = "CortexERP-Setup.exe"
    publicada_em = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    notas        = $Notas
}
$ArqManifesto = Join-Path $Repo "installer\Output\cortex-update.json"
[IO.File]::WriteAllText($ArqManifesto, ($manifesto | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false)))
Write-Host "SHA-256: $hash"

if ($SemPublicar) {
    Write-Host ""
    Write-Host "Pronto (sem publicar). Instalador e manifesto em installer\Output." -ForegroundColor Yellow
    Write-Host "A versão $Versao ficou gravada em backend\version.py, ainda sem commit."
    exit 0
}

Passo "Commit, tag v$Versao e push"
git add backend/version.py
git commit -m "chore: versão $Versao" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
Checar "git commit"
git tag -a "v$Versao" -m "Cortex ERP $Versao"
Checar "git tag"
git push origin HEAD
Checar "git push"
git push origin "v$Versao"
Checar "git push da tag"

Passo "Publicando a Release no GitHub"
$ArqNotas = Join-Path $env:TEMP "cortex-notas-$Versao.md"
[IO.File]::WriteAllText($ArqNotas, $Notas, (New-Object System.Text.UTF8Encoding($false)))
gh release create "v$Versao" $Setup $ArqManifesto --title "Cortex ERP $Versao" --notes-file $ArqNotas
Checar "gh release create"
Remove-Item $ArqNotas -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Versão $Versao lançada." -ForegroundColor Green
Write-Host " - Nuvem: o Render publica sozinho em alguns minutos (o navegador avisa quem estiver com o sistema aberto)."
Write-Host " - Servidores instalados: aparece em Painel do Sistema > Atualizações (ou instala de madrugada, se ligado)."

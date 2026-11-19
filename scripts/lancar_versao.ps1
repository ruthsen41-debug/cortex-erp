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
    7. envia o instalador ao servidor de atualizações (Cloudflare, depósito privado)
       e publica a versão -> os servidores dos clientes com licença ativa veem
       "Nova versão disponível" em Administração > Atualizações

  Servidor de atualizações (cloudflare/atualizacoes): endereço e token do dono em
      %USERPROFILE%\.cortex\atualizacoes.json   {"url": "https://...workers.dev", "token": "..."}
  ou nas variáveis CORTEX_ATUALIZACOES_URL e CORTEX_ATUALIZACOES_ADMIN_TOKEN.
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

# servidor de atualizações (confere antes de gastar tempo com testes e instalador)
$AtuUrl = $env:CORTEX_ATUALIZACOES_URL
$AtuToken = $env:CORTEX_ATUALIZACOES_ADMIN_TOKEN
$ArqAtu = Join-Path $env:USERPROFILE ".cortex\atualizacoes.json"
if ((-not $AtuUrl -or -not $AtuToken) -and (Test-Path $ArqAtu)) {
    $cfgAtu = Get-Content $ArqAtu -Raw | ConvertFrom-Json
    if (-not $AtuUrl) { $AtuUrl = $cfgAtu.url }
    if (-not $AtuToken) { $AtuToken = $cfgAtu.token }
}
if (-not $SemPublicar -and (-not $AtuUrl -or -not $AtuToken)) {
    throw "Servidor de atualizações não configurado. Crie $ArqAtu com o endereço (url) e o token do Worker."
}
if ($AtuUrl) { $AtuUrl = $AtuUrl.TrimEnd("/") }

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

$curl = (Get-Command curl.exe -ErrorAction Stop).Source

Passo "Enviando o instalador ao servidor de atualizações"
# -T envia o arquivo aos poucos (não carrega os ~50 MB na memória)
$up = & $curl -sS --fail-with-body -X PUT -T $Setup -H "Authorization: Bearer $AtuToken" -H "X-Sha256: $hash" "$AtuUrl/v1/admin/versoes/$Versao/arquivo"
Checar "Envio do instalador ($up)"
Write-Host $up

Passo "Publicando a versão $Versao"
$pub = [ordered]@{ sha256 = $hash; notas = $Notas; publicada_em = $manifesto.publicada_em }
$ArqPub = Join-Path $env:TEMP "cortex-publicar-$Versao.json"
[IO.File]::WriteAllText($ArqPub, ($pub | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false)))
$res = & $curl -sS --fail-with-body -X PUT -H "Authorization: Bearer $AtuToken" -H "Content-Type: application/json" --data-binary "@$ArqPub" "$AtuUrl/v1/admin/versoes/$Versao/publicar"
Checar "Publicação da versão ($res)"
Remove-Item $ArqPub -ErrorAction SilentlyContinue
Write-Host $res

Write-Host ""
Write-Host "Versão $Versao lançada." -ForegroundColor Green
Write-Host " - Nuvem: o Render publica sozinho em alguns minutos (o navegador avisa quem estiver com o sistema aberto)."
Write-Host " - Servidores instalados (licença ativa): aparece em Administração > Atualizações (ou instala de madrugada, se ligado)."

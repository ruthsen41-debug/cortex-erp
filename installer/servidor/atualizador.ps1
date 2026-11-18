<#
  Atualizador do Cortex ERP no servidor do cliente.

  Quem chama: o próprio Cortex (Painel do Sistema > Atualizações), que baixa o
  instalador novo, confere o SHA-256, grava Atualizacoes\plano.json e roda este
  script como tarefa agendada "CortexERP_Atualizacao" (conta SYSTEM). Ele roda
  fora do serviço porque o serviço precisa ser parado durante a troca.

  Passos:
    1. backup do banco (o mesmo do backup diário, vai para a pasta Backups)
    2. para o serviço e guarda uma cópia da versão atual em Atualizacoes\anterior
    3. instala a versão nova em modo silencioso (mantém dados, porta e senha)
    4. confere em /api/health se a versão nova subiu
    5. se algo falhar depois do passo 2, volta a cópia (programa + banco) sozinho

  O andamento vai para Atualizacoes\status.json (a tela mostra) e o detalhe para
  Atualizacoes\atualizacao.log.
#>
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Raiz     = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dir      = Join-Path $Raiz "Atualizacoes"
$Anterior = Join-Path $Dir "anterior"
$Log      = Join-Path $Dir "atualizacao.log"
$StatusArq = Join-Path $Dir "status.json"
$Servico  = Join-Path $Raiz "CortexServico.exe"
$NomeServico = "CortexERP"
$Tarefa   = "CortexERP_Atualizacao"

# o que é trocado pela instalação (e copiado antes, para poder voltar)
$Pastas   = @("python", "app\backend", "app\frontend", "app\scripts", "app\alembic", "cliente")
$Arquivos = @("cortex_servidor.py", "configurar.py", "backup_agora.cmd", "atualizador.ps1",
              "CortexServico.exe", "CortexServico.xml", "app\alembic.ini", "app\requirements.txt")
$Banco    = @("app\data\cortex_erp.db", "app\data\cortex_erp.db-wal", "app\data\cortex_erp.db-shm")

function Escrever-Log([string]$Msg) {
    $linha = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Msg
    Add-Content -Path $Log -Value $linha -Encoding UTF8
}

function Gravar-Status([string]$Fase, [string]$Mensagem, $Progresso = $null, [string]$Erro = "") {
    $st = @{}
    if (Test-Path $StatusArq) {
        try {
            $atual = Get-Content $StatusArq -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach ($p in $atual.PSObject.Properties) { $st[$p.Name] = $p.Value }
        } catch { }
    }
    $st["fase"] = $Fase
    $st["mensagem"] = $Mensagem
    $st["progresso"] = $Progresso
    $st["atualizado_em"] = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    if ($Erro) { $st["erro"] = $Erro }
    if ($Fase -in @("concluida", "revertida", "erro")) { $st["concluido_em"] = $st["atualizado_em"] }
    $json = $st | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($StatusArq + ".tmp", $json, (New-Object System.Text.UTF8Encoding($false)))
    Move-Item -Force ($StatusArq + ".tmp") $StatusArq
    Escrever-Log "$Fase - $Mensagem $Erro"
}

# comandos externos sempre via cmd, com saída descartada: no PowerShell 5.1 qualquer
# texto em stderr de um .exe vira erro quando $ErrorActionPreference = "Stop"
function Executar([string]$Linha) {
    & cmd.exe /c "$Linha >nul 2>&1"
    return $LASTEXITCODE
}

function Parar-Servico {
    Executar "`"$Servico`" stop" | Out-Null
    $limite = (Get-Date).AddSeconds(90)
    while ((Get-Service $NomeServico -ErrorAction SilentlyContinue).Status -ne "Stopped") {
        if ((Get-Date) -gt $limite) { throw "o serviço não parou em 90 segundos" }
        Start-Sleep -Seconds 2
    }
}

function Iniciar-Servico {
    $svc = Get-Service $NomeServico -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne "Running") { Executar "`"$Servico`" start" | Out-Null }
}

function Copiar-Pasta([string]$Origem, [string]$Destino) {
    if (-not (Test-Path $Origem)) { return }
    $codigo = Executar "robocopy `"$Origem`" `"$Destino`" /MIR /R:2 /W:2 /NFL /NDL /NJH /NJS /NP"
    if ($codigo -ge 8) { throw "falha ao copiar $Origem (robocopy $codigo)" }
}

function Aguardar-Versao([string]$Porta, [string]$Versao, [int]$Segundos) {
    $limite = (Get-Date).AddSeconds($Segundos)
    while ((Get-Date) -lt $limite) {
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Porta/api/health" -TimeoutSec 5 -UseBasicParsing
            if (-not $Versao -or $r.version -eq $Versao) { return $true }
        } catch { }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Guardar-VersaoAtual {
    if (Test-Path $Anterior) { Remove-Item -Recurse -Force $Anterior }
    New-Item -ItemType Directory -Force $Anterior | Out-Null
    foreach ($p in $Pastas) { Copiar-Pasta (Join-Path $Raiz $p) (Join-Path $Anterior $p) }
    foreach ($a in ($Arquivos + $Banco)) {
        $origem = Join-Path $Raiz $a
        if (Test-Path $origem) {
            $destino = Join-Path $Anterior $a
            New-Item -ItemType Directory -Force (Split-Path -Parent $destino) | Out-Null
            Copy-Item -Force $origem $destino
        }
    }
}

function Restaurar-VersaoAnterior {
    try { Parar-Servico } catch { Escrever-Log "aviso ao parar o serviço: $_" }
    foreach ($p in $Pastas) {
        $copia = Join-Path $Anterior $p
        if (Test-Path $copia) { Copiar-Pasta $copia (Join-Path $Raiz $p) }
    }
    foreach ($a in $Banco) { $alvo = Join-Path $Raiz $a; if (Test-Path $alvo) { Remove-Item -Force $alvo } }
    foreach ($a in ($Arquivos + $Banco)) {
        $copia = Join-Path $Anterior $a
        if (Test-Path $copia) { Copy-Item -Force $copia (Join-Path $Raiz $a) }
    }
    Executar "`"$Servico`" refresh" | Out-Null
    Iniciar-Servico
}

# ── execução ──────────────────────────────────────────────────────────────────
$plano = Get-Content (Join-Path $Dir "plano.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$Versao = [string]$plano.versao
$Porta = [string]$plano.porta
$Tipo = [string]$plano.tipo
$Setup = [string]$plano.setup
$Trocou = $false

Escrever-Log "===== Atualização para a versão $Versao (atual: $($plano.versao_anterior)) ====="
try {
    if (-not (Test-Path $Setup)) { throw "instalador não encontrado: $Setup" }
    $hash = (Get-FileHash -Algorithm SHA256 $Setup).Hash.ToLower()
    if ($hash -ne ([string]$plano.sha256).ToLower()) { throw "o instalador não confere com o SHA-256 publicado" }

    Gravar-Status "preparando" "Fazendo backup do banco de dados..." 10
    if ((Executar "`"$Raiz\backup_agora.cmd`" /silencioso") -ne 0) { throw "o backup do banco falhou (veja logs\backup.log); nada foi alterado" }

    Gravar-Status "preparando" "Guardando uma cópia da versão atual..." 25
    Parar-Servico
    $Trocou = $true
    Guardar-VersaoAtual

    Gravar-Status "instalando" "Instalando a versão $Versao..." 50
    $argumentos = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOCANCEL", "/CLOSEAPPLICATIONS",
              "/TIPO=$Tipo", "/PORTA=$Porta", "/LOG=`"$Dir\instalacao.log`"")
    $proc = Start-Process -FilePath $Setup -ArgumentList $argumentos -Wait -PassThru
    if ($proc.ExitCode -ne 0) { throw "o instalador terminou com erro (código $($proc.ExitCode)); veja Atualizacoes\instalacao.log" }

    Gravar-Status "conferindo" "Conferindo se a versão nova está no ar..." 85
    Iniciar-Servico
    if (-not (Aguardar-Versao $Porta $Versao 240)) { throw "a versão $Versao não respondeu depois de instalada" }

    Gravar-Status "concluida" "Atualizado para a versão $Versao." 100
    Remove-Item -Force $Setup -ErrorAction SilentlyContinue
}
catch {
    $erro = "$_"
    Escrever-Log "ERRO: $erro"
    if ($Trocou) {
        try {
            Gravar-Status "revertendo" "Algo deu errado. Voltando para a versão anterior..." 90 $erro
            Restaurar-VersaoAnterior
            if (Aguardar-Versao $Porta "" 180) {
                Gravar-Status "revertida" "A atualização falhou e o sistema voltou para a versão anterior. Nenhum dado foi perdido." $null $erro
            } else {
                Gravar-Status "erro" "A atualização falhou e o sistema não voltou sozinho. Reinicie o computador; se continuar fora do ar, rode o instalador da versão anterior." $null $erro
            }
        } catch {
            Gravar-Status "erro" "A atualização falhou e a volta automática também. Rode o instalador novamente." $null "$erro / $_"
        }
    } else {
        Iniciar-Servico
        Gravar-Status "erro" "A atualização não foi feita: $erro" $null $erro
    }
}
finally {
    Executar "schtasks.exe /Delete /F /TN $Tarefa" | Out-Null
}

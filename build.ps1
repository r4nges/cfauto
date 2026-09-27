$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

uv run pytest
if ($LASTEXITCODE -ne 0) { throw "Testes falharam; build cancelado." }

uv run pyinstaller --noconfirm --clean --onefile --windowed `
    --name CFAUTO `
    --add-data "cfauto/migrations;cfauto/migrations" `
    --collect-submodules cfauto `
    --collect-submodules apscheduler `
    cfauto/__main__.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou." }

$dados = Join-Path $env:TEMP ("cfauto-build-" + [guid]::NewGuid())
$env:CFAUTO_HOME = $dados
try {
    $proc = Start-Process -FilePath "dist/CFAUTO.exe" -ArgumentList "--verificar-instalacao" `
        -Wait -PassThru
    if ($proc.ExitCode -ne 0) { throw "Executável falhou na verificação (código $($proc.ExitCode))." }
    if (-not (Test-Path (Join-Path $dados "cfauto.db"))) { throw "Banco não foi criado." }
    Write-Host "OK: dist/CFAUTO.exe criou o banco em $dados"
} finally {
    Remove-Item Env:CFAUTO_HOME
    Remove-Item -Recurse -Force $dados -ErrorAction SilentlyContinue
}

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& "$projectRoot\.venv\Scripts\python.exe" -m PyInstaller packaging/frequencia.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw 'Falha ao empacotar o aplicativo.' }
$compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$compilerPath = if ($compiler) { $compiler.Source } else { $null }
if (-not $compiler) {
    $candidate = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
    if (Test-Path -LiteralPath $candidate) { $compilerPath = $candidate }
}
if ($compilerPath) {
    & $compilerPath packaging/installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar o instalador.' }
} else {
    Write-Host 'Aplicativo gerado em dist/Frequencia. Instale Inno Setup 6 para gerar o instalador.'
}

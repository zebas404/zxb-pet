<#
.SYNOPSIS
    Verifica que la API de Zebot responde. Se ejecuta desde el PC.
.EXAMPLE
    .\scripts\smoke-test.ps1                                  # zxb-app01
    .\scripts\smoke-test.ps1 -BaseUrl http://127.0.0.1:8000   # local
#>
param(
    [string]$BaseUrl = "http://192.168.1.63:8000"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$failed = 0

function Check([string]$Name, [scriptblock]$Test) {
    try {
        $detail = & $Test
        Write-Host ("[ OK ] {0,-10} {1}" -f $Name, $detail) -ForegroundColor Green
    } catch {
        Write-Host ("[FAIL] {0,-10} {1}" -f $Name, $_.Exception.Message) -ForegroundColor Red
        $script:failed++
    }
}

Write-Host "Zebot smoke test -> $BaseUrl`n"

Check "health" {
    $h = Invoke-RestMethod "$BaseUrl/health" -TimeoutSec 10
    if ($h.status -ne "ok") { throw "status=$($h.status) vault_ok=$($h.vault_ok)" }
    if (-not $h.api_key_configured) { throw "ANTHROPIC_API_KEY no configurada" }
    "v$($h.version), $($h.notes) notas, modelo $($h.model)"
}
Check "tasks" {
    $t = Invoke-RestMethod "$BaseUrl/tasks?limit=1" -TimeoutSec 10
    "$($t.open) abiertas, $($t.overdue) atrasadas. Primera: $($t.tasks[0].text)"
}
Check "study" {
    $s = Invoke-RestMethod "$BaseUrl/study" -TimeoutSec 10
    ($s.roadmaps | ForEach-Object {
        $phase = if ($_.current) { $_.current.title } else { "sin fase activa" }
        "$($_.name): $phase"
    }) -join " | "
}
Check "pet" {
    $p = Invoke-RestMethod "$BaseUrl/pet" -TimeoutSec 10
    "$($p.name) $($p.mood): energia $($p.energy), felicidad $($p.happiness), racha $($p.streak), nivel $($p.level)"
}
Check "briefing" {
    $b = Invoke-RestMethod "$BaseUrl/briefing" -TimeoutSec 60
    if ($b.source -eq "fallback") { throw "Claude no respondio (source=fallback). Revisa los logs." }
    "source=$($b.source)"
}

Write-Host ""
if ($failed) { Write-Host "$failed comprobaciones fallaron." -ForegroundColor Red; exit 1 }
Write-Host "Todo OK." -ForegroundColor Green

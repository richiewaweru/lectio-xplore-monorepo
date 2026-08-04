[CmdletBinding()]
param(
    [ValidateSet("baseline", "contracts", "planning", "writers", "document", "frontend", "full")]
    [string]$Phase = "full",
    [string]$Root = "C:\Projects\lectio"
)

$ErrorActionPreference = "Stop"
$failures = @()

function Run-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "`n=== $Name ==="
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) { throw "exit code $LASTEXITCODE" }
    } catch {
        $script:failures += "$Name`: $($_.Exception.Message)"
    }
}

Push-Location $Root
try {
    # Cursor must replace/extend these commands in Run 00 using actual repo scripts.
    if ($Phase -in @("baseline", "contracts", "full")) {
        Run-Step "Page tests" { pnpm --filter @lectio/page test }
        Run-Step "Page check" { pnpm --filter @lectio/page check }
    }
    if ($Phase -in @("planning", "writers", "document", "full")) {
        Run-Step "Backend focused tests" {
            Push-Location "apps/textbook-agent/backend"
            try { uv run pytest -q }
            finally { Pop-Location }
        }
    }
    if ($Phase -in @("frontend", "full")) {
        Run-Step "Frontend check" { pnpm --dir apps/textbook-agent/frontend check }
        Run-Step "Frontend tests" { pnpm --dir apps/textbook-agent/frontend test }
        Run-Step "Frontend build" { pnpm --dir apps/textbook-agent/frontend build }
    }
    if ($Phase -eq "full") {
        Run-Step "Page fixture PDF" { pnpm --filter @lectio/page pdf:fixture }
        Run-Step "Clean worktree" { git diff --check }
    }
} finally {
    Pop-Location
}

if ($failures.Count -gt 0) {
    Write-Error ("Verification failed:`n- " + ($failures -join "`n- "))
    exit 1
}
Write-Host "Verification passed for phase: $Phase"

[CmdletBinding()]
param(
    [string]$Root = "C:\Projects\lectio",
    [string]$LectioSource = "C:\Projects\lectio - Copy",
    [string]$TextbookRemote = "https://github.com/richiewaweru/text-book-generator.git",
    [string]$TextbookBranch = "xplore"
)

$ErrorActionPreference = "Stop"

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not available."
    }
}

Require-Command git
Require-Command node
Require-Command pnpm
Require-Command python

if (-not (Test-Path $LectioSource)) {
    throw "Lectio source does not exist: $LectioSource"
}
if (-not (Test-Path (Join-Path $LectioSource ".git"))) {
    throw "History-preserving import requires a Git repository at $LectioSource. Use an explicit reviewed snapshot import instead."
}
$dirty = git -C $LectioSource status --porcelain
if ($LASTEXITCODE -ne 0) { throw "Cannot inspect Lectio source." }
if ($dirty) {
    throw "Lectio source has uncommitted changes. Commit them or create a reviewed snapshot before import. Source was not modified."
}

if (Test-Path $Root) {
    $items = Get-ChildItem -Force $Root
    if ($items.Count -gt 0) {
        throw "Target root is not empty: $Root"
    }
} else {
    New-Item -ItemType Directory -Path $Root | Out-Null
}

$lectioHead = (git -C $LectioSource rev-parse HEAD).Trim()
$lectioBranch = (git -C $LectioSource branch --show-current).Trim()

Push-Location $Root
try {
    git init
    git checkout -b pageobject-integration

    @"
# Lectio + Xplore Monorepo

Imported safely from the page-object package and the textbook-agent xplore branch.
"@ | Set-Content -Path "README.md" -Encoding UTF8
    git add README.md
    git commit -m "chore(monorepo): initialize integration root"

    git remote add lectio-source $LectioSource
    git fetch lectio-source --tags
    git subtree add --prefix="packages/lectio-page" lectio-source $lectioHead

    git remote add textbook-source $TextbookRemote
    git fetch textbook-source $TextbookBranch
    $textbookHead = (git rev-parse "textbook-source/$TextbookBranch").Trim()
    git subtree add --prefix="apps/textbook-agent" textbook-source $textbookHead

    New-Item -ItemType Directory -Force -Path "docs/implementation-runs" | Out-Null
    $provenance = @"
# Import Provenance

- Imported at: $(Get-Date -Format o)
- Lectio source path: `$LectioSource`
- Lectio branch: `$lectioBranch`
- Lectio HEAD: `$lectioHead`
- Textbook remote: `$TextbookRemote`
- Textbook branch: `$TextbookBranch`
- Textbook HEAD: `$textbookHead`
"@
    Set-Content -Path "docs/implementation-runs/IMPORT_PROVENANCE.md" -Value $provenance -Encoding UTF8

    @"
packages:
  - "packages/*"
  - "apps/textbook-agent/frontend"
"@ | Set-Content -Path "pnpm-workspace.yaml" -Encoding UTF8

    @"
{
  "name": "lectio-xplore-monorepo",
  "private": true,
  "scripts": {
    "page:test": "pnpm --filter @lectio/page test",
    "page:check": "pnpm --filter @lectio/page check",
    "page:pdf": "pnpm --filter @lectio/page pdf:fixture",
    "app:check": "pnpm --dir apps/textbook-agent/frontend check",
    "app:test": "pnpm --dir apps/textbook-agent/frontend test",
    "contracts:sync": "python apps/textbook-agent/tools/update_lectio_page_contracts.py"
  }
}
"@ | Set-Content -Path "package.json" -Encoding UTF8

    @"
node_modules/
.venv/
__pycache__/
*.pyc
.env
out/
.svelte-kit/
dist/
.pytest_cache/
"@ | Set-Content -Path ".gitignore" -Encoding UTF8

    git add package.json pnpm-workspace.yaml .gitignore docs/implementation-runs/IMPORT_PROVENANCE.md
    git commit -m "chore(monorepo): import xplore and lectio page package"
    git tag pageobject-import-baseline

    Write-Host "Imported monorepo at $Root"
    Write-Host "Lectio: $lectioHead"
    Write-Host "Textbook xplore: $textbookHead"
} finally {
    Pop-Location
}

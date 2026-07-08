# ═══════════════════════════════════════════════════════════════
# TELEGRAMTRADER — MISE À JOUR AUTOMATIQUE
# Tire les dernières modifications Git et redémarre les services.
# Usage : double-cliquer sur METTRE_A_JOUR.bat
# ═══════════════════════════════════════════════════════════════

# ── Helpers d'affichage ──────────────────────────────────────────
function Write-Step { param($msg) Write-Host "`n  ▶  $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "  ✅  $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  ⚠️   $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "  ❌  $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "      $msg" -ForegroundColor Gray }

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Blue
Write-Host "  ║       TELEGRAMTRADER  —  Mise à jour                 ║" -ForegroundColor Blue
Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Blue
Write-Host ""

# ════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Vérifier Git
# ════════════════════════════════════════════════════════════════
Write-Step "Vérification de Git..."

try {
    $gitVer = (git --version 2>&1).ToString()
    Write-OK "Git trouvé : $gitVer"
} catch {
    Write-Fail "Git n'est pas installé."
    Write-Host "  Téléchargez Git depuis https://git-scm.com/" -ForegroundColor Yellow
    Read-Host "  Appuyez sur Entrée pour fermer"
    exit 1
}

# ════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Récupérer les mises à jour
# ════════════════════════════════════════════════════════════════
Write-Step "Récupération des mises à jour depuis GitHub..."

# Sauvegarder la version actuelle
$currentCommit = (git rev-parse --short HEAD 2>&1).ToString().Trim()
Write-Info "Version actuelle : $currentCommit"

# Vérifier s'il y a des modifications locales non commitées
$status = git status --porcelain 2>&1
if ($status) {
    Write-Warn "Des modifications locales ont été détectées."
    Write-Info "Elles seront préservées (stash automatique)."
    git stash push -m "Auto-stash avant mise à jour $(Get-Date -Format 'yyyy-MM-dd HH:mm')" 2>&1 | Out-Null
    $stashed = $true
} else {
    $stashed = $false
}

# Pull
git pull origin main 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warn "git pull a rencontré un problème. Tentative avec --rebase..."
    git pull --rebase origin main 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Impossible de récupérer les mises à jour."
        Write-Info "Vérifiez votre connexion internet ou contactez le support."
        if ($stashed) {
            Write-Info "Restauration de vos modifications locales..."
            git stash pop 2>&1 | Out-Null
        }
        Read-Host "  Appuyez sur Entrée pour fermer"
        exit 1
    }
}

$newCommit = (git rev-parse --short HEAD 2>&1).ToString().Trim()
if ($currentCommit -eq $newCommit) {
    Write-OK "Déjà à jour (version $currentCommit)."
} else {
    Write-OK "Mise à jour : $currentCommit → $newCommit"
    # Afficher le changelog
    Write-Host ""
    Write-Host "  📝  Nouveautés :" -ForegroundColor Cyan
    git log --oneline "$currentCommit..$newCommit" 2>&1 | ForEach-Object { Write-Host "      $_" -ForegroundColor White }
}

# Restaurer les modifications locales si stashées
if ($stashed) {
    Write-Info "Restauration de vos modifications locales..."
    git stash pop 2>&1 | Out-Null
}

# ════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Redémarrer les services
# ════════════════════════════════════════════════════════════════
Write-Step "Redémarrage des services avec les nouvelles images..."

# Vérifier Docker
try {
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Docker non actif" }
} catch {
    Write-Fail "Docker n'est pas actif. Démarrez Docker Desktop d'abord."
    Read-Host "  Appuyez sur Entrée pour fermer"
    exit 1
}

Write-Info "Arrêt des conteneurs actuels..."
docker-compose down 2>&1 | Out-Null

Write-Info "Reconstruction et redémarrage..."
docker-compose up -d --build

if ($LASTEXITCODE -ne 0) {
    Write-Fail "Erreur lors du redémarrage."
    Write-Host "  Consultez les logs : docker-compose logs --tail=50" -ForegroundColor Yellow
    Read-Host "  Appuyez sur Entrée pour fermer"
    exit 1
}

# ════════════════════════════════════════════════════════════════
# ÉTAPE 4 — Vérification
# ════════════════════════════════════════════════════════════════
Write-Step "Vérification du démarrage..."

$maxWait = 60
$elapsed = 0
$ok = $false
while ($elapsed -lt $maxWait) {
    Start-Sleep -Seconds 3
    $elapsed += 3
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $ok = $true; break }
    } catch {}
    Write-Host "      ... $elapsed s" -ForegroundColor DarkGray
}

Write-Host ""
if ($ok) {
    Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "  ║     ✅  MISE À JOUR TERMINÉE — Version $newCommit      ║" -ForegroundColor Green
    Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
} else {
    Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "  ║  ⚠️   Mise à jour appliquée — backend en démarrage   ║" -ForegroundColor Yellow
    Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  📱  Interface web : http://localhost:3000" -ForegroundColor White
Write-Host ""

$open = Read-Host "  Ouvrir l'application dans le navigateur ? (O/N)"
if ($open -eq "O" -or $open -eq "o") {
    Start-Process "http://localhost:3000"
}

Write-Host ""
Write-Host "  Appuyez sur une touche pour fermer..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

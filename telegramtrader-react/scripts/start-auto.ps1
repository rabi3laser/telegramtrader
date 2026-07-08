# ═══════════════════════════════════════════════════════════════
# TELEGRAMTRADER — DÉMARRAGE AUTOMATIQUE CLIENT
# Script principal : vérifie les prérequis, configure, démarre.
# Usage : double-cliquer sur DEMARRER.bat (à la racine du projet)
# ═══════════════════════════════════════════════════════════════

param(
    [switch]$SkipBuild,    # Sauter la reconstruction des images Docker
    [switch]$NoBrowser,    # Ne pas ouvrir le navigateur automatiquement
    [switch]$Quiet         # Mode silencieux (moins de messages)
)

# ── Helpers d'affichage ──────────────────────────────────────────
function Write-Step   { param($msg) Write-Host "`n  ▶  $msg" -ForegroundColor Cyan }
function Write-OK     { param($msg) Write-Host "  ✅  $msg" -ForegroundColor Green }
function Write-Warn   { param($msg) Write-Host "  ⚠️   $msg" -ForegroundColor Yellow }
function Write-Fail   { param($msg) Write-Host "  ❌  $msg" -ForegroundColor Red }
function Write-Info   { param($msg) Write-Host "      $msg" -ForegroundColor Gray }
function Write-Banner {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Blue
    Write-Host "  ║         TELEGRAMTRADER  —  Démarrage Auto            ║" -ForegroundColor Blue
    Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Blue
    Write-Host ""
}

# ── Se placer à la racine du projet ─────────────────────────────
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Banner

# ════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Vérification des prérequis
# ════════════════════════════════════════════════════════════════
Write-Step "Vérification des prérequis..."

# Docker Desktop
$dockerOk = $false
try {
    $dockerVer = (docker --version 2>&1).ToString()
    if ($dockerVer -match "Docker version") {
        Write-OK "Docker trouvé : $dockerVer"
        $dockerOk = $true
    }
} catch {}

if (-not $dockerOk) {
    Write-Fail "Docker Desktop n'est pas installé ou pas démarré."
    Write-Host ""
    Write-Host "  📥  Téléchargez Docker Desktop ici :" -ForegroundColor Yellow
    Write-Host "      https://www.docker.com/products/docker-desktop/" -ForegroundColor White
    Write-Host ""
    Write-Host "  Après installation, relancez ce script." -ForegroundColor Yellow
    Write-Host ""
    Start-Process "https://www.docker.com/products/docker-desktop/"
    Read-Host "  Appuyez sur Entrée pour fermer"
    exit 1
}

# Docker daemon actif ?
$daemonOk = $false
try {
    $info = docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $daemonOk = $true }
} catch {}

if (-not $daemonOk) {
    Write-Warn "Docker Desktop est installé mais pas encore démarré."
    Write-Host ""
    Write-Host "  ⏳  Tentative de démarrage de Docker Desktop..." -ForegroundColor Yellow
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue

    $waited = 0
    $maxWait = 60
    Write-Host "  ⏳  Attente du démarrage de Docker (max ${maxWait}s)..." -ForegroundColor Yellow
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds 3
        $waited += 3
        $check = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-OK "Docker Desktop démarré !"
            $daemonOk = $true
            break
        }
        Write-Host "      ... $waited s" -ForegroundColor DarkGray
    }

    if (-not $daemonOk) {
        Write-Fail "Docker Desktop n'a pas démarré dans les ${maxWait}s."
        Write-Host "  Démarrez Docker Desktop manuellement puis relancez ce script." -ForegroundColor Yellow
        Read-Host "  Appuyez sur Entrée pour fermer"
        exit 1
    }
}

Write-OK "Docker daemon actif."

# ════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Configuration (fichier .env)
# ════════════════════════════════════════════════════════════════
Write-Step "Vérification de la configuration..."

$envFile = Join-Path $ProjectRoot "backend\.env"
$envExample = Join-Path $ProjectRoot "backend\.env.example"

if (-not (Test-Path $envFile)) {
    Write-Warn "Fichier de configuration backend\.env introuvable."
    Write-Info "Création depuis le modèle .env.example..."
    Copy-Item $envExample $envFile
    Write-Host ""
    Write-Host "  ┌─────────────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "  │  CONFIGURATION REQUISE — À faire une seule fois     │" -ForegroundColor Yellow
    Write-Host "  │                                                     │" -ForegroundColor Yellow
    Write-Host "  │  Remplissez vos clés Telegram dans le fichier qui   │" -ForegroundColor Yellow
    Write-Host "  │  va s'ouvrir :                                      │" -ForegroundColor Yellow
    Write-Host "  │                                                     │" -ForegroundColor Yellow
    Write-Host "  │    TELEGRAM_API_ID=votre_id                         │" -ForegroundColor Yellow
    Write-Host "  │    TELEGRAM_API_HASH=votre_hash                     │" -ForegroundColor Yellow
    Write-Host "  │    SECRET_KEY=une-cle-aleatoire-longue              │" -ForegroundColor Yellow
    Write-Host "  │                                                     │" -ForegroundColor Yellow
    Write-Host "  │  Obtenez vos clés sur : https://my.telegram.org     │" -ForegroundColor Yellow
    Write-Host "  └─────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host ""
    Start-Process notepad $envFile
    Read-Host "  Appuyez sur Entrée une fois le fichier .env sauvegardé"
}

# Vérifier que les clés Telegram sont renseignées
$envContent = Get-Content $envFile -Raw
$apiIdOk   = $envContent -match "TELEGRAM_API_ID=\d+"
$apiHashOk = $envContent -match "TELEGRAM_API_HASH=[a-f0-9]{32}"

if (-not $apiIdOk -or -not $apiHashOk) {
    Write-Warn "Les clés Telegram ne semblent pas configurées dans backend\.env"
    Write-Info "TELEGRAM_API_ID et TELEGRAM_API_HASH doivent être renseignés."
    Write-Host ""
    $edit = Read-Host "  Ouvrir le fichier .env maintenant ? (O/N)"
    if ($edit -eq "O" -or $edit -eq "o") {
        Start-Process notepad $envFile
        Read-Host "  Appuyez sur Entrée une fois le fichier .env sauvegardé"
    }
} else {
    Write-OK "Configuration Telegram détectée."
}

# ════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Arrêt des anciens conteneurs (si actifs)
# ════════════════════════════════════════════════════════════════
Write-Step "Nettoyage des anciens conteneurs..."

$running = docker ps --filter "name=telegramtrader" --format "{{.Names}}" 2>&1
if ($running) {
    Write-Info "Conteneurs actifs détectés : $($running -join ', ')"
    docker-compose down --remove-orphans 2>&1 | Out-Null
    Write-OK "Anciens conteneurs arrêtés."
} else {
    Write-OK "Aucun conteneur actif à arrêter."
}

# ════════════════════════════════════════════════════════════════
# ÉTAPE 4 — Construction et démarrage
# ════════════════════════════════════════════════════════════════
Write-Step "Démarrage de TelegramTrader..."

# Première fois ou --SkipBuild non demandé → build complet
$firstRun = -not (docker images --filter "reference=telegramtrader*" --format "{{.Repository}}" 2>&1 | Select-String "telegramtrader")

if ($SkipBuild -and -not $firstRun) {
    Write-Info "Mode rapide : reconstruction des images ignorée (--SkipBuild)."
    $composeCmd = "docker-compose up -d"
} else {
    if ($firstRun) {
        Write-Info "Première installation — construction des images Docker..."
        Write-Info "(Cela peut prendre 3-5 minutes, une seule fois)"
    } else {
        Write-Info "Reconstruction des images Docker..."
    }
    $composeCmd = "docker-compose up -d --build"
}

Write-Host ""
Invoke-Expression $composeCmd

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Fail "Erreur lors du démarrage Docker Compose."
    Write-Host ""
    Write-Host "  Consultez les logs pour diagnostiquer :" -ForegroundColor Yellow
    Write-Host "    docker-compose logs --tail=50" -ForegroundColor White
    Write-Host ""
    $showLogs = Read-Host "  Afficher les logs maintenant ? (O/N)"
    if ($showLogs -eq "O" -or $showLogs -eq "o") {
        docker-compose logs --tail=50
    }
    Read-Host "  Appuyez sur Entrée pour fermer"
    exit 1
}

# ════════════════════════════════════════════════════════════════
# ÉTAPE 5 — Attente que les services soient prêts
# ════════════════════════════════════════════════════════════════
Write-Step "Attente que les services soient prêts..."

$maxWaitSec = 90
$elapsed    = 0
$backendOk  = $false

while ($elapsed -lt $maxWaitSec) {
    Start-Sleep -Seconds 3
    $elapsed += 3
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $backendOk = $true
            break
        }
    } catch {}
    Write-Host "      ... $elapsed s / ${maxWaitSec}s" -ForegroundColor DarkGray
}

if (-not $backendOk) {
    Write-Warn "Le backend n'a pas répondu dans les ${maxWaitSec}s."
    Write-Info "Il est peut-être encore en cours de démarrage."
    Write-Info "Vérifiez avec : docker-compose logs backend"
} else {
    Write-OK "Backend opérationnel (http://localhost:8000)"
}

# ════════════════════════════════════════════════════════════════
# ÉTAPE 6 — Résumé final
# ════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║         ✅  TELEGRAMTRADER EST DÉMARRÉ !             ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  📱  Accès à l'application :" -ForegroundColor Cyan
Write-Host "      Interface web  →  http://localhost:3000" -ForegroundColor White
Write-Host "      API Backend    →  http://localhost:8000" -ForegroundColor White
Write-Host "      Documentation  →  http://localhost:8000/api/docs" -ForegroundColor White
Write-Host ""
Write-Host "  🖥️   Agent NinjaTrader 8 :" -ForegroundColor Cyan
Write-Host "      Téléchargez TelegramTraderAgent.exe depuis l'interface web" -ForegroundColor White
Write-Host "      (Paramètres → Agent NinjaTrader → Télécharger l'agent)" -ForegroundColor Gray
Write-Host ""
Write-Host "  📋  Commandes utiles :" -ForegroundColor Cyan
Write-Host "      Voir les logs    →  docker-compose logs -f" -ForegroundColor Gray
Write-Host "      Arrêter          →  docker-compose down" -ForegroundColor Gray
Write-Host "      Redémarrer       →  docker-compose restart" -ForegroundColor Gray
Write-Host "      Statut           →  docker-compose ps" -ForegroundColor Gray
Write-Host ""

# Afficher le statut des conteneurs
Write-Host "  📊  Statut des conteneurs :" -ForegroundColor Cyan
docker-compose ps
Write-Host ""

# Ouvrir le navigateur automatiquement
if (-not $NoBrowser) {
    Write-Host "  🌐  Ouverture de l'interface web..." -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:3000"
}

Write-Host ""
Write-Host "  Appuyez sur une touche pour fermer cette fenêtre." -ForegroundColor DarkGray
Write-Host "  (L'application continue de tourner en arrière-plan)" -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

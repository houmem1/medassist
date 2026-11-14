# Lance MedAssist : Ollama + lecteur radio + Open WebUI (installation pip), tout en local, sans connexion sortante.
# Usage :  powershell -ExecutionPolicy Bypass -File start-medassist.ps1
$ErrorActionPreference = "Stop"
# Dossier d'installation : variable MEDASSIST_ROOT, sinon <profil utilisateur>\open-webui
$Root = if ($env:MEDASSIST_ROOT) { $env:MEDASSIST_ROOT } else { "$env:USERPROFILE\open-webui" }
$Port = 8080
$Ollama = "http://localhost:11434"
# Modèle principal selon le profil matériel choisi par install.py (medassist.json) ; complet par défaut
$MainModel = "qwen3.6:35b"
if (Test-Path "$Root\medassist.json") {
    try { $MainModel = (Get-Content "$Root\medassist.json" -Raw | ConvertFrom-Json).model } catch { }
}
$RequiredModels = @($MainModel, "medgemma:4b", "bge-m3")

# 1. Ollama doit répondre sur le port 11434 (attente jusqu'à 30 s après son lancement)
function Test-Ollama { try { Invoke-WebRequest -UseBasicParsing "$Ollama/api/tags" -TimeoutSec 3 | Out-Null; $true } catch { $false } }
if (-not (Test-Ollama)) {
    $exe = "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
    if (-not (Test-Path $exe)) { Write-Error "Ollama introuvable ($exe) : installez-le depuis ollama.com, puis relancez." }
    Write-Host "Démarrage d'Ollama..."
    Start-Process $exe
    $deadline = (Get-Date).AddSeconds(30)
    while (-not (Test-Ollama) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
    if (-not (Test-Ollama)) { Write-Error "Ollama ne répond pas sur $Ollama après 30 s." }
}

# 2. Les modèles nécessaires sont-ils installés ? (avertissement seulement : MedAssist explique l'absence à l'usage)
try {
    $tags = (Invoke-WebRequest -UseBasicParsing "$Ollama/api/tags" -TimeoutSec 5).Content | ConvertFrom-Json
    $installed = @($tags.models | ForEach-Object { $_.name })
    foreach ($m in $RequiredModels) {
        $found = $installed | Where-Object { $_ -eq $m -or $_ -eq "$($m):latest" }
        if (-not $found) { Write-Warning "Modèle Ollama absent : $m  ->  ollama pull $m" }
    }
} catch { Write-Warning "Liste des modèles Ollama illisible : $_" }

# 3. Configuration Open WebUI (lue au premier démarrage, ensuite modifiable dans l'Admin Panel)
$env:DATA_DIR             = "$Root\data"
$env:OLLAMA_BASE_URL      = $Ollama
$env:ENABLE_OPENAI_API    = "False"
$env:WEBUI_NAME           = "MedAssist"
# Valeurs initiales seulement : openwebui\install.py les fixe ensuite dans la base
$env:DEFAULT_MODELS       = "medassist.pro"
# RAG / base de connaissances avec un modèle d'embeddings local et multilingue
$env:RAG_EMBEDDING_ENGINE = "ollama"
$env:RAG_EMBEDDING_MODEL  = "bge-m3:latest"
$env:RAG_OLLAMA_BASE_URL  = $Ollama
# Hors ligne : pas de vérification de version, pas de téléchargement de modèles Hugging Face
$env:OFFLINE_MODE         = "true"
$env:HF_HUB_OFFLINE       = "1"
$env:ENABLE_VERSION_UPDATE_CHECK = "False"
# Antivirus interceptant le HTTPS (Avast Web Shield…) : si un ca-bundle.pem est présent dans le dossier
# d'installation, Python l'utilise ; sinon, rien à faire (tout est local de toute façon)
if (Test-Path "$Root\ca-bundle.pem") {
    $env:SSL_CERT_FILE      = "$Root\ca-bundle.pem"
    $env:REQUESTS_CA_BUNDLE = "$Root\ca-bundle.pem"
}
# Pas de télémétrie
$env:SCARF_NO_ANALYTICS   = "true"
$env:DO_NOT_TRACK         = "true"
$env:ANONYMIZED_TELEMETRY = "false"

# 4. Clé de session fixe. Sans WEBUI_SECRET_KEY, Open WebUI lit ou crée « .webui_secret_key » dans le dossier
#    COURANT : lancé depuis un autre dossier, il changeait de clé et déconnectait tout le monde.
$KeyFile = "$Root\.webui_secret_key"
if (-not (Test-Path $KeyFile)) {
    $old = "$env:USERPROFILE\.webui_secret_key"   # clé des lancements précédents (depuis le dossier utilisateur)
    if (Test-Path $old) { Copy-Item $old $KeyFile }
    else { [IO.File]::WriteAllText($KeyFile, [Convert]::ToBase64String((1..24 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]])) }
}
$env:WEBUI_SECRET_KEY = (Get-Content $KeyFile -Raw).Trim()

# 5. Lecteur spécialisé de radiographies thoraciques (service local sur 127.0.0.1:8765)
$CxrPython = "$Root\cxr-venv\Scripts\python.exe"
$CxrService = "$Root\radiology\service.py"
if ((Test-Path $CxrPython) -and (Test-Path $CxrService)) {
    try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/health -TimeoutSec 2 | Out-Null }
    catch {
        Write-Host "Démarrage du lecteur de radiographies thoraciques..."
        Start-Process -WindowStyle Hidden -FilePath $CxrPython -ArgumentList "`"$CxrService`""
    }
} else { Write-Warning "Lecteur radio absent ($CxrService) : les radios ne passeront que par la lecture généraliste." }

New-Item -ItemType Directory -Force "$env:DATA_DIR" | Out-Null
Set-Location $Root
Write-Host "MedAssist sur http://localhost:$Port  (Ctrl+C pour arrêter)"
& "$Root\venv\Scripts\open-webui.exe" serve --host 127.0.0.1 --port $Port

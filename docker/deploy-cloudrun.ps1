# =============================================================================
# deploy-cloudrun.ps1
# Script PowerShell pour déployer l'image Docker sur Google Cloud Run
#
# Prérequis :
#   1. Google Cloud SDK installé (gcloud)
#   2. Un projet GCP actif (gcloud config set project <PROJECT_ID>)
#   3. Docker (ou laisser Cloud Build construire l'image)
#
# Usage :
#   .\docker\deploy-cloudrun.ps1 -ProjectId "mon-projet-gcp"
# =============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,

    [string]$Region       = "europe-west1",
    [string]$ServiceName  = "medsearch",
    [string]$ImageName    = "medsearch",
    [int]$MaxInstances    = 3,
    [int]$Memory          = 512,
    [int]$Cpu             = 1,
    [int]$Timeout         = 300,
    [string]$SecretKey    = ""
)

$ErrorActionPreference = "Stop"
$ImageUri = "${Region}-docker.pkg.dev/${ProjectId}/cloud-run-source-deploy/${ImageName}"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Medical Search - Cloud Run Deployment"       -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Project   : $ProjectId"
Write-Host "  Region    : $Region"
Write-Host "  Service   : $ServiceName"
Write-Host "  Image     : $ImageUri"
Write-Host ""

# ---------- Step 1: Authenticate & set project ----------
Write-Host "[1/5] Configuring gcloud project..." -ForegroundColor Yellow
gcloud config set project $ProjectId
gcloud auth configure-docker "${Region}-docker.pkg.dev" --quiet 2>$null

# ---------- Step 2: Enable required APIs ----------
Write-Host "[2/5] Enabling Cloud APIs..." -ForegroundColor Yellow
gcloud services enable `
    run.googleapis.com `
    containerregistry.googleapis.com `
    artifactregistry.googleapis.com `
    cloudbuild.googleapis.com `
    --quiet

# ---------- Step 3: Create Artifact Registry repo (idempotent) ----------
Write-Host "[3/5] Ensuring Artifact Registry repository exists..." -ForegroundColor Yellow
$repoExists = gcloud artifacts repositories list --location=$Region --format="value(name)" 2>$null | Where-Object { $_ -eq "cloud-run-source-deploy" }
if (-not $repoExists) {
    gcloud artifacts repositories create cloud-run-source-deploy `
        --repository-format=docker `
        --location=$Region `
        --description="Docker images for Cloud Run" `
        --quiet
}

# ---------- Step 4: Build & push image via Cloud Build ----------
Write-Host "[4/5] Building & pushing Docker image via Cloud Build..." -ForegroundColor Yellow
# We submit from the project root using the Dockerfile inside docker/
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    gcloud builds submit `
        --tag "${ImageUri}:latest" `
        --dockerfile "docker/Dockerfile" `
        --timeout=600 `
        .
} finally {
    Pop-Location
}

# ---------- Step 5: Deploy to Cloud Run ----------
Write-Host "[5/5] Deploying to Cloud Run..." -ForegroundColor Yellow

# Generate secret key if not provided
if (-not $SecretKey) {
    $SecretKey = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 50 | ForEach-Object { [char]$_ })
    Write-Host "  -> Generated random DJANGO_SECRET_KEY" -ForegroundColor DarkGray
}

gcloud run deploy $ServiceName `
    --image "${ImageUri}:latest" `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --port 8080 `
    --memory "${Memory}Mi" `
    --cpu $Cpu `
    --max-instances $MaxInstances `
    --timeout $Timeout `
    --set-env-vars "DEBUG=false,DJANGO_SECRET_KEY=${SecretKey},ALLOWED_HOSTS=*,GUNICORN_WORKERS=2,GUNICORN_THREADS=4" `
    --quiet

# ---------- Done ----------
$serviceUrl = gcloud run services describe $ServiceName --region $Region --format="value(status.url)"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  Deployment successful!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  URL : $serviceUrl" -ForegroundColor White
Write-Host ""
Write-Host "  IMPORTANT : Mettez a jour CSRF_TRUSTED_ORIGINS avec cette URL :" -ForegroundColor Yellow
Write-Host "    gcloud run services update $ServiceName --region $Region --update-env-vars CSRF_TRUSTED_ORIGINS=$serviceUrl" -ForegroundColor DarkGray
Write-Host ""
